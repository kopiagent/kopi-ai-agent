# 产品待决事项（2026-08-10 整理）

> 这些是 v17 同步 + E2E 排查期间**发现但刻意没有顺手改**的事项 —— 每一项都改变
> 用户可见行为或对外暴露面，属于产品决策，不该夹在技术 PR 里。
> 每项自带证据指针（file:line / issue / CLAUDE.md 章节），按可直接开发的粒度写。
>
> 背景事实的唯一来源是本文档引用的位置；若与本文冲突，以代码现状为准。

---

## 1. 第三方 URL：用户会被导去谁的网站

**现状**：内置 provider 的显示名已全部改为 "Kopi Official"（56 处，
commit `50d65583`），默认端点已指向 `kopiaiagent.com`
（`kopi_cli/auth.py:80-81`）。但**硬编码的第三方 URL 仍在**，它们决定用户
在哪个网站注册、付费、看文档：

| URL | 处数 | 出口 |
|---|---|---|
| `portal.nousresearch.com/manage-subscription` | 3 | `kopi setup` 向导的注册引导（`kopi_cli/setup.py`） |
| `portal.nousresearch.com/billing` | 3 | 账单链接（`agent/billing_links.py` 一带） |
| `inference-api.nousresearch.com` | 7 | 默认值已迁走后的残留（注释/allowlist/兼容判断混杂） |
| `kopi-ai-agent.nousresearch.com` | 5+ | 文档站/安装站链接 —— CLAUDE.md §6.3 记录的半改名产物 |

**前置条件（硬性）**：改之前必须确认 `kopiaiagent.com` 上对应路径
（`/portal/manage-subscription`、`/portal/billing` 等）**真实存在**，
否则是把用户从"第三方页面"换成"我们的 404"。

**注意区分**：`auth.py:2234` 的 `inference-api.nousresearch.com` 在
**allowlist** 里（接受用户旧配置），`providers.py:681` 的
`{"nous","nous-portal","nousresearch"}` 是**输入归一化**——这两类是兼容逻辑，
不是品牌出口，**不要改**。

**做法建议**：一个 PR，逐 URL 给出去向决定；每处改动跑
`grep -rn 'nousresearch' tests/` 找配套断言一起改。

### 1a. 网关侧能提供什么（2026-08-10 对照 Kopi-TokenMax 核对）

> 证据来源：`/Users/zhaokunming/1_code/kopi-proxy/Kopi-TokenMax` 的
> `docs/OPERATIONS.md` §七（全部线上路径，2026-08-05 逐个实测）、
> `docs/SAAS_INTEGRATION.md`、`litellm/proxy/kopi_billing/router.py`。

**🔴 先于一切的发现：`kopiaiagent.com` 已下线。** 本 CLI 的默认端点
（`kopi_cli/auth.py:80-81`）指向它，但网关侧文档明确记载
"旧默认指向**已下线**的 kopiaiagent.com"（SAAS_INTEGRATION.md，SaaS 侧因此
删光了该域名的所有代码默认值）。真实生产网关是 **`https://bill.kopiagent.ai`**
（Let's Encrypt，2026-08-05 上线实测）。也就是说第 1 项的前置条件今天不成立
不止于"第三方 URL"——**我们自己的默认端点也是死的**（DNS/证书现状须核实）。
先决策：把 `kopiaiagent.com` 指到网关，还是 CLI 默认端点改成 `bill.kopiagent.ai`。

逐 URL 对照（网关今天真实存在、实测过的替代品）：

| 现硬编码 URL | 能否替代 | 网关/生态现状 |
|---|---|---|
| `inference-api.nousresearch.com` | ✅ 现成 | `https://bill.kopiagent.ai/v1`（OpenAI 兼容，流式/非流式实测 200；存量老 key 走 `/kp/v1`）。鉴权用 `kopi_` 前缀 virtual key；对外模型名 `kopi-o` / `kopi-siew-dai` / `kopi-o-flash` / `kopi-siew-dai-flash`（MiMo）+ 3 个 `kopi-grok-*`（2026-08-06 加），`GET /v1/models` 为准 |
| `portal.nousresearch.com/manage-subscription` | ⚠️ 只有 API，没有页面 | 网关有 `POST /kopi/subscribe/checkout`（客户 key + `price_id` → Stripe 订阅支付页 URL，router.py:204）；订阅入账/退款/争议/fair-use 上限均已实现（近期 commits）。但"查看/退订已有订阅"的**用户页面不存在**——退订目前是 SaaS 服务端调 `/kopi/admin/suspend` 的动作。页面归 Kopi-Web（本地 4002），**Kopi-Web 尚无生产域名** |
| `portal.nousresearch.com/billing` | ⚠️ 只有 API，没有页面 | 数据全齐且实测 200：`GET /kopi/usage/balance`、`GET /kopi/usage/summary?days=N`（客户 key，含日曲线/模型分布/充值记录）；充值 `POST /kopi/topup/checkout {"amount_usd": N}` → Stripe 支付页 URL（验签/入账/幂等全在网关）。账单**页面**同样归 Kopi-Web，无生产域名 |
| `kopi-ai-agent.nousresearch.com`（文档/安装站） | ❌ 不存在 | 网关只有 `/redoc`（API 文档，实测 200；注意 `/docs` 是 404）。产品文档站/安装站在整个生态里还没有 |

