# Cursor 提词 04b：K 线、BOLL 与成交量图表

## 前置条件

阶段 04a 已完成，页面能稳定取得 daily 技术图表响应，并能处理各类状态。

## 提词正文

```text
你正在维护 daily_stock_analysis 项目。先读取 AGENTS.md、页面结构设计、计算契约、阶段 03 API 交付和阶段 04a 页面代码。

本阶段目标：固定并接入 Apache ECharts，只实现 K 线主图、MA、BOLL、支撑压力、近期高低点和成交量副图。不要实现 MACD、RSI、KDJ、CCI、BIAS。

图表技术选型已固定：

- 使用 `echarts` 本体，不引入 echarts-for-react、Lightweight Charts 或第二套技术图表库。
- 优先使用 `echarts/core` 模块化注册，只注册 CandlestickChart、LineChart、BarChart、GridComponent、TooltipComponent、DataZoomComponent、AxisPointerComponent、MarkLineComponent、MarkPointComponent、LegendComponent 和 CanvasRenderer 等实际需要模块。
- 图表代码只由 lazy TechnicalChartPage 路由加载；不要在 App、Shell 或首页静态导入 ECharts。
- 现有 Recharts 继续服务已有页面，不在本阶段迁移或删除。

实施前：

1. 检查工作区状态，保留已有改动，不执行 reset、checkout、stash、commit、push 或 tag。
2. 检查 package.json/package-lock.json 和实际 Node/npm 版本。
3. 如果缺少 echarts，使用 `npm install echarts` 更新 package.json 和 lockfile；需要网络时按环境要求请求授权。
4. 记录新增依赖版本、许可证和 build 前后包体积。

必须实现：

1. ECharts 生命周期封装
   - 创建单一图表容器组件，mount 时 init，option 变化时 setOption，resize 时 resize，unmount 时 dispose。
   - 避免 StrictMode 下重复实例和事件泄漏。
   - ResizeObserver 不可用时提供安全降级。
   - 不把完整 ECharts 实例放入全局 store。

2. 纯 option builder
   - 建立可单元测试的 `buildTechnicalChartOption` 或等价纯函数。
   - 输入为已转换的 TechnicalChartResponse 和可见指标配置。
   - 日期、K 线、MA、BOLL、成交量数组必须按同一 items 顺序生成。
   - null 保持 null，不使用 0 填充。

3. K 线主图
   - candlestick 数据顺序固定为 ECharts 要求的 open/close/low/high，并用测试锁定，避免 high/low 颠倒。
   - 红涨绿跌沿用项目现有变量，不写死与主题冲突的颜色。
   - 显示 MA5、MA10、MA20。
   - 显示 BOLL upper/mid/lower；bandwidth 和 position 进入 tooltip/图例，不新增无需求副图。

4. 支撑压力和近期高低点
   - support/resistance 使用 markLine 或等价水平标记。
   - recent_high/recent_low 使用 markPoint，显示价格和日期。
   - 相近水平位的标签避免重叠；数据缺失时不创建无效 mark。

5. 成交量副图
   - 与 K 线共享 category xAxis 和 dataZoom。
   - 柱颜色与对应 K 线涨跌一致。
   - tooltip 显示 volume、volume_ratio、volume_status。

6. 基础交互
   - inside + slider dataZoom；默认定位最近数据。
   - axisPointer/tooltip 同步主图和成交量。
   - days 和 stock 变化时完整更新 series、markLine、markPoint 和 zoom，不能残留上一只股票状态。

测试要求：

- 单元测试 option builder，不只 snapshot 整个大对象。
- 明确断言 candlestick 顺序、日期对齐、MA/BOLL null、成交量颜色、支撑压力和近期高低点映射。
- 测试空 items、部分指标缺失和切换股票后的 option 重建。
- ECharts DOM/canvas 边界可 mock，但数据映射函数必须真实运行。
- 保留并运行 04a 页面状态测试。

建议验证命令：

cd apps/dsa-web
npm run lint
npm run test
npm run build

视觉检查：至少使用一只有足够历史数据的真实股票检查 K 线方向、MA/BOLL、成交量、缩放和 tooltip。截图作为临时验收证据，不提交仓库。

文档和进度：

- 更新页面设计中的最终 ECharts 方案和包体积记录。
- 更新 docs/CHANGELOG.md。
- 更新进度表：P3 保持进行中，记录 04b 测试、视觉证据和下一节点 04c。

交付时说明依赖、组件、option 映射、构建体积、测试、截图、风险和回滚方式。完成后停止。
```

## 阶段验收

- ECharts 只在技术图表路由加载。
- K 线、MA、BOLL、支撑压力、近期高低点和成交量正确联动。
- 数据映射测试和前端 build 通过。
- P3 仍为进行中。
