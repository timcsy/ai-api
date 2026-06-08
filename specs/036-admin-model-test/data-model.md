# Phase 1 Data Model: admin 依模型種類測試

**無 schema 變更、無新表、無 migration。** 只讀既有 `ModelCatalog`；新增一個 audit 列舉值（非 native enum，無 migration）。

## 既有實體：`ModelCatalog`（只讀）

判定種類用到的既有欄：
- `modality_input: list[str]`、`modality_output: list[str]`（所有模型必有）
- `litellm_sync: dict | None`——其 `["raw"]["mode"]` 為 litellm 原生 mode（litellm 對接過的模型才有；手動為 null）

## 概念：模型種類（`model_kind`）

`services/model_kind.py:model_kind(model) -> Literal["chat","embedding","tts","image","stt","unknown"]`

### 判定表（上而下，先命中先回）

| 條件（優先 litellm mode，退 modality） | kind | 測法 | billable |
|---|---|---|---|
| `litellm_sync.raw.mode ∈ {chat, completion}` | `chat` | 1-token completion | 否 |
| `litellm_sync.raw.mode == embedding` | `embedding` | 短字串 embedding | 否 |
| `litellm_sync.raw.mode == image_generation` | `image` | 最小尺寸生圖 | **是** |
| `litellm_sync.raw.mode == audio_speech` | `tts` | 極短文字→語音 | **是** |
| `litellm_sync.raw.mode == audio_transcription` | `stt` | （未支援） | — |
| `litellm_sync.raw.mode` 其他值 | `unknown` | （未支援） | — |
| 無 mode 且 `modality_output == ["image"]` | `image` | 同上 | **是** |
| 無 mode 且 `modality_output == ["audio"]` | `tts` | 同上 | **是** |
| 無 mode 且 `modality_input` 含 `audio`、輸出 text | `stt` | （未支援） | — |
| 無 mode 且其餘（輸出 text） | `chat` | 同上 | 否 |

> **已知限制**：手動建立（無 `litellm_sync`）的 embedding 模型會落 `chat`（modality 與 chat 撞型）；測對話呼叫會自然失敗給訊號，非靜默誤判。

### 衍生欄（admin `_to_dict` 輸出，唯讀）
- `test_kind`: 上表的 kind
- `test_billable`: kind ∈ {image, tts}
- `test_supported`: kind ∉ {stt, unknown}

## 測試結果（暫態，不落表）

```text
TestResult = {
  ok: bool,
  kind: str,
  latency_ms?: int,          # 成功時
  error_type?: str,          # 失敗時（如 upstream_error / provider_unavailable）
  message?: str,             # 失敗原因（帶上游訊息）
  needs_confirmation?: bool, # billable 未確認時
  supported?: bool,          # stt/unknown 時 false
}
```

## 既有實體：`AuditEventType`（加一值，非 native enum → 無 migration）

- 新增 `model_tested = "model_tested"`；details `{kind, ok, latency_ms?, error_type?}`；actor `admin`、target `model_catalog/{slug}`。

## 不變式
- `model_kind` 對任一 `ModelCatalog` 必回上述六值之一（不丟例外）。
- billable 種類在未帶 `acknowledge_billable` 時 MUST NOT 觸發上游呼叫。
- 測試呼叫 MUST 寫 `model_tested` audit、MUST NOT 寫成員 `CallRecord`。
