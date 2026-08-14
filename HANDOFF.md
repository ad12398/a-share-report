# HANDOFF — A 股量化报告系统

## 🚨 新会话速览（2026-08-14 盘中状态）

### 系统运行中
- 5 时段报告正常生成，Windows Task Scheduler 自动触发
- 服务器：阿里云 ECS `8.148.233.129`，代码在 `C:\a-share-report\`
- 网站：`https://ad12398.github.io/a-share-report/reports/`（浅色主题已上线）
- 本地：`c:\Users\Krug2\langchain_demo\a-share-report\`，Python 用 `venv\Scripts\python.exe`（3.12.4）
- **服务器更新方式**（本地网络经常连不上 GitHub，优先从服务器操作 git）：
  ```cmd
  cd C:\a-share-report && git fetch origin main && git reset --hard origin/main
  python -B -c "import pathlib, shutil; [shutil.rmtree(d, ignore_errors=True) for d in pathlib.Path('src').rglob('__pycache__')]"
  ```

### 🚨 最优先：服务器需同步到 `83e08df`（8-14 假北向指标移除）
最新代码已推送到 GitHub `83e08df`，**但服务器可能还没同步**。上一条会话结束时刚给出同步命令。如果 14:00/15:00 报告仍出现"北向活跃度/外资占比"，说明服务器还没同步——立即执行上面的更新命令。

### 🚨 当前阻塞（用户需手动执行）
1. **注册 Tushare 学生认证** → 获取融资融券 API（`margin` 接口，学生 2000 分免费）+ 真实北向数据（`moneyflow_hsgt`）——最高优先级
2. **注册同花顺 quantapi** → `quantapi.10jqka.com.cn`（备用，可能收费）
3. **M2/社融 7 月数据更新** → `data/macro_data.json`（CPI/PPI 已更新，M2/社融央行 8 月中旬发布，8-14 仍未发布）

### 上次离开时在做
- 刚修复完 **mx-source 假北向数据事故**：mx 的"北向成交总额"查询实际返回 A 股板块成交额，8-6 以来"北向活跃度/外资占比/沪深偏好"全是假数据（占比 150-260%），由 AI 在 8-14 报告中自己发现。已删除全部假指标，外资监测退回二维（南向+外部联动），详见踩坑记录
- 8-13 至 8-14 完成：全面代码审查修复（严重 8 + 中等 10 + 轻微 14 全部修复）
- 0925 涨跌榜回填：代码正常但 8-14 首次运行因昨日摘要缺 movers 字段而跳过（旧代码保存的摘要），8-15 起自动生效
- 待验证：恒生指数进入共识引擎、外资监测二维框架首份报告
- 下一步可选：龙虎榜营业部明细 或 钉钉/微信推送

---

## 项目概述

构建全自动 A 股量化分析报告系统，交易时段生成 5 份报告，输出浅色仪表盘网页 + Word 下载，部署在 GitHub Pages。

- **仓库**: `ad12398/a-share-report`
- **网站**: `https://ad12398.github.io/a-share-report/reports/`
- **AI**: DeepSeek API (`deepseek-v4-pro`)
- **服务器**: 阿里云 ECS `8.148.233.129`，Windows Server 2022，Administrator 登录
- **代码位置**: 服务器 `C:\a-share-report\`
- **本地**: `c:\Users\Krug2\langchain_demo\a-share-report\`

---

## 🚨 核心开发规则

**新增功能不能影响已经跑通的核心流程。** `src/main.py` 的 `run()` 函数是主流程，不要在里面直接写新逻辑。正确做法：

- **新功能 = 新文件或新函数**，通过注入/回调方式接入
- 数据采集：新数据源写在 `src/data/sources/` 下，通过 `collector.py` 统一聚合
- 分析逻辑：写在 `src/analysis/` 下，在 `run()` 的固定步骤点调用
- 前端展示：新数据类型通过 `renderer.py` 传给模板，模板新增区块

---

## 已完成功能

### 核心流程
- [x] 5 时段报告生成（0925盘前/1030早盘/1130午盘/1400午后/1500收盘）
- [x] DeepSeek AI 分析（量化交易视角，中文）
- [x] 北京时间全局修复（`datetime.now(BEIJING_TZ)`）
- [x] 多源交叉校验：腾讯 + 新浪指数偏差检测
- [x] 板块数据三级降级：东财 → 新浪 → 腾讯申万行业指数
- [x] IPO 新股识别：N/C 前缀保留不删
- [x] 宏观数据 KPI 卡片 + DeepSeek 分析
- [x] 商品/汇率/全球指数
- [x] 市场概况（涨跌比/涨停跌停/换手率）
- [x] 时段边际对比系统（上一时段 + 昨日同期 delta 对比）
- [x] 历史报告统计面板（KPI + 5 张图表）
- [x] 龙虎榜数据（新浪 HTML 解析，含上榜原因）
- [x] 免责声明

### 外资监测体系（2026-08-06 重构）
- [x] **废弃 hexin 假数据**：同花顺 dayChart API 返回静态缓存，已停用
- [x] **北向活跃度**：mx-source 成交总额（沪+深合计，真实数据）
- [x] **外资占比**：北向成交/两市成交（外资定价权指标）
- [x] **沪/深偏好**：沪市占北向成交比例（价值防御 vs 成长进攻）
- [x] **南向资金**：东财 datacenter RPT_MUTUAL_QUOTA API，港股通净买入（真实数据，A股反向情绪指标）
- [x] **外部联动共识引擎**：三层信号引擎（方向×幅度加权 + 一致性评分 + 背离检测），恒生指数已加入
- [x] AI prompt 中共识引擎降级为"参考假设"，AI 有权质疑和推翻预计算

### 网页功能
- [x] 浅色仪表盘 + ECharts 图表（TradingView 风格，2026-08-06 由暗色换肤）
- [x] KPI 卡片（指数 / 商品汇率 / 宏观 / 外资监测）
- [x] 涨跌榜表格（含新股标签）
- [x] 搜索 + 归档页（客户端 JS + JSON 索引）
- [x] Word 报告下载（python-docx，HTML→docx，文件名含日期时段）
- [x] XSS 防护：`_safe_script_json()` 转义 `</` → `<\/`

### 安全
- [x] GitHub Token 不写入代码文件（读环境变量 `%GH_TOKEN%`）
- [x] Token 90 天有效，到期前需更新

### 部署 & 定时
- [x] `deploy.py` — 生成报告 + 推送 HTML/docx/index/stats 到 gh-pages
- [x] Windows Task Scheduler × 5（09:25 / 10:30 / 11:30 / 14:00 / 15:00）
- [x] `run_report.bat` — 日志写到 `C:\a-share-report\logs\`
- [x] 定时任务已设为"无论用户是否登录都要运行"

---

## 2026-08-06 今日完成

### 第一阶段：标签修正（北向→沪股通）
1. **全局标签审计** — 追踪全数据管线（采集→聚合→prompt→输出），发现 `slot_summary.py`/`prompts.py`/`docx_renderer.py` 中"北向资金"标签散落各处
2. **统一修正** — 所有注入 AI prompt 和用户可见的文本中，hgt 数据标注为"沪股通净买入"，修正 19 处
3. **跨文件字符串匹配修复** — `prompts.py` 红黄绿灯依赖 `slot_summary.py` 生成的文本做字符串匹配，修正后两端一致

### 第二阶段：方案 B——外资流向监测升级
4. **二维框架** — 将单一"沪股通净买入"升级为 方向+活跃度+强度 三维分析
5. **AI 分析口诀** — SYSTEM_PROMPT 新增"高成交+高净买=坚定看多"等 4 条口诀
6. **Word 文档改版** — 外资监测卡片变为结构化展示（方向/活跃度/强度/判定词）
7. **统计面板更新** — KPI 和图表标签改为"外资流向监测"

### 第三阶段：P0——发现并修复假数据
8. **根因发现** — 同花顺 `data.hexin.cn/dayChart` API 返回 262 个数据点（09:10→15:00），当前时间仅 10:57 就有全天数据，确认是静态缓存。5 个交易日 `north_flow` 全部为 -9.28
9. **AKShare 调研** — `stock_hsgt_fund_min_em()` 沪股通/深股通全部返回 0.0，证实证监会新规后北向净买入实时数据不再公开
10. **切换数据源** — `fetch_north_flow()` 标记废弃，北向活跃度切换为 mx-source 成交总额（每日限额 10 次，4 个时段使用）
11. **新增南向资金** — `fetch_south_bound()` 使用东财 datacenter `RPT_MUTUAL_QUOTA` API（需 `BOARD_CODE` 在 columns 中），港股通净买入数据仍公开发布
12. **三维分析框架** — SYSTEM_PROMPT 重写为活跃度+南向+外部联动，红黄绿灯 14 条规则全面重写
13. **数据采集重构** — `collector.py` 中 north_data 新结构：`turnover_total`/`participation_pct`/`sh_ratio`/`south_flow`
14. **所有呈现层更新** — `slot_summary.py` 对比指标（4 维）/ `docx_renderer.py` Word 卡片 / `renderer.py`+`stats.html` 图表数据

### 第四阶段：P1——统计面板 + 沪/深偏好
15. **北向图改双轴** — 柱状（成交总额）+ 折线（外资占比），含 5%/10% 基准线和高/中/低活跃度阈值线
16. **新增南向图** — 红绿柱状图（正=南下偏空A股，负=回流偏多A股），±30 亿阈值线
17. **1400 模块四加外资偏好** — 沪/深风格分析段（>55%=价值防御/<45%=成长进攻），红黄绿灯加偏好切换检测
18. **renderer.py** — `chart_json` 新增 `south_flow` 和 `north_participation` 数组

### 第五阶段：P2——外部联动共识引擎
19. **新建 `src/analysis/external_consensus.py`** — 三层信号引擎：
    - 第一层：单项信号质量（方向 × 幅度加权，-3~+3，含弱/中/强三级）
    - 第二层：一致性评分 + 置信度（强/中/弱/分歧）+ 背离检测
    - 第三层：边际变化（从 `last_slot.json` 读取上一时段共识对比）
20. **恒生指数新增** — `linked_markets_source.py` 加入 `int_hangseng`，4 线程并发
21. **集成到 collector** — 提取上证涨跌幅用于背离检测，`external_consensus` 注入 result dict
22. **slot_summary 存储** — 保存 `consensus_score` + `confidence` 供边际对比
23. **P2 修复** — 共识引擎从"权威结论"降级为"参考假设"：AI 拿到一行摘要 + 原始数据，有权质疑和推翻预计算。微弱信号>0 时 AI 应忽略外部联动

### 第六阶段：浅色主题换肤
24. **网站换肤** — 暗色 → 经典浅色 TradingView 风格，解决热力图中性区不可辨识问题
25. **dashboard.css** — 14 个 CSS 变量全换（bg/文字/强调/涨跌/边框），新增 `--up`/`--down` 变量
26. **stats.html** — 56 处 ECharts 硬编码色替换（含 5 张图表/热力图/基准线/图例）
27. **report.html** — 6 处 ECharts 硬编码色替换
28. **热力图修复** — 中性色 `#3a3e4a`（深灰）→ `#ecf0f1`（浅灰），在白色底上清晰可辨

