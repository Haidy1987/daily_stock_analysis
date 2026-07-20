# Cursor 提词 04d：响应式、国际化与 Web 阶段验收

## 前置条件

阶段 04a～04c 已完成，daily 完整指标在 PC 宽屏可用，前端测试和 build 当前通过。

## 提词正文

```text
你正在维护 daily_stock_analysis 项目。先读取 AGENTS.md、页面结构设计、导航规划、阶段 04a～04c 代码和交付记录。

本阶段目标：完成技术图表页面的手机响应式、深浅主题、中英文、可访问性、Web 回归和视觉验收。只有全部通过后才能把 P3 标记为完成。不要实现周/月线或跨页面入口。

实施前：

1. 检查工作区状态，保留已有改动，不执行 reset、checkout、stash、commit、push 或 tag。
2. 复核项目现有 Tailwind 断点、Shell 移动抽屉、ThemeContext/next-themes 和 UiLanguageContext。
3. 不通过复制一套移动端图表实现响应式；复用同一 TechnicalChart 和 option builder。

必须实现：

1. 手机布局
   - 股票搜索、摘要和工具栏在窄屏可换行或横向滚动。
   - 主图保持可操作高度，支持触控 dataZoom。
   - 手机默认显示主图、成交量和一个副图；MACD/RSI/KDJ/CCI/BIAS 使用单选或折叠面板切换。
   - tooltip 使用紧凑布局或底部信息区，不能完全遮住 K 线。
   - 菜单点击后关闭移动导航抽屉。

2. PC/Mac 布局
   - 宽屏允许多个副图同时展开，页面和图表高度不产生不可控嵌套滚动。
   - 折叠侧边栏、窗口 resize 和浏览器缩放时 ECharts 正确 resize。

3. 深浅主题
   - 背景、坐标轴、网格、tooltip、markLine、文字和涨跌色读取项目主题变量或集中映射。
   - 主题切换后更新 option，不重建错误实例或丢失 zoom。
   - 颜色之外使用线型、标签或图例区分指标，满足基本可访问性。

4. 国际化
   - 补齐中英文：导航、页面说明、股票摘要、周期、范围、指标名称、状态、错误、tooltip 标签、数据说明和免责声明。
   - UiTextKey 中英文集合保持一致，不遗留硬编码中文/英文。
   - 股票名称、代码和数值不翻译；技术指标缩写保持通用写法。

5. 可访问性
   - 页面标题层级、导航 aria-label、股票输入标签、指标按钮 pressed 状态、重试按钮和图表可访问名称完整。
   - 键盘可操作股票搜索、范围和指标切换。
   - 图表提供当前股票/周期/数据范围的文本摘要，不能只依赖 canvas。

6. 测试与视觉证据
   - 完成导航、RouteBoundary、页面状态、URL、所有指标、主题和语言测试。
   - 使用 viewport 测试或 Playwright smoke 覆盖 PC 和手机关键路径；沿用仓库现有 smoke 能力。
   - 至少检查浅色/深色、中文/英文、PC 宽屏/手机窄屏。
   - 页面截图放 PR 描述、评论或临时验收位置，不提交一次性图片。

建议验证命令：

cd apps/dsa-web
npm ci
npm run lint
npm run test
npm run build

如现有 Playwright 环境可用：

npm run test:smoke

在线数据源不可用时，可以使用已实现 API 的确定性测试数据完成布局 smoke，但必须另行记录真实 API 未验证，不得声称真实数据联调通过。

文档和进度：

- 更新技术图表页面、导航和使用说明。
- 更新 docs/CHANGELOG.md。
- 更新进度表：只有 daily 页面、全部指标、响应式、主题、i18n、测试和视觉证据全部通过后，才把 P3 标记为完成；记录日期、命令、证据、风险和 P4 前置条件。

本阶段不要启用 weekly/monthly，不修改后端聚合，不增加首页/选股/持仓跳转，不构建独立 Desktop 图表。交付后停止。
```

## 阶段验收

- PC/Mac 和手机浏览器共享一套可用图表实现。
- 深浅主题、中英文和基本可访问性通过。
- Web lint、test、build 以及适用 smoke 通过。
- P3 有证据地标记为完成。
