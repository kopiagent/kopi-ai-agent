# KOPI 网关成为默认 provider（`kopi` + `bill.kopiagent.ai`）

> 2026-08-22。落地依据：Kopi-Web 的 [`给引擎侧-provider默认值说明.md`](../../Kopi-Web/docs/engineering/给引擎侧-provider默认值说明.md)
> （SaaS 侧在销售演示环境实测出的问题）+ 网关仓
> `~/1_code/kopi-proxy/Kopi-TokenMax/docs/ops/OPERATIONS.md`（模型清单、真实域名）。
> 本次采纳该文档的**方向 B**（规范名改成 `kopi`），并先解决它 §4 指出的前置缺陷。

## 1. 改了什么

| # | 位置 | 改动 |
|---|---|---|
| 1 | `plugins/model-providers/kopi-proxy/__init__.py` | `ProviderProfile.name` `kopi-proxy` → **`kopi`**；`kopi-proxy` / `kopi_proxy` / `kopiaiagent` / `kopiagent` / `KOPI Proxy` 降级为 alias；加 `display_name="Kopi Official"`、`description`；`env_vars` 增加 `KOPI_API_KEY`（配置模板插值的就是它）；新增 `fallback_models`（11 个 `kopi-*`）|
| 2 | `kopi_cli/providers.py` | 新增 `KOPI_OVERLAYS["kopi"]`（**这一条是 `/model` 能切过去的关键**）、`ALIASES` 五个别名、`_LABEL_OVERRIDES["kopi"]="Kopi Official"` |
| 3 | `kopi_cli/providers.py` `resolve_provider_full()` | sibling-collapse 判定从「注册表 key 计数」改成「**distinct provider id** 计数」 |
| 4 | `kopi_cli/models.py` | `_KOPI_LOCKED_SLUGS = {"kopi", "kopi-proxy"}`；`_PROVIDER_ALIASES` 加四个别名 |
| 5 | `cli-config.yaml.example` | `provider: "custom"` → **`"kopi"`**；`base_url: kopiaiagent.com/v2` → **`https://bill.kopiagent.ai/v1`**；模型注释换成网关实际在卖的 11 个名字 |
| 6 | `tests/kopi_cli/test_kopi_provider_gateway.py` | 18 项，覆盖两套解析体系 + 别名 + 标签 + 离线模型表 + 切换回归 + 模板默认值 |

### 为什么第 2 条是关键（SaaS 文档 §4 的根因）

引擎有**两套互不相通**的 provider 解析：

- **列表侧**：`providers/` 插件注册表 → `kopi status`、`kopi model` / `/model` 的候选列表、
  `provider_catalog()`。它只认插件。
- **切换侧**：`kopi_cli/providers.py` 的 `resolve_provider_full()` → `get_provider()`
  （`model_switch.py:1297` PATH A）。它**只认** `KOPI_OVERLAYS` + models.dev + config.yaml 的
  `providers:` / `custom_providers:`，**看不见插件注册表**。

结果是：我们只卖一个 provider，它出现在选单里，选下去就报
`Unknown provider 'kopi-proxy'`（`model_switch.py:1306`）。之前没暴露，只因为默认值一直是
`custom`——`custom` 在 `main.py` 有显式特判，绕开了这段判断。

本次没有去做「让切换侧也去查插件注册表」这种大改（见 §4 遗留 ①），而是**在 overlay 里补了一条
同名 provider**，两侧对齐。代价：`kopi` 的 id / base_url / env 变量现在写在两处，必须同步改 ——
两处都有互指的注释，测试 `test_resolve_provider_full_accepts_every_kopi_spelling` 会在漂移时红。

### 第 3 条为什么必须改

`resolve_provider_full()` 有一段「精确 id 优先于 lossy alias 折叠」的逻辑，判据是
「有多少注册表 key 折叠到同一 canonical 名」。插件是**按 alias 逐条注册**的
（`kopi` / `kopi-proxy` / `kopi_proxy` / `kopiaiagent` / `kopiagent` 五条，`id` 全是 `kopi`），
于是这段逻辑把「同一个 provider 的五个别名」误判成「五个 provider 撞名」，走 auth-registry 分支
返回，**丢掉 `base_url_env_var`** —— 表现是 `provider: kopi-proxy` 的实例 `KOPI_PROXY_BASE_URL`
不生效、静默落回生产网关。改成按 distinct `id` 计数后，真正需要区分的
`kimi-coding` / `kimi-coding-cn` 仍然分开（有测试守）。

