# Quickstart / 驗證: OpenAI 相容 `/v1/models` ＋ Copilot

`<BASE>` = 平台對外 base（如 `https://ai.example.org`）；`<KEY>` = 一把應用金鑰。

## 1. curl — 列模型 / 取單一模型

```bash
# 列出這把金鑰能用的模型
curl -s "$BASE/v1/models" -H "Authorization: Bearer $KEY"
# → {"object":"list","data":[{"id":"azure/gpt-5.4","object":"model",...}, ...]}

# 取回單一模型（slug 含 / 直接放 path）
curl -s "$BASE/v1/models/azure/gpt-5.4" -H "Authorization: Bearer $KEY"

# 無金鑰 → 401
curl -s "$BASE/v1/models"            # → {"error":{"code":"unauthorized",...}}
```

## 2. OpenAI 官方 SDK — `models.list()`

```python
from openai import OpenAI
client = OpenAI(base_url=f"{BASE}/v1", api_key=KEY)

# 列模型（任何 OpenAI 相容客戶端的共同第一步）
for m in client.models.list():
    print(m.id)            # azure/gpt-5.4 ...

# 用清單裡的 id 原樣呼叫 → 必中（SC-002）
resp = client.chat.completions.create(
    model="azure/gpt-5.4",
    messages=[{"role": "user", "content": "ping"}],
)
print(resp.choices[0].message.content)
```

## 3. GitHub Copilot（VS Code）— 真機驗收（SC-004）

> 維護者在真實 VS Code 上跑；過不了就誠實標限制 / 延後（FR-010）。

1. 在會員「應用」商店開 **GitHub Copilot** 卡 → 用「建金鑰」捷徑建一把 scope 含 chat（responses 相容）模型的金鑰。
2. 依卡上步驟把 Copilot 的自訂 OpenAI 端點 base URL 指向 `<BASE>/v1`、填入金鑰。
3. 在 VS Code：
   - 確認 Copilot 能**列出模型**（打 `/v1/models`，選單出現 scope 內模型）。
   - 發起一次**對話**成功完成、用量歸戶到對應分配。
4. **跨 model 行為（US3）**：同一把金鑰切換 model 續用同一對話 → 應收到**可操作**的明確錯誤（提示開新對話），非靜默失憶；卡上已先說明此行為。

## 4. 部署後煙霧（非只 401）

```bash
# 帶真金鑰對真 gateway 真打一次（呼應「壞 token→401 不算驗過」）
curl -s "$BASE/v1/models" -H "Authorization: Bearer $REAL_KEY" | jq '.data[].id'
```
帶**真**金鑰回非空 list（且 id 能拿去 chat 成功）才算 `/v1/models` 驗收通過。

## 自動化測試對應

- 後端 contract：`tests/contract/test_v1_models.py`（list/retrieve/401/scope 隔離/排除非 active/未定價仍列/id 路由/既有端點零回歸）。
- 前端：`frontend/src/__tests__/apps-copilot.test.tsx`（Copilot 卡渲染、零分配指引、跨 model 文案）。
- SC-004 真機為人工驗收，不在 CI。
