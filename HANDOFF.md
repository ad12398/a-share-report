# HANDOFF — A 股量化报告系统

## 🚨 新会话速览（2026-08-06 收盘后状态）

### 系统运行中
- 5 时段报告正常生成，Windows Task Scheduler 自动触发
- 服务器：阿里云 ECS `8.148.233.129`，代码在 `C:\a-share-report\`
- 网站：`https://ad12398.github.io/a-share-report/reports/`
- 本地：`c:\Users\Krug2\langchain_demo\a-share-report\`，Python 用 `venv\Scripts\python.exe`（3.12.4）
- **服务器更新方式**：
  ```cmd
  cd C:\a-share-report && git fetch origin main && git reset --hard origin/main
  python -B -c "import pathlib, shutil; [shutil.rmtree(d, ignore_errors=True) for d in pathlib.Path('src').rglob('__pycache__')]"
  ```

### 🚨 当前阻塞（用户需手动执行）
1. **注册 Tushare 学生认证** → 获取融资融券 API（`margin` 接口，学生 2000 分免费）——最高优先级
2. **注册同花顺 quantapi** → `quantapi.10jqka.com.cn`（备用，可能收费）
3. **CPI/PPI/M2 更新** → `data/macro_data.json`，等 8/10-15 统计局发布 7 月数据

### 上次离开时在做
- 刚完成外部联动三层信号引擎（P2），AI 在 1400 模块四能拿到预计算的方向一致性摘要
- 服务器代码已推送到 `06c0edf`，明天 9:25 盘前自动生效新代码
- 下一步可选：龙虎榜营业部明细 或 钉钉/微信推送

---

## 项目概述

构建全自动 A 股量化分析报告系统，交易时段生成 5 份报告，输出暗色仪表盘网页 + Word 下载，部署在 GitHub Pages。

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
- [x] 暗色仪表盘 + ECharts 图表
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

### 踩坑记录（本次新增）
- **hexin dayChart 是静态数据** — 同一时间点调用返回 262 个数据点覆盖 09:10→15:00，当前才 10:57 就有完整数据，确认是缓存而非实时
- **东财 datacenter RPT_MUTUAL_QUOTA 需要 BOARD_CODE** — columns 里不加 BOARD_CODE 则 quoteColumns 全部返回 null
- **AKShare `stock_hsgt_north_net_flow_in_em` 函数名不存在** — 实际函数名是 `stock_hsgt_fund_min_em`、`stock_hsgt_fund_flow_summary_em`、`stock_hsgt_hist_em`
- **AKShare 南向有值、北向全零** — 港股通(沪/深) 净买入正常，沪股通/深股通全部为零，符合监管要求
- **南向数据单位是万元** — `netBuyAmt` 返回 391654.1 万元 = 39.17 亿元，需 ÷10000
- **共识引擎过强会误导 AI** — 微弱噪声信号（±0.05%）也被判定为"看多/看空"，导致 4/4 假一致。修复：AI 拿到摘要而非完整诊断树，被告知有权质疑
- **跨文件字符串匹配是隐藏炸弹** — `prompts.py` 红黄绿灯用 `"北向资金反转" in comparison_text` 匹配 `slot_summary.py` 生成的文本，改一个忘了另一个就静默失效

---

## 当前数据源矩阵

| 数据 | 来源 | 函数 | 可靠性 | 备注 |
|------|------|------|:---:|------|
| 指数行情 | 腾讯 qt.gtimg.cn | `akshare_source.fetch_index_quotes()` | ✅ | 新浪备用校验 |
| 板块表现 | 新浪/腾讯 | `akshare_source.fetch_sector_performance()` | ✅ | 三级降级 |
| 涨跌榜 | 新浪 | `akshare_source.fetch_top_movers()` | ✅ | |
| 市场概况 | 腾讯 | `akshare_source.fetch_market_overview()` | ✅ | 成交额字段动态搜索 |
| **北向成交总额** | mx-source | `mx_source.fetch_north_turnover()` | ✅ | 每日限额10次 |
| **南向净买入** | 东财 datacenter | `eastmoney_source.fetch_south_bound()` | ✅ | 港股通实时可用 |
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
- [ ] `macro_data.json` CPI/PPI/M2 更新（预计 8 月 10-15 日统计局发布）

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
| `assets/css/dashboard.css` | 暗色仪表盘样式 |
