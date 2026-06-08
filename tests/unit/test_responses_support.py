"""Phase 25: responses_support marker state machine (axis ③ — gateway endpoint
availability, decoupled from litellm mode/capabilities). State + source are carried
in the existing ModelCatalog.capabilities JSON list via internal markers."""
from __future__ import annotations

from ai_api.services import responses_support as rs


def test_unknown_when_no_markers() -> None:
    s = rs.get_support(["chat", "vision"])
    assert s["state"] == "unknown"
    assert s["source"] is None


def test_available_tested() -> None:
    s = rs.get_support(["chat", rs.RESPONSES, rs.RESPONSES_TESTED])
    assert s["state"] == "available"
    assert s["source"] == "tested"


def test_available_manual() -> None:
    s = rs.get_support(["chat", rs.RESPONSES, rs.RESPONSES_MANUAL])
    assert s["state"] == "available"
    assert s["source"] == "manual"


def test_available_without_source() -> None:
    s = rs.get_support([rs.RESPONSES])
    assert s["state"] == "available"
    assert s["source"] is None


def test_blocked_is_unavailable_manual() -> None:
    # blocked implies manual source and takes precedence over any available marker
    s = rs.get_support([rs.RESPONSES, rs.RESPONSES_BLOCKED, rs.RESPONSES_TESTED])
    assert s["state"] == "unavailable"
    assert s["source"] == "manual"


def test_mark_tested_ok_sets_available_tested_and_clears_others() -> None:
    caps = rs.mark_tested_ok(["chat", rs.RESPONSES_BLOCKED, rs.RESPONSES_MANUAL])
    assert "chat" in caps
    assert rs.RESPONSES in caps and rs.RESPONSES_TESTED in caps
    assert rs.RESPONSES_BLOCKED not in caps and rs.RESPONSES_MANUAL not in caps
    s = rs.get_support(caps)
    assert s == {"state": "available", "source": "tested"}


def test_mark_tested_failed_resets_to_unknown() -> None:
    caps = rs.mark_tested_failed(["chat", rs.RESPONSES, rs.RESPONSES_TESTED])
    assert "chat" in caps
    assert not any(c.startswith("responses") for c in caps if c != "chat")
    assert rs.get_support(caps)["state"] == "unknown"


def test_mark_manual_on() -> None:
    caps = rs.mark_manual_on(["chat", rs.RESPONSES_TESTED])
    assert rs.get_support(caps) == {"state": "available", "source": "manual"}
    assert rs.RESPONSES_TESTED not in caps


def test_mark_manual_off_blocks() -> None:
    caps = rs.mark_manual_off(["chat", rs.RESPONSES, rs.RESPONSES_TESTED])
    assert rs.get_support(caps) == {"state": "unavailable", "source": "manual"}
    assert rs.RESPONSES not in caps and rs.RESPONSES_TESTED not in caps


def test_invariants_mutually_exclusive() -> None:
    for caps in (
        rs.mark_tested_ok(["x"]),
        rs.mark_manual_on(["x"]),
        rs.mark_manual_off(["x"]),
        rs.mark_tested_failed(["x"]),
    ):
        assert not (rs.RESPONSES in caps and rs.RESPONSES_BLOCKED in caps)
        assert not (rs.RESPONSES_TESTED in caps and rs.RESPONSES_MANUAL in caps)


def test_transitions_dedupe_existing_markers() -> None:
    # starting from a dirty list with duplicates, markers stay single
    caps = rs.mark_tested_ok([rs.RESPONSES, rs.RESPONSES, rs.RESPONSES_MANUAL, "chat"])
    assert caps.count(rs.RESPONSES) == 1
    assert caps.count(rs.RESPONSES_TESTED) == 1


def test_strip_internal_keeps_bare_responses() -> None:
    out = rs.strip_internal(["chat", rs.RESPONSES, rs.RESPONSES_TESTED, rs.RESPONSES_MANUAL])
    assert out == ["chat", rs.RESPONSES]


def test_strip_internal_drops_blocked() -> None:
    out = rs.strip_internal(["chat", rs.RESPONSES_BLOCKED, rs.RESPONSES_MANUAL])
    assert out == ["chat"]


def test_preserve_into_carries_old_responses_markers() -> None:
    new_caps = ["chat", "vision", "function-calling"]
    old_caps = ["chat", rs.RESPONSES, rs.RESPONSES_MANUAL]
    merged = rs.preserve_into(new_caps, old_caps)
    assert "vision" in merged and "function-calling" in merged
    assert rs.RESPONSES in merged and rs.RESPONSES_MANUAL in merged
    # no duplicates
    assert merged.count(rs.RESPONSES) == 1


def test_preserve_into_carries_blocked() -> None:
    merged = rs.preserve_into(["chat"], ["chat", rs.RESPONSES_BLOCKED, rs.RESPONSES_MANUAL])
    assert rs.get_support(merged)["state"] == "unavailable"
