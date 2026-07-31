# HANDOFF — A 股量化报告系统

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

- **新功能 = 新文件或新函数**，通过注入/回调方式接入，不在 `run()` 内部散落临时代码
- 数据采集：新数据源写在 `src/data/sources/` 下，通过 `collector.py` 统一聚合
- 分析逻辑：写在 `src/analysis/` 下，在 `run()` 的固定步骤点调用（如"prompt 构建前"、"报告生成后"）
- 前端展示：新数据类型通过 `renderer.py` 传给模板，模板新增区块

**反面教材**：本次会话结束后发现 `main.py` 里散落着几行成交额计算、摘要保存等临时插进去的代码。后续会话应该把这些抽到独立模块。

---

## 已完成

### 核心功能
- [x] 5 时段报告生成（0925盘前/1030早盘/1130午盘/1400午后/1500收盘）
- [x] DeepSeek AI 分析（量化交易视角，中文）
- [x] 数据采集：腾讯（指数）+ 新浪（个股/板块/资金流）+ 同花顺（北向）
- [x] 东财 push2 全封 —— 北向改用同花顺 hexin.cn（零认证），两融改新浪 30 股资金流聚合替代
- [x] 多源交叉校验：腾讯 + 新浪指数偏差检测
- [x] 板块数据三级降级：东财 → 新浪 newSinaHy.php → 腾讯申万行业指数
- [x] 板块涨跌幅启发式字段检测
- [x] IPO 新股识别：N/C 前缀保留不删
- [x] 宏观数据 KPI 卡片 + DeepSeek 分析
- [x] 北京时间全局修复（`datetime.now(BEIJING_TZ)`）
- [x] 商品/汇率/全球指数
- [x] 市场概况（涨跌比、涨停/跌停、换手率）
- [x] 免责声明

### 网页功能
- [x] 暗色仪表盘 + ECharts 柱状图（涨幅/跌幅/板块）
- [x] KPI 卡片（指数 → 商品汇率 → 宏观 → 北向 → 资金流）
- [x] 涨跌榜表格（含新股标签）
- [x] 搜索 + 归档页（客户端 JS + JSON 索引）
- [x] Word 报告下载（python-docx，HTML→docx）
- [x] 下载文件名含日期时段：`2026-07-30 15时00分 A股量化报告.docx`
- [x] 首页/归档/报告之间导航链接正常工作

### 安全
- [x] XSS 防护：`_safe_script_json()` 转义 `</` → `<\/`
- [x] production console.log 已清理
- [x] GitHub Token 不写入代码文件（读环境变量 `%GH_TOKEN%`）
- [x] Token 已更新（2026-07-30 会话结束前更换）

