# HANDOFF — A 股量化报告系统

## 🚨 新会话速览（2026-08-06 状态）

### 系统已稳定运行
- 5 时段报告正常生成，Windows Task Scheduler 自动触发
- 服务器：阿里云 ECS `8.148.233.129`，代码在 `C:\a-share-report\`
- 网站：`https://ad12398.github.io/a-share-report/reports/`
- 本地：`c:\Users\Krug2\langchain_demo\a-share-report\`，Python 用 `venv\Scripts\python.exe`（3.12.4）

### 当前阻塞（用户需手动执行）
1. **注册 Tushare 学生认证** → 获取融资融券 API（`margin` 接口，2000 分学生免费）
2. **注册同花顺 quantapi** → `quantapi.10jqka.com.cn`（备用，可能收费）
3. **CPI/PPI/M2 更新** → 等 8 月 10-15 日统计局发布

### 已解决但需知晓
- 北向数据只含沪股通净买入（hgt），深股通因监管无法获取。报告中必须标注"沪股通净买入"，不可称"北向资金"
- 龙虎榜来自新浪，数据流正常
- 定时任务 bat 已改为纯 ASCII，不会出现 `%1` 参数丢失问题
- 融资融券目前用新浪资金流替代，真正数据依赖 Tushare/同花顺
- mx-source（东方财富妙想 API）已安装但北向数据不可靠，标签已修正
- 本地 GitBash 经常连不上 GitHub，优先从服务器 ECS 操作 git

### 上次离开时在做
- 刚清理完北向历史假数据，修正了统计面板标签
- 0925 盘前板块图表改用昨日数据回填
- 准备推进 Tushare 学生认证获取融资融券

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
- [x] `deploy.py` — 生成报告 + 推送 HTML/docx/index/stats 到 gh-pages
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
8. **历史报告统计面板** — 新建 `src/web/templates/stats.html`，KPI 卡片 + 4 张 ECharts 图表（市场宽度/北向趋势/指数累计收益/板块轮动热力图）。`renderer.py` 新增 `build_stats_data()` 从 `data/last_slot.json` 历史数据构建统计。数据不足 3 天时显示积累提示。导航栏已加"统计"链接。`slot_summary.py` 改存完整 30 板块 + 写前 `.bak` 备份。`deploy.py` 每次部署自动生成 `stats.html`
9. **宏观数据 PMI 更新** — 7 月制造业 PMI 49.2%（↓1.1pp，跌破荣枯线），服务业 PMI 49.3%。极端天气+生产淡季致全线回落。更新 `data/macro_data.json`。CPI/PPI/M2 等预计 8 月 10-15 日发布

## 2026-08-03 今日完成

1. **定时任务 bat 修复** — 中文注释在 GBK CMD 下导致 `%1` 参数无法展开。`run_report.bat` 所有注释改为纯 ASCII，`%1` 正常传递。同时删掉日志里 Unicode 字符（`✓` → 移除），避免 GBK 编码 crash
2. **docx 文件名修复** — 之前文件存在服务器上是 `1500.docx`，靠 HTML `download` 属性覆盖中文名。GitHub Pages 不保证支持该属性。现在 `save_docx()` 直接存为 `2026-08-03 15时00分 A股量化报告.docx`，`deploy.py` 用 glob 找文件推送
3. **网站报告加龙虎榜表格** — 之前龙虎榜数据只传 DeepSeek 不在网页展示。`report.html` 新增表格（代码/名称/收盘价/涨跌幅/成交量/成交额/上榜原因），`renderer.py` 传入 `dragon_tiger` 变量
4. **删掉冗余 GitHub Actions** — `.github/workflows/report.yml` 和 Windows Task Scheduler 两套系统冲突，Actions 环境缺 DeepSeek key 反复发失败邮件。已删除，HANDOFF 加坑 #14
5. **服务器 git 分支修复** — 服务器上是 `master`，远程是 `main`。改为 `main` 并同步
6. **1400 实战快评** — 重写 `build_afternoon_prompt`，Python 端计算红黄绿灯（`_compute_warning_lights()`）。`slot_summary` 存 `linked_markets` 并计算外围联动 delta（A50/恒生/CNH）+ 背离检测
7. **模块五持续性评估** — `_compute_persistence()` 读 `last_slot.json` 历史：连续偏多/偏空小时数 + 涨跌比方向反转检测。反转信号触发红/黄灯

### 踩坑记录
- **GitHub 本地连不上**：本地 Git Bash `git push` 反复超时，但服务器 ECS 正常。原因可能是本地网络 DNS/代理问题。后续优先从服务器推送
- **服务器 commit 身份**：服务器首次用 `git commit` 需要先配 `user.email` 和 `user.name`
- **CMD 不支持多行命令**：CMD 无法解析换行符分隔的多行参数。给 CMD 的命令必须用 `echo ... >> file.py` 拼接或写到文件。Bash（Git Bash）可以直接多行粘贴

## 2026-08-05 今日完成

1. **mx-source 集成** — 接入东方财富妙想 API（`mkapi2.dfcfs.com`），新建 `src/data/sources/mx_source.py`。最初想用 mx 获取北向成交总额来补充 hgt 净买入，计算"流量强度 = 净买入/成交总额"。但测试发现 mx 的自然语言查询把"北向资金成交总额"错误解析为"A 股板块成交额"，返回的是全市场数据而非北向通道数据。**mx 不能用于北向数据。** 已废弃该用法，但 mx 作为通用金融数据查询工具仍保留可用。
2. **mx-source 调用频率限制** — mx API 每日限额 10 次。`collector.py` 中 4 个时段（1030/1130/1400/1500）各调 1 次 = 4 次/天，在限额内。
3. **mootdx 接入测试** — 通达信 TCP 协议行情源（端口 7709），安装成功能连。46 字段含五档盘口、实时行情。不封 IP，可作为备用行情源。但 mootdx 不含融资融券数据。
4. **融资融券数据探索** — 测试了三条路，全部失败：
   - 东财 datacenter-web：API 能通（HTTP 200）但所有 reportName 已废弃（`RPTA_WEB_MARGIN_TRADE` 等返回 9501）
   - 东财 push2ex：阿里云 IP 同样被封（404）
   - mootdx：只有财报数据，无融资融券
   - **结论：免费源已全部死亡，唯一出路是用户注册同花顺 quantapi 或 Tushare**
5. **Tushare 学生认证** — Tushare `margin` 接口需 2000 积分。学生可通过高校认证直接获得 2000 分，免费。这是目前融资融券数据最可行的路径。用户尚未注册。
6. **北向 sgt 数据彻底废弃** — 同花顺 hexin API 的 sgt（深股通）字段返回的是证券出借余额（绝对值 370-400），相邻差值不等於净买入。之前代码用差值倒推导致所有报告显示相同 -30.68。已废弃，北向数据现在只取 hgt（沪股通净买入）。
7. **北向数据标注修正** — SYSTEM_PROMPT 加规则强制 AI 用"沪股通净买入"代替"北向资金"。统计面板标签修正：`北向资金趋势` → `沪股通净买入趋势`，`北向累计` → `沪股通累计净买入`。
8. **历史假数据清理** — `last_slot.json` 中所有 `net_flow == -30.68` 的旧记录已修正，用正确的 `net_flow_sh` 替换。
9. **0925 盘前图表回填** — 0925（9:25 盘前）新浪板块 API 返回全零（市场 9:30 才开盘）。`main.py` 新增 `_load_yesterday_sectors()` 从 `last_slot.json` 读取昨日收盘板块数据来填充 ECharts 图表。
10. **a-stock-data 开源项目探索** — 测试了 simonlin1212 的 A 股数据工具包。push2ex 被封、datacenter 报表名失效，只有 mootdx 可用。
11. **东财 kamt API 测试** — 能通（HTTP 200）但数据全零（2024 年监管新规后免费接口停止发布北向实时数据）。

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
python -B -c "import pathlib, shutil; [shutil.rmtree(d, ignore_errors=True) for d in pathlib.Path('src').rglob('__pycache__')]"
```