### 冒烟测试（本地）
29. **全量冒烟测试通过** — 13 模块导入 / 南向 API / 龙虎榜 / 共识引擎强信号&弱信号边界 / 5 时段 Prompt / 4 模板编译。仅 mx-source 因本地无 MX_APIKEY 跳过（服务器正常）

### 踩坑记录（本次新增）
- **hexin dayChart 是静态数据** — 同一时间点调用返回 262 个数据点覆盖 09:10→15:00，当前才 10:57 就有完整数据，确认是缓存而非实时
- **东财 datacenter RPT_MUTUAL_QUOTA 需要 BOARD_CODE** — columns 里不加 BOARD_CODE 则 quoteColumns 全部返回 null
- **AKShare `stock_hsgt_north_net_flow_in_em` 函数名不存在** — 实际函数名是 `stock_hsgt_fund_min_em`、`stock_hsgt_fund_flow_summary_em`、`stock_hsgt_hist_em`
- **AKShare 南向有值、北向全零** — 港股通(沪/深) 净买入正常，沪股通/深股通全部为零，符合监管要求
- **南向数据单位是万元** — `netBuyAmt` 返回 391654.1 万元 = 39.17 亿元，需 ÷10000
- **共识引擎过强会误导 AI** — 微弱噪声信号（±0.05%）也被判定为"看多/看空"，导致 4/4 假一致。修复：AI 拿到摘要而非完整诊断树，被告知有权质疑
- **跨文件字符串匹配是隐藏炸弹** — `prompts.py` 红黄绿灯用 `"北向资金反转" in comparison_text` 匹配 `slot_summary.py` 生成的文本，改一个忘了另一个就静默失效

