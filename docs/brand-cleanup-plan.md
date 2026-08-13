# "Nous Research" 清理执行方案（2026-08-11）

> 待批准的执行计划 —— **尚未动手**。批准后按 Step 顺序执行，每步一个独立 PR。
>
> 前置审计：[brand-rename-audit.md](brand-rename-audit.md)（那份是「应用内用户可见串」的分类，
> 本份是「全仓 `Nous Research` / `NousResearch` 861 处」的处置方案，范围更大且包含 `website/`）。

## 已定的命名规则（2026-08-11 拍板）

| 场合 | 用词 | 例 |
|---|---|---|
| **公司 / 法律主体 / 署名** | `Kopi Ai Agent Pte Ltd` | "created by Kopi Ai Agent Pte Ltd"、PyPI author |
| **产品名** | `Kopi Agent`（**不变**） | "You are Kopi Agent, an intelligent AI assistant…" |
| **紧凑 UI 落款** | `Kopi Ai Agent`（短名） | CLI banner 落款、web i18n footer `org` |
| **仓库路径** | `kopiagent/kopi-ai-agent` | clone URL、workflow 门控、issue 链接 |

⚠️ **产品名 ≠ 公司名。** `"created by Kopi Agent"` 读起来像产品自己造了自己 —— 署名场合一律用法定全称。

---

## 🔴 绝对不动的（先讲，避免误伤）

### 1. 版权 / 许可证声明 —— 4 处（2026-08-11 确认保留）

本项目 MIT（`pyproject.toml`），MIT 明文要求 *"The above copyright notice … shall be included
in all copies"*。这是**法律义务，不是品牌偏好**；改它等于剥离上游作者署名。

| file:line | 内容 |
|---|---|
| `LICENSE:3` | `Copyright (c) 2025 Nous Research` |
| `apps/bootstrap-installer/src-tauri/tauri.conf.json:40` | `"copyright": "Copyright © 2026 Nous Research"` |
| `apps/desktop/scripts/set-exe-identity.mjs:68` | `LegalCopyright: 'Copyright (c) 2026 Nous Research'` |
| `tests/agent/test_restore_primary_pool_reselect.py:1` | 文件头 Apache 声明 |

> 需要体现我方版权时**追加**一行（`Copyright (c) 2026 Kopi Ai Agent Pte Ltd`），
> **不替换**原有行。本方案不含此动作 —— 要做请单独提。

### 2. 真实语义引用 —— 7 处

改了会**表意错误或功能损坏**：

- `cli.py:7271`、`kopi_cli/model_switch.py:207`、`agent/agent_init.py:2557` ——
  "Nous Research Kopi 3 & 4 models are NOT agentic"（真实的 Nous 托管模型族警告）
- `plugins/dashboard_auth/nous/__init__.py:157` —— `display_name = "Nous Research"`
  （OAuth provider 真的是 Nous；登录按钮渲染 "Sign in with {display_name}"）
- `kopi_cli/auth.py:2193-2231` allowlist 主机（改了存量登录会挂）

### 3. 真上游仓库 —— 4 处

`NousResearch/hermes-agent` —— 那**确实是**上游仓库地址，保留。

---

## Step 0（已完成，等合并）—— 不含新工作

| 项 | 状态 |
|---|---|
| `fix/brand-legal-entity-name` 分支 | 代码完成，全量 **27109 passed / 30 failed（零新增）**；命名与本文规则一致 → **可直接开 PR** |
| PR #50（1.23.0 版本 bump） | required 全绿，**压着不合** —— 必须先合上面那个修复，再 rebase #50，否则 1.23.0 出厂带短名 |

**执行顺序**：开 PR → CI 绿 → 合 → `git rebase origin/main` #50 分支 → CI 绿 → 合 #50 → `git tag v1.23.0 && git push origin v1.23.0`。

---

## Step A —— 修「正在造成损害」的（最高优先，与命名无关）

这一步修的**不是文案，是坏掉的东西**。可以在任何命名决策之前独立执行。

### A-1. 三个 CI workflow 门控写错，job 从未运行过

```yaml
.github/workflows/deploy-site.yml:50             if: github.repository == 'NousResearch/kopi-agent'
.github/workflows/skills-index.yml:21            同
.github/workflows/skills-index-freshness.yml:21  同
```

本仓库是 `kopiagent/kopi-ai-agent` → 条件恒假 → **三个 job 从来没跑过**。
不报错、只显示 `skipping`，所以门禁全程无感。推论：**文档站可能从未部署过**，
skills 索引从未更新。属 CLAUDE.md §6.3 记录的失效模式（当时只修了 `docker.yml`）。

### 🔴 A-1 结论：**不改**（2026-08-11 查证后推翻原计划）

