# 12-ladderbill（阶梯电费）

Ladderbill — 居民阶梯电价分段累进（含尖峰系数）

## 启动

```bash
docker compose up --build
```

| 入口 | 地址 |
| --- | --- |
| 前端 | http://localhost:4100 |
| API | http://localhost:9100 |

## 主链

抄表录入 → 阶梯分段计费 → 账单明细

## 片区档位绑定

- 户号带 `zone_code`（片区代码）；`tier_schemes` 维护完整档位方案（含档表），`zone_bindings` 维护片区→启用方案绑定（每片区唯一）。
- 测算（`POST /api/bill`、`POST /api/compare`）与 `GET /api/accounts/{id}/resolved-tiers` 按「户号→片区→绑定→方案」解析档表；无片区/无绑定/绑定方案停用均回退全局 `tiers`。
- 回包含 `resolution`：`zone_code`、`scheme_id/scheme_code`、`fallback`、`fallback_reason`、`resolved_path`。
- 重复绑定冲突返回 **409**，`detail` 中带 `conflict_scheme_id` / `conflict_scheme_code`；改绑走 `PUT /api/zone-bindings/{zone}`。

## 技术栈

Python 3.12 + FastAPI + SQLite；Vue 3 + Vite + Nginx。