---

## 2026-08-13 今日完成：全面代码审查 + 修复

### 背景
上午发现 1130/1400/1500 三份报告 AI 内容空白。查日志发现 DeepSeek API 返回 `output=4096` 但 content 为空——模型进入"思考模式"，全部 token 进了 `reasoning_content` 字段。修复后 1500 补跑成功。之后启动全项目审查 agent，发现 8 项严重 + 10 项中等 + 15 项轻微问题，严重和中等全部修复。

### 严重问题修复（1-8）
1. **离岸人民币字段错位** — `linked_markets_source.py` 原来用买入价 vs 今开算涨跌幅。实测新浪 fx_ 格式：`[0]时间 [1]买入 [2]卖出 [3]昨收 [5]今开 [6]最高 [7]最低 [8]最新价 [9]名称`。改为 `[8]最新价/[3]昨收`
2. **在岸人民币买卖价差当涨跌幅** — `commodities_source.py` 同族错误（[1]买入 vs [2]卖出=点差，恒为负→永远假"升值"）。同样改 [8]/[3]
3. **恒生科技方向算反 + 恒生指数永远缺失** — rt_hk 格式 `[2]最新 [3]今开(非昨收) [7]涨跌额 [8]涨跌幅%`，原代码用 [2]/[3] 算反方向。改为直接取官方 [8]。int_hangseng 是 4 字段短格式 `[0]名称 [1]最新 [2]涨跌额 [3]涨跌幅%`，原 `len<9` 检查使其永远 None。改为短格式解析
4. **外资占比恒为 0** — `collector.py` 用 overview 的 total_amount（源数据恒 0）算 participation，而 main.py 在清洗后才注入。修复：collector 采集阶段直接用 index_data 计算两市成交额（amount 单位万元÷1e4=亿），main.py 删除重复计算
5. **富时A50 解析必然失败** — collector 的 `_fetch_overnight_global` 把 vals[1]（时间串/非价格）当价格。修复：复用 `linked_markets_source._parse_a50`，裸 except 补 debug 日志
6. **commodities 无异常兜底** — 全链路唯一无 try/except 的采集模块。修复：`_parse_futures` + `fetch_all_commodities` 逐项兜底，单项失败不影响其它项和主流程
7. **涨停溢价率用今开价** — A 股格式 `[0]名称 [1]今开 [2]昨收 [3]最新价`，原代码用 [1] 当价格。改为 [3]
8. **"成交额暂缺"标注恒真** — 清洗层在 total_amount 注入前检查，必然加"暂缺"note，与注入后的真实数字自相矛盾。修复 4 连带解决（collector 提前注入）

