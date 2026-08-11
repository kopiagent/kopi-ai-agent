# 品牌改名审计：剩余 "Nous" 用户可见字符串分类（2026-08-10）

> 目的：为「1.23.0 要不要带品牌修复发版」提供决策依据，并作为文档
> `pending-product-decisions.md` §5（品牌显示名单一来源）的执行清单。
>
> 背景：PR #47 已把 `feat/demo-capabilities` 的两个品牌 commit（`ea46405b` + `50d65583`）
> cherry-pick 进 main，覆盖 **26 个文件**。本审计回答的是「剩下还有多少、哪些该改」。
> 结论：**还有约 150 处用户可见串**，分布在 ~40 个文件。

## 判据（沿用两个品牌 commit 的作者规则）

- 内部 slug `nous` 是**继承来的命名空间 ID**，代码里保留（`provider="nous"`、`NOUS_*` 环境变量、
  `is_nous`、`kopi auth add nous` 等一律不动）。
- 但本 fork 里该 provider **指向 KOPI 自己的网关**（`auth.py:80-81` 两个默认端点都是
  `kopiaiagent.com`），所以它的**用户可见显示名**应为 KOPI 品牌。
- 对**真实上游 NousResearch** 的公司/服务/主机引用（allowlist、向后兼容、真模型族）**保留**。

---

## 🔴 T1 — 阻断级：产品自称是别家做的（4 处字符串，改动极小）

一个叫 Kopi 的产品，用户问「你是谁」会答「我是 Nous Research 造的」。这是**系统提示词**，
不是边角文案。

| file:line | 当前串 |
|---|---|
| `kopi_cli/default_soul.py:4` | `"You are Kopi Agent, an intelligent AI assistant created by Nous Research. "` —— **首次运行写进每个用户的 `SOUL.md`** |
| `agent/prompt_builder.py:145` | 同串，`DEFAULT_AGENT_IDENTITY` |
| `agent/prompt_builder.py:155` | `"You run on Kopi Agent (by Nous Research). ..."` |
| `docker/SOUL.md:1` | 同串（容器镜像） |

⚠️ **联动陷阱**：`agent/anthropic_adapter.py:2906` 有
`text = text.replace("Nous Research", "Anthropic")`，在给 Anthropic OAuth 线路消毒系统提示词。
改了上面的 identity 串，**这行消毒会失效**，新品牌串将未经处理地发上线。必须同批处理。

**同级对外署名**：

| file:line | 当前串 | 影响 |
|---|---|---|
| `pyproject.toml:16` | `authors = [{ name = "Nous Research" }]` | **PyPI 页面上的包作者** |
| `kopi_cli/banner.py:653` | `[dim]Nous Research[/]` | 每次启动 CLI 的落款（MoA 分支） |
| `kopi_cli/banner.py:670` | 同上 | 落款（普通模型分支） |
| `web/src/i18n/ar.ts:58` | `org: "Nous Research"` | **纯漏网**：其它所有语言均为 `"Kopi Ai Agent"` |

---

## 🟠 T2 — 商业级：注册/付费出口指向第三方

不是文案问题，是**在售流程里的错误出口** —— 让用户去第三方站点为我们的服务付费。

| file:line | 当前值 |
|---|---|
| `kopi_cli/portal_cli.py:30` | `SUBSCRIPTION_URL = "https://portal.nousresearch.com/manage-subscription"` |
| `kopi_cli/portal_cli.py:61` | `print(f"  Sign up: {SUBSCRIPTION_URL}")` |
| `kopi_cli/portal_cli.py:109` | `_cmd_open` —— **真的 `webbrowser.open()` 打开它** |
| `kopi_cli/portal_cli.py:166` | `"  Manage your subscription: {SUBSCRIPTION_URL}"` |
| `kopi_cli/portal_cli.py:29` | `DEFAULT_PORTAL_URL = "https://portal.nousresearch.com"`（`:55` 直接打印给用户） |
| `kopi_cli/setup.py:3192` | `"Sign up: https://portal.nousresearch.com/manage-subscription"` —— 就在 `print_header("Kopi Official")` **下面第 3 行** |
| `kopi_cli/setup.py:2891` | 同类注册 URL |
| `kopi_cli/portal_cli.py:31` | `DOCS_URL = "https://kopi-ai-agent.nousresearch.com/docs/..."` —— 半改名产物，**该域名不存在** |

而订阅/账单/权益的真实后端是 `kopiaiagent.com/portal`（`nous_billing.py:35`、`nous_account.py:135`）。
即：**出口与后端不一致**。

> 关联：这就是 `pending-product-decisions.md` §1 里那 3 处注册 URL + 5 处文档站链接。
> 之前判定「卡在 Kopi-Web 无生产域名」—— 本审计认为它比「待办」更严重，是在售缺陷。

---

## ⚖️ T3 — 需要商业/法务判定，代码里看不出来

**刷卡授权文案的收单主体**：

| file:line | 当前串 |
|---|---|
| `ui-tui/src/components/billingOverlay.tsx:488` | `By confirming, you allow Nous Research to charge your card.` |
| `ui-tui/src/components/billingOverlay.tsx:890` | `By confirming, you authorize Nous Research to charge {card} whenever...` |
| `kopi_cli/cli_billing_mixin.py:1210` | 同文案（CLI 版） |
| `kopi_cli/cli_billing_mixin.py:1580` | 同上 |

两份独立取证在这条上**结论相反**：一份认为该改（扣款请求打的是 `kopiaiagent.com/portal/api/billing/charge`），
一份认为保留（Nous 是真实 merchant of record）。

