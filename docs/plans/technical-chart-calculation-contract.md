# 技术图表计算与 API 契约（technical-v1）

> 状态：P0～P4 已完成（2026-07-14）
> 版本：`calculation_version = "technical-v1"`
> 范围：口径、完整指标引擎、日/周/月线 API 与 Web 页面；不含旧 `/history` 周/月修复。

本文档是技术图表后续 P1～P4 的实现真源。与现有 `history` 接口、报告分析 `TrendAnalysisResult`、告警 `alert_indicators` 的兼容策略见第 7 节。

## 1. 输入数据契约

### 1.1 字段

计算引擎输入为按交易日排列的 K 线表，字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `date` | date / datetime（日历日） | 是 | 交易日；序列化对外为 `YYYY-MM-DD` |
| `open` / `high` / `low` / `close` | float | 是 | OHLC |
| `volume` | float | 是 | 成交量（股） |
| `amount` | float \| null | 否 | 成交额 |
| `change_percent` | float \| null | 否 | 涨跌幅（%）；来源侧常为 `pct_chg` |

来源对齐：`data_provider.base.STANDARD_COLUMNS` 与现有 history `KLineData`。

### 1.2 清洗规则

1. `date` 转为日期并按**升序**排序。
2. OHLC、`volume`、`amount`、`change_percent` 数值化；非法值变 NaN。
3. 丢弃 `close` 或 `volume` 为空的行（与 `_clean_data` 一致）。
4. **同一交易日多行**：保留最后一行（后写覆盖），再重置索引。现有 `_clean_data` 未显式去重；图表引擎必须补上，避免滚动窗口重复计权。
5. 计算前不再依赖 `data_provider._calculate_indicators` 产出的 `ma*` / `volume_ratio`（口径与图表不一致，见第 7 节）。

### 1.3 预热与展示窗口

| 概念 | 含义 |
| --- | --- |
| `days` / `range_days` | 请求的**展示** K 线根数（用户可见） |
| 预热窗口 | 为使展示窗口内指标尽快有效，服务端额外向前多取历史 bar 再计算，**响应 `items` 只保留展示窗口** |

建议预热长度（实现可用常量，不对外暴露）：

```text
warmup_bars = max(60, 26 + 9, 24, 20, 14, 9)  # ≥ MACD / RSI24 / BOLL / CCI / KDJ 等
calculation_bars = days + warmup_bars
```

首版 `days`：默认 **120**，允许 **60～250**；契约预留 **500** 上限，05c 测量后**暂不开放**（前后端仍校验 ≤250）。

### 1.4 结果缓存（05c 决策）

- **不新增**技术指标结果缓存；继续复用行情数据源既有缓存，按请求实时计算。
- 依据（mock 取数、本机 2026-07-14，min of 5 runs）：daily 120/250 点约 **22/34 ms**；weekly 120/250 约 **50/80 ms**；monthly 120/250 约 **41/68 ms**（不含真实网络）。
- 未达需引入结果缓存的阈值；如未来开放 500 点或真实 P95 超标，再评估 TTL/键隔离方案（键须含 `stock_code+period+days+indicators+calculation_version+as_of`）。

## 2. 指标公式与空值规则

以下均在**聚合后的目标周期 K 线**上计算（日线直接算；周/月先聚合再算）。不足完整窗口的位置一律 JSON `null`，禁止用 `0` / `50` 伪装有效点。

### 2.1 MA（SMA）

- 公式：`SMA(close, n)`，`n ∈ {5, 10, 20}`
- 完整窗口不足：`null`
- **不使用** `min_periods=1`（与 `data_provider._calculate_indicators` 不同）
- 字段：`ma5`、`ma10`、`ma20`
- 首个有效点：第 `n` 根 bar（1-based）

图表**不输出** MA60。报告分析中「数据不足时 MA60=MA20」仅保留在适配层，不得进入图表契约。

### 2.2 MACD

- `EMA12 = ewm(close, span=12, adjust=False)`
- `EMA26 = ewm(close, span=26, adjust=False)`
- `DIF = EMA12 - EMA26`
- `DEA = ewm(DIF, span=9, adjust=False)`
- `MACD_BAR = (DIF - DEA) * 2`（沿用 `StockTrendAnalyzer`）
- 字段：`macd_dif`、`macd_dea`、`macd_bar`
- 实现上 EMA 从序列起点即可产出数值；**对外有效性**：自第 26 根 bar 起视为可展示（此前可统一为 `null`，避免误导用户）。单测需固定该截断规则。

