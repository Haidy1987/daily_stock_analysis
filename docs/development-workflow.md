# 固定开发与交付流程

本文档把项目日常开发、验证、PR 和发布流程整理为一套可重复执行的 SOP。仓库协作规则仍以根目录 `AGENTS.md` 为唯一真源；如本文档与实际代码、脚本或工作流不一致，以可执行内容为准，并同步修正文档。

## 1. 环境基线

推荐统一使用：

- Python 3.11（项目最低要求为 Python 3.10，PR CI 使用 Python 3.11）
- Node.js 20.19+、npm 10+
- Docker 稳定版

后端初始化：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install flake8 pytest
```

Web 初始化：

```bash
cd apps/dsa-web
npm ci
```

桌面端初始化：

```bash
cd apps/dsa-desktop
npm ci
```

若本地 Python 或 Node 低于上述版本，不把由版本不匹配产生的测试收集、语法或构建错误判断为代码回归；先切换到项目支持的运行时再验证。

## 2. 接到任务后的固定动作

### 2.1 检查工作区

```bash
git status --short --branch
git diff --stat
```

- 已存在的修改和未跟踪文件默认属于用户，不覆盖、不清理、不擅自 stash。
- 未经明确确认，不执行 commit、tag、push。
- PR 创建、更新、审查或 Issue 分析任务，按 `AGENTS.md` 要求先检查工作区并同步远端 refs；工作区不安全时不强行切分支或覆盖本地状态。

### 2.2 判断任务类型

从以下类型中选择一个主类型：

```text
fix / feat / refactor / docs / chore / test / review
```

一个任务只解决一个明确问题。与当前目标无关的重构、依赖升级和“顺手优化”拆到其他任务。

### 2.3 标记影响面

开始修改前至少检查以下边界：

| 影响面 | 主要目录或入口 |
| --- | --- |
| 分析主流程 | `main.py`、`src/core/`、`src/services/` |
| 数据源与 fallback | `data_provider/` |
| API、Schema、认证 | `api/`、`src/schemas/`、`src/auth.py` |
| Web | `apps/dsa-web/` |
| Desktop | `apps/dsa-desktop/`、桌面构建脚本 |
| Bot 与通知 | `bot/`、`src/notification*`、`src/notification_sender/` |
| 报告 | `src/reports/`、`templates/`、报告渲染服务 |
| 调度 | `src/scheduler.py`、运行时调度服务、每日 workflow |
| 部署与发布 | `docker/`、`scripts/`、`.github/workflows/` |
| 文档与治理 | `docs/`、`AGENTS.md`、`.github/instructions/`、`.claude/skills/` |

配置、API、报告、数据源 fallback、认证、调度和发布流程属于高风险区域，必须检查上下游调用方。

## 3. 实现阶段规则

- 优先复用现有模块、配置入口、脚本和测试，不建立平行实现。
- 保持现有 API 和 Schema 兼容；优先追加字段或提供兼容层。
- 单一数据源或通知渠道失败默认不应拖垮整个分析流程。
- 新增配置时，同步更新 `.env.example` 和对应专题文档。
- 用户可见能力、CLI/API 行为、通知、部署或报告结构变化，同步更新 `docs/CHANGELOG.md`。
- 修改中文或英文文档时，评估对应语言版本；未同步要在交付说明中写明原因。
- Web UI 或报告展示变更需要准备截图或可复现的视觉证据，但一次性证据不提交到仓库。

收到 review 反馈后，应重新检查同一业务语义涉及的运行时、API、Web、配置、workflow、测试和文档，避免只在评论行附近追加补丁。

## 4. 固定验证矩阵

先运行最接近改动面的定向测试，再运行对应完整门禁。

### 4.1 Python 后端

最低检查：

```bash
python -m py_compile <changed_python_files>
```

完整离线门禁：

```bash
./scripts/ci_gate.sh
```

高风险改动应先补充并运行定向测试，例如：

```bash
python -m pytest tests/test_<affected_area>.py -q
```

### 4.2 Web

```bash
cd apps/dsa-web
npm ci
npm run lint
npm test
npm run build
```

涉及路由、登录、报告渲染、设置页或核心用户路径时，再执行：

```bash
npm run test:smoke
```

当前 PR CI 的 `web-gate` 只阻断 lint 和 build，因此本地 `npm test` 和必要的 Playwright smoke 结果需要在 PR 中单独记录。

### 4.3 Desktop

先构建 Web，再验证桌面端：

```bash
cd apps/dsa-web
npm ci
npm run lint
npm run build

