# 010：bookkeeping 寫入從「掛在請求 session」到「獨立短交易立即 commit」
> 日期：2026-06-29

## 轉移
- 舊（superseded）：共用 provider 憑證的 `last_used_at` 寫入掛在**請求 session** 上，鎖持有跨整段上游呼叫。
- 新：`get_next()` 的 `last_used_at` flush 改**獨立短交易立即 commit**（鎖只持毫秒、絕不跨外部慢呼叫），
  且不弄髒請求 session 上的 ORM 物件；+ 可調連線池 + `pool_pre_ping`。

## 為什麼變
ccsh 遷入後高併發塞車：`/v1/responses` 500，`pg_stat_activity` 50 條 active 卡死、最久 1004 秒全是同一句
`UPDATE provider_credentials … last_used_at`，而 CPU 全程 12% 很閒——症狀像「算力/連線不夠」、根因是「鎖持有
時間 × 共用單把 Azure key 熱列 × 併發」。**誤判彎路**：先當容量問題加 pod（2→5）+ 加大連線池（治標、甚至
更糟：更多連線搶同一列）。修後連線 79→5、active 51→1、卡死 UPDATE 50→0、500 歸零。既有 app-key `last_used_at`
早有 >5min 節流、provider-cred 這條漏了——同類 bookkeeping 要套同一防護。

## 狀態
✅ 已採用（事故治本）。已知擴充：多 provider 憑證／負載分散——round-robin 已具，但單把 key 時無效，未來量再
大需多把 key 或連線池中介（PgBouncer），見 `draft/`。