### 中等问题修复（9-18）
9. **mx_source 标签匹配顺序** — 泛"成交"匹配吞掉"沪股通成交额/深股通成交额"，且"两市成交额"可能错配为北向成交。修复：先精确匹配沪/深股通，再匹配北向/全部A股总额，泛"成交"不再匹配
10. **DeepSeek 失败时错误文案当正式报告** — 新增 `ReportGenerationError`，3 次重试+指数退避（5s×N），main 捕获后写错误页（不入索引/不存摘要/不生成 docx）
11. **南向跨交易日混算** — API 可能返回多日数据。修复：先筛最大 TRADE_DATE 再聚合
12. **deploy.py 推送异常未处理** — get_sha/put_file 全异常捕获返回 False，推送循环统计失败数+非零退出码（调度器可感知 gh-pages 半新半旧状态）
13. **deploy 时段窗口粗糙** — 错时手动触发会生成错误时段报告。修复：复用 `calendar.get_current_slot()` 精确窗口
14. **时段摘要 KeyError 静默断链** — limit_up_codes 用 `g["code"]` 直接下标。改 `.get()` 并过滤空 code；history 裁剪至最近 30 天（之前注释有代码无）
15. **indexer 用本地时间** — 改 BEIJING_TZ
16. **calendar 1400 窗口** — 补上 13:55-13:59（与注释一致）
17. **0925 涨跌榜只回填图表不回填表格** — 回填时同步更新 `data["movers"]`，movers_summary 保存 code 字段
18. **隔夜数据静默失败** — `_fetch_overnight_global` 裸 except 补 debug 日志