**这取决于谁是 Stripe 的收单主体，是商业事实而非代码事实。** 若实际收单方是
Kopi Ai Agent Pte Ltd 而文案写 Nous Research，则是**支付授权页上的主体错述**。
需人工确认后再动。

同类待定：**"Nous Tool Gateway"**（`status.py:347,369` 等 ~14 处）。传输层确实是上游托管
（`tools/managed_tool_gateway.py:18` → `*-gateway.nousresearch.com`），但权益与账单是 KOPI 的。
一份取证判 KEEP、一份判 RENAME —— 属产品品牌判断，需拍板。

---

## 🟡 T4 — 面广但机械（建议走 §5 单一来源重构）

| 簇 | 量 | 关键注意 |
|---|---|---|
| `Nous Portal` 用户可见串 | **~100 处 / ~25 文件** | 取证结论：**没有一处是真上游引用**，全部该改。高可见：`cli_billing_mixin.py:172,831`、`portal_cli.py:50,88,147,156`、`model_setup_flows.py:421,617`、`doctor.py:1382,1384`、`nous_billing.py:234`、`auth.py:5846,6191`、`cli_agent_setup_mixin.py:235` |
| `Nous Subscription` | **~50 处** | 是 **KOPI 自己的产品**（账单打 kopiaiagent.com）。⚠️ 其中 **6 处是跨端 wire value**（`tools_config.py:334,427,500,535,555,632`）—— desktop 回传、server 匹配、6+ 测试断言，改必须三端同步 |
| `Nous-approved MCPs` | 5 处 | 目录是本仓 `optional-mcps/`，是我们的。`McpPage.tsx:755`、`mcp_config.py:1123`、`subcommands/mcp.py:114`、`tips.py:230,231` |
| "official skills from Nous Research" | 3 处 | `skills_hub.py:431,702`、`web_server.py:13489`。是我们 bundled 的 |
| UI 主题 `nous-blue` / `nous` | 2 套 | ⚠️ **是持久化值**（localStorage `kopi-dashboard-theme` / `kopi-desktop-theme-v2` + config `dashboard.theme`）。直接改会让老用户主题静默丢失 —— 必须加 `THEME_NAME_ALIASES`（`web/src/themes/context.tsx:50`）/ `RETIRED_SKINS` 迁移项 |
| desktop provider 卡片描述 | 1 处 | `apps/desktop/src/app/settings/constants.ts:45` —— 卡片名已是 `KOPI Proxy`，描述仍写 `Nous-trained models` |
| `subcommands/model.py` argparse help | 8 处 | `:29,33,38,41,46,52,55,60` "Nous login" / "Nous TLS verification" |

**其它已知不一致**（同一功能两处品牌打架，改哪边都要成对）：
- `subscription.ts:145` help 说 "Nous subscription"，同文件 `:159` 已是 "Kopi Official"
- `status.py:347` 打印 "◆ Nous Tool Gateway"，下一行已是 "Kopi Official"
- `billingDialog.ts:23-24`（ui-tui）说 "Nous credits"，而 desktop i18n 已是 "KOPI credits"
- `conversation_loop.py:5219` 说 "Nous Portal OAuth token"，`:5222` 已打印 `kopiaiagent.com/portal`

---

## ✅ 确认保留（真上游引用）

| 项 | 位置 | 理由 |
|---|---|---|
| auth allowlist 主机 | `auth.py:2193-2231` | 向后兼容既有登录，不渲染给用户 |
| `kopi debug share --nous` | `subcommands/debug.py:33,83-87`、`debug.py:1041` | 真的上传到 Nous 的 S3，仅 Nous 员工可看，措辞准确 |
| "Nous Research Kopi 3 & 4 models are NOT agentic" | `cli.py:7271`、`model_switch.py:207`、`agent_init.py:2557` | 真实的 Nous 托管模型族 |
| `_DEFAULT_TOOL_GATEWAY_DOMAIN = "nousresearch.com"` | `tools/managed_tool_gateway.py:18` | 真实 infra 默认值，非展示名 |
| `plugins/dashboard_auth/nous` `display_name = "Nous Research"` | `:157` | OAuth provider 确实是 Nous |
| 凭据厂商列举 | `security_advisories.py:118`、`model_setup_flows.py:2771`、`vision_tools.py:1424` | 是"厂商清单"里的一项 |
| 所有 `NOUS_*` / `provider="nous"` / `is_nous` 等标识符 | 全仓 | 命名空间 ID，按规则保留 |

---

## 对 1.23.0 的建议

1. **合 #47**（已 36 pass / 0 fail）。
2. **单独小 PR 只修 T1**（4 处 identity + `anthropic_adapter` 消毒联动 + PyPI author + banner ×2 +
   `ar.ts`）—— 约 7 个文件，半天量级，风险低、收益最高。
3. **发 1.23.0**。
4. T2 商业出口：需 Kopi-Web 生产域名（`pending-product-decisions.md` §1a 清单 #2）。
5. T3：需你/法务确认收单主体与 Tool Gateway 品牌归属。
6. T4：作为 §5 单一来源重构独立排期 —— **不要手工逐串改**，
   ~150 处 + 跨端 wire value + 持久化主题键，正是 §5 说的「要在十八个地方改才能保持绿色，
   这本身才是缺陷」。

---

## 方法论备注

本审计由三个并行取证任务产出，覆盖 Python / TypeScript / TSX / web / plugins / 配置。
已排除：代码注释、docstring、变量名/函数名、测试文件、`node_modules`。
TypeScript 侧结论：`ui-tui/src`、`web/src`、`apps/desktop/src` 中**剩余的 Nous 命中全是注释**，
用户可见串只剩本文列出的几处。
