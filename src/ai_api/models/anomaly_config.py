"""Phase (spec 054): anomaly-detector settings as an admin-editable DB singleton.

Holds the auto-quarantine on/off switch, an optional pause-until (auto-resumes
when it passes), and the detection thresholds — moved out of env so admins can
pause enforcement (e.g. during a workshop) and tune sensitivity without a
redeploy. Exactly one row (CHECK id = 1), same idiom as pool_config /
notification_config. get_anomaly_config lazy-seeds from settings on first read
so first run is a no-op behaviour change.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ai_api.db import Base


class AnomalyConfig(Base):
    """Singleton config — exactly one row enforced via CHECK (id = 1)."""

    __tablename__ = "anomaly_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # Master switch. When false (or paused), the detector still scans + audits
    # but does NOT quarantine anyone.
    auto_quarantine_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    # Non-null and in the future ⇒ enforcement paused until then; past/null ⇒ ignored.
    pause_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Detection thresholds (previously env-only; env is now bootstrap default).
    threshold_multiplier: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    min_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    absolute_cold_start: Mapped[int] = mapped_column(Integer, nullable=False, default=10000)
    # Ratio rule only applies when the baseline has at least this many samples;
    # below it the baseline is too sparse to trust → fall back to absolute only.
    baseline_min_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_anomaly_config_singleton"),
        CheckConstraint("threshold_multiplier >= 1", name="ck_anomaly_config_multiplier"),
        CheckConstraint("min_calls >= 0", name="ck_anomaly_config_min_calls"),
        CheckConstraint("absolute_cold_start >= 0", name="ck_anomaly_config_abs"),
        CheckConstraint("baseline_min_calls >= 0", name="ck_anomaly_config_baseline_min"),
    )

    def _paused(self, now: datetime) -> bool:
        return self.pause_until is not None and self.pause_until > now

    def effective_enforcing(self, now: datetime) -> bool:
        """True ⇒ the detector should quarantine; False ⇒ scan/audit only."""
        return self.auto_quarantine_enabled and not self._paused(now)

    def status(self, now: datetime) -> str:
        if not self.auto_quarantine_enabled:
            return "disabled"
        if self._paused(now):
            return "paused"
        return "enabled"
