# 多用户切换、备份与验收说明（阶段 4）

> 依赖：阶段 0–3（盘点、认证核心、数据隔离、管理员 Web）已完成。
> 总规划：[multi-user-system-plan.md](./multi-user-system-plan.md)

本文档是可执行的切换手册，并附本仓库离线验收记录。禁止把真实密钥、生产备份或含密码的截图提交到仓库。

## 1. 配置语义（与规划对齐）

| 配置 | 含义 |
| --- | --- |
| `ADMIN_AUTH_ENABLED=false` | 本地/桌面开放模式；业务数据回落到默认 admin 归属 |
| `ADMIN_AUTH_ENABLED=true` | 启用登录；Cookie 仍为 `dsa_session` |
| `AUTH_MODE=single_admin` | 仅使用 admin；**禁止**创建额外用户 / 提升管理员（灰度推荐起点） |
| `AUTH_MODE=multi_user` | 允许管理员创建用户与角色提升（未设置时默认 `multi_user`，兼容已部署环境） |

说明：

- 数据库侧 `users` / `user_id` 迁移在应用启动时幂等执行，与 `AUTH_MODE` 无关。
- `AUTH_MODE` 只约束「是否开放多人运营」，不关闭已有隔离逻辑。

`.env` 示例：

```env
ADMIN_AUTH_ENABLED=true
AUTH_MODE=single_admin
ADMIN_SESSION_MAX_AGE_HOURS=24
# 单层可信反向代理时建议：
# TRUST_X_FORWARDED_FOR=true
```

## 2. 上线前检查清单

1. 在**独立数据库副本**上启动新版本（不要直接在生产库试验未验证迁移）。
2. 执行备份（见第 3 节）。
3. 启动服务，设置 `AUTH_MODE=single_admin`，确认旧 `admin` 可登录。
4. 运行迁移校验脚本，确认私有表 `user_id` 空值可接受（admin 存在时应为 0）。
5. 将 `AUTH_MODE=multi_user` 并滚动重启。
6. 由管理员创建测试用户 A/B，完成隔离验收。
7. 观察登录失败、SQLite 锁、后台任务、通知与容器日志。
8. 验收通过后再创建真实用户。

> 提词原文将「创建 A/B」写在切换 `multi_user` 之前；以本仓库实现为准：**必须先切到 `multi_user` 才能创建用户**。

## 3. 备份与恢复

```bash
# 建议先停写或停服务，再备份（含 WAL）
chmod +x scripts/backup_multi_user_data.sh scripts/restore_multi_user_data.sh
./scripts/backup_multi_user_data.sh ./data

# 输出类似：backup_ok path=./backups/multi-user-YYYYMMDDHHMMSS
# 备份目录默认在 backups/，请加入本地忽略策略，勿提交仓库
```

恢复（停服务后）：

```bash
./scripts/restore_multi_user_data.sh ./backups/multi-user-YYYYMMDDHHMMSS
# 如需还原 .env：手动复制 backups/.../config/dotenv.env -> .env
```

回滚规则：

1. **优先**回滚应用镜像/代码版本，不要先删迁移后的表或字段。
2. 配置问题：将 `AUTH_MODE` 改回 `single_admin`（或关闭 `ADMIN_AUTH_ENABLED` 仅用于本地排障）。
3. 数据损坏或不可逆问题时：停服务，从停机前备份恢复 `data/`。
4. 禁止用旧版本程序对已完成破坏性迁移的库继续写入。
5. 记录回滚时间、备份目录名、镜像/git 版本与影响范围。

## 4. 迁移校验

```bash
# 针对当前 ENV_FILE / DATABASE_PATH
python scripts/verify_multi_user_migration.py --require-admin
python scripts/verify_multi_user_migration.py --json
```

期望：`ok=true`，`missing_columns=[]`，在 admin 已存在时 `total_null_user_id=0`。

## 5. Docker / Traefik 部署要点

Compose 文件：`docker/docker-compose.yml`（服务名 `server` / `analyzer`）。

```bash
docker compose -f docker/docker-compose.yml config
# FastAPI：
docker compose -f docker/docker-compose.yml up -d server
docker compose -f docker/docker-compose.yml ps
curl -fsS "http://127.0.0.1:${API_PORT:-8000}/api/v1/health"
```

注意：

- 数据持久化依赖 volume：`../data`、`../logs`、`../reports`。
- 镜像 `HEALTHCHECK` 探测 `/api/health` 或 `/health`（认证豁免）。
- 经 HTTPS 反代时 Cookie 需 Secure；开启 `ADMIN_AUTH_ENABLED` 后建议配置 `TRUST_X_FORWARDED_FOR`（见 [deploy-webui-cloud.md](../deploy-webui-cloud.md)）。
- 重启后确认 `users` / `user_sessions` / 业务 `user_id` 仍在 `data/` 卷中。

## 6. 验收矩阵与离线结果

| 项 | 覆盖点 | 命令 / 证据 | 结果 |
| --- | --- | --- | --- |
| 认证 | 登录、logout-all、/me、禁用、admin 门禁 | `pytest tests/test_multi_user_auth.py -q` | 8 passed |
| 权限 | admin users CRUD、`AUTH_MODE` 门闩 | `pytest tests/test_admin_users.py -q` | 5 passed |
| 隔离 | 历史 / 自选 / 持仓 / 预警 / 信号 | `pytest tests/test_multi_user_isolation.py -q` | 5 passed |
| 异步 | TaskQueue 按 user_id 去重与查询 | `pytest tests/test_multi_user_task_queue.py -q` | 3 passed |
| 迁移 | 空库、遗留库回填、幂等 | `pytest tests/test_multi_user_migration.py -q` | 4 passed |
| Web | lint/build；账户页与用户管理 | `cd apps/dsa-web && npm run lint && npm run build` | 阶段 3 已通过；阶段 4 未强制重跑 |
| Docker | compose config | `docker compose -f docker/docker-compose.yml config` | exit 0（未做完整 image build / Traefik） |
| 备份演练 | backup 脚本对副本目录 | `./scripts/backup_multi_user_data.sh <tmp-data>` | `backup_ok` |
| 迁移校验脚本 | 独立临时库 | `python scripts/verify_multi_user_migration.py --require-admin` | `ok=true` |

多用户相关 pytest 汇总（本机）：**25 passed**（migration + task_queue + admin_users + auth + isolation）。

### 已知残余风险（不阻断阶段 4 文档交付）

- Decision signal outcomes / reassess / feedback 部分次要路径隔离可能不完整。
- Alert triggers/notifications 列表隔离弱于规则 CRUD。
- `reports/` 落盘目录尚未按用户分子目录。
- Bot 会话不绑定 Web `users.id`。
- 完整 Docker build / Traefik HTTPS / 真实公网 Secure Cookie 需在目标环境验证。

## 7. 监控观察项

- 登录 401/403/429 比例与限流日志
- SQLite `database is locked` 频率
- 分析任务失败率与跨用户 task_id 访问
- 通知渠道失败（fail-open 不应拖垮主流程）
- 容器 health 与重启后会话是否仍有效

## 8. 阶段交接

- 下一动作：在目标环境按第 2–5 节灰度；通过后再创建真实用户。
- 回滚：第 3 节。
- 不在本阶段引入开放注册、OAuth、租户或用户级模型密钥。