---

## 下一步计划

### 短期
- [x] 明早 9:25 验证定时任务自动运行（2026-07-31 已完成）
- [x] 成交额数据修复（2026-07-31 已完成）
- [x] 外围市场联动 KPI（2026-07-31 已完成）
- [x] 时段边际对比系统（2026-07-31 已完成）
- [x] 龙虎榜数据恢复（2026-07-31 已迁移到新浪）
- [x] 历史报告统计面板（2026-07-31 已完成，需 3 天数据积累后激活）
- [ ] **注册 Tushare 学生认证**（获取 2000 积分 → 免费调 `margin` 融资融券接口）——最高优先级
- [ ] **注册同花顺 quantapi**（`quantapi.10jqka.com.cn`，备用路径，可能收费）
- [x] PMI 已更新为 7 月数据（2026-07-31 发布）
- [ ] `macro_data.json` CPI/PPI/M2 更新（预计 8 月 10-15 日统计局发布）

### 长期
- [ ] **模块三：盘口博弈**（涨停封单/炸板率/委卖压）——需新数据源（Tushare 或同花顺）
- [ ] 盘中实时异动提醒
- [ ] 钉钉/微信机器人推送
- [ ] 龙虎榜营业部明细深度分析（新浪 JSONP API 已能通，待单独开发）
- [ ] 融资融券数据恢复（依赖用户注册数据源）

