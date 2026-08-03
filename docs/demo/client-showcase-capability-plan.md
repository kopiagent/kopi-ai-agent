# 客户演示能力盘点与实施方案

> 分支:`feat/demo-capabilities` · 2026-08-03 · **待确认,尚未合并**
>
> 前提(已定):外部账号走**混合策略** —— 社媒和域名用真号,会计与交易走官方 sandbox/paper;
> 交付**只做 agent 能力,不做演示脚本**,录屏由你自己操作;第 1 条的素材站先用一个公开站跑通。

盘点方法:逐条在仓库里 grep + 读代码确认,不靠印象。下表的"现状"列都能指到具体文件。

---

## 一、总览

"缺口"一列是**调研之后**的估计 —— 第三节说明了为什么有两条大幅缩水、两条反而变大。

| # | 客户要求 | 现状 | 缺口 |
|---|---|---|---|
| 1 | 研究网站 → 生成 2-3 段视频 → 剪辑拼接 | 生成有,**剪辑没有** | ✅ 已做 |
| 1/4 | 动画办公室、agent 互相传指令/说话 | 协议全通,**大半效果没人触发** | ✅ 已做 |
| 2 | 发布到 Instagram / X | X 有,**Instagram 没有** | ✅ 已做(卡凭据,见第八节) |
| 3 | 专业 PPT/Word + 同时给 PDF | 四个 skill 都在,**双交付没强制** | ✅ 已做(见第八节) |
| 4 | root 终端权限 | 本来就有 | 无 |
| 4 | 自动买域名 + 接到新站 | 完全没有 | 小 · 接官方 MCP |
| 5 | Telegram/WhatsApp 接 Zoho/Xero/QuickBooks | Xero+QB 有,**Zoho 没有** | 中 · 自己写 |
| 6 | 快速做网站和仪表盘 | 有底座 | 小 |
| 7 | 接 Binance/OKX/Alpaca 模拟盘交易 | 完全没有 | ✅ 已做(见第八节) |
| 8 | 每日 cron 新闻/竞品分析 | cron 框架完整 | 小 |
| 9 | 其他值得加的 | 见第五节 | — |

---

## 二、已经做掉的两件(在分支上,可直接看)

这两件是我在你喊停之前做完并验证过的。**要不要留,你定** —— 不留我 revert 掉。

### 2.1 动画办公室:让 agent 真的会说话

`web/src/pages/OfficePage.tsx` 的渲染器支持 7 种一次性特效
(`tool_call` / `handoff` / `error` / `retry` / `done` / `speak` / `emote`),
后端协议 `office.fx` 也全通(`tools/delegate_tool.py` → 快照 → `kopi_cli/web_server.py`
的 watcher → 前端)。

**但后端只触发了 2 种**:工具调用的火花、交办时飞出去的工单。
客户点名要的"agents 说话"(`speak`)、完成打勾(`done`)、报错(`error`)、
限流等待(`retry`)—— 一次都没被触发过。
`note_waiting_activity()`(把 NPC 送去咖啡机)更是**零调用点**。

改动:

| 位置 | 效果 |
|---|---|
| `_register_subagent` | 工单飞出的同时,父 agent 头顶弹出气泡说出**交办的任务内容** |
| `_unregister_subagent` | 子任务完成 → 父 agent 头顶 ✓ + 气泡念出**结果摘要**;失败则是红色 "!" |
| `note_waiting_activity` | 被限流退避时闪 "…" |
| `agent_runtime_helpers.py` 的重试路径 | 真正接上上面那条(原先没人调用) |

一个设计取舍值得说明:完成的 ✓ 挂在**父** agent 身上而不是子 agent。
因为 watcher 只广播它在快照里看到的特效,而子 agent 在同一次调用里就被移出快照了 ——
写在子 agent 上的 ✓ 永远送不到前端。挂父 agent 既能送达,语义也对("交办出去的活回来了")。

