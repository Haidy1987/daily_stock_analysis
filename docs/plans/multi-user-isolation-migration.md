# 多用户数据隔离迁移说明（阶段 2）

> 依赖：阶段 1 认证核心（`users` / `user_sessions`）已可用。

## 备份（迁移前）

停服务后备份数据目录（含 WAL）：

```bash
# 示例：备份整个 data 目录
cp -a data "data.backup.$(date +%Y%m%d%H%M%S)"
```

需包含：`stock_analysis.db`、`.db-wal`、`.db-shm`、`.admin_password_hash`、`.env`。

## 迁移行为

数据库初始化（`DatabaseManager`）会：

1. `create_all` 新建缺失表（含 `user_watchlist_items`）。
2. `_ensure_user_owned_user_id_columns`：为下列表 `ALTER TABLE ... ADD COLUMN user_id`（若不存在），并将 `NULL` 回填为初始 `admin` 用户 ID：
   - `analysis_history`
   - `portfolio_accounts`
   - `alert_rules`
   - `decision_signals`
   - `decision_signal_feedback`
   - `conversation_messages` / `conversation_summaries` / `agent_provider_turns`
   - `llm_usage`（可空，仅观测）
3. 若 admin 尚无（未设密），跳过回填；`set_initial_password` 成功后会再触发回填。
4. 将全局 `STOCK_LIST` 种子复制到 admin 的 `user_watchlist_items`（仅当 admin 自选为空）。

全局 `STOCK_LIST` 仍保留给 CLI / schedule；Web 自选走 per-user 表。

## 校验命令

```bash
python3 - <<'PY'
from src.storage import DatabaseManager, AnalysisHistory, PortfolioAccount, AlertRuleRecord, UserWatchlistItem
from src.auth import get_default_admin_user_id
from sqlalchemy import select, func

db = DatabaseManager.get_instance()
admin_id = get_default_admin_user_id()
with db.get_session() as s:
    null_hist = s.execute(select(func.count()).select_from(AnalysisHistory).where(AnalysisHistory.user_id.is_(None))).scalar_one()
    null_acct = s.execute(select(func.count()).select_from(PortfolioAccount).where(PortfolioAccount.user_id.is_(None))).scalar_one()
    null_alert = s.execute(select(func.count()).select_from(AlertRuleRecord).where(AlertRuleRecord.user_id.is_(None))).scalar_one()
    wl = s.execute(select(func.count()).select_from(UserWatchlistItem).where(UserWatchlistItem.user_id == admin_id)).scalar_one()
print("admin_id", admin_id)
print("null analysis_history.user_id", null_hist)
print("null portfolio_accounts.user_id", null_acct)
print("null alert_rules.user_id", null_alert)
print("admin watchlist rows", wl)
PY
```

期望：各 `null_*` 为 `0`（在 admin 已存在的前提下）。

## 回滚

1. 停服务
2. 还原备份的 `data/`（含 db/wal/shm）
3. 部署阶段 2 之前的代码

新列/新表残留在旧代码下通常可忽略；干净回滚以文件还原为准。

## 已知缺口

- Decision signal outcomes / reassess / feedback 部分次要路径可能尚未全量按 `user_id` 过滤。
- Alert triggers/notifications 列表隔离弱于规则 CRUD。
- `reports/` 落盘目录尚未按用户分子目录。
- Bot 会话仍按平台 `session_id` 前缀，不绑定 Web `users.id`。