#### 盘中实战报告升级（仅 1400 生效）

| 模块 | 状态 |
|------|------|
| 一：边际速览 | ✅ |
| 二：量价结构 | ✅ |
| 三：盘口博弈 | ⬜ 等待数据源 |
| 四：内外联动 | ✅ |
| 五：持续性评估 | ✅ |
| 六：红黄绿灯 | ✅ |

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
8. **北向 sgt 数据是假的** — 同花顺 hexin API 的 sgt 字段返回的是证券出借余额（绝对值 370-400），差值不等於净买入。已废弃，只用 hgt（沪股通净买入）。报告中必须标注"沪股通净买入"而非"北向资金"
9. **mx-source 不能用于北向数据** — 东方财富妙想 API 的自然语言查询会把"北向资金成交总额"错误解析为"A 股板块成交额"，返回的是全市场数据。mx 仍可作为通用金融查询工具使用
10. **融资融券免费源已全部死亡** — 东财 datacenter 报表名废弃（9501）、push2/push2ex 被封、mootdx 无该数据。只有 Tushare（学生 2000 分）或同花顺 quantapi 能获取

### 代码相关
8. **Python 函数内不要 `import datetime`**: 会和模块级 `datetime` 冲突导致 `UnboundLocalError`
9. **`__pycache__` 导致代码更新不生效**: 服务器更新代码后须清 `__pycache__`
10. **CMD 不支持多行命令**：CMD 无法识别换行符分隔的多行字符串（如 `git commit -m "line1\n\nline2"`）。给 CMD 用户的命令必须用多个 `-m` 拼接或一行写完。用 Bash（Git Bash）可以直接粘贴多行命令。
11. **本地 Bash 默认 Python 是 3.9**（`D:\Python\python.exe`），不支持 `dict | None` 等 3.10+ 语法。本项目需要 3.12，使用 `c:\Users\Krug2\langchain_demo\venv\Scripts\python.exe`（3.12.4）。不要删 D:\Python（有旧脚本依赖），跑命令时指定 venv 路径即可。
12. **`setx` 只对新 CMD 窗口生效**: 设置环境变量后必须关掉重开 CMD
13. **GitHub 的 main.zip 有缓存延迟**: 不要用 ZIP，用 `git pull`

### 部署相关
14. **不要建 GitHub Actions 自动部署** — 和服务器 Windows Task Scheduler 冲突。两套系统同时推 gh-pages 会互相覆盖，且 Actions 环境缺少 DeepSeek key / 网络，跑一次失败一次发一次邮件。部署只走服务器 `deploy.py`。
15. **GitHub Pages 部署目标分支是 `gh-pages`**: 推送报告到 gh-pages，不是 main
15. **GitHub Pages 部署目标分支是 `gh-pages`**: 推送报告到 gh-pages，不是 main
16. **GitHub Secret Scanning 会拦截 Token**: bat 文件里不能硬编码 Token，必须读环境变量
17. **Windows 定时任务**: 不加 `/rp 密码` 则离线不跑；加 `/rp` 确保"无论用户是否登录都要运行"
18. **`.docx` 是二进制文件**: `deploy.py` 用 `open(..., "rb")` 读，base64 编码后推送