cd ../dsa-desktop
npm ci
npm test
npm run build
```

平台不支持目标安装包时，明确记录未验证的平台、发布链路复核人和需要检查的 Release 产物。

### 4.4 API、Schema、认证

同时覆盖：

- 对应后端定向测试和完整后端门禁
- API 请求/响应兼容
- Web 调用方
- Desktop 内置后端或启动链路
- 登录、Cookie、会话、用户数据隔离

字段删除、改名、枚举变化和认证默认值变化不得无提示破坏现有客户端。

### 4.5 数据源、搜索和第三方依赖

- 先验证 timeout、retry、fallback、字段标准化和异常文案。
- 优先运行离线 mock 测试。
- 在线验证单独执行，不用网络成功替代离线回归。
- 网络 smoke 是观测项，不等同于 PR 阻断门禁。

可选的实际链路检查：

```bash
python main.py --dry-run --stocks 600519,AAPL --no-notify
```

### 4.6 通知

```bash
python main.py --check-notify
```

真实发送测试必须使用明确的测试目标，避免向生产群组或用户误发。单一通知渠道失败时，检查是否保持主流程成功和其他渠道可继续发送。

### 4.7 Docker、脚本和 workflow

```bash
docker build -f docker/Dockerfile -t stock-analysis:test .
docker run --rm stock-analysis:test python -c "from api.app import app; print('ok')"
docker compose --env-file .env -f docker/docker-compose.yml config
```

验证 Docker 配置时使用脱敏配置。不得把真实密钥输出到日志或提交到仓库。

涉及 Docker Compose 发布时，必须确认：

- 根目录 `.env` 只用于 Compose 解析部署变量。
- 容器运行时配置继续来自 `data/runtime.env`。
- 发布同步排除 `data/`，不覆盖数据库和运行时配置。

### 4.8 文档与 AI 治理

纯文档改动不强制运行代码测试，但需要核对命令、路径、配置名和 workflow 名称。

修改 AI 协作治理资产时执行：

```bash
python scripts/check_ai_assets.py
```

## 5. PR 固定流程

### 5.1 提交前自审

- `git diff` 中没有密钥、本地配置、数据库、日志和临时截图。
- diff 只覆盖当前任务。
- 新行为有回归测试。
- 用户可见变化已更新专题文档和 `docs/CHANGELOG.md`。
- 中英文文档同步情况已说明。
- 实际验证命令和结果已记录。

### 5.2 PR 描述必须包含

1. 原问题或目标
2. 根因（fix 类必填）
3. 修改范围和文件清单
4. 验证命令及结果
5. 未验证项
6. 兼容性与风险
7. 回滚方式
8. Web UI 或报告变更的视觉证据

PR 标题建议使用：

```text
<类型>: <修改内容>
```

不添加工具或 agent 来源前缀。

### 5.3 合入判断

必须关注：

- `ai-governance`
- `backend-gate`
- `docker-build`
- 触发时的 `web-gate`
- PR 描述与当前 Head 的一致性
- 高风险业务契约是否完整收敛

CI 通过不能替代人工语义检查。网络 smoke 为非阻断观测项，应独立记录。

## 6. 调度所有权

每个部署环境只保留一个明确的分析调度所有者：

| 部署方式 | 推荐调度所有者 |
| --- | --- |
| GitHub Actions | `.github/workflows/00-daily-analysis.yml` |
| Docker 定时分析 | `analyzer` 服务 |
| Docker Web/API | `server` 服务只提供 Web/API；需要调度时明确启用运行时调度 |
| 本地 CLI | `python main.py --schedule` |
| Desktop | Electron 管理的内置后端 |

启用多个调度入口前必须确认不会重复分析、重复写入或重复通知。

## 7. 发布流程

推荐顺序：

```text
任务完成
→ 定向验证
→ 完整门禁
→ PR 审查与合入
→ 明确版本类型
→ 创建 annotated tag
→ Docker/Desktop 发布
→ 健康检查与实际 smoke
→ 观察日志和通知
```

- 自动 tag 保持 opt-in，只有 commit title 含 `#patch`、`#minor` 或 `#major` 时触发。
- 手动 tag 必须是 annotated tag。
- 未经用户确认，不执行 commit、tag 或 push。
- 生产部署优先固定版本 tag，避免无法确认 `latest` 对应的代码。
- 发布前记录上一个稳定版本和配置备份位置。

Docker 发布后至少检查：

```bash
docker compose --env-file .env -f docker/docker-compose.yml ps
docker compose --env-file .env -f docker/docker-compose.yml logs --tail=200 server
curl -f http://127.0.0.1:8000/api/health
```

回滚时恢复上一个稳定镜像/tag；除非迁移文档明确要求，不覆盖或删除 `data/`、`data/runtime.env` 和数据库。

## 8. 固定交付格式

每次交付使用以下结构：

```text
改了什么
为什么这么改
验证情况
未验证项
风险点
回滚方式
```

纯文档任务可写 `Docs only, tests not run`，同时说明已核对的命令、路径和文件名。

## 9. 日常速查清单

```text
[ ] 检查工作区和现有改动
[ ] 判断任务类型与影响面
[ ] 使用 Python 3.11 / Node 20.19+
[ ] 阅读现有实现、测试、配置和文档
[ ] 做最小范围修改
[ ] 补充定向回归测试
[ ] 按影响面执行验证矩阵
[ ] 同步专题文档和 CHANGELOG
[ ] 检查中英文文档同步
[ ] 准备 PR 风险、回滚和视觉证据
[ ] 确认只有一个调度所有者
[ ] 发布使用固定版本并保留运行时数据
```
