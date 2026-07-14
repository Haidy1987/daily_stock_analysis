# Cursor 提词 04c：完整技术指标副图

## 前置条件

阶段 04b 已完成，K 线、BOLL、成交量、缩放和共享时间轴经过测试与视觉检查。

## 提词正文

```text
你正在维护 daily_stock_analysis 项目。先读取 AGENTS.md、计算契约、页面结构设计、阶段 04b 图表实现和技术图表 API 类型。

本阶段目标：在现有 ECharts 容器和 option builder 上增加 MACD、RSI、KDJ、CCI、BIAS，完成所有本期指标的显示、开关、共享 tooltip 和时间轴联动。不要处理移动端最终布局、完整 i18n 或周/月线。

实施前：

1. 检查工作区状态，保留已有改动，不执行 reset、checkout、stash、commit、push 或 tag。
2. 确认只扩展现有 TechnicalChart/option builder，不为每个指标创建独立 ECharts 实例。
3. 核对 API nullable 字段和计算契约，不在前端重算指标。

必须实现：

1. 面板模型
   - 主图和所有副图使用同一日期数组。
   - 通过统一 panel 配置计算 grid、xAxis、yAxis 和 series 索引，避免手写索引在开关面板后错位。
   - 指标关闭时移除对应 grid/axis/series；再次打开时恢复，不残留事件或缩放状态。

2. MACD
   - DIF、DEA 折线，BAR 柱和零轴。
   - BAR 正负颜色与图例清晰，不把 MACD BAR 再乘 2。

3. RSI
   - RSI6、RSI12、RSI24。
   - yAxis 建议 0～100，显示 30/70 参考线。
   - null 区间断线，不补成 50。

4. KDJ
   - K、D、J 折线，显示 20/80 参考线。
   - J 可以超出 0～100 时，yAxis 不强行裁剪有效值；参考线仍可见。

5. CCI
   - CCI 折线、零轴、+100/-100 参考线。
   - 极值不能把其他面板坐标轴污染；每个面板使用独立 yAxis。

6. BIAS
   - BIAS5、BIAS10、BIAS20 和零轴。
   - 百分比 tooltip 保留合理精度，不重复乘 100。

7. 指标开关与 URL
   - 工具栏提供 MA、BOLL、成交量、MACD、RSI、KDJ、CCI、BIAS 开关。
   - PC 默认主图+MA+BOLL、成交量、MACD、RSI；KDJ/CCI/BIAS 默认关闭但必须可用。
   - indicators 参数与开关双向同步；浏览器前进/后退恢复面板。
   - support_resistance 与主图标记单独控制或跟随主图默认开启，行为写入测试。

8. 共享 tooltip 和 dataZoom
   - 同一日期展示 OHLC、MA、BOLL、volume、MACD、RSI、KDJ、CCI、BIAS 当前可用值。
   - 只显示已启用指标；null 显示 `--`，不显示 0。
   - dataZoom、axisPointer 覆盖所有当前可见 xAxis。
   - 切换指标后 zoom 范围尽量保持，不能跳回错误日期。

测试要求：

- 分指标测试 series 类型、字段映射、参考线和 yAxis。
- 测试动态面板索引：关闭中间面板后，后续面板 axisIndex 仍正确。
- 测试完整指标同时开启、全部可选副图关闭和 API 某一指标全 null。
- 测试 URL indicators 恢复、开关更新 URL、浏览器后退恢复。
- 测试 tooltip 不重复计算、不把 null 转 0、不把百分比重复乘 100。
- 运行 04a/04b 所有页面和 option builder 回归。

建议验证命令：

cd apps/dsa-web
npm run lint
npm run test
npm run build

视觉检查：PC 宽屏下逐一打开 MACD、RSI、KDJ、CCI、BIAS，检查时间轴、缩放、tooltip、参考线和颜色。临时截图不提交仓库。

文档和进度：

- 更新页面结构设计中的最终面板和默认开关。
- 更新 docs/CHANGELOG.md。
- 更新进度表：P3 保持进行中，记录全部指标可用、测试结果和下一节点 04d。

本阶段不要增加第二个图表库、前端指标公式、用户持久化模板、周/月线或跨页面入口。完成后停止。
```

## 阶段验收

- MACD、RSI、KDJ、CCI、BIAS 全部可展示和切换。
- 所有面板共享日期、缩放、十字光标和 tooltip。
- 动态面板索引和 null 行为有真实测试。
- P3 仍为进行中。
