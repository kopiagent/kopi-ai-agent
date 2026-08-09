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

**候选方案**（当时给过，未决）：

| 方案 | 代价 |
|---|---|
| A. 默认绑 `127.0.0.1` | 开箱仍可用（端口映射可达），但改变现有部署方式 |
| B. tier 3 改为首启生成随机口令并打到启动日志 | 消除共享口令，仍开箱可用；很多镜像的通行做法 |
| C. 保持现状，只文档警示 | 零改动；暴露面照旧 |

**测试牵连**：`tests/docker/test_dashboard.py` 已按"provider 永远存在"改写
（4c277213），方案 A/B 落地时它的三条断言需要同步审一遍。

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

**未解决的**：约 **28 个 spec 在 CI 上失败**。机制已实测定案：

> 每次测试失败后 Playwright 丢弃 worker，重建一次付 60–90 秒编排开销
> （worker index 在 2 并发配置下涨到 23；新进程本身 1.0s 起来）。
> 我们可控的全部阶段合计 ~2.5 分钟；其余 ~33 分钟全是这个乘法。
> **失败数量是根，超时是果** —— 修 spec 是唯一根治。

**已知的真 bug（起点）**：

- ✅ 已定性并立案 **#41**：resume 一个带在途后台推理的会话时，**整个先前历史
  从 transcript 消失**，只渲染在途回合（数据无损 —— SessionDB 直接探得全部
  54 行；首次打开正常渲染 —— 是 live-session resume 路径的缺陷）。两个测试
  变体已标 `test.fixme` 引用 #41，止住每轮 ~3 分钟的失败烧耗；修复归后端
  `session.resume` 快路径（线索与排除项全在 issue 里）
- `interim-messages.spec.ts:190` — flag OFF 分支，本地也失败（尚未定性）

**顺序约束**：

1. 修 spec → 失败数降 → worker 重建随之降 → 套件自然回到 ~15 分钟内
2. 基线策略二选一：**提交进仓库**（可 review、本地可用；需删 `.gitignore:67`
   的 `*-snapshots/`）或维持缓存方案（已修好但依旧不可见）
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