### 其他今日改动
- **0925 盘前简报结构强化** — prompt 强制 `<h3>一、隔夜传导</h3>` + `<h3>二、今日关注</h3>` 分节输出，AI 不再混为一段
- **0925 涨跌榜回填** — 盘前新浪返回全零/空时，从 last_slot.json 回填昨日收盘涨跌榜，标题标注橙色"（昨日收盘数据）"
- **板块轮动热力图 → 表格** — ECharts 热力图反复调不好（颜色糊/溢出），改为纯 HTML 表格：每格内嵌条形图（红涨绿跌）、5日累计列排序、行底色 5 档离散色、top 18 板块
- **docx 下载链接修复** — deploy.py 原来 `docx_files[0]` 永远取 09:25 的文件，改为按"XX时XX分"匹配当前时段
- **CSS 从未推送 gh-pages 修复** — deploy.py files_to_push 加入 `assets/css/dashboard.css`
- **echarts dark 主题残留** — report.html `echarts.init(el, 'dark')` → `init(el)`，涨跌标签 13px bold
- **宏观数据更新** — CPI/PPI 7 月数据（8-9 发布）：CPI 同比+0.5%/环比-0.1%/核心+0.9%，PPI 同比+3.5%/环比-0.7%

### 踩坑记录（本次新增）
- **🚨 mx-source 北向数据是假的（2026-08-14 发现）** — 查询"北向资金成交总额 沪股通 深股通"实际返回**A股板块成交额**：表标签是 `"全部A股(板块)"`（全市场成交 ~2.5万亿）、`"沪股通(板块)"`（沪股通标的股成交）。8-6 至 8-14 期间被误当"北向活跃度/外资占比/沪深偏好"，产生 150-260% 占比的数学不可能值，最终由 AI 在报告中自己发现并标注。**教训：8-5 的 HANDOFF 已记录"mx 不能用于北向数据"，但 P0 重构时忘了读。踩过的坑必须翻记录！** 修复：删除 mx 调用，外资监测退回二维（南向+外部联动），等 Tushare 的 moneyflow_hsgt 恢复真实北向数据
- **DeepSeek 思考模式** — 模型可能把全部 token 输出到 `reasoning_content`，content 为空。特征：output=4096（撞 max_tokens）但页面空白。修复：检测空 content+非空 reasoning 时重试，最终兜底用 reasoning_content。**日志现在会打印 content/reasoning 字数**
- **部署失败让调度器感知** — 之前 deploy 失败也 exit 0，日志里"部署完成"实际半新半旧。现在失败 exit 1，Windows Task Scheduler 能记录失败状态
- **本地网络间歇性断 GitHub** — 本次会话多次 push 失败。工作流：本地改代码 → 本地 commit → 复制文件到服务器 → 服务器 commit+push → 本地 `git fetch + reset --hard origin/main`
- **实测新浪字段格式**（都验证过，改代码前先 curl 实测）：
  - fx_susdcnh/fx_susdcny: `[3]昨收 [8]最新价`
  - rt_hkHSTECH: `[2]最新 [3]今开 [7]涨跌额 [8]涨跌幅%`（[3]不是昨收！）
  - int_hangseng: 4 字段短格式 `[0]名称 [1]最新 [2]涨跌额 [3]涨跌幅%`
  - nf_ 系列两种格式：带名称 `[0]名称 [1]时间 [2]最新价`；不带名称 `[0]最新价`
  - A 股 hq_str: `[0]名称 [1]今开 [2]昨收 [3]最新价`

