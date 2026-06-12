# Quickstart: realtime 即時字幕端點

## 給接平台的開發者（客戶端怎麼用）

平台暴露 OpenAI 相容的 realtime transcription WebSocket 端點。用你分配到的**應用金鑰**連線、串流麥克風音訊（PCM），即時收文字事件，自己渲染字幕。

```python
# 概念範例（實際以 OpenAI realtime 客戶端慣例為準）
import websockets, json, base64

async with websockets.connect(
    "wss://<平台網域>/v1/realtime",
    additional_headers={"Authorization": "Bearer <你的應用金鑰>"},
) as ws:
    await ws.send(json.dumps({
        "type": "session.update",
        "session": {"type": "transcription", "model": "azure/gpt-realtime-whisper",
                    "audio": {"input": {"format": {"type": "audio/pcm", "rate": 24000}}}},
    }))
    # 串流音訊
    await ws.send(json.dumps({"type": "input_audio_buffer.append",
                              "audio": base64.b64encode(pcm_chunk).decode()}))
    # 收即時字幕
    async for msg in ws:
        ev = json.loads(msg)
        if ev["type"] == "conversation.item.input_audio_transcription.delta":
            print(ev["delta"], end="", flush=True)
```

- 你拿不到、也不需要底層供應商金鑰——只用平台金鑰連平台端點。
- 用量按**分鐘**計，歸戶到你的分配、計入配額，可在「用量」頁看到。
- 金鑰被撤回 / 分配被暫停時，進行中的連線會被平台主動中止。

## 給維護者（implement 階段的真打驗證步驟）

CI 不真連 Azure realtime WS（Constitution Deviation）；真實邊界以**部署後手動煙霧**驗。建議順序：

1. **協定真打**（research R1/R2 校驗）：用 Azure Foundry 的 gpt-realtime-whisper endpoint+key，跑一支最小腳本連 WS、送一段已知秒數的 PCM、確認：
   - 收到 `...transcription.delta`（接得通、首段 <1s）
   - 我們自算的時長 vs（若有）provider usage / Azure 帳單對得上（R2 校驗，必要時加校正）
2. **relay 整合**（不需真 Azure）：起一個 **mock provider WS server** 送預錄事件流，跑契約測試 1–7（contracts/）。
3. **連線中撤回**：建立連線 → 後台撤回該分配 → 確認 N 秒內被 close(revoked) + 已累計時長落帳。
4. **部署煙霧**（rev 上線後）：
   - pod egress 實證 `wss://<foundry>.services.ai.azure.com:443` 可達。
   - nginx WS upgrade 生效（壞金鑰連線被 close 而非 200/SPA fallback）。
   - 真打一次完整字幕 → 用量頁看到一筆 `unit=minute` 歸戶分配。

## 驗收對照（spec Success Criteria）

| SC | 驗證 |
|---|---|
| SC-001 首段 <1s | 步驟 1 真打計時 |
| SC-002 100% 歸戶 | 步驟 4 用量頁查 CallRecord |
| SC-003 異常不漏記 | 契約測試 6（client 直接斷）|
| SC-004 撤回上限內斷線 | 步驟 3 / 契約測試 5 |
| SC-005 無效金鑰 100% 拒絕 | 契約測試 1 |
| SC-006 既有端點零回歸 | 全套件 + 既有 contract 測試 git diff 為空 |
