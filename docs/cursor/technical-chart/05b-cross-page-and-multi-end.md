# Cursor 提词 05b：跨页面与多端联动

## 前置条件

阶段 05a 已完成，后端 daily/weekly/monthly 接口通过测试；P3 日线页面已完成。

## 提词正文

```text
你正在维护 daily_stock_analysis 项目。先读取 AGENTS.md、导航规划、页面结构、阶段 04a～04d 和 05a 的实际代码与交付记录。

本阶段目标：在 Web 页面开放周线/月线，增加首页、选股、持仓等现有页面的技术图表跳转，并完成手机浏览器和 Electron Desktop 联动验证。不要增加缓存、Docker 发布或最终 100% 标记。

实施前：

1. 检查工作区状态，保留已有改动，不执行 reset、checkout、stash、commit、push 或 tag。
2. 阅读 HomePage、StockScreeningPage、PortfolioPage、历史记录组件和 Desktop 加载 Web 产物的真实链路。
3. 识别各页面已有的 canonical stock code，禁止通过显示名称或用户输入字符串拼接 URL。

必须实现：

1. 周/月线页面开放
   - 启用 daily、weekly、monthly 控件。
   - period 与 URL 双向同步；非法值回退 daily。
   - 切换周期时取消旧请求，清空旧 mark/tooltip/series，保留合理 indicators 配置。
   - partial/warnings 能解释周/月历史不足。

2. 首页入口
   - 在当前股票分析结果或历史记录的合适操作区增加“查看技术图表”。
   - 跳转 `/technical-chart?stock={canonicalCode}`。
   - 不改变首页分析提交、历史趋势和删除行为。

3. 选股入口
   - 在选股结果行或详情操作中增加技术图表入口。
   - 仅传标准化股票代码，不把策略结果塞入公共图表 API。
   - AlphaSift 未启用时不影响技术图表一级菜单和其他入口。

4. 持仓入口
   - 在持仓股票操作中增加技术图表入口。
   - 只传股票代码；持仓成本、账户、盈亏和 user_id 不进入技术图表 URL/API。
   - 用户 A/B 持仓隔离仍由现有接口负责。

5. 历史趋势和其他入口
   - 历史趋势抽屉保持“分析历史”语义，可增加跳转按钮但不嵌入第二套完整 ECharts。
   - 不复制 TechnicalChart 计算或 option builder。

6. 多端
   - 手机浏览器验证各新增入口、周期切换和返回导航。
   - Electron Desktop 复用 Web 路由和构建产物，不新增独立图表页面。
   - 检查 BrowserRouter 深链接和 Desktop 启动/刷新 `/technical-chart` 是否符合现有路由托管方式。
   - PC/Windows 与 Mac 共用 Web 代码；平台差异只在验证记录中说明。

测试要求：

- 页面周期切换、URL、旧请求取消和 series 更新测试。
- HomePage、StockScreeningPage、PortfolioPage 新入口测试，断言 canonical code。
- 测试持仓入口不泄漏 accountId、user_id、成本或盈亏到 URL。
- 测试 AlphaSift 开关不影响技术图表一级导航。
- 运行 P3 完整 Web 回归。

建议验证命令：

cd apps/dsa-web
npm ci
npm run lint
npm run test
npm run build

Desktop：

cd ../dsa-desktop
npm install
npm run build

如当前平台无法完成 Electron 打包，至少验证 Web 构建产物路径和 Desktop 启动链路，并明确未验证平台，禁止声称全平台完成。

视觉证据：检查 PC/Mac、手机窄屏和 Desktop 中的导航入口、日/周/月切换。临时截图不提交仓库。

文档和进度：

- 更新导航、Desktop 或使用文档和 docs/CHANGELOG.md。
- 更新进度表：P4 保持进行中，记录 05b Web/Desktop 验证、缺口和下一节点 05c。

本阶段不增加用户图表模板、持仓叠加线、缓存、Docker 部署或 100% 完成标记。完成后停止。
```

## 阶段验收

- Web 日/周/月线切换可用。
- 首页、选股、持仓和历史入口使用 canonical code。
- 私有持仓字段未进入公共图表 API。
- 手机 Web 和 Desktop 适用构建/验证完成，P4 仍为进行中。
