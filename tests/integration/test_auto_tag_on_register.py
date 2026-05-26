"""Phase 5.2 T015 / US2: auto-tag at member first registration.

Covers both creation entry points (OIDC self-register + admin create), the
first-registration-only guarantee, the no-match case, and that an auto tag
flows through the existing access policy identically to a manual tag.
"""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from ai_api.db import get_sessionmaker
from ai_api.models import AuditEventType, MemberProvider, ModelCatalog, TagSource


async def _seed_rules(client: AsyncClient, headers: dict[str, str]) -> None:
    r1 = await client.post(
        "/admin/tag-rules",
        headers=headers,
        json={"matcher_type": "email_localpart_regex", "pattern": r"[a-z]{0,2}\d{6,}", "tag": "student"},
    )
    assert r1.status_code == 201, r1.text
    r2 = await client.post(
        "/admin/tag-rules", headers=headers, json={"matcher_type": "always", "tag": "teacher"}
    )
    assert r2.status_code == 201, r2.text


async def _member_tag_rows(member_id: str):
    from sqlalchemy import select

    from ai_api.models import MemberTag

    sm = get_sessionmaker()
    async with sm() as s:
        rows = (
            await s.execute(select(MemberTag).where(MemberTag.member_id == member_id))
        ).scalars().all()
        return {r.tag: r for r in rows}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_oidc_first_register_auto_tags(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    from ai_api.api.auth import _find_or_create_oidc_member

    await _seed_rules(app_client, admin_headers)

    sm = get_sessionmaker()
    async with sm() as s:
        result = SimpleNamespace(
            email="b10901234@school.edu",
            external_id="ext-1",
            display_name="Student One",
        )
        member = await _find_or_create_oidc_member(s, result)
        await s.commit()
        mid = member.id

    rows = await _member_tag_rows(mid)
    assert "student" in rows
    assert rows["student"].source == TagSource.auto
    assert rows["student"].rule_id is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_oidc_relogin_does_not_rerun(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    from ai_api.api.auth import _find_or_create_oidc_member

    await _seed_rules(app_client, admin_headers)
    result = SimpleNamespace(email="b10901234@school.edu", external_id="ext-1", display_name="S")

    sm = get_sessionmaker()
    async with sm() as s:
        m1 = await _find_or_create_oidc_member(s, result)
        await s.commit()
        mid = m1.id

    # admin manually removes the auto tag
    await app_client.delete(f"/admin/members/{mid}/tags?tag=student", headers=admin_headers)

    # second login → existing member returned, rules NOT re-run
    async with sm() as s:
        m2 = await _find_or_create_oidc_member(s, result)
        await s.commit()
        assert m2.id == mid

    rows = await _member_tag_rows(mid)
    assert "student" not in rows  # not re-applied


@pytest.mark.integration
@pytest.mark.asyncio
async def test_admin_create_auto_tags(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    from ai_api.services.members import MemberService

    await _seed_rules(app_client, admin_headers)

    sm = get_sessionmaker()
    async with sm() as s:
        created = await MemberService(s).create(
            email="c20905678@school.edu",
            provider=MemberProvider.external,
        )
        await s.commit()
        mid = created.member.id

    rows = await _member_tag_rows(mid)
    assert "student" in rows
    assert rows["student"].source == TagSource.auto


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fallback_and_no_match(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    from ai_api.services.members import MemberService

    # only a localpart rule, NO always fallback
    r = await app_client.post(
        "/admin/tag-rules",
        headers=admin_headers,
        json={"matcher_type": "email_localpart_regex", "pattern": r"[a-z]{0,2}\d{6,}", "tag": "student"},
    )
    assert r.status_code == 201

    sm = get_sessionmaker()
    async with sm() as s:
        created = await MemberService(s).create(email="prof.wang@school.edu", provider=MemberProvider.external)
        await s.commit()
        mid = created.member.id

    rows = await _member_tag_rows(mid)
    assert rows == {}  # no match, no fallback → no auto tag (not an error)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auto_tag_flows_through_access_policy(
    app_client: AsyncClient, admin_headers: dict[str, str], make_provider_credential
) -> None:
    from ai_api.services.members import MemberService

    await _seed_rules(app_client, admin_headers)
    await make_provider_credential(provider="anthropic", api_key="sk-ant-test-9999")

    # seed a restricted model allowed only for 'student'
    sm = get_sessionmaker()
    now = datetime.now(UTC)
    async with sm() as s:
        s.add(
            ModelCatalog(
                slug="anthropic/claude-3-5-sonnet", provider="anthropic",
                display_name="Claude", family="claude-3", description="x",
                modality_input=["text"], modality_output=["text"], capabilities=["chat"],
                context_window=200000, cost_tier="high", recommended_for=["chat"], tags=[],
                example_request={}, official_doc_url=None, status="active", deprecation_note=None,
                created_at=now, updated_at=now,
                default_access="restricted", allowed_tags=["student"], denied_tags=[],
            )
        )
        await s.commit()

    # student auto-tagged member
    async with sm() as s:
        student = (await MemberService(s).create(email="b10901234@school.edu", provider=MemberProvider.external)).member
        await s.commit()
        student_id = student.id
    # teacher (fallback) member
    async with sm() as s:
        teacher = (await MemberService(s).create(email="prof.wang@school.edu", provider=MemberProvider.external)).member
        await s.commit()
        teacher_id = teacher.id

    rs = await app_client.get(f"/admin/members/{student_id}/visible-models", headers=admin_headers)
    assert rs.status_code == 200
    assert "anthropic/claude-3-5-sonnet" in [m["slug"] for m in rs.json()]

    rt = await app_client.get(f"/admin/members/{teacher_id}/visible-models", headers=admin_headers)
    assert "anthropic/claude-3-5-sonnet" not in [m["slug"] for m in rt.json()]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auto_tag_audit_has_source_and_rule_id(
    app_client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """T019/T020: member_tag_added audit details carry source=auto + rule_id."""
    from sqlalchemy import select

    from ai_api.models import AuthAuditLog
    from ai_api.services.members import MemberService

    await _seed_rules(app_client, admin_headers)

    sm = get_sessionmaker()
    async with sm() as s:
        created = await MemberService(s).create(email="b10901234@school.edu", provider=MemberProvider.external)
        await s.commit()
        mid = created.member.id

    async with sm() as s:
        rows = (
            await s.execute(
                select(AuthAuditLog).where(
                    AuthAuditLog.event_type == AuditEventType.member_tag_added,
                    AuthAuditLog.target_id == mid,
                )
            )
        ).scalars().all()
    assert len(rows) == 1
    details = rows[0].details or {}
    assert details.get("source") == "auto"
    assert details.get("rule_id")

