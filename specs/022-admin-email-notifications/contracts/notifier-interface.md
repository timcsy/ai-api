# 內部介面契約：`Notifier`

本檔定義平台內部「通知派發抽象層」的 Python interface 契約。第一版只實作
`EmailNotifier`；未來 LINE Bot / Web Push 等新 channel 以平行 adapter 加入時實作同
介面、不修改既有 caller。

---

## 介面定義（草稿；最終 code 於 `src/ai_api/services/notifier.py`）

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class NotificationEvent:
    """Event 來源資料的標準化封裝，供 Notifier 派發時取材。"""
    audit_event_id: str | None       # None for test sends
    event_type: str                  # AuditEventType value
    occurred_at: datetime            # tz-aware UTC
    target_type: str | None          # e.g. "allocation" / "provider_credential"
    target_id: str | None
    target_display_name: str | None  # friendly name when available
    details: dict[str, Any]          # event-specific data (e.g. last_hour_calls, baseline)


@dataclass(frozen=True)
class NotificationResult:
    outcome: str                     # see notification_record.outcome enum
    smtp_response_code: int | None
    per_recipient_status: dict[str, str]
    error_message: str | None
    latency_ms: int


class Notifier(ABC):
    """單一通知 channel 的派發介面。"""

    @abstractmethod
    async def notify(
        self,
        session: AsyncSession,
        event: NotificationEvent,
    ) -> NotificationResult:
        """
        Dispatch event to the channel.

        Implementations MUST:
          - Read NotificationConfig; if absent/disabled → return outcome=skipped_disabled
          - Apply 5-min same-event-type dedup (via notification_dedup_bucket)
          - Persist a notification_record row regardless of outcome
          - Never raise; capture all exceptions and surface via NotificationResult
          - Complete within 30 seconds (FR-017); rely on aiosmtplib timeout
        """

    @abstractmethod
    async def test_send(
        self,
        session: AsyncSession,
        test_recipient: str,
    ) -> NotificationResult:
        """
        Send a synthetic test message to a one-off recipient (NOT the saved
        recipient list — see FR-007). Does NOT consult or update dedup buckets.
        Persists a notification_record row with outcome=test_sent / test_failed_*.
        """
```

---

## EmailNotifier 行為契約

### 必須符合：

1. **使用 `aiosmtplib` + `email.message.EmailMessage`**：純 async；TLS 與 STARTTLS 皆支援
2. **TLS policy**：
   - port 587 → STARTTLS（required）
   - port 465 → 直接 TLS
   - 其他 port → 嘗試 STARTTLS，若 server 不支援則失敗（不退回 plaintext）
3. **timeout**：connect 15s、command 30s（與 FR-017 對齊）
4. **dedup query**：
   ```sql
   SELECT id, event_count FROM notification_dedup_bucket
   WHERE event_type = :event_type AND window_end > :now
   FOR UPDATE  -- row lock to handle concurrent inserts (multi-replica)
   ```
   - 命中 → `event_count += 1`, `last_event_at = now`, record `outcome=suppressed`, return
   - 未命中 → insert bucket, send email, record `outcome=sent` / `send_failed_*`
5. **per_recipient_status**：
   - SMTP 多 recipient 寄送時，server 可能個別 reject 某幾位（FR-021）
   - `aiosmtplib.send()` 回傳的 `errors` dict 直接 mapping 到 `per_recipient_status`
6. **失敗分類**：
   - `aiosmtplib.SMTPAuthenticationError` → `send_failed_auth`
   - `aiosmtplib.SMTPConnectError / SMTPServerDisconnected / OSError` → `send_failed_connect`
   - `aiosmtplib.SMTPSenderRefused` → `send_failed_sender`
   - 所有 recipient 都 reject → `send_failed_all_recipients`
   - 其他 → `send_failed_unknown`
7. **subject 與 body 內容**：見 `research.md` R6 範本
8. **logging**：每筆寄送結束 log 一筆 INFO/ERROR 結構化 JSON，含：
   - `event_type`、`audit_event_id`、`recipients_count`（不含 email 明文）、`outcome`、
     `smtp_response_code`、`latency_ms`
   - email 地址在 log 中採 partial mask（`tim***@school.edu.tw`）

### 不可：

- ❌ 在寄信失敗時 raise（必須 catch 並回 `NotificationResult`）
- ❌ 在 dedup 命中時嘗試「合併寄一封新信」（v1 不做 follow-up summary，見 research R3）
- ❌ 重試（v1 不重試，見 research R7）
- ❌ 讓寄送阻塞超過 30 秒（透過 `aiosmtplib` timeout 強制）

---

## 訂閱注入契約

`audit.record()` 在寫入 audit event 後，若 `event_type ∈ NOTIFY_EVENT_TYPES`（module-level
frozenset），即觸發：

```python
asyncio.create_task(
    notifier.notify(session, NotificationEvent.from_audit_row(audit_row))
)
```

**契約規定**：
- 此 hook 失敗 / 拋例外 MUST NOT 影響 audit.record() 自身寫入（FR-025）
- `asyncio.create_task` 為 fire-and-forget；notifier 內部自行管理 session 與 lifecycle
- `NOTIFY_EVENT_TYPES` 預設為：`{allocation_quarantined, responses_upstream_error_burst,
  provider_credential_auth_failed, allocation_daily_cap_exceeded}`
- 可被 `NOTIFY_EVENT_TYPES_OVERRIDE` 環境變數覆寫（comma-separated）以利測試與 operator
  調整

---

## 測試契約

實作必須有以下測試（在 `/speckit.tasks` 階段拆解）：

1. **unit**：`EmailNotifier.notify()` 對各種 SMTP 異常分類正確
2. **unit**：dedup logic 在同 window 內第二筆事件 → suppressed；window 過後 → 新 bucket
3. **integration**：用 `aiosmtpd` 起內部 SMTP server，驗證真實 TLS / STARTTLS / auth 握手
4. **integration**：`audit.record()` 觸發 hook，notifier 收到 event 並寄信
5. **contract**：4 條 endpoint（GET/PUT/DELETE config、POST test-send、GET history）回應
   符合 `admin-notifications.openapi.yaml`
6. **edge**：FR-005 — config 不存在時，audit event 觸發後 record 落 `outcome=skipped_disabled`
   且 audit 寫入無異常
