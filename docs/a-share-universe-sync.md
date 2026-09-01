# A 股全量主数据与快照同步

本文档描述 Issue #2 的分阶段落地契约。Phase 0 提供数据库表结构与 Repository；Phase 1 起提供主数据采集 CLI。

## 目标

- 维护**沪深京 A 股全量主数据**（慢变字段）
- 维护**交易日快照**（行情、估值、财务摘要等快变字段）
- 供自动补全、筛选、选股和分析预热复用

## 表结构

### `a_share_universe`（慢变主数据）

| 字段 | 说明 |
| --- | --- |
| `code` | 6 位 A 股代码，唯一 |
| `name` | 股票简称 |
| `exchange` | `SH` / `SZ` / `BJ` |
| `board` | 板块，如主板/创业板/科创板 |
| `industry` | 所属行业 |
| `list_date` | 上市日期 |
| `active` | 是否仍在 universe 中 |
| `source` | 数据来源标识 |

### `a_share_snapshot`（快变快照）

按 `(code, data_date)` 唯一，字段覆盖：

- 行情：`price/open/high/low/pre_close/pct_chg/amplitude/volume/amount/turnover_rate/volume_ratio`
- 估值：`pe_ttm/pe_dynamic/pb/ps/total_mv/circ_mv/total_share/float_share`
- 财务摘要：`eps/bps/roe/revenue/revenue_yoy/net_profit/net_profit_yoy`
- 区间：`high_52w/low_52w/ytd_pct_chg`

> 与 `stock_daily`（单股历史 K 线）和 `fundamental_snapshot`（单次分析 write-only 快照）职责分离。

## 代码入口（Phase 0）

- ORM：`src/storage.py` → `AShareUniverse` / `AShareSnapshot`
- 类型：`src/schemas/a_share_universe.py`
- Repository：`src/repositories/a_share_universe_repo.py`

## 代码入口（Phase 1）

- Provider：`src/services/a_share_universe/providers.py`
- 同步服务：`src/services/a_share_universe_sync_service.py`
- CLI：`scripts/sync_a_share_universe.py`

## 代码入口（Phase 2）

- 快照映射：`src/services/a_share_universe/snapshot_mapping.py`
- 快照 Provider：`src/services/a_share_universe/snapshot_providers.py`
- Checkpoint/报告：`src/services/a_share_universe/checkpoint.py` → `data/a_share_sync/`

## 代码入口（Phase 3）

- 索引构建：`src/services/a_share_universe/index_builder.py`
- 共享索引逻辑：`src/services/stock_index_builder.py`
- DB 索引脚本：`scripts/generate_index_from_db.py`
- 刷新入口：`scripts/refresh_stock_index.py --source db`
- Loader 回退：`src/data/stock_index_loader.py`
- 搜索 API：`GET /api/v1/universe/a-share/search?q=茅台&limit=20`

```bash
# 从 universe 表生成 Web 索引并同步 static 副本
python scripts/refresh_stock_index.py --source db

# 仅生成索引（可指定合并来源）
python scripts/generate_index_from_db.py
python scripts/generate_index_from_db.py --no-merge
```

### CLI 用法

```bash
# 默认东方财富（AkShare）拉取并入库
python scripts/sync_a_share_universe.py --mode universe-only

# 同步快照（行情/估值/财务摘要）
python scripts/sync_a_share_universe.py --mode snapshot

# 主数据 + 快照
python scripts/sync_a_share_universe.py --mode full

# 只验证拉取，不写库
python scripts/sync_a_share_universe.py --dry-run

# 从 checkpoint 继续快照补充
python scripts/sync_a_share_universe.py --mode snapshot --resume

# 使用 Tushare（需配置 TUSHARE_TOKEN；快照仍走 eastmoney）
python scripts/sync_a_share_universe.py --source tushare --mode full
```

Phase 1 同步**主数据**；Phase 2 增加**快照**（bulk spot + 业绩报表 + 可选个股补充），报告写入 `data/a_share_sync/last_report.json`。

常用 Repository 方法：

```python
from src.repositories.a_share_universe_repo import AShareUniverseRepository

repo = AShareUniverseRepository()
repo.upsert_universe([...])
repo.upsert_snapshot([...])
repo.get_by_code("600519")
repo.get_latest_snapshot("600519")
repo.search("茅台", limit=20)
```

## 配置项

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `A_SHARE_UNIVERSE_SYNC_ENABLED` | `false` | Phase 1+ 启用采集调度 |
| `A_SHARE_UNIVERSE_SOURCE` | `eastmoney` | `eastmoney` / `tushare` |
| `A_SHARE_UNIVERSE_WORKERS` | `6` | 个股补充接口并发 |
| `A_SHARE_UNIVERSE_MIN_INTERVAL_SEC` | `1.0` | 请求最小间隔 |
| `A_SHARE_UNIVERSE_HISTORY_RETENTION_DAYS` | `0` | `0`=仅保留最新快照 |

Phase 0 只注册配置，不启动采集。

## 与现有链路关系

| 现有能力 | 关系 |
| --- | --- |
| `scripts/fetch_tushare_stock_list.py` | 仍输出 CSV；Phase 1 可复用逻辑但不写 DB |
| `scripts/refresh_stock_index.py` | Phase 3 增加 `--source db` |
| `src/data/stock_index_loader.py` | Phase 3 增加 DB fallback |
| `GET /api/v1/universe/a-share/search` | Phase 3 只读搜索 API |
| `StockDaily` | 不变，继续服务单股历史 K 线 |

## 分阶段计划

1. **Phase 0**（当前）：Schema + Repository + 配置 + 文档
2. **Phase 1**：东方财富/Tushare universe 主数据采集 CLI
3. **Phase 2**：快照字段 + 业绩报表合并 + checkpoint/resume + 同步报告
4. **Phase 3**（当前）：自动补全索引生成、loader DB 回退与 universe 搜索 API
5. **Phase 4**：调度 / Docker / 运维文档

## 排障

- 空库首次启动时会通过 SQLAlchemy `create_all` 自动建表。
- 若需隔离测试库，设置 `DATABASE_PATH` 指向独立 sqlite 文件。
- Phase 0 不包含外部采集；Repository/Provider 单测使用 mock 数据。
- 快照同步报告：`data/a_share_sync/last_report.json`
- 断点文件：`data/a_share_sync/checkpoint.json`（`--resume` 使用）

## 回滚

- Phase 0 无运行时行为变化；删除新表不影响现有 `stock_daily` 与分析主流程。
- 停用 `A_SHARE_UNIVERSE_SYNC_ENABLED`（默认已关闭）即可避免后续 Phase 调度。