### 2.3 RSI（Wilder / SMMA）

- 周期：6 / 12 / 24
- `delta = close.diff()`；`gain` / `loss` 分离
- `avg_gain = ewm(gain, alpha=1/period, adjust=False)`（同 `avg_loss`）
- `RS = avg_gain / avg_loss`；`RSI = 100 - 100/(1+RS)`
- `avg_loss == 0` 且存在上涨：RSI = 100；双零：RSI = `null`（或实现为 50 仅限内部一瞬，**不得**写入图表序列）
- **图表禁止 `fillna(50)`**：预热不足区间为 `null`
- 字段：`rsi6`、`rsi12`、`rsi24`
- 报告 / 告警现有 `fillna(50)` 通过适配层保留，不改变 `TrendAnalysisResult` 对外语义

### 2.4 BOLL

- 周期 20，标准差倍数 2，`ddof=0`（总体标准差）
- `mid = SMA(close, 20)`
- `std = close.rolling(20).std(ddof=0)`
- `upper = mid + 2 * std`；`lower = mid - 2 * std`
- `bandwidth = (upper - lower) / mid * 100`；`mid == 0` 或不足窗口 → `null`
- `position = (close - lower) / (upper - lower) * 100`；**不裁剪**到 0～100；`upper == lower` → `null`
- 字段：`boll_upper`、`boll_mid`、`boll_lower`、`boll_bandwidth`、`boll_position`
- 仓库内无既有 BOLL 实现；本契约为唯一真源

### 2.5 KDJ

参数与 `alert_indicators._evaluate_kdj` 默认一致：RSV 窗口 **9**，K/D 平滑 **3 / 3**。

- `LLV = low.rolling(9).min()`；`HHV = high.rolling(9).max()`
- `RSV = (close - LLV) / (HHV - LLV) * 100`；`HHV == LLV` 时 **RSV = 50**
- 递推（等价于 `α=1/3` 平滑）：
  - `K_t = (2/3) * K_{t-1} + (1/3) * RSV_t`
  - `D_t = (2/3) * D_{t-1} + (1/3) * K_t`
  - **首个可计算 RSV 处**：`K_0 = D_0 = 50`，再递推
- `J = 3 * K - 2 * D`
- 字段：`kdj_k`、`kdj_d`、`kdj_j`
- RSV 窗口不足：三者均为 `null`
- 告警模块当前用 `ewm` 且不算 J；图表补 J，并用显式初值 50 固定序列起点。P1 应加固定样本，避免与告警交叉判定产生不可追溯漂移；告警交叉语义不要求与图表 tip 数值逐点字节一致，但参数与 RSV 除零规则必须一致。

### 2.6 CCI

- 周期 14（与告警默认一致）
- `TP = (high + low + close) / 3`
- `TP_MA = SMA(TP, 14)`
- `MD = mean(|TP - TP_MA|)` over 同窗口（平均绝对偏差）
- `CCI = (TP - TP_MA) / (0.015 * MD)`；`MD == 0` → `null`
- 字段：`cci`
- 窗口不足 → `null`

### 2.7 BIAS

- 依赖完整窗口 MA5/10/20
- `bias_n = (close - MA_n) / MA_n * 100`
- `MA_n` 为 `null` 或 `0` → `bias_n = null`（**不**像报告层把无法计算时保持 0）
- 字段：`bias5`、`bias10`、`bias20`

### 2.8 量比与量价状态

量比（对齐 `StockTrendAnalyzer._analyze_volume`，**不用** provider 的 `rolling(5).mean().shift(1).fillna(1.0)`）：

```text
volume_ratio[t] = volume[t] / mean(volume[t-5 : t])   # 前 5 根，不含当日
```

- 前 5 根均量不存在或均量为 0 → `null`
- 字段：`volume_ratio`

量价状态（机读枚举与展示文案分离）：