**对本仓库的直接推论：**

1. **TUI `/topup`（第 6 项提到的待验证项）今天就能接真后端**：用户自己的
   key 调 `POST /kopi/topup/checkout` 拿 Stripe URL 开浏览器即可，无需 admin
   权限。⚠️ 支付完成的回跳目前指向网关 `/ui/` 登录页（`KOPI_TOPUP_SUCCESS_URL`
   等 SaaS 有生产域名后才会改）——体验上要有预期。Stripe live key 已配置、
   checkout 已能创建 `cs_live_` session；按 OPERATIONS.md §二，仅剩一笔真卡
   付款验证服务端投递。
2. **`kopi setup` 的注册引导暂时没有可指的真实地址**：发卡是服务端动作
   （`POST /kopi/admin/provision`，admin token，终端用户不可直调），正确去向
   是 Kopi-Web 注册页（其服务端注册时调 provision 发 `kopi_` key）——而
   Kopi-Web 没有生产域名。结论：第 1 项里 setup.py 的 3 处注册 URL **现在改
   等于换成我们自己的 404**，被前置条件卡死，先解 Kopi-Web 域名。
3. billing_links.py 的 3 处账单链接同理被卡；但如果接受"CLI 内直接渲染余额/
   用量而不是丢一个网页链接"，`/kopi/usage/balance` + `/kopi/usage/summary`
   今天就够用（注意 spend 异步落账，调用后 10–15s 才可见）。
4. 网关另有管理面 MCP（`POST /kopi/mcp/`，7 tools，admin token）——那是运营
   侧工具，**不要**进 C 端 CLI。

---

## 2. Docker 镜像的默认安全姿态

**现状**（CLAUDE.md §6.4 已记录，2026-08-05）：

- `Dockerfile:398` — `ENV KOPI_DASHBOARD=1`（默认开启）
- `docker/s6-rc.d/dashboard/run:30` — `dash_host="${KOPI_DASHBOARD_HOST:-0.0.0.0}"`（默认公网绑定）
- `docker/cont-init.d/04-dashboard-auth` tier 3 — 口令回退 `kopi-admin`，
  **该镜像所有实例共享同一口令**（Dockerfile 注释自己承认 "SHARED across
  instances until changed"）

上游 2026-06 硬化堵的是"未认证的公开 dashboard"（起因是 kopi-0day
MCP-persistence 攻击活动）；我们的现状是"**公开可知口令保护的公开 dashboard**"。
镜像现已发布到 GHCR（虽然还是 private），一旦转 Public 这个面直接暴露。

**✅ 已定并实现（2026-08-10）：方案 B。** tier 3 从共享字面量 `kopi-admin`
改为首启生成每实例随机口令（`secrets.token_urlsafe(12)`），打进容器日志一次；
`.env` 只存 scrypt 哈希。tier 1（幂等）/ tier 2（env 注入）语义不变。

**方案 A 被否的原因**：portal 供给的实例依赖 `0.0.0.0` 绑定 + OAuth 门
（`test_dashboard_oauth_gate_engages_on_non_loopback_bind` 注释明写
"every portal-provisioned agent binds 0.0.0.0"），改绑 loopback 破坏产品
自己的部署模型。

行为守卫：`tests/docker/test_dashboard.py` 新增两个 tier-3 测试
（生成口令可验证哈希、重启只记录一次、env 注入压过生成、明文永不落盘）。

原候选方案存档：A. 默认绑 `127.0.0.1`（破坏 portal 部署）；
B. 首启随机口令（已采纳）；C. 保持现状仅文档警示。

---

## 3. GHCR 可见性 + 用户可见的 `docker pull` 提示

**现状**：镜像已发布 `ghcr.io/kopiagent/kopi-ai-agent:main` / `:latest`
（multi-arch manifest 验证过），但 package 是 **private**（匿名拉取 403）。

**改 Public 只能在网页操作** —— GitHub 的 packages REST API 没有改可见性的
端点（GET 200 / PATCH 404 / OPTIONS 无 PATCH，已验证）：
`https://github.com/orgs/kopiagent/packages/container/package/kopi-ai-agent`
→ Package settings → Danger Zone → Change visibility。

**转 Public 前建议先做第 2 项**（共享口令 + 0.0.0.0 的镜像公开可拉，
等于把已知口令的公开 dashboard 分发出去）。

**转 Public 后的配套改动**（一个 PR）：以下 4 处给用户看的 pull 命令仍指向
上游命名空间，今天就是错的（我们从未在那发布过），但改动牵连 **5 个测试文件**
断言这些字符串：

