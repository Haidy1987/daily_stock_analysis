# Cursor 提词 04a：页面骨架、导航与股票上下文

## 前置条件

阶段 03 日线技术图表 API 已完成并通过真实股票 smoke。接口字段和状态语义已经固定。

## 提词正文

```text
你正在维护 daily_stock_analysis 项目。先读取 AGENTS.md、技术图表需求、页面结构设计、导航规划、计算契约、进度表和阶段 03 交付记录。

本阶段目标：只完成 `/technical-chart` 页面骨架、一级导航、技术图表 API client、股票选择、URL 状态和 loading/error/empty/partial 状态。不要引入 ECharts，不要绘制任何图表。

实施前：

1. 检查工作区状态，保留已有改动，不执行 reset、checkout、stash、commit、push 或 tag。
2. 阅读 apps/dsa-web/src/App.tsx、components/layout/SidebarNav.tsx、Shell、RouteBoundary、AuthContext、UiLanguageContext、uiText.ts 和对应测试。
3. 阅读并复用 apps/dsa-web/src/components/StockAutocomplete/StockAutocomplete.tsx、hooks/useStockIndex、hooks/useAutocomplete，不创建第二套股票搜索或本地股票索引。
4. 阅读 apps/dsa-web/src/api/index.ts、api/utils.ts 的 `toCamelCase` 和现有 API client 模式。

必须实现：

1. 路由与导航
   - 新增 lazy `TechnicalChartPage`，注册 `/technical-chart`。
   - SidebarNav 增加“技术图表”，位置在选股后、持仓前。
   - 菜单不依赖 AlphaSift，不设置 adminOnly；认证行为沿用全局守卫。
   - 使用当前 lucide-react 真实存在的图标；折叠导航和移动抽屉都有 aria-label、激活状态和点击关闭行为。

2. API client 与类型
   - 新增 apps/dsa-web/src/api/technicalChart.ts 和对应类型文件或就近类型定义。
   - 复用 apiClient、`toCamelCase` 和项目现有错误解析，不新增 fetch/axios 实例。
   - 定义完整 nullable 类型，但本阶段只显示摘要和状态，不绘图。
   - unknown/null/NaN 风险值不得通过 `Number(value)` 静默转 0。
   - 支持请求取消或请求序列保护，快速切换股票时旧响应不得覆盖新页面。

3. URL 状态
   - 支持 `stock`、`period`、`days`、`indicators`。
   - 本阶段 period 只接受 daily；weekly/monthly 不显示为可点击能力。
   - days 默认 120，只允许 60/120/250。
   - indicators 默认完整集合；解析非法值时回退到明确默认值并规范化 URL，不能把未知指标发送给 API。
   - 刷新、复制 URL、浏览器前进/后退都能恢复页面状态。

4. 股票上下文
   - 使用 StockAutocomplete 接收股票代码或名称，并使用其 onSubmit 返回的 canonical code。
   - 无 stock 时不请求 API，显示搜索、最近分析候选或自选股快捷入口。
   - 最近分析候选优先复用 historyApi.getStockBarList；自选股复用现有 watchlist API/Hook，不新增存储。
   - 本阶段不修改首页、选股和持仓页的跳转入口。

5. 页面骨架与状态
   - 页面标题、说明、股票搜索、当前股票摘要、日线/范围/指标占位工具栏和图表占位区域。
   - available：展示股票名称、代码、最新收盘、涨跌、数据日期和数据点数。
   - partial：展示可用摘要及 warnings。
   - empty：显示无行情数据和重新选择股票。
   - source_unavailable/网络失败：显示项目统一错误组件和重试按钮。
   - loading：使用项目现有 PageLoading/骨架模式。
   - 页面错误不能导致 Shell 或其他路由白屏。

6. i18n 最小范围
   - 补齐导航名称、页面标题、搜索、loading、empty、partial、错误和重试的中英文文案。
   - 完整指标名称和图表文案留给 04d，但新增 UiTextKey 时必须保持中英文类型完整。

测试要求：

- 更新 App、SidebarNav、Shell/RouteBoundary 受影响测试。
- 新增 TechnicalChartPage 测试：无 stock 不请求、URL stock 自动请求、成功摘要、partial、empty、失败重试、快速切换和浏览器 URL 恢复。
- 验证普通用户、管理员和认证关闭模式都能看到菜单；AlphaSift 关闭不影响技术图表。
- 验证使用 StockAutocomplete canonical code，不把显示名称直接当代码请求。

建议验证命令：

cd apps/dsa-web
npm run lint
npm run test
npm run build

本阶段不需要新增 npm 依赖。如果构建要求重新安装现有依赖，按 AGENTS.md 使用 npm ci。

文档和进度：

- 更新导航/页面文档和 docs/CHANGELOG.md。
- 更新 technical-chart-implementation-progress.html：P3 标记为进行中，记录 04a 完成内容、测试和下一节点 04b；不得标记 P3 完成。

交付时输出修改文件、路由/API client 契约、测试结果、未验证项、风险和回滚方式。完成后停止，不实现图表。
```

## 阶段验收

- 路由、一级导航、股票选择、URL 和页面状态可独立工作。
- 使用现有 API client、toCamelCase 和 StockAutocomplete。
- 没有引入图表依赖或绘图代码。
- P3 仅标记为进行中。