## 2. 默认端点

`https://bill.kopiagent.ai/v1`（Kopi TokenMax，OpenAI 兼容）。旧默认 `kopiaiagent.com`
按网关侧文档**已不再提供推理**，留着等于让每个新装实例指向一个死地址。

模型名取自网关 `OPERATIONS.md`（2026-08-22 全量实测的 11 个对外名）：
`kopi-o`、`kopi-siew-dai`、`kopi-o-flash`、`kopi-siew-dai-flash`、`kopi-flash`、
`kopi-grok-4.5`、`kopi-grok-4.3`、`kopi-grok-4.20-0309-reasoning`、
`kopi-free-{1-120B,2-20B,3-llama70B}`。**权威清单永远是 `GET <base_url>/models`**，
`fallback_models` 只是没 key / 没网时选单不为空的兜底。

## 3. 🔴 验证缺口（必须知道，不要当成验过了）

**本机 clash 的 fake-IP DNS 让「真连一次网关」这件事做不到**：
`socket.gethostbyname('bill.kopiagent.ai')` → `198.18.0.192`（判据见 `CLAUDE.md` §1）。
所以本次**没有**端到端实测过 `GET https://bill.kopiagent.ai/v1/models` 或一次真实 chat 调用。

已验证的是**解析与配置层**（全部本机实跑）：

- `resolve_provider_full()` 五种拼写都返回 `id=kopi` / `base_url=bill.kopiagent.ai/v1` / `base_url_env_var=KOPI_PROXY_BASE_URL`
- `auth.resolve_provider('kopi-proxy') == 'kopi'`
- `switch_model(..., explicit_provider='kopi'|'kopi-proxy')` → `success=True`（即 SaaS 文档 §4 那条报错的回归）
- 无 key 时 `provider_model_ids('kopi')` 返回 11 个名字（选单不空）
- `CANONICAL_PROVIDERS` 锁后仍含 `kopi`，标签是 `KOPI Gateway` 而不是裸 slug
- 全量两轮：`27124 passed / 31 failed` → **`27126 passed / 30 failed`**（差值 = 修掉的
  1 个真回归 + 新增 1 条守卫测试）。剩下 20 个失败文件全部在 `origin/main` worktree 上
  逐字复现 = 既有环境噪音

### 踩到的坑：标签不能撞车（本次唯一的真回归）

`Kopi Official` 这个名字**已经属于 `nous` provider**（Portal/OAuth、
`plugins/image_gen/openrouter`、`web/src/pages/EnvPage.tsx`）。给我们的 provider 复用它
→ 选单里两行同名 → `model_catalog.excluded_providers` 按标签排除时**两个都排不掉**
（`tests/kopi_cli/test_model_picker_excluded_providers.py` 抓到）。现用 `KOPI Gateway`。

第二层更隐蔽：**CLI 选单渲染插件 provider 的行时只用 `description`，不用 label**
（`kopi_cli/models.py` 的 auto-extend 把 `description` 存进 `tui_desc`）。description
里不含标签，那一行就"按标签找不到"，排除同样失效。所以 description 必须以 display_name
开头 —— 有 `test_picker_row_is_findable_by_label` 守着。

**判据（下一个人怎么补上这个缺口）**：在无代理环境（关 clash，或在实例 pod 内）跑
`curl -s -H "Authorization: Bearer $KOPI_API_KEY" https://bill.kopiagent.ai/v1/models | jq '.data[].id'`，
数量应为 11 且与 `fallback_models` 对齐；再在实例里 `/model kopi-o-flash` 看是否真的切过去并能对话。

## 4. 遗留问题（本次刻意没做）