新增 `tests/tools/test_office_fx_emission.py`,7 个测试全过。

### 2.2 视频剪辑工具 `video_edit`

新文件 `tools/video_edit_tool.py`,本地 ffmpeg,不需要任何 API key。五个操作:

| 操作 | 用途 |
|---|---|
| `probe` | 读时长/分辨率/有没有音轨 |
| `concat` | **按顺序拼接多段** —— 第 1 条的核心 |
| `trim` | 裁剪时间段 |
| `caption` | 烧字幕/标题 |
| `add_audio` | 铺背景音乐或配音 |

`concat` 特意走**重编码**而不是 ffmpeg 的快速 concat demuxer。demuxer 要求各段编码参数
逐字一致,不同模型生成的片段一混就会出静默损坏或音画不同步。这里统一把每段缩放+letterbox
到同一分辨率/帧率/采样率,并给**没有音轨的片段自动补静音**(生成的片段经常没声音,
而 concat filter 要求各段流结构一致)。

已端到端验证:拿 1920×1080 30fps 有声 和 720×1280 24fps 无声 两段故意不匹配的片段拼接 →

```
clips_joined: 2, silent_clips_padded: 1
结果 4.03s / 1920×1080 / h264 + aac
```

已挂进 `video_gen` toolset。

---

## 三、GitHub 现成方案调研

结论先说:**七条里有三条能直接用第一方现成方案,两条不该用现成的,两条本来就不需要。**

