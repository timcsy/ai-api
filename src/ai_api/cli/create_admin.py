"""CLI: provision the first admin member (idempotent).

Designed to run as a Helm hook Job after migrations and before the app pods
roll out, or by an operator as a one-off (e.g. break-glass recovery). Reuses
``MemberService.create`` + ``set_is_admin`` so it shares the exact code path the
admin API uses — no schema change, no bespoke SQL.

Two provider paths (see specs/017-admin-bootstrap):
- ``google_oidc`` (default): create a password-less member; the person binds to
  it on their first Google login (``_find_or_create_oidc_member`` matches by
  email). No secret is ever printed.
- ``local_password``: create the member and emit a one-time invitation link for
  the admin to set their password.

Idempotent: re-running for an already-provisioned admin is a no-op and exits 0.
Refuses to overwrite a member whose login provider differs (exits non-zero).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from ai_api.db import dispose_engine, get_sessionmaker
from ai_api.models import MemberProvider
from ai_api.observability.logging import setup_logging
from ai_api.services.access_control import WhitelistService
from ai_api.services.members import MemberService

ProvisionStatus = Literal["created", "promoted", "unchanged", "conflict"]

_CREATED_BY = "bootstrap-cli"


@dataclass
class ProvisionResult:
    status: ProvisionStatus
    email: str
    member_id: str | None = None
    provider: str | None = None
    invitation: str | None = None  # one-time link, local_password path only
    message: str = ""


def result_to_exit_code(result: ProvisionResult) -> int:
    """Map a provision outcome to a process exit code. Only conflicts fail."""
    return 1 if result.status == "conflict" else 0


async def provision(
    session: AsyncSession,
    *,
    email: str,
    provider: str = "google_oidc",
    display_name: str | None = None,
) -> ProvisionResult:
    """Ensure an admin member exists for ``email``. Caller commits the session.

    Idempotent and conflict-safe — see module docstring.
    """
    prov = MemberProvider(provider)
    email_n = email.strip().lower()
    svc = MemberService(session)

    existing = await svc.get_by_email(email_n)
    if existing is not None and existing.provider != prov:
        return ProvisionResult(
            status="conflict",
            email=email_n,
            member_id=existing.id,
            provider=existing.provider.value,
            message=(
                f"refusing: {email_n} already exists with provider "
                f"{existing.provider.value}, not {prov.value}"
            ),
        )

    # Whitelist the admin so the OIDC/local policy gate lets them log in.
    # Without this, login fails the is_email_allowed() check even though the
    # member + is_admin flag exist. Idempotent — safe on every (re-)run.
    await WhitelistService(session).add(
        email_n, added_by=_CREATED_BY, note="bootstrap admin"
    )

    if existing is not None:
        if existing.is_admin:
            return ProvisionResult(
                status="unchanged",
                email=email_n,
                member_id=existing.id,
                provider=prov.value,
                message=f"admin {email_n} already exists; no change",
            )
        await svc.set_is_admin(existing.id, True, actor=_CREATED_BY)
        return ProvisionResult(
            status="promoted",
            email=email_n,
            member_id=existing.id,
            provider=prov.value,
            message=f"promoted existing member {email_n} to admin",
        )

    created = await svc.create(
        email=email_n,
        provider=prov,
        display_name=display_name,
        send_invitation=(prov == MemberProvider.local_password),
        created_by=_CREATED_BY,
    )
    await svc.set_is_admin(created.member.id, True, actor=_CREATED_BY)
    if prov == MemberProvider.local_password:
        msg = f"created admin {email_n}; invitation: {created.invitation_plaintext}"
    else:
        msg = f"created admin {email_n} ({prov.value}); will bind on first Google login"
    return ProvisionResult(
        status="created",
        email=email_n,
        member_id=created.member.id,
        provider=prov.value,
        invitation=created.invitation_plaintext,
        message=msg,
    )


async def _run(args: argparse.Namespace) -> int:
    sm = get_sessionmaker()
    try:
        async with sm() as session:
            result = await provision(
                session,
                email=args.email,
                provider=args.provider,
                display_name=args.name,
            )
            if result.status == "conflict":
                # Do not commit — leave existing member untouched.
                print(result.message, file=sys.stderr)
                return result_to_exit_code(result)
            await session.commit()
        print(result.message)
        return result_to_exit_code(result)
    finally:
        await dispose_engine()


def main(argv: Sequence[str] | None = None) -> int:
    setup_logging()
    parser = argparse.ArgumentParser(
        prog="create_admin",
        description="Provision the first admin member (idempotent).",
    )
    parser.add_argument("--email", required=True, help="admin email")
    parser.add_argument(
        "--provider",
        choices=[MemberProvider.google_oidc.value, MemberProvider.local_password.value],
        default=MemberProvider.google_oidc.value,
        help="login provider (default: google_oidc)",
    )
    parser.add_argument("--name", default=None, help="display name (default: email)")
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