### 部署 & 定时
- [x] GitHub Actions 推送工作流
- [x] `deploy.py` — 生成报告 + 推送 HTML/docx/index 到 gh-pages
- [x] Windows Task Scheduler × 5（09:25 / 10:30 / 11:30 / 14:00 / 15:00）
- [x] `run_report.bat` — 日志写到 `C:\a-share-report\logs\`
- [x] 定时任务已设为"交互方式/后台方式"（断开 RDP 也能跑）

---

## 2026-07-30 今日完成

1. **板块图修复** — 数据采集链路正常，但生成环节 data dict 字段传递丢失导致所有 `change_pct=0`。重走完整 `collect → clean → chart_data → render` 链路后修复
2. **北向资金恢复** — 东财 push2 全封 → 改用同花顺 `data.hexin.cn/market/hsgtApi/method/dayChart/`，零认证，返回 hgt/sgt 分钟级数据
3. **融资融券替代** — 东财两融 API 全封 → 新浪 `MoneyFlow.ssl_qsfx_lscjfb` 聚合 30 只代表性大盘股的大单/特大单净流入，报告中标注"资金流（替代两融）"
4. **Word 下载** — 新增 `src/web/docx_renderer.py`（HTML→docx），部署到 gh-pages，网页加下载按钮
5. **XSS 防护** — `renderer.py` 加 `_safe_script_json()`，所有 `<script>` 内 JSON 转义 `</` 序列
6. **console.log 清理** — 移除生产环境诊断日志，只保留一条 `console.error`
7. **链接修复** — `indexer.py` URL 加 `reports/` 前缀，所有模板导航链接指向正确路径
8. **定时任务** — 创建 `run_report.bat`，Windows Task Scheduler 5 时段，Administrator 账户 + 密码
9. **Token 更换** — GitHub 旧 Token 已 revoke，新 Token 只勾 `repo`，90 天有效，服务器 `setx GH_TOKEN` 设置

## 2026-07-31 今日完成

1. **git 部署** — 服务器装了 Git，以后更新代码 `git pull` 一条命令替代所有 curl 下载
2. **成交额 KPI 卡片** — 新增"两市成交额"橙色卡片。修了腾讯 API 成交额字段提取：`fields` 位置不固定，改为动态搜索 `价格/成交量/成交额(元)` 格式字段
3. **成交额传给 DeepSeek** — `main.py` 注入 `overview.total_amount`，AI 不再说"数据暂缺"
4. **下载文件名优化** — `2026-07-31 10时30分 A股量化报告.docx`（用 slot 拼 `XX时XX分`）
5. **外围市场联动 KPI** — 恒生科技/离岸人民币/富时A50 三指标紫色边框卡片。新建 `src/data/sources/linked_markets_source.py`，新浪 `hq.sinajs.cn`，3 线程并发
6. **时段边际对比系统** — 新建 `src/analysis/slot_summary.py`，保存每时段关键指标摘要到 `data/last_slot.json`，下一时段 prompt 自动加载"上一时段"和"昨日同期"数据，计算 delta + 标记异常（北向反转、量价异常、板块轮动）。1030 起生效，0925 对比昨日收盘
7. **龙虎榜数据源迁移** — 东财 push2 阿里云 IP 被封，新建 `src/data/sources/sina_lhb_source.py`，改用新浪 `vInvestConsult/kind/lhb/index.phtml` HTML 页面解析。支持多 dataTable（按上榜类型分组）+ 上榜原因提取。`collector.py` 已切换，`eastmoney_source.py` 废弃函数已删除

### 成交额字段踩坑记录
- 腾讯 `qt.gtimg.cn` 的 `fields` 位置**不固定**，盘中/盘后偏移可达 4+ 位
- `fields[7]` 不是成交额（永远是 0），`fields[31]` 和 `fields[35]` 位置都会变
- **最终解法**：遍历所有 fields，动态搜索 `数字/数字/大数字` 格式的字段（`parts[2] > 9 位且 isdigit()`），提取第三个数字（元）后转万元

### 服务器更新方式变更
```cmd
# 旧方式（已废弃）
curl -o 文件1 URL1; curl -o 文件2 URL2; ...