---

## 当前数据源矩阵

| 数据 | 来源 | 函数 | 可靠性 | 备注 |
|------|------|------|:---:|------|
| 指数行情 | 腾讯 qt.gtimg.cn | `akshare_source.fetch_index_quotes()` | ✅ | 新浪备用校验 |
| 板块表现 | 新浪/腾讯 | `akshare_source.fetch_sector_performance()` | ✅ | 三级降级 |
| 涨跌榜 | 新浪 | `akshare_source.fetch_top_movers()` | ✅ | |
| 市场概况 | 腾讯 | `akshare_source.fetch_market_overview()` | ✅ | 成交额字段动态搜索 |
| **南向净买入** | 东财 datacenter | `eastmoney_source.fetch_south_bound()` | ✅ | 港股通实时可用 |
| ~~北向成交总额~~ | ~~mx-source~~ | ~~`fetch_north_turnover()`~~ | ❌ | 8-14 确认返回A股板块成交额（假数据），已移除 |
| 外围联动 | 新浪 | `linked_markets_source.fetch_linked_markets()` | ✅ | A50+恒生科技+恒生指数+CNH，4线程 |
| 龙虎榜 | 新浪 | `sina_lhb_source.fetch_daily_lhb()` | ✅ | HTML解析 |
| 资金流（替代两融）| 新浪 | `eastmoney_source.fetch_market_fund_flow()` | ⚠️ | 30股聚合，非官方两融 |
| 宏观数据 | 本地 JSON | `load_macro_data()` | ✅ | 月度手动更新 |
| ~~北向净买入~~ | ~~同花顺 hexin~~ | ~~`fetch_north_flow()`~~ | ❌ | 已废弃，静态假数据 |

---

## 下一步计划

### 短期
- [ ] **注册 Tushare 学生认证**（获取 2000 积分 → 免费调 `margin` 融资融券接口）——最高优先级
- [ ] **注册同花顺 quantapi**（`quantapi.10jqka.com.cn`，备用路径，可能收费）
- [ ] `macro_data.json` M2/社融 7 月数据更新（CPI/PPI 已完成 8-13，M2 等央行 8 月中旬发布）
- [x] 轻微问题清理（14 项）— 2026-08-14 已完成（死模块/hexin残留/时区/北交所前缀等）

### 中期
- [ ] **龙虎榜营业部明细深度分析** — 新浪 JSONP API 已通，能看游资/机构具体动向，HANDOFF 标记"待单独开发"
- [ ] **钉钉/微信机器人推送** — 报告生成后自动推送通知
- [ ] **盘中实时异动提醒** — 需要数据源支持

