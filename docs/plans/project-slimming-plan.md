---
type: plan
status: draft
owner: maintainer
updated: 2026-07-13
scope: repository
---

# 项目瘦身规划

## 1. 文档定位

本文是当前项目的瘦身实施规划，不直接改变运行时行为，也不代表其中的清理项已经执行。

项目瘦身拆分为三条线：

1. 仓库文件瘦身：减少工作区和普通 clone 的体积。
2. 运行依赖瘦身：减少安装量、构建时间和 Docker 镜像体积。
3. 代码复杂度瘦身：减少重复入口、可选能力耦合和长期维护面。

Git 历史清理单独处理，不与普通文件删除混合进行。

## 2. 当前基线

截至 2026-07-13，仓库盘点结果如下：

| 项目 | 当前规模 | 说明 |
| --- | ---: | --- |
| 工作区 | 约 184 MB | 包含源码、文档、资源和本地 Git 数据 |
| `.git/` | 约 96 MB | 历史对象体积，普通删除不会减少 |
| `docs/` | 约 71 MB | 主要由图片、GIF 和设计源文件组成 |
| `docs/assets/` | 约 68 MB | 当前最明显的工作区瘦身位置 |
| `apps/dsa-web/public/stocks.index.json` | 约 3.2 MB | Web 运行时股票索引，暂不删除 |

当前工作区还有未跟踪的 `.agents/`，属于用户现有内容，瘦身过程中必须保留。

## 3. 总体原则

- 稳定性优先，先做不影响运行链路的清理。
- 先确认引用关系，再删除或迁移文件。
- 不因减少文件数量而删除仍承担 fallback、打包、兼容或文档入口职责的模块。
- 不把用户可见能力变更伪装成清理；功能移除必须单独说明兼容性影响。
- 不修改 Git 历史，除非维护者明确确认并完成备份。
- 每个阶段都保留可回滚边界，不做跨阶段的大型混合提交。

## 4. 实施阶段

### P0：建立可比较的基线

在任何删除前记录：

- `du -sh . .git docs docs/assets`；
- 当前已跟踪的大文件清单；
- 前端 lint、build 和 test 结果；
- 后端离线测试或 CI gate 结果；
- Docker 构建是否受影响。

每个阶段完成后重新记录同一组指标，避免只凭文件数量判断瘦身效果。

### P1：清理文档资源

目标：在不影响应用运行的前提下减少约 40–55 MB 工作区体积。

优先审查以下资源：

- `docs/assets/2026-01-10_155341_daily_analysis.gif`，约 30 MB，当前未发现文本引用；
- `docs/assets/all_2026-01-13_221547.gif`，约 7.3 MB，当前未发现文本引用；
- `docs/assets/dsa_vi/darklogo.psd`，约 13.7 MB；
- `docs/assets/dsa_vi/lightlogo.psd`，约 9.2 MB；
- `docs/assets/dsa_vi/bannersource.psd` 及 `dsa_logo.ai`；
- 已确认没有文档引用的重复图标和截图。

处理规则：

1. 先用全仓库搜索确认引用，包括 Markdown、代码、Workflow 和打包脚本。
2. 有长期产品展示价值的资源保留或压缩。
3. 仅用于设计编辑的 PSD/AI 源文件不进入运行产物，可移出仓库或删除。
4. Issue/PR 临时截图不转移到 `docs/assets/`，应放在 PR 附件或外部证据位置。
5. README 和双语项目首页使用的演示 GIF 暂不删除，除非先完成替代素材或压缩方案。

完成后更新受影响的文档链接，并在 `docs/INDEX.md` 中保持入口有效。

### P2：前端依赖瘦身

第一候选是 `apps/dsa-web/package.json` 中的 `@remixicon/react`：当前源码搜索未发现引用。

实施要求：

1. 使用包管理器移除依赖并同步 `package-lock.json`。
2. 对其他依赖逐项检查静态引用、动态导入和构建插件引用。
3. 不因为源码中没有直接 import 就删除可能被 Vite、Tailwind 或测试环境使用的依赖。
4. 执行：

```bash
cd apps/dsa-web
npm ci
npm run lint
npm run build
npm run test
```

### P3：Python 依赖分层

当前 `requirements.txt` 同时包含多数据源、搜索服务、Bot、LLM、报告生成和文件导入能力。直接删除依赖会破坏 fallback 或可选功能，因此先做分层，不立即删能力。

建议逐步形成以下依赖集合：