# 新方式
cd C:\a-share-report && git fetch origin main && git reset --hard origin/main
rmdir /s /q src\__pycache__   # 注意：可能散布在子目录
python -B -c "import pathlib, shutil; [shutil.rmtree(d, ignore_errors=True) for d in pathlib.Path('src').rglob('__pycache__')]"
```

---

## 下一步计划

### 短期
- [x] 明早 9:25 验证定时任务自动运行（2026-07-31 已完成）
- [x] 成交额数据修复（2026-07-31 已完成）
- [x] 外围市场联动 KPI（2026-07-31 已完成）
- [x] 时段边际对比系统（2026-07-31 已完成，首次运行后生效）
- [ ] 注册同花顺量化平台（`quantapi.10jqka.com.cn`）获取真正的融资融券 API
- [ ] 龙虎榜数据恢复（依赖东财 push2，目前仍被封）
- [ ] `macro_data.json` 月度更新（每月 10-15 日统计局发布后）
- [ ] 如果以后再换 Token，只需 `setx GH_TOKEN "新Token"` + 重开 CMD

### 长期
- [ ] 盘中实时异动提醒
- [ ] 钉钉/微信机器人推送
- [ ] 历史报告统计面板
- [ ] 边际对比系统补充"昨日同期"数据积累（需 2 个交易日以上历史）

---

## 绝对不要踩的坑

### 🚨 开发规则
0. **新功能不进 main.py** — `src/main.py` 的 `run()` 是核心流程。新数据源写新文件 → `collector.py` 聚合；新分析逻辑写新文件 → 在 `run()` 的固定步骤点注入。不要往 `run()` 里塞临时代码。本条优先级最高。

### API 相关
1. **东财 push2/push2his/datacenter-web 全封** — 阿里云 IP 彻底连不上，不要再试。北向用同花顺 hexin，两融用新浪资金流
2. **DeepSeek 模型名**: `deepseek-v4-pro`，不是 `deepseek-chat`
3. **DeepSeek API URL**: `https://api.deepseek.com/chat/completions`，**没有 `/v1`**
4. **新浪 `newSinaHy.php` 涨跌幅字段**: `fields[4]` 才是涨跌幅，`fields[5]` 是成交量
5. **同花顺 hexin sgt 数据**: 绝对值 >100 大概率是余额而非净买入，代码里已做启发式判断（取相邻差值）
6. **新浪资金流是 T-1 日期** — 聚合数据 date 显示上一交易日，这是正常的（当日资金流要等收盘才公布）
7. **龙虎榜数据源已切换为新浪** — 东财 push2 全封，不要再用。新源 `sina_lhb_source.py`，HTML 解析，字段比东财更丰富（多了收盘价/成交量/成交额）

### 代码相关
7. **Python 函数内不要 `import datetime`**: 会和模块级 `datetime` 冲突导致 `UnboundLocalError`
8. **`__pycache__` 导致代码更新不生效**: 服务器 curl 更新代码后必须 `rmdir /s /q __pycache__`
9. **github raw URL 有 CDN 缓存**: 服务器更新代码加随机参数 `?t=%RANDOM%%RANDOM%`，更新后 `findstr` 验证内容正确
10. **CMD 不支持多行命令**：CMD 无法识别换行符分隔的多行字符串（如 `git commit -m "line1\n\nline2"`）。给 CMD 用户的命令必须用多个 `-m` 拼接或一行写完。用 Bash（Git Bash）可以直接粘贴多行命令。
11. **`setx` 只对新 CMD 窗口生效**: 设置环境变量后必须关掉重开 CMD
12. **GitHub 的 main.zip 有缓存延迟**: 不要用 ZIP，逐个 `curl -o` 从 `raw.githubusercontent.com` 下载

### 部署相关
13. **`push_files.py` Token 用命令行传参**: 进程列表可见，用完改回环境变量读法
14. **`.docx` 是二进制文件**: `deploy.py` 用 `open(..., "rb")` 读，base64 编码后推送
15. **GitHub Pages 部署目标分支是 `gh-pages`**: 推送报告到 gh-pages，不是 main
16. **GitHub Secret Scanning 会拦截 Token**: bat 文件里不能硬编码 Token，必须读环境变量
17. **Windows 定时任务**: 不加 `/rp 密码` 则离线不跑；加 `/rp` 确保"无论用户是否登录都要运行"
18. **chcp 65001 会导致 Python urllib 编码错误**: 推送时切回 `chcp 437`
19. **报告 HTML 缩成 14 字节**: 模板文件被覆盖成 `404: Not Found`，重新 curl 下载即可