| `volume_status`（API） | 条件 | 建议中文文案 |
| --- | --- | --- |
| `heavy_volume_up` | ratio ≥ 1.5 且 close > prev_close | 放量上涨 |
| `heavy_volume_down` | ratio ≥ 1.5 且 close ≤ prev_close | 放量下跌 |
| `shrink_volume_up` | ratio ≤ 0.7 且 close > prev_close | 缩量上涨 |
| `shrink_volume_down` | ratio ≤ 0.7 且 close ≤ prev_close | 缩量回调 |
| `normal` | 其余（含 ratio 为 null 时不写状态，或标 `null`） | 量能正常 |

阈值：缩量 **0.7**、放量 **1.5**。价格比较用相邻已展示周期 K 线收盘价；无前一根时 `volume_status = null`。

说明：报告 `VolumeStatus` 现为中文 enum 值；图表 API **固定英文机读码**，前端 i18n 映射文案，避免中英混用破坏客户端契约。

### 2.9 支撑压力（仅 summary，无 look-ahead）

默认窗口：**请求结束日（展示序列最后一根）之前（含当日）最近 20 根聚合后 K 线**。

候选：

- 支撑：当前 `close` **以下**的有效 `ma5` / `ma10` / `ma20`，以及窗口内近期低点
- 压力：当前 `close` **以上**的有效 `ma5` / `ma10` / `ma20`，以及窗口内近期高点

合并：相对价差 ≤ **0.5%** 的水平位合并为一条，保留来源标签（可拼接）。

返回结构（每项）：

```json
{
  "price": 1000.0,
  "label": "MA20",
  "date": "2026-07-01",
  "source": "ma20"
}
```

- `recent_high` / `recent_low`：`{ "price": number, "date": "YYYY-MM-DD" }`，取自上述 20 根窗口的 high max / low min 及**首次出现该极值的日期**
- 禁止使用结束日之后的 bar；禁止用整段未来序列回刷历史每日标线（v1 只在 `summary` 给出相对最新收盘的水平位）

与报告层差异：报告使用约 **2%** MA 触碰容忍度且逻辑偏买点；图表改用 **0.5% 合并** + MA 相对现价上下分侧，二者不得直接共用未经适配的结果列表。

## 3. 周线 / 月线聚合口径（已实现，05a）

在日线清洗后的序列上聚合：

| 字段 | 周线 / 月线 |
| --- | --- |
| `open` | 周期内第一根交易日 open |
| `high` | 周期内最高 high |
| `low` | 周期内最低 low |
| `close` | 周期内最后一根 close |
| `volume` / `amount` | 求和（`min_count=1`；全为 null 则 null） |
| `date` | 周期内**最后一个交易日** |
| `change_percent` | 相对**上一根聚合 K 线** close 的涨跌幅；首根可为 null |

周线边界：按自然周周一至周日分组（pandas `W-SUN`）；月线按年-月分组。
**所有指标在聚合后的 K 线上重新计算**，禁止对日线指标再做二次平均。

实现锚点：[`src/services/ohlcv_aggregation.py`](../../src/services/ohlcv_aggregation.py) → `TechnicalChartService`。
API 已开放 `period=daily|weekly|monthly`。`calculation_version` 仍为 `technical-v1`（指标公式未变，仅启用聚合入口）。

**旧 `/history` 决策（05a）**：不复用聚合函数；`StockService.get_history_data` 仍仅支持 `daily`（422/`ValueError`）。技术图表不得依赖旧 history 做周/月线。

取数：始终拉日线；周/月按 ` (days + 60) * 5|22 ` 估算日线根数，软上限 `MAX_DAILY_FETCH_BARS=5000`，不足则 `partial` + warning（`daily_history_fetch_capped` / `history_shorter_than_display_days`），不伪造周期。

## 4. API 契约

### 4.1 端点

```text
GET /api/v1/stocks/{stock_code}/technical-chart
```

### 4.2 查询参数

| 参数 | 必填 | 取值 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `period` | 否 | `daily` / `weekly` / `monthly` | `daily` | 05a 已开放周/月 |
| `days` | 否 | 60～250 | 120 | 目标周期 K 线根数；最终可扩到 500 |
| `indicators` | 否 | 见下 | 完整集 | 逗号分隔，去空格，大小写不敏感 |

`indicators` 合法 token：

`ma`、`volume`、`macd`、`rsi`、`boll`、`kdj`、`cci`、`bias`、`support_resistance`

默认完整集：