```text
requirements-core.txt
requirements-data.txt
requirements-search.txt
requirements-bot.txt
requirements-report.txt
requirements-dev.txt
```

推荐默认部署只安装核心依赖和目标数据源；Bot、图片报告、额外搜索源和低频数据源按能力安装。

在分层前必须确认实际部署画像：

- 是否需要 A 股、港股、美股以及 JP/KR/TW 能力；
- 是否使用 Discord、钉钉、飞书、Telegram 等通知渠道；
- 是否需要图片报告和 `wkhtmltopdf`；
- 是否需要 AlphaSift、Agent 和本地 CLI backend；
- Docker、GitHub Actions 和桌面端是否共用同一份依赖入口。

`alphasift`、`tiktoken`、`openai` 等被打包脚本或隐藏导入使用的依赖，必须先检查构建链路再决定是否调整。

### P4：代码复杂度瘦身

该阶段不以删除文件数量为目标，而以收敛职责为目标。

建议顺序：

1. 绘制 CLI、FastAPI、Web、Desktop、Bot、定时任务的真实入口图。
2. 识别只被历史脚本、测试或文档引用的模块。
3. 检查 `webui.py` 与当前 `main.py` / `server.py` 的兼容职责，确认是否仍需保留旧入口。
4. 将可选数据源、通知渠道和外部 SDK 改为按需加载，避免启动时加载全部能力。
5. 合并重复的配置、fallback 和异常处理逻辑。
6. 每删除一个模块，补充覆盖真实入口的回归测试。

本阶段禁止一次性删除整组数据源、Bot 或 Agent 模块；功能移除应作为独立变更评估。

### P5：Git 历史清理（可选）

只有当目标是减少远程仓库 clone 体积时才执行。

流程要求：

1. 备份仓库、分支和 tag。
2. 评估所有协作者、镜像和自动化流水线的影响。
3. 使用 `git filter-repo` 或同等工具清理历史中的大资源。
4. 本地验证分支、tag、构建和发布脚本。
5. 明确取得维护者确认后，才允许 force-push。

该阶段会改变历史，不能通过普通 PR 直接完成。

## 5. 验收标准

### 仓库文件

- 未引用的大型 GIF、PSD、AI 和重复资源已处理；
- README、`docs/INDEX.md`、双语文档链接有效；
- `.agents/` 等用户现有未跟踪内容未被修改；
- `git ls-files` 不再包含未经说明的临时验收证据。

### 应用运行

- 后端离线测试或 `./scripts/ci_gate.sh` 通过；
- 修改过的 Python 文件通过 `py_compile`；
- Web lint、build、test 通过；
- Docker 构建链路未因依赖或资源清理失效；
- Desktop 构建引用的 Web 静态资源和后端产物仍完整。

### 依赖分层

- 默认安装路径仍可启动核心分析流程；
- 各可选能力有清晰安装入口和文档说明；
- 数据源优先级、fallback、通知失败降级语义不变；
- 不再使用的依赖从清单、锁文件、Workflow 和文档中一并移除。

## 6. 风险与回滚

| 风险 | 处理方式 | 回滚方式 |
| --- | --- | --- |
| 删除了仍被文档引用的资源 | 删除前全仓库检索，保留引用资源 | 恢复资源文件并 revert |
| 删除前端依赖导致构建失败 | 先静态检查，再执行 lint/build/test | 恢复 `package.json` 和 lockfile |
| 依赖分层导致部署缺包 | 保留完整安装入口，逐环境验证 | 恢复原 `requirements.txt` 入口 |
| 删除数据源破坏 fallback | 先确认部署画像和 fallback 测试 | revert 对应能力变更 |
| Git 历史重写影响协作者 | 独立阶段、备份、明确授权 | 使用备份仓库恢复，不直接覆盖本地状态 |

## 7. 推荐执行顺序

```text
P0 基线记录
  -> P1 文档资源清理
  -> P2 前端无引用依赖清理
  -> P3 Python 依赖分层
  -> P4 代码复杂度收敛
  -> P5 Git 历史清理（可选）
```

建议先完成 P0–P2，再根据实际部署画像决定是否继续 P3。P5 不纳入常规瘦身迭代。

## 8. 当前待确认事项

- 项目默认部署是否仍需全部市场和全部数据源 fallback；
- 哪些 Bot / 通知渠道是必须保留的；
- 图片报告和 `wkhtmltopdf` 是否属于默认能力；
- Desktop 是否仍是正式发布目标；
- 是否有减少远程仓库 clone 体积的明确需求。