| 需求 | 现成方案 | 评价 | 用不用 |
|---|---|---|---|
| 交易所(币) | [`ccxt/ccxt`](https://github.com/ccxt/ccxt) | 一个库统一 100+ 交易所,`set_sandbox_mode(True)` 一行切沙盒 | ✅ **用** |
| 交易所(美股) | [`alpacahq/alpaca-mcp-server`](https://github.com/alpacahq/alpaca-mcp-server) | **Alpaca 官方**,65 个工具,`ALPACA_PAPER_TRADE=true` 切模拟盘 | ✅ **用** |
| 域名 + DNS + 部署 | [`cloudflare/mcp`](https://github.com/cloudflare/mcp) | **Cloudflare 官方**,692★,Apache-2.0,覆盖 2500+ 端点 | ✅ **用** |
| 文档转 PDF | [Gotenberg](https://gotenberg.dev/) / headless LibreOffice | 成熟,但见下方"字体"那条 | ⚠️ 有条件 |
| Instagram | 一堆第三方 MCP | 见下 | ❌ **自己写** |
| Zoho | 一堆第三方 MCP | 同上 | ❌ **自己写** |
| 视频剪辑 | MoviePy | 见下 | ❌ 维持现状 |

### 3.1 ccxt —— 把第 7 条的工作量砍掉一大半

我原方案是给 Binance 和 OKX 各写一套工具。没必要:
[ccxt](https://github.com/ccxt/ccxt) 用一套统一 API 覆盖 100 多家交易所,
行情/下单/持仓/订单的方法名和返回结构都是标准化的,
沙盒只要 `exchange.set_sandbox_mode(True)` —— 它自己知道每家的 testnet 域名该切到哪。

这也顺手解掉了我原先担心的 OKX 问题:不用自己去记"OKX 是靠请求头切 demo 而不是换域名"。

**注意**:ccxt 只管加密货币,**不覆盖 Alpaca**(美股)。所以第 7 条是 ccxt + Alpaca 两条腿。

### 3.2 Alpaca 官方 MCP —— 第一方,直接接

[`alpacahq/alpaca-mcp-server`](https://github.com/alpacahq/alpaca-mcp-server) 是 Alpaca 自己维护的,
65 个工具覆盖交易和行情 API,v2 是基于 FastMCP 的重写。模拟盘就是一个环境变量
`ALPACA_PAPER_TRADE=true`。

这比我自己包 SDK 好:官方跟着 API 变更走,我们不用追。

### 3.3 Cloudflare 官方 MCP —— 第 4 条不用从零做了

[`cloudflare/mcp`](https://github.com/cloudflare/mcp),692★,Apache-2.0,Cloudflare 官方组织。
设计很聪明:不是把 2500 个端点铺成 2500 个工具(那会撑爆上下文),而是只暴露三个 ——
`docs`(查文档)、`search`(在 API spec 里找端点)、`execute`(调用),
整体只占约 1100 tokens。也就是说**注册域名、建 DNS、部署 Workers 全在这一个 MCP 里**。

认证支持 OAuth(推荐)或 API token。

这一条我原本估"工作量最大",现在变成最小的之一 —— 剩下的活只是把它和现有的
`optional-skills/web-development/cloudflare-temporary-deploy` 串起来。

### 3.4 Instagram 和 Zoho:**不建议用现成的**

两边都有一堆第三方 MCP,但没有一个是官方的。我查了其中口碑最好的
[`mcpware/instagram-mcp`](https://github.com/mcpware/instagram-mcp):

- 24 星,61 次提交,MIT
- npm 发布者 `@mcpware`,**身份不明**
- 而它要拿到的是一个**长期有效的 Meta access token**

用真客户账号做演示,把长期 token 交给一个来路不明的 npm 包 —— 这个风险不对等。
Instagram 的发布流程本身很小(创建媒体容器 → 轮询状态 → 发布,两三个 API 调用),
**自己写一个 skill 比审计别人的包更省事也更安全**。

Zoho 同理:候选全是第三方,没有官方。

> 顺带一提,仓库自己的 MCP 目录政策(`kopi_cli/mcp_catalog.py` 开头)本来就写着
> "进 `optional-mcps/` = 经过审核",版本要钉死、发布满两周。
> 官方的三个(Cloudflare / Alpaca)过这个门槛没问题,第三方的过不了。

### 3.5 视频剪辑:维持直接调 ffmpeg

主流替代是 [MoviePy](https://github.com/Zulko/moviepy),但它本身就是 ffmpeg 的封装,
代价是内存占用更高、长视频渲染更慢、大任务偶发不稳定。业界普遍建议是
**编排用 MoviePy、性能敏感的步骤直接调 ffmpeg**。

我们的场景(拼接 + 重编码)恰好就是"性能敏感的那步",所以 2.2 里直接调 ffmpeg 的做法是对的,
不换。

### 3.6 文档转 PDF:方案成熟,但坑在字体

[Gotenberg](https://gotenberg.dev/) 是个 Docker 化的转换 API,底下就是 LibreOffice,
支持 docx/xlsx/pptx 和上百种格式。保真度最高的路径确实是 headless LibreOffice ——
它用的是完整的桌面排版引擎。

但有一条**直接关系到客户那句"PDF 不能变形"**:

> LibreOffice 依赖机器上已安装的字体来计算分页和排版,
> **字体缺失是版式错位/分页偏移最常见的原因。**

所以这条的真正工作量不在"接个转换器",而在**保证生成 pptx/docx 时只用目标机器上装了的字体**,
或者把字体一起打包。要不要上 Docker(Gotenberg)取决于演示机器 ——
本机装 LibreOffice 最简单,但字体得对齐。

---

## 四、剩下七条的方案(**这些还没动,等你确认**)

调研之后,原方案里的工作量分布变了不少 —— 第 4 条从"最大"掉到"最小之一",
第 7 条砍掉一大半,反而 Instagram 和 Zoho 因为不能用第三方包而变成要自己写。

### 4.1 交易所模拟盘(第 7 条)

**加密货币走 ccxt,美股走 Alpaca 官方 MCP。** 不再自己包 Binance/OKX 的 SDK。

- ccxt:装依赖 + 一个薄工具层(行情/下单/持仓/订单),`set_sandbox_mode(True)` 切沙盒
- Alpaca:接官方 MCP,`ALPACA_PAPER_TRADE=true`

原先我担心的 OKX(demo 靠请求头切换、和真实 key 共用)由 ccxt 内部处理掉了,
所以**三家可以都上**,不用像原方案那样砍掉 OKX。

仍然建议加一条硬闸:**没显式打开实盘开关时,任何指向主网的下单直接拒绝** ——
不依赖"配置有没有配对",而是代码层面拒绝。ccxt 让切换变得太容易了,这个闸更有必要。

### 4.2 域名购买 + 自动接站(第 4 条)

**接 Cloudflare 官方 MCP,不自己写注册商工具。**

它三个工具(`docs` / `search` / `execute`)就覆盖了注册、DNS、Workers 部署,
只占约 1100 tokens 上下文。剩下的活是把它和现有的
`optional-skills/web-development/cloudflare-temporary-deploy` 串成
"生成站点 → 部署 → 绑定刚买的域名"。

> **需要你确认**:演示预算(一个 `.com` 约 US$10/年),
> 以及是否接受"真花钱下单"这一步现场发生。买域名建议加二次确认。

### 4.3 Instagram 发布(第 2 条)—— 自己写

X 已有 `skills/social-media/xurl`,直接可用。Instagram 自己写一个 skill(理由见 3.4)。

走 Instagram Graph API,需要:
- Instagram **Business/Creator** 账号(个人号发不了,Meta 的硬限制)
- 绑定一个 Facebook 主页
- Meta 开发者应用 + 长期 access token

发视频是两步:`POST /media` 建容器(要轮询容器状态),再 `POST /media_publish`。
视频必须是**公网可访问的 URL**,不能传本地文件 —— 正好用 4.2 的 Cloudflare 链路托管。

> **需要你提供**:IG 账号类型确认 + Meta 应用凭据。
> 拿不到的话这条只能做成"片子和文案都备好,最后一步人工点发布"。

### 4.4 Zoho(第 5 条)—— 自己写

Xero 和 QuickBooks 已有 skill(`SKILL.md` 形式,OAuth + REST),Zoho 照抄这个形态。
第三方 MCP 不用(理由见 3.4)。

Telegram / WhatsApp 通道 `plugins/platforms/` 下都有,不用新做 ——
"在 Telegram 里问一句就查到账"是把已有通道和会计 skill 接起来。

> **需要你确认**:Zoho **Books** 还是 **CRM**?两者 API 完全不同,这个不定我没法开工。
> 三家会计软件是都要,还是挑一家做深?

### 4.5 PPT/Word + PDF 双交付(第 3 条)

`skills/productivity/` 下 `powerpoint`、`docx`、`xlsx`、`pdf`、`nano-pdf` 都在,生成不缺。
缺的是"**永远同时给两份,且 PDF 不变形**"。

做法:加一个本地转换工具走 headless LibreOffice(`soffice --convert-to pdf`),
再把双交付写进 skill 的产出约定。

**真正的坑是字体**(见 3.6):LibreOffice 靠已装字体算分页,字体缺失就是版式错位的头号原因。
所以这条要额外做一件事 —— **约束生成时只用目标机器上确实有的字体**。
不做这一步,转出来的 PDF 照样会变形,等于没解决客户的问题。

### 4.6 网站与仪表盘(第 6 条)

`optional-skills/web-development/` 有 `cloudflare-temporary-deploy` 和 `page-agent`,
配合 4.2 就完整了。不用新造轮子,主要是把链路串顺。

### 4.7 每日 cron(第 8 条)

`cron/` 框架完整,`blueprint_catalog.py` 里已有 `briefing`、`digest`、`bill-renewal-watch`
这类模板。加两个 blueprint(新闻摘要、竞品监控)即可,工作量很小。

---

## 五、我建议补的两条(客户第 9 条"其他")

1. **成本与用量看板** —— 演示 agent 干活的同时实时显示 token 花费和耗时。
   企业客户第一个问的永远是"这玩意一个月烧多少钱"。仓库里已有 `AnalyticsPage.tsx`
   和 session cost 统计,拼起来即可。

2. **失败与人工接管的演示** —— 故意让一个子任务失败,展示红色 "!" + 自动重试 +
   转人工确认。全程无失误反而像录播;看到它出错并恢复,可信度高得多。
   底座已经有了(2.1 的 `error` / `retry` 特效)。

---

## 六、修订后的优先级建议

调研之后顺序变了 —— 域名从最后提到了前面,因为它现在是接一个官方 MCP 而不是从零写:

| 顺序 | 条目 | 理由 |
|---|---|---|
| 1 | 交易所(ccxt + Alpaca MCP) | 现成方案最成熟,效果最惊艳 |
| 2 | 域名 + 建站(Cloudflare MCP) | 官方 MCP,工作量比原估小一个量级 |
| 3 | PDF 双交付 | 工作量小,但字体那步别省 |
| 4 | cron blueprint | 最小 |
| 5 | Instagram | 要自己写,且卡账号凭据 |
| 6 | Zoho | 要自己写,且要先定 Books/CRM |

---

## 七、要你拍板的六件事

1. **分支上已做的两件留不留**(动画办公室 + 视频剪辑)?
2. **是否接受引入三个外部依赖**:ccxt(pip)、Alpaca 官方 MCP、Cloudflare 官方 MCP。
   按仓库自己的 MCP 目录政策,进 `optional-mcps/` 要走 PR + 钉死版本 + 发布满两周。
3. **是否认同 Instagram / Zoho 自己写**(不用第三方 MCP)—— 我的理由是不该把长期
   access token 交给来路不明的 npm 包,但这会多花时间,你可以推翻。
4. **凭据**:Meta 应用、Cloudflare、Zoho、Alpaca paper、Binance/OKX testnet ——
   哪些能给到?拿不到的我就做成"到最后一步停下等人工"。
5. **Zoho 是 Books 还是 CRM**;三家会计软件都要还是挑一家做深。
6. **交易所是否接受"默认拒绝主网下单"的硬闸**;买域名是否接受现场真花钱。

确认后我按 CLAUDE.md 的门禁逐条实现:每条单独跑全量 + 开 PR + 等 CI 全绿再合。

---

## 八、实施进度记录(持续更新)

### 2026-08-03

#### 第 7 条 · 交易所模拟盘 —— ✅ 完成并真机验证

- 加密货币:新工具 `crypto_exchange`(`tools/crypto_exchange_tool.py`),ccxt 统一 API,
  binance + okx,7 个操作(ticker/balance/create_order/open_orders/order_status/cancel_order/positions)。
  **硬闸已实现**:默认一律 `set_sandbox_mode(True)`;打主网必须双重开启
  (`KOPI_EXCHANGE_ALLOW_MAINNET=true` 环境变量 **且** 调用传 `live:true`),缺一即在
  创建 client 之前代码级拒绝。12 个单测锁住闸门行为。
- ccxt 钉 **4.5.64** —— ⚠️ 4.5.65 起上游把全部传递依赖精确钉死(certifi/setuptools),
  与我们核心钉版本无解冲突;升级前先看 ccxt 的 requires_dist(pyproject 里有 ceiling 注释)。
- 美股:Alpaca **官方** MCP 进目录(`optional-mcps/alpaca/manifest.yaml`,
  `alpaca-mcp-server==2.1.1`,manifest 强制 `ALPACA_PAPER_TRADE=true`)。
- 真机验证:Binance testnet 完整回路(鉴权→限价单→查单→撤单,含价格带过滤器的
  错误透传);Alpaca paper 经 MCP 握手 69 工具,`get_account_info` 返回真实 paper 账户。
- 凭据:Binance testnet + Alpaca paper key 已配入 `~/.kopi/.env`;**OKX 暂缓**(用户定)。

#### 第 1 条 · 视频剪辑 —— ✅ 五操作全部真机验证,并修掉一个真 bug

- probe/concat/trim/add_audio 直接通过;**caption 在演示机上原本是坏的**:
  Homebrew ffmpeg 8.x 不带 libfreetype,无 `drawtext` 滤镜。
- 修复:运行时探测 drawtext;缺失时用 Pillow(已是核心依赖)渲染字幕 PNG +
  内置 `overlay` 滤镜合成。字体按文字内容选择(含 CJK 时优先苹方/冬青黑/Noto CJK),
  修掉了中文字幕豆腐块问题。中英文均抽帧目检通过。新增 5 个单测
  (`tests/tools/test_video_edit_tool.py`)。

#### 第 1 条 · 视频生成 —— ⚠️ 阻塞在 provider key,等拍板

- 工具与三个插件(fal/xai/deepinfra)都在,但本机无任何 provider key
  (`FAL_KEY` 在 .env 里是注释状态)。
- 查证:kopiaiagent.com 网关 **没有视频模型**(71 个模型里只有 3 个图像模型;
  上游 mimo/deepseek/openrouter/agnes 均不出视频)。
- 两条路等定:**A. 配 FAL/XAI key**(现成插件,推荐,演示走这条);
  **B. kopi-proxy 加视频上游**(异步 job 路由 + 计费落库,是 proxy 仓库的独立项目,
  排在演示之后)。

#### 第 1/4 条 · 动画办公室 —— ✅ 代码层完成,真实链路验证通过

- 7 个单测全过;另做了一次不 mock 的落盘验证:交办→完成后,快照文件里父 agent 的
  fx 序列为 `handoff → speak(交办内容) → done → speak(结果摘要)`,与设计一致。
- 剩余:浏览器内动画目检(演示彩排时顺手确认即可)。

#### 第 2 条 · Instagram —— ✅ 代码完成,卡 Meta 凭据

- 自写 skill(`skills/social-media/instagram/`,理由见 3.4):纯标准库脚本走官方
  Graph API 容器协议(建容器→轮询→发布),image/reel/carousel + whoami/quota/status,
  `--no-publish` 即"备好人工点发布"模式。9 个测试(urllib 层伪造),token 不泄漏有专测。
- 待用户提供:Business/Creator 账号 + Meta 应用 + 长期 token(SKILL.md 有步骤)。

#### 第 3 条 · PPT/Word + PDF 双交付 —— ✅ 完成并真机验证

- 现状核实:soffice 包装器和 PDF 渲染 QA 本来就在(powerpoint/docx/xlsx 三个 skill),
  真正缺的是"强制双交付"和"字体不变形的把关"。
- 新增 `scripts/deliver_pdf.py`(powerpoint + docx 各一份,有测试锁两份不漂移):
  转换后读取 PDF **实际内嵌字体**,把每个源字体判为 kept / metric-safe
  (Calibri→Carlito 等同宽度替换,版式不动)/ **risky**(不同宽度替换,会重排)。
  比"检查字体装没装"更真实 —— 验证的是转换实际发生了什么。
- SKILL.md(powerpoint + docx)新增 MANDATORY 双交付章节:交付必须两份文件,
  verdict 是 check_layout 时必须换安全字体或装字体重转,禁止静默交付重排的 PDF。
- 真机 e2e:合成 docx(Calibri + 不存在字体)→ LibreOffice 转换 →
  Calibri 判 metric-safe、假字体判 risky 并给修复指引。8 个测试全过。

#### 其他

- kopi CLI 的 `KOPI_API_KEY` 失效问题已解决(经 `/v1/auto-provision/ready` 领新 key,
  10M tokens;用户提供的两个 key 在服务端不存在,第三个是复制截断)。
- 提交状态:动画办公室 + 视频剪辑 + 本文档已在 `feat/demo-capabilities` 提交
  (`c5ada659`);crypto_exchange 一批与 caption 修复**尚未提交**,等用户测试确认。