### 模板 & 前端
20. **ECharts 富文本花括号 `{ipo|新股}` 会破坏 JS**: 图表标签用纯文本 `[新股]`
21. **N/C 前缀新股**: 科创/创业板前5日无涨跌停，100%+ 涨跌幅是真实数据，不要过滤
22. **`json.dumps` 用 `ensure_ascii=False`**: 否则中文变 `\uXXXX`
23. **`| safe` + `<script>` = XSS 风险**: 必须用 `_safe_script_json()` 转义 `</` → `<\/`
24. **板块 >30% 硬过滤**（cleaner 处理），新股除外
25. **网页地址是 `/a-share-report/reports/`**，不是根路径。所有链接必须含 `reports/` 前缀

### 数据源相关（2026-07-31 新增）
26. **腾讯 `qt.gtimg.cn` 指数成交额字段位置不固定** — 绝对不要用固定索引（`fields[7]`、`fields[31]`、`fields[33]` 都会变）。正确做法：遍历所有 fields，动态搜索 `数字/数字/大数字` 格式的复合字段，`split("/")` 取第三部分
27. **`__pycache__` 散布在 src/ 所有子目录** — `rmdir /s /q __pycache__` 只能清根目录的。子目录的要用 `pathlib.Path('src').rglob('__pycache__')` 递归清，或直接用 `python -B` 跳过缓存
28. **成交额单位** — 腾讯 API 返回的 amount 是元。代码转两次：先 `/1e4` 得万元（存入 data），再 `/1e4` 得亿元（显示用）。两市成交额只在 `main.py` 和 `renderer.py` 两处计算，要改一起改
29. **服务器装 git 了** — 以后更新代码用 `git fetch origin main && git reset --hard origin/main`，不要用 curl

### 服务器运维（2026-07-31 新增）
30. **定时任务 2026-07-31 首次成功运行** — 5 个时段均正常触发
31. **GitHub Token 2026-07-30 已换新** — 90 天有效，到期前 GitHub 会邮件提醒，服务器 `setx GH_TOKEN "新Token"` 即可
32. **Word 下载文件名格式** — `{{ date }} {{ slot[:2] }}时{{ slot[2:] }}分 A股量化报告.docx`，如 `2026-07-31 15时00分 A股量化报告.docx`

---

## 关键文件清单

| 文件 | 作用 |
|------|------|
| `src/main.py` | 主入口，`run(slot)` 一次性生成 HTML+docx+索引 |
| `deploy.py` | 服务器部署：调用 run() + 推送到 GitHub Pages（gh-pages 分支） |
| `run_report.bat` | Windows Task Scheduler 入口脚本 |
| `push_files.py` | GitHub Contents API 推送工具（开发用） |
| `src/data/collector.py` | 多源数据聚合 |
| `src/data/cleaner.py` | 数据清洗（标记>删除） |
| `src/data/sources/eastmoney_source.py` | 北向（同花顺hexin）+ 资金流（新浪30股）+ 龙虎榜（东财，已封） |
| `src/data/sources/akshare_source.py` | 腾讯指数 + 新浪涨跌榜 + 东财/新浪/腾讯板块 |
| `src/data/sources/commodities_source.py` | 商品/汇率/全球指数 |
| `src/data/sources/sina_source.py` | 新浪备用指数源 |
| `src/data/macro_loader.py` | 宏观数据加载（CPI/PPI/PMI/M2/LPR） |
| `data/macro_data.json` | 宏观数据 |
| `src/analysis/deepseek_client.py` | DeepSeek API 调用 |
| `src/analysis/prompts.py` | 5 时段 prompt 模板 |
| `src/web/renderer.py` | Jinja2 渲染（含 `_safe_script_json` XSS 防护） |
| `src/web/docx_renderer.py` | HTML→Word（python-docx） |
| `src/web/indexer.py` | 搜索索引维护 |
| `src/web/templates/report.html` | 报告 HTML 模板（含下载按钮） |
| `src/web/templates/index.html` | 首页模板 |
| `src/web/templates/archives.html` | 归档页模板 |
| `assets/css/dashboard.css` | 暗色仪表盘样式 |
| `.github/workflows/report.yml` | GitHub Actions |