- `kopi_cli/config.py:548,583,589,595`（`docker pull nousresearch/kopi-ai-agent:latest` 等）
- `tools/browser_tool.py:410,1144,2492,4988`（`ghcr.io/nousresearch/...`）
- `kopi_cli/tools_config.py:1708`
- `docker-compose.windows.yml:14,25`（`nousresearch/kopi-agent:latest`）

配套测试：`tests/kopi_cli/test_doctor.py:33`、`tests/kopi_cli/test_web_server.py:2922,2931`、
`tests/kopi_cli/test_cmd_update_docker.py:45,77` 等（改前重新 grep 为准）。

---

## 4. Desktop E2E 变绿（#32）—— 唯一未解的技术主线

**已解决的部分**（全在 main）：

- 视觉基线冻结在 v1.21.1 → 缓存 key 按 sha 轮转（#34），基线可更新、可下载
- 本地不可跑（`ELECTRON_RUN_AS_NODE` 泄漏）→ 已修，本地 3.8 分钟跑全量
- 无诊断数据 → 后端日志 + 全链路计时齐备（#33/#35）
- 每 PR 白烧 45 分钟 → fail-fast 降回 20 分钟（#38）

**机制（已实测定案）**：

> 每次测试失败后 Playwright 丢弃 worker，重建一次付 60–90 秒编排开销
> （worker index 在 2 并发配置下涨到 23；新进程本身 1.0s 起来）。
> 我们可控的全部阶段合计 ~2.5 分钟；其余 ~33 分钟全是这个乘法。
> **失败数量是根，超时是果** —— 修 spec 是唯一根治。

**✅ 本地一侧已清零（2026-08-10）**：`npx playwright test e2e/` 在 main 上
**36 passed / 0 failed / 9 skipped，1.7 分钟**。逐个消化的结果：

- `worktree-branch-status:71` — **真 bug，已修（#43）**。测试硬编码
  `Control+Shift+B`，但 `mod` 在 macOS = Cmd（`combo.ts:118`），本地不触发、
  Linux CI 触发 —— 长期被误判为"git/macOS 差异"。按 `warm-resume-jitter:287`
  的先例改成平台判断。
- `large-session-resume` ×2 — **真后端 bug，fixme + 立案 #41**（见下）。
- `interim-messages:190` — **假警报**：本就绿（单跑 + 全量都过），早前"本地
  失败"记录已陈旧，无需动作。
- 9 skipped = #41 的 2 个 + `:198` 第三次重绘 fixme + 其余既有 skip。

**⚠️ 本地清零 ≠ CI 全绿**：本地只有 ~10 个 spec 会失败，CI 侧的失败集合更大
（视觉基线比对、Linux 特有时序 —— 本地跑不到）。下一步是**对比 CI 失败清单**：
本地已修的部分 CI 应同步减少，剩下的 CI 特有失败大概率是视觉基线（见下第 2 点）。

**已立案的真 bug**：

- **#41**：resume 一个带在途后台推理的会话时，**整个先前历史从 transcript
  消失**，只渲染在途回合（数据无损 —— SessionDB 直接探得全部 54 行；首次打开
  正常 —— 是 live-session resume 路径的缺陷）。2 个变体已 `test.fixme` 引用
  #41；修复归后端 `session.resume` 快路径（`_reuse_live_payload` →
  `_live_visible_history`，线索与探针盲区全在 issue 里）。

**顺序约束**：

1. ✅ 修 spec 降失败数 —— 本地已完成；CI 侧待对比后收尾
2. 基线策略二选一：**提交进仓库**（可 review、本地可用；需删 `.gitignore:67`
   的 `*-snapshots/`）或维持缓存方案（#34 已修好但依旧不可见）。这是 CI 特有
   失败的大头，本地根本触发不到
3. **最后**才把聚合器改成 `cancelled` 也阻塞（`ci.yml` 的
   `result == 'failure'` 判据，CLAUDE.md §3）—— 提前改会卡死所有 PR

---

## 5. 品牌显示名的单一来源（技术债，非紧急）

56 处替换、18 个文件才完成一次改名 —— commit `50d65583` 里写明：
**"要在十八个地方改才能保持绿色，这本身才是缺陷"**。
"Kopi Official" 现在仍散落在 Python / TS / 派生 JSON / 测试断言中。

**方向**：显示名收敛到单一常量（Python 侧一处 + 经 API 传给前端），
派生物（`model-catalog.json`）由 `scripts/build_model_catalog.py` 统一生成。
改动面广但机械，适合作为独立小 PR。

---

## 6. 运维遗留（非产品决策，勿丢）

- **`feat/demo-capabilities` 分支**：本地领先 23 commit（main 已合入 +
  品牌补齐 `50d65583`），**未推送** —— 等品牌文案人工验证
  （`kopi status` / `kopi setup` / TUI `/topup`）后推送
- **E2E 视觉基线两处待人工过目**（接受新基线前）：底部状态栏消失是
  `gateway-pill` 插件化的设计结果（已核实非回归）；onboarding overlay
  须确认仍只有 KOPI Agent 一项（v10 batch1 有被上游还原的前科，
  见 `.upstream-sync.json` conflict_policy）