1. **两套 provider 解析体系仍未打通。** 只是让 `kopi` 在两边都存在，机制本身没合并。
   证据：`kopi_cli/providers.py` 的 `get_provider()` 只查 `KOPI_OVERLAYS` + models.dev；
   `providers/__init__.py` 的 `_REGISTRY` 在它视野外。
   为什么没做：真正的修法（让 `get_provider()` 回落查插件注册表）会改变**所有**插件 provider
   的解析行为，属于独立改动，需要单独跑全量 + 想清楚优先级（插件 vs models.dev 谁赢）。
   判据：`grep -n "get_provider_profile" kopi_cli/providers.py` 仍为空 = 这条还成立。
2. **余额 / 充值面没跟着改（本次范围只到推理面，用户明确划的界）。**
   - `kopi_cli/kopi_balance.py:44` `DEFAULT_KOPI_BASE_URL` 仍是 `https://kopiaiagent.com/v1`；
     `is_kopi_proxy_base()`（`:335`）按 `kopiaiagent.com` 主机名判定，新网关只能靠它第二条
     「与 `_resolve_kopi_credentials()` 解析出的 base 同主机」命中 —— 也就是**依赖实例真的设了
     `KOPI_PROXY_BASE_URL`**，没设就判不出来。
   - 网关的余额路径是 `GET /kopi/usage/balance`（网关 `OPERATIONS.md`），与旧 `/v1/balance` **形状不同**，
     所以这不是改个域名的事，是换契约。
   - 判据：`grep -n "kopiaiagent" kopi_cli/kopi_balance.py`。
3. **`nous` overlay 与 OAuth 端点仍指旧域名**：`kopi_cli/providers.py` 的
   `KOPI_OVERLAYS["nous"].base_url_override` 与 `kopi_cli/auth.py:81` `DEFAULT_NOUS_INFERENCE_URL`
   都是 `https://kopiaiagent.com/v1`。它是 device-code OAuth 的 provider，不是我们卖的 api-key
   通路，且被 provider 锁挡在选单外；动它要连 OAuth 流程一起验。
   判据：`grep -rn "kopiaiagent.com/v1" kopi_cli/providers.py kopi_cli/auth.py`。
4. **安装脚本仍写旧域名**：`scripts/install.sh:1951`、`scripts/auto-provision.sh:13` 的
   `KOPI_PROXY_BASE_URL` 默认值。它们只在没有外部注入时生效；实例是由 SaaS 注入的，
   所以不在本次范围。判据：`grep -rn "kopiaiagent.com/v1" scripts/`。
5. **桌面端 onboarding 的 `id: 'kopi-proxy'`**（`apps/desktop/src/components/onboarding/index.tsx:79`）
   是 desktop 自己的 i18n key，不是后端 slug，本次故意没动（改了要连 i18n 与 vitest 一起改）。
   判据：该文件里 `t.onboarding.apiKeyOptions[option.id]` 仍按此 id 取文案。
6. **模型元数据缺失**：`website/static/api/model-catalog.json` 里没有 `kopi` 段
   （只有 `openrouter` / `nous`），所以选单里 `kopi-*` 没有上下文长度 / 价格。
   要补就往那份 manifest 加一个 `kopi` provider 块（含 `"default": true` 标记）。
   判据：`python3 -c "import json;print(list(json.load(open('website/static/api/model-catalog.json'))['providers']))"`。

## 5. 与 SaaS 侧的联动

- 网站**不需要**再注入 `provider`：镜像模板默认就是 `kopi`（SaaS 文档 §1 说的那个「只能引擎侧做」
  的口子已经关掉）。`05-model-base-url` 继续只改 `base_url`，行为不变。
- 存量实例的 `config.yaml` 里是 `provider: custom` 或 `kopi-proxy`：两者都仍然可用
  （`custom` 走原有特判，`kopi-proxy` 现在是 alias）。**要显示成 `Kopi Official` 必须换成 `kopi`
  或重新 seed 配置**，光换镜像不会改已存在的 config.yaml。
- 新镜像发布后建议网站侧顺手核对：`GET /v1/capabilities` 里的模型/provider 展示，以及控制台
  「接入 · 客户用的 API 地址」（SiteContent `api.endpoint`）是否也已切到 `bill.kopiagent.ai/v1`
  —— 引擎默认值改了，但那一处是网站的库里的值，不会自动跟。