原计划是把三处门控改成 `kopiagent/kopi-ai-agent`。**查证后否决** —— 改了不是修复，
是把「静默跳过」变成「必然红」。三个 workflow 的前置设施在本 fork **全都不存在**：

| 前置 | 需要它的 workflow | 现状（2026-08-11 查 GitHub API） |
|---|---|---|
| `environment: github-pages` | `deploy-site` (deploy-docs) | ❌ 不存在（仓库只有 `gh-image`） |
| GitHub Pages 本身 | `deploy-site` | ❌ 未启用（`GET repos/…/pages` → 404） |
| `environment: trusted-automation` | `skills-index`、`skills-index-freshness` | ❌ 不存在 |
| `vars.APP_CLIENT_ID` | 三个都要 | ❌ 仓库 variables 为空 |
| `secrets.APP_PRIVATE_KEY` | 三个都要 | ❌ 仓库 secrets 为空 |
| `secrets.VERCEL_DEPLOY_HOOK` | `deploy-site` (deploy-vercel) | ❌ 无 |

CLAUDE.md §6.5 已记过这个失效模式：**不存在的 `environment` 会让 job 在启动阶段直接失败。**
所以当前的跳过虽然出于错误的理由（仓库名写错），**行为恰好是对的**。

**这不是字符串问题，是基建缺失。** 真要让它们跑起来，需要先：
建 `github-pages` / `trusted-automation` 两个 environment、启用 Pages、
创建 GitHub App 并配 `APP_CLIENT_ID` + `APP_PRIVATE_KEY`（`deploy-vercel` 还要 Vercel hook）。
**那是运维决策，不在本方案范围。**

**判据**（下一个人确认此条是否仍成立）：

```bash
gh api repos/kopiagent/kopi-ai-agent/environments -q '.environments[].name'   # 有无 github-pages / trusted-automation
gh api repos/kopiagent/kopi-ai-agent/pages                                    # 404 = Pages 未启用
gh api repos/kopiagent/kopi-ai-agent/actions/variables -q '.variables[].name' # 有无 APP_CLIENT_ID
```

三项都就绪后，再把 `deploy-site.yml:50`、`skills-index.yml:21`、
`skills-index-freshness.yml:21` 的 `NousResearch/kopi-agent` 改成 `kopiagent/kopi-ai-agent`。
届时会触碰 `.github/workflows/**` → 触发 `Review label gate`，需人工加 `ci-reviewed` 标签
（AI 不自签）。

### A-2. 8 处 clone 指令指向不存在的仓库

用户照着敲会拿到 404（`github.com/NousResearch/kopi-agent` 不存在）：

`CONTRIBUTING.md`、`CONTRIBUTING.es.md`、`README.es.md`、`README.ur-pk.md`、
`website/docs/getting-started/nix-setup.md`、
`website/docs/user-guide/features/extending-the-dashboard.md`、
以及上面两份的 `website/i18n/zh-Hans/` 对应译文。

**动作**：`NousResearch/kopi-agent` → `kopiagent/kopi-ai-agent`。

### A-3. 14 处 issue/PR 模板 + SECURITY + AGENTS 里的链接

`.github/ISSUE_TEMPLATE/*.yml`、`.github/PULL_REQUEST_TEMPLATE.md`、
`SECURITY.md`、`SECURITY.es.md`、`AGENTS.md` —— 点击即 404。

**验收**：`git grep 'git clone.*NousResearch/kopi'` 只剩 `kopi-example-plugins`（见下）；
YAML 模板仍可解析；随机点 3 个模板链接可达。

### A-4. 未处理：`NousResearch/kopi-example-plugins`（16 处）

**刻意没改** —— 目标未知。上游应为 `NousResearch/hermes-example-plugins`，rebrand 把它变成了
`kopi-example-plugins`；我不知道我们是否有对应的自有仓库（`kopiagent/kopi-example-plugins`
是否存在未验证）。乱改会把一个坏链换成另一个坏链。

位置：`AGENTS.md:848`、`website/docs/user-guide/features/extending-the-dashboard.md:700,837,851`
及其 `website/i18n/zh-Hans/` 译文（684/821/835），另有若干散落处。

**判据**：`git grep 'NousResearch/kopi-example-plugins'`。
**解开需要**：确认我们是否 fork 了示例插件仓库；有则改指向它，无则删掉这些引用
（连同它们描述的 `example-dashboard` / `strike-freedom-cockpit` 演示段落）。

---

## Step B —— Discord 链接注释掉（16 处 / 9 文件）

`https://discord.gg/NousResearch` 是**上游社区**，不是我们的。