```text
ma,volume,macd,rsi,boll,kdj,cci,bias,support_resistance
```

OHLCV 始终返回。未请求的指标组：**从 `items` 中省略对应字段**（非填 null），以减小载荷；`summary` 中支撑压力仅在包含 `support_resistance` 时返回。

非法 token 或非法 `days` / `period`：HTTP **422**（或框架校验 **400**），不返回伪装成功体。

### 4.3 成功响应形状

```json
{
  "stock_code": "600519",
  "stock_name": "贵州茅台",
  "period": "daily",
  "range_days": 120,
  "calculation_version": "technical-v1",
  "data_status": "available",
  "data_source": "cache_or_provider_tag",
  "updated_at": "2026-07-14T12:00:00+08:00",
  "items": [],
  "summary": {
    "latest_close": 1010.0,
    "latest_change_percent": 1.2,
    "volume_status": "normal",
    "volume_ratio": 1.35,
    "support_levels": [],
    "resistance_levels": [],
    "recent_high": { "price": 1050.0, "date": "2026-06-20" },
    "recent_low": { "price": 980.0, "date": "2026-06-05" }
  },
  "warnings": []
}
```

- `data_source` / `updated_at`：低敏元数据；**禁止**密钥、堆栈、内部 URL。
- `items`：日期升序；每项必含 OHLCV + `change_percent`；指标字段按第 2 节命名。
- `warnings`：可展示的字符串列表（数据不足、部分指标缺失、预热不足等）。

### 4.4 `data_status`

| 值 | 含义 | HTTP |
| --- | --- | --- |
| `available` | 有展示数据，请求的指标在有效区间可计算 | 200 |
| `partial` | 有 K 线，但部分指标因历史过短等多为 null | 200 |
| `empty` | 合法请求，确认无历史记录 | 200，`items=[]`，带 warning |
| `source_unavailable` | 全部数据源不可用或上游失败 | **503**（或项目统一 upstream unavailable）；**不得**伪装成 `empty` |

与现有 history 差异：`StockService.get_history_data` 在空数据与异常时都返回 `data: []`。技术图表**必须**区分 `empty` 与 `source_unavailable`，不得沿用吞错为空数组的行为。

### 4.5 错误语义汇总

| 场景 | HTTP | 说明 |
| --- | --- | --- |
| 股票代码格式非法 / 参数非法 | 400 或 422 | 校验失败 |
| `period` 非 daily（首版） | 422 | `unsupported_period` |
| 合法代码但无行情 | 200 | `data_status=empty` |
| 上游全失败 | 503 | `source_unavailable` 或统一错误体 |
| 部分指标无法计算 | 200 | `partial` + null/省略 + `warnings` |

认证：公共行情与指标**不绑定 `user_id`**；是否需登录沿用现有 Auth / 中间件全局策略。

## 5. 完整 `items[]` 字段类型（请求完整 indicators 时）

| 字段 | 类型 | 可 null |
| --- | --- | --- |
| `date` | string | 否 |
| `open`/`high`/`low`/`close` | number | 否（清洗后） |
| `volume` | number | 否 |
| `amount` | number | 是 |
| `change_percent` | number | 是 |
| `ma5`/`ma10`/`ma20` | number | 是 |
| `volume_ratio` | number | 是 |
| `volume_status` | string enum | 是 |
| `macd_dif`/`macd_dea`/`macd_bar` | number | 是 |
| `rsi6`/`rsi12`/`rsi24` | number | 是 |
| `boll_upper`/`boll_mid`/`boll_lower`/`boll_bandwidth`/`boll_position` | number | 是 |
| `kdj_k`/`kdj_d`/`kdj_j` | number | 是 |
| `cci` | number | 是 |
| `bias5`/`bias10`/`bias20` | number | 是 |

前端**禁止**自行计算技术指标；只做渲染与显隐。

## 6. 示例响应（节选）