### 模板 & 前端
19. **ECharts 富文本花括号 `{ipo|新股}` 会破坏 JS**: 图表标签用纯文本 `[新股]`
20. **N/C 前缀新股**: 科创/创业板前5日无涨跌停，100%+ 涨跌幅是真实数据，不要过滤
21. **`json.dumps` 用 `ensure_ascii=False`**: 否则中文变 `\uXXXX`
22. **`| safe` + `<script>` = XSS 风险**: 必须用 `_safe_script_json()` 转义 `</` → `<\/`
23. **板块 >30% 硬过滤**（cleaner 处理），新股除外
24. **网页地址是 `/a-share-report/reports/`**，不是根路径。所有链接必须含 `reports/` 前缀

### 数据源相关
25. **腾讯 `qt.gtimg.cn` 指数成交额字段位置不固定** — 绝对不要用固定索引。正确做法：遍历所有 fields，动态搜索 `数字/数字/大数字` 格式的复合字段，`split("/")` 取第三部分
26. **`__pycache__` 散布在 src/ 所有子目录** — 用 `python -B` 或 `pathlib.Path('src').rglob('__pycache__')` 递归清
27. **成交额单位** — 腾讯 API 返回的 amount 是元。转两次：先 `/1e4` 得万元（存入 data），再 `/1e4` 得亿元（显示用）。两市成交额只在 `main.py` 和 `renderer.py` 两处计算，要改一起改
28. **服务器装 git 了** — 更新代码用 `git fetch origin main && git reset --hard origin/main`，不要用 curl

### 服务器运维
29. **定时任务 5 个时段均正常触发** — 0925/1030/1130/1400/1500
30. **GitHub Token 90 天有效** — 到期前 GitHub 会邮件提醒，服务器 `setx GH_TOKEN "新Token"` 即可
31. **`data/last_slot.json` 写入前自动备份** — 同路径 `.json.bak`，写入中断可恢复

---

## 关键文件清单

| 文件 | 作用 |
|------|------|
| `src/main.py` | 主入口，`run(slot)` 一次性生成 HTML+docx+索引 |
| `deploy.py` | 服务器部署：调用 run() + 推送 HTML/docx/index/stats 到 gh-pages |
| `run_report.bat` | Windows Task Scheduler 入口脚本 |
| `src/data/collector.py` | 多源数据聚合 |
| `src/data/cleaner.py` | 数据清洗（标记→删除） |
| `src/data/sources/akshare_source.py` | 腾讯指数 + 新浪涨跌榜 + 东财/新浪/腾讯板块 |
| `src/data/sources/eastmoney_source.py` | 北向（同花顺hexin）+ 资金流（新浪30股）|
| `src/data/sources/sina_source.py` | 新浪备用指数源 |
| `src/data/sources/sina_lhb_source.py` | 🆕 龙虎榜（新浪 HTML 解析，替代东财 push2） |
| `src/data/sources/commodities_source.py` | 商品/汇率/全球指数 |
| `src/data/sources/linked_markets_source.py` | 外围市场联动（A50+恒生科技+离岸人民币） |
| `src/data/macro_loader.py` | 宏观数据加载（CPI/PPI/PMI/M2/LPR） |
| `src/analysis/deepseek_client.py` | DeepSeek API 调用 |
| `src/analysis/prompts.py` | 5 时段 prompt 模板 |
| `src/analysis/slot_summary.py` | 时段摘要保存/加载/边际对比 |
| `src/web/renderer.py` | Jinja2 渲染（含 `_safe_script_json` XSS 防护）+ 统计面板 |
| `src/web/docx_renderer.py` | HTML→Word（python-docx） |
| `src/web/indexer.py` | 搜索索引维护 |
| `src/web/templates/report.html` | 报告 HTML 模板 |
| `src/web/templates/index.html` | 首页模板 |
| `src/web/templates/archives.html` | 归档页模板 |
| `src/web/templates/stats.html` | 🆕 统计面板（KPI+ECharts 图表+板块热力图） |
| `data/macro_data.json` | 宏观数据（月度更新） |
| `data/last_slot.json` | 🆕 时段摘要历史（自动积累，统计面板数据源） |
| `data/index.json` | 搜索索引（部署时推送到 gh-pages） |
| `assets/css/dashboard.css` | 暗色仪表盘样式 |