| 文件 | 处数 |
|---|---|
| `CONTRIBUTING.md` | 3 |
| `CONTRIBUTING.es.md` / `README.es.md` / `README.ur-pk.md` / `README.zh-CN.md` / `apps/desktop/README.md` | 各 2 |
| `.github/ISSUE_TEMPLATE/config.yml` / `.github/ISSUE_TEMPLATE/setup_help.yml` / `website/src/components/UserStoriesCollage/index.tsx` | 各 1 |

**动作**：按你的要求**注释掉**（不是删除），保留原文便于将来换成我们自己的社区链接。
各文件语法不同：Markdown 用 `<!-- -->`，YAML 用 `#`，TSX 用 `{/* */}`。

⚠️ `.github/ISSUE_TEMPLATE/config.yml` 的 `contact_links` 若整块注释掉，
issue 页面会少一个入口 —— 需确认是否要留占位。

**验收**：`git grep 'discord.gg/NousResearch'` 只在注释行命中；
`.github/ISSUE_TEMPLATE/config.yml` YAML 仍可解析。

---

## Step C —— 仓库路径大扫除（~578 处）

`NousResearch/kopi-agent`(267) + `NousResearch/kopi-ai-agent`(291) + `.git`(12) 等
—— **半改名产物**：既不是上游（`NousResearch/hermes-agent`）也不是我们
（`kopiagent/kopi-ai-agent`），是 rebrand 把 `hermes`→`kopi` 时造出来的、
**指向不存在仓库**的字符串。

| 区域 | 处数 | 说明 |
|---|---|---|
| `website/` | 435 | 文档站正文 + i18n 译文；用户可见 |
| 源码/其它 | 93 | 含 `optional-mcps` manifest、`nix/`、`scripts/` |
| `tests/` | 50 | **断言这些字符串的测试，必须同批改** |

**动作**：统一改 `kopiagent/kopi-ai-agent`。
⚠️ 注意 `kopi-agent` 与 `kopi-ai-agent` **两种形态**都要覆盖（CLAUDE.md §6.3）。

**风险**：面广。50 处测试断言是"值和断言配套"型 —— 改值不改断言会红。
**做法**：脚本替换 + 计数断言，然后跑全量证明 `passed` 数不降。

**验收**：`git grep 'NousResearch/kopi'` 为空（`hermes-agent` 那 4 处除外）；
全量 Python `passed` 数不低于当前基线；`website` 构建通过。

---

## Step D —— 品牌文案（~151 处）

真正的"把 Nous Research 换成我们"的部分，按上表命名规则执行。

| 区域 | 处数 |
|---|---|
| `website/` | 44 |
| `plugins/` | 35 |
| `apps/` | 17 |
| `optional-skills/` | 13 |
| `skills/` | 8 |
| `tests/` | 7 |
| `kopi_cli/` | 6 |
| `ui-tui/` | 3 |

**动作**：逐条判断用**公司全称**还是**短名**（见命名规则表），
不是无脑替换 —— 例如 skills/plugins 的 `author:` 字段用全称，UI 落款用短名。

⚠️ 与 [brand-rename-audit.md](brand-rename-audit.md) 的 T4 有重叠但**不等同**：
那份只管应用内用户可见串，本步含 `website/` 与 plugin manifest。执行时以本文为准，
完成后回去更新那份审计的状态。

**验收**：`git grep 'Nous Research'` 只剩「不动的」清单里那 15 处（4 版权 + 7 语义 + 4 上游）。

---

## 顺序与理由

```
Step 0（合修复 → rebase #50 → tag 1.23.0）   ← 与命名无关，已就绪
  └─ Step A（修坏掉的：workflow 门控 + 404 链接）  ← 独立，价值最高
       └─ Step B（Discord 注释）                  ← 独立，小
            └─ Step C（仓库路径 578）             ← 面广，需全量证明
                 └─ Step D（品牌文案 151）        ← 需逐条判断
```

A 与 B 互不依赖，可并行；C 建议在 A 之后（A 已改掉的部分不必重复）；
D 最后（面最杂、判断最多）。

## 每步共同的门禁（CLAUDE.md）

- 改到代码/配置 → 本地全量 + 每个改动 workspace 的 `npm run check`
- 纯文档（只动 `*.md`）→ 命中豁免，但**仍走 PR + CI 全绿**
- 改到 `.github/workflows/**` → `Review label gate`，`ci-reviewed` **人工签字**
- 收尾：按第 4 步把本次遗留写回 `docs/`，并更新 [README.md](README.md) 索引

## 待你确认的两个点

1. **A-1 修好后 `deploy-site` 会首次真跑** —— 部署目标配置是否就绪？
   若未就绪，建议先只修 `skills-index` 两个，`deploy-site` 单独处理。
2. **B 里 `.github/ISSUE_TEMPLATE/config.yml` 的 `contact_links`** 整块注释后
   issue 页面少一个入口 —— 要留占位还是就这样？