```json
{
  "stock_code": "600519",
  "stock_name": "贵州茅台",
  "period": "daily",
  "range_days": 120,
  "calculation_version": "technical-v1",
  "data_status": "partial",
  "data_source": "akshare",
  "updated_at": "2026-07-14T15:00:00+08:00",
  "items": [
    {
      "date": "2026-01-05",
      "open": 1400.0,
      "high": 1410.0,
      "low": 1390.0,
      "close": 1405.0,
      "volume": 1000000,
      "amount": null,
      "change_percent": 0.5,
      "ma5": null,
      "ma10": null,
      "ma20": null,
      "volume_ratio": null,
      "volume_status": null,
      "macd_dif": null,
      "macd_dea": null,
      "macd_bar": null,
      "rsi6": null,
      "rsi12": null,
      "rsi24": null,
      "boll_upper": null,
      "boll_mid": null,
      "boll_lower": null,
      "boll_bandwidth": null,
      "boll_position": null,
      "kdj_k": null,
      "kdj_d": null,
      "kdj_j": null,
      "cci": null,
      "bias5": null,
      "bias10": null,
      "bias20": null
    }
  ],
  "summary": {
    "latest_close": 1405.0,
    "latest_change_percent": 0.5,
    "volume_status": null,
    "volume_ratio": null,
    "support_levels": [],
    "resistance_levels": [],
    "recent_high": { "price": 1410.0, "date": "2026-01-05" },
    "recent_low": { "price": 1390.0, "date": "2026-01-05" }
  },
  "warnings": ["history_too_short_for_full_indicators"]
}
```

## 7. 兼容与冲突处理

| 冲突点 | 现状 | 图表 technical-v1 | 兼容策略 |
| --- | --- | --- | --- |
| MA 完整窗口 | analyzer 完整窗口；provider `min_periods=1` | 完整窗口 + null | 图表与后续共享引擎用完整窗口；provider 内部列不动 |
| RSI `fillna(50)` | analyzer / alerts | 图表序列不用 50 填 | 报告适配层可继续填 50，保持 `TrendAnalysisResult` |
| 量比 | analyzer 前 5 根不含当日；provider shift+fillna(1) | 同 analyzer | 图表与报告抽取时以 analyzer 为准 |
| MACD 柱 ×2 | analyzer 有；alerts 交叉用 DIF−DEA | 柱 ×2 | 告警交叉逻辑可继续用 delta，不强制改 |
| KDJ / CCI | 仅 alerts；无 J / 无 BOLL | 补 J + 新 BOLL | 禁止平行第二套参数；抽共享函数时 alerts 逐步复用 |
| 支撑压力 | 报告 2% 触碰买点逻辑 | 0.5% 合并 + 上下分侧 | **不得**直接复用报告列表；需要独立函数 |
| history 空/错 | 均变 `[]` | empty vs 503 | **不修改** history 响应；仅新接口区分 |
| DB / user_id | 多用户私有业务隔离 | 公共行情指标不绑 user_id | 无新业务表；复用行情缓存按请求计算 |

**硬约束：**

1. 不修改 `GET /stocks/{stock_code}/history` 响应结构。
2. 不为技术指标新增数据库表（第一版）。
3. 抽取共享引擎时，若与 `TrendAnalysisResult` 语义冲突，通过适配层转换；回归测试必须覆盖报告字段行为不静默漂移。

## 8. 已落地 / 建议源码与测试

### 8.1 阶段 01～02 已落地（完整计算层 / P1）

| 路径 | 职责 |
| --- | --- |
| `src/services/technical_indicators.py` | `normalize_ohlcv_frame`、`calculate_technical_indicators`（完整组）、`calculate_kdj_series`、`calculate_cci_series`、`build_support_resistance_summary`、`wilder_rsi`、`compute_report_indicator_frame` |
| `src/services/alert_indicators.py` | KDJ/CCI 边缘穿越消费共享序列 |
| `src/stock_analyzer.py` | MA/MACD/RSI 走共享引擎；报告 RSI `fillna(50)`；MA60 适配保留 |
| `tests/test_technical_indicators.py` | 固定样本：MA/MACD/RSI/BIAS/量价/BOLL/KDJ/CCI/支撑压力/告警兼容 |

公开接口（最终采用名）：

- `normalize_ohlcv_frame(df) -> DataFrame`
- `calculate_technical_indicators(df, indicators=None, *, normalize=True) -> DataFrame`
- `build_support_resistance_summary(df, *, as_of_index=None, window=20) -> Dict`
- `calculate_kdj_series(...)` / `calculate_cci_series(...)`
- 列名 snake_case：见 `CORE_INDICATOR_GROUPS`（含 `boll_*` / `kdj_*` / `cci`；`support_resistance` 仅 summary）