### 长期
- [ ] **模块三：盘口博弈**（涨停封单/炸板率/委卖压）——需要 Tushare 或同花顺数据源
- [ ] 融资融券数据恢复（依赖用户注册 Tushare/同花顺）

### 1400 盘中实战报告模块进度

| 模块 | 状态 |
|------|------|
| 一：边际速览 | ✅ |
| 二：量价结构 | ✅ |
| 三：盘口博弈 | ⬜ 等待数据源 |
| 四：内外联动 | ✅（外资偏好+外部共识引擎） |
| 五：持续性评估 | ✅ |
| 六：红黄绿灯 | ✅（活跃度+南向+共识+背离） |

---

## 绝对不要踩的坑

### 🚨 开发规则
0. **新功能不进 main.py** — `src/main.py` 的 `run()` 是核心流程。新数据源写新文件 → `collector.py` 聚合；新分析逻辑写新文件 → 注入。不要往 `run()` 里塞临时代码
1. **跨文件字符串匹配** — 如果你在 A 文件改了某个标签文本，必须同时检查 B/C/D 文件是否有 `"xxx" in variable` 的依赖。最危险的是 `prompts.py` 的红黄绿灯用 `"沪股通净买入反转" in comparison_text` 匹配 `slot_summary.py` 生成的文本
2. **修改 prompt 时考虑 AI 的质疑能力** — 不要让 Python 端输出"权威结论"让 AI 照单全收。AI 应该拿到原始数据 + 简短摘要 + 质疑权限

### API 相关
3. **东财 push2/push2his/datacenter-web 全封** — 阿里云 IP 彻底连不上，不要再试
4. **同花顺 hexin dayChart API 是静态缓存** — 不要用它做实时分析。数据不含时间戳，每次返回同样的完整数据集
5. **AKShare 北向全零、南向可用** — `stock_hsgt_fund_min_em()` 沪股通/深股通全部返回 0.0，但港股通数据正常
6. **东财 datacenter RPT_MUTUAL_QUOTA 需要 BOARD_CODE** — columns 必须含 `BOARD_CODE`，否则 quoteColumns 返回 null
7. **南向 netBuyAmt 单位是万元** — ÷10000 = 亿元
8. **mx-source 每日限额 10 次** — 当前 4 时段使用 4 次/天
9. **DeepSeek 模型名**: `deepseek-v4-pro`，不是 `deepseek-chat`
10. **DeepSeek API URL**: `https://api.deepseek.com/chat/completions`，没有 `/v1`

### 代码相关
11. **Python 函数内不要 `import datetime`**: 会和模块级 `datetime` 冲突导致 `UnboundLocalError`
12. **`__pycache__` 导致代码更新不生效**: 服务器更新代码后须清 pycache，用 `python -B` 或递归清
13. **本地 Python 3.9 不支持 `dict | None` 语法**: 本项目需要 3.12，使用 `venv\Scripts\python.exe`
14. **CMD 不支持多行命令** — CMD 给多行字符串会失败。给 CMD 用户的命令必须用多个 `-m` 或一行写完。Bash（Git Bash）可以直接多行粘贴
15. **`setx` 只对新 CMD 窗口生效** — 设置环境变量后须关掉重开 CMD

### 部署相关
16. **不要建 GitHub Actions 自动部署** — 和服务器 Windows Task Scheduler 冲突。两套系统同时推 gh-pages 会互相覆盖，且 Actions 环境缺 DeepSeek key
17. **部署只走服务器 `deploy.py`** — 推送报告到 gh-pages，不是 main
18. **GitHub Secret Scanning 会拦截 Token**: bat 文件里不能硬编码 Token，必须读环境变量
19. **`.docx` 是二进制文件**: `deploy.py` 用 `open(..., "rb")` 读，base64 编码后推送
20. **服务器 commit 身份**: 服务器首次用 `git commit` 需先配 `user.email` 和 `user.name`
21. **服务器装 git 了** — 更新代码用 `git fetch origin main && git reset --hard origin/main`，不要用 curl

### 模板 & 前端
22. **ECharts 富文本花括号 `{ipo|新股}` 会破坏 JS**: 图表标签用纯文本 `[新股]`
23. **N/C 前缀新股**: 科创/创业板前5日无涨跌停，100%+ 涨跌幅是真实数据，不要过滤
24. **`json.dumps` 用 `ensure_ascii=False`**: 否则中文变 `\uXXXX`
25. **`| safe` + `<script>` = XSS 风险**: 必须用 `_safe_script_json()` 转义 `</` → `<\/`
26. **网页地址是 `/a-share-report/reports/`**，不是根路径。所有链接必须含 `reports/` 前缀

### 数据源相关
27. **腾讯 `qt.gtimg.cn` 指数成交额字段位置不固定** — 绝对不要用固定索引。正确做法：遍历所有 fields，动态搜索 `数字/数字/大数字` 格式
28. **北向成交额单位** — mx-source 返回的是中文格式（"2.039万亿"），用 `_parse_amount()` 解析
29. **上证指数 key 是 `000001`** — 在 `index_data` 中用字符串 key，不是数字

---

## 关键文件清单

| 文件 | 作用 |
|------|------|
| `src/main.py` | 主入口，`run(slot)` 一次性生成 HTML+docx+索引 |
| `deploy.py` | 服务器部署：调用 run() + 推送 HTML/docx/index/stats 到 gh-pages |
| `run_report.bat` | Windows Task Scheduler 入口脚本 |
| `src/data/collector.py` | 多源数据聚合（所有数据在此汇合） |
| `src/data/cleaner.py` | 数据清洗（标记→删除） |
| `src/data/sources/akshare_source.py` | 腾讯指数 + 新浪涨跌榜 + 板块 |
| `src/data/sources/eastmoney_source.py` | 南向资金 + 资金流替代两融 + [已废弃]hexin 北向 |
| `src/data/sources/sina_source.py` | 新浪备用指数源 |
| `src/data/sources/sina_lhb_source.py` | 龙虎榜（新浪 HTML 解析） |
| `src/data/sources/commodities_source.py` | 商品/汇率/全球指数 |
| `src/data/sources/linked_markets_source.py` | 外围联动（A50+恒生科技+恒生指数+CNH） |
| `src/data/sources/mx_source.py` | 北向成交总额（东方财富妙想 API，每日限额 10 次） |
| `src/data/macro_loader.py` | 宏观数据加载（CPI/PPI/PMI/M2/LPR） |
| `src/analysis/deepseek_client.py` | DeepSeek API 调用 |
| `src/analysis/prompts.py` | 5 时段 prompt 模板 + SYSTEM_PROMPT + 红黄绿灯 |
| `src/analysis/external_consensus.py` | 🆕 外部联动三层信号引擎（方向×幅度加权+一致性+背离） |
| `src/analysis/slot_summary.py` | 时段摘要保存/加载/边际对比文本生成 |
| `src/web/renderer.py` | Jinja2 渲染 + XSS 防护 + 统计面板数据构建 |
| `src/web/docx_renderer.py` | HTML→Word（python-docx） |
| `src/web/indexer.py` | 搜索索引维护 |
| `src/web/templates/report.html` | 报告 HTML 模板 |
| `src/web/templates/index.html` | 首页模板 |
| `src/web/templates/archives.html` | 归档页模板 |
| `src/web/templates/stats.html` | 🆕 统计面板（5 张图表：涨跌比/北向双轴/南向/指数/热力图） |
| `data/macro_data.json` | 宏观数据（月度更新） |
| `data/last_slot.json` | 时段摘要历史（运行时自动生成，统计面板数据源） |
| `data/index.json` | 搜索索引（部署时推送到 gh-pages） |
| `assets/css/dashboard.css` | 浅色仪表盘样式（TradingView 风格） |