指标组：`ma`、`macd`、`rsi`、`bias`、`volume`、`boll`、`kdj`、`cci`、`support_resistance`。

### 8.2 后续阶段建议新增

| 路径 | 职责 |
| --- | --- |
| `src/services/technical_chart_service.py` | 拉数、预热裁剪、周期聚合入口、`data_status` 映射 |
| `api/v1/schemas/technical_chart.py` | 请求响应 Pydantic 模型 |
| `api/v1/endpoints/` 内 technical-chart 路由 | HTTP 层 |
| `tests/test_technical_chart_service.py` / `tests/test_technical_chart_api.py` | 服务与 API |
| `apps/dsa-web/src/api/technicalChart.ts` 等 | 客户端（P3） |

### 8.3 建议修改（后续）

| 路径 | 说明 |
| --- | --- |
| `api/v1/endpoints/stocks.py` / `router` | 注册新路由，不改 history schema |
| `apps/dsa-web` 导航 / i18n | `/technical-chart` 入口（P3） |
| `.env.example` / 部署文档 | 仅当出现缓存 TTL 等新配置时同步 |

## 9. 固定样本测试要求（给 P1）

至少覆盖：

1. 长度 < 5 / < 9 / < 14 / < 20 / < 26 时各指标 null 位置。
2. MACD 柱 = `(DIF - DEA) * 2` 数值回归。
3. RSI 不足区间不得出现填 50。
4. BOLL `ddof=0`；分母为 0 时 bandwidth/position 为 null。
5. KDJ high==low → RSV 50；J=3K-2D。
6. CCI MD=0 → null。
7. 量比分母不含当日。
8. 支撑压力无 look-ahead；0.5% 合并。
9. 与 `alert_indicators` 同参数下 KDJ/CCI 序列可对齐到约定容差（文档化容差）。

## 10. 与阶段文档的一致性

- 必达指标：K 线 OHLCV、MA、MACD、RSI、BOLL、KDJ、CCI、BIAS、量比/量价、支撑压力 —— 与 [README](../cursor/technical-chart/README.md) 完成定义一致。
- 05a 已开放 `period=daily|weekly|monthly`；旧 `/history` 仍仅 daily。
- 05b 已开放 Web 周期切换与跨页入口；Desktop 复用 Web 路由。
- **05c 完成**：性能测量通过、不新增结果缓存、`days` 上限保持 250；项目进度 **100%**。

### 实现锚点（P2 + 05a + 05c）

- Endpoint：`GET /api/v1/stocks/{stock_code}/technical-chart`（[`api/v1/endpoints/stocks.py`](../../api/v1/endpoints/stocks.py)）
- Schema：[`api/v1/schemas/technical_chart.py`](../../api/v1/schemas/technical_chart.py)
- Aggregation：[`src/services/ohlcv_aggregation.py`](../../src/services/ohlcv_aggregation.py)
- Service：[`src/services/technical_chart_service.py`](../../src/services/technical_chart_service.py)（目标周期 `days + WARMUP_BARS(60)`；周/月按估测算日线预取，上限 5000；**不缓存指标结果**）
- 计算耗时基线（mock 行情，2026-07-14）：daily 120/250 ≈ 22/34 ms；weekly 120/250 ≈ 50/80 ms；monthly 120/250 ≈ 41/68 ms
- Web 拆包（gzip）：`vendor-echarts` ≈ 203.5 kB（lazy）；`TechnicalChartPage` ≈ 9.1 kB；`index`/`HomePage` 初始 chunk **不含** ECharts

### 回滚方案（05c）

1. 移除侧边栏与 `/technical-chart` 路由；删除跨页「查看技术图表」入口。
2. 停用或回退 `GET .../technical-chart`（可保留后端模块但返回 404/移除路由注册）。
3. 回退 `technical_chart_service` / `ohlcv_aggregation` 与 Web `technical-chart` 组件目录。
4. 恢复旧 `/history` 行为（仍仅 daily，无额外动作）。
5. 卸载 `echarts` 依赖并移除 `vendor-echarts` manual chunk。
6. **不删除**用户业务数据；本项目未新增技术指标数据库表。

---

**文档回滚**：删除或还原本文件相关 05c 段落，并将进度表 P4 退回「进行中」。
