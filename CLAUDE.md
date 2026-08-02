# CLAUDE.md — 合并门禁(强制)

> 本文件对**所有 AI 助手**具有强制约束力。任何要进 `main` 的改动,必须按此执行,不得跳步。
>
> **上游同步的规则也在本文件里**(见「上游同步」章)。`.upstream-sync.json` 只剩三类**数据**,
> 不含规则:① 状态(`synced_to_commit` / `sync_tag` / `synced_date` / `history`)、
> ② `conflict_policy` 逐文件的 union-preserve 清单、③ `known_noise_failures` 已知噪音名单。
> 规则与数据冲突时,**以本文件为准**。

## 铁律

**本地全量测试通过 → 开 PR → CI 全绿 → 才能合入 main。**

三步缺一不可。禁止:直推 main、CI 红着合、"只跑了受影响的测试就说没问题"。

### 豁免(仅此两类,从窄不从宽)

两类改动**可跳过本地全量**,但**都仍须走 PR 且 CI 全绿** ——
分支保护是仓库层面强制的:任何改动都推不了 main,必需检查 `All required checks pass`
不通过就合不了。豁免免的是"本地那 10 分钟",不是 CI。

1. **纯文档**:只动 `*.md`,不碰任何代码/配置/锁文件。
2. **纯版本号 bump(发版用)**:只动 `scripts/bump-version.sh` 会改的那几样 ——
   `package.json` / `apps/desktop/package.json` / `pyproject.toml` /
   `kopi_cli/__init__.py`(`__version__` + `__release_date__`)+ 重锁的 `uv.lock`。
   代码与刚跑过全量的那次**逐字相同**,再跑一遍纯属浪费。

   发版前只需确认这三件事,然后直接提 PR:

   ```bash
   bash scripts/bump-version.sh          # 不传参 = 只校验四处一致
   uv lock --check                       # 锁文件无漂移
   git diff --stat origin/main..HEAD     # 确认只有上面那 5 个文件
   ```

   🔴 **前提**:被发版的那个 commit 必须**已经**通过完整流程进了 main。
   如果 bump 的同时还夹带了任何代码改动,豁免作废,按全量跑。

拿不准算不算豁免,就按全量跑。

---

## 第 1 步:本地全量测试(**不是只跑 lint**)

> ⚠️ 最常犯的错:只跑了 `typecheck`/`lint` 就宣称"全绿"。**typecheck 不等于测试。**
> 本会话已两次因此漏掉真实回归(v15 的 `Setup required` i18n 改名就是补跑 UI 测试才发现的)。

**跑之前先 `unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy`** ——
本机 clash 用 fake-IP DNS(198.18.0.0/16),不清代理会造出几十个假失败。

### 1.1 Python 全量(必跑)

```bash
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
bash scripts/run_tests.sh          # 约 7 分钟,per-file 进程隔离,与 CI 一致
```

必须看到最终 `=== Summary: N files, M tests passed, K failed (100% complete) ===`。
**没有 `100% complete` 就不算跑完。**

### 1.2 JS/TS —— **每个改动到的 workspace 都要跑它的 `check`(含测试)**

各 workspace 的 `check` 覆盖范围不同,**别只跑 `check:lint`**:

| workspace | 命令 | `check` 含什么 |
|---|---|---|
| `apps/desktop` | `npm run check` | check:lint(tsc×3 + eslint)+ **check:test:ui** + **test:desktop:platforms** + **test:desktop:all** |
| `web` | `npm run check` | typecheck + **test** + lint |
| `ui-tui` | `npm run check` | build:ink + typecheck + **test** + lint |
| `apps/shared` | `npm run check` | typecheck + lint(无测试) |
| `apps/bootstrap-installer` | `npm run check` | lint |

判断改了哪些 workspace:

```bash
git diff --name-only origin/main..HEAD | grep -E '^(web|ui-tui|apps)/' | cut -d/ -f1-2 | sort -u
```

`apps/desktop/npm run check` 里的 `test:desktop:all` 会**真的构建 DMG/安装包**并校验 bundle,较慢但必须过。

### 1.3 其余门禁项

```bash
uv lock --check                                   # 锁文件无漂移
bash scripts/bump-version.sh                      # 四处版本一致(不传参=只校验)
.venv/bin/ruff check .                            # 阻塞性 lint
.venv/bin/python scripts/check-windows-footguns.py --all
grep -rn 'NousResearch/hermes-agent\|hermes-agent.git' \
  --include='*.py' --include='*.sh' --include='*.ts' --include='*.ps1' .   # 必须为空
```

### 1.4 🔴 修完 bug 后必须**重跑全量**

只验"我改的那个文件通过了"是不够的 —— 修改可能波及别处。
以最终代码重跑一次全量,并用**通过/失败数的变化**证明修复生效
(例:`24472 passed/39 failed` → `24479 passed/32 failed`,差值正好等于修掉的 7 个)。

---

## 第 2 步:失败分类(区分真回归 vs 环境噪音)

**不要把所有失败都当噪音,也不要把噪音都当回归。** 判定顺序:

1. **该失败文件在本次 diff 里改动过吗?**

   ```bash
   git diff --name-only origin/main..HEAD | grep '^tests/'
   ```

   - **改动过** → 按真回归查,直到证明不是。
   - **没改动过** → 大概率环境噪音,但仍要比对 `.upstream-sync.json` 的 `known_noise_failures` 确认属于已知类别。

2. **⚠️ 测试文件没改 ≠ 被测源码没改。**
   最阴的一类是 **test/source skew**:测试保留了我们的、源码吃了上游的(或反之)。
   本会话 v15 出现两次,方向相反:
   - 源码 `load_config()` → `load_config_readonly()`,测试仍 patch 旧 seam
   - 上游改了 UI 文案并改了测试,而 i18n"kept ours"没跟上改名

3. **声称"是已知 flake"之前,必须单独重跑该文件确认。**
   runbook 里记的 flake 也可能这次是真失败 —— v15 的 `toolset-config-panel` 就在 known-flake 名单里,
   但单独重跑仍失败,查出来是真回归。

4. 已知噪音类别(macOS 平台/FS、clash fake-IP SSRF、可选依赖未装、Linux-only、upstream-identical)
   见 `.upstream-sync.json` 的 `known_noise_failures`,**只跳过,不"修"**。

---

## 第 3 步:PR → CI 全绿 → 合并

仓库已开启分支保护,**技术上也禁止直推**:

- 改动必须走 PR(禁止直接 push main)
- **禁止 merge commit**(历史保持线性)→ 合并用 `--squash` 或 `--rebase`
- 必需状态检查:`All required checks pass`

```bash
gh pr create --base main --head <branch> --title "..." --body "..."
gh pr checks <PR> --watch          # 或轮询
gh pr merge <PR> --squash --delete-branch     # 单一改动
gh pr merge <PR> --rebase --delete-branch     # 多提交需保留结构(如 sync 的 batch)
```

**只有 `All required checks pass` 为 pass 才能合。** 注意:

- CI 会抓到本地噪音掩盖的真问题(Linux runner 无 clash、无本机凭据)。
  v13 本地看着全是噪音,CI 却抓出 2 个真回归。**CI 是最终裁判,不是形式。**
- 遇到红:先判断是真失败还是基础设施 flake(典型:`Desktop E2E` 在 setup 阶段挂、
  没产出 playwright-report、通用 exit 1)。真 flake 用 `gh run rerun <run> --failed` 重跑;
  **不要**为了合并而绕过门禁。
- 改到 CI 敏感文件(`.github/workflows/**`、`mcp_catalog.py`、`model-catalog.json`)会触发
  `Review label gate`,需要 `ci-reviewed` 标签。
- 提交作者邮箱必须在 `scripts/release.py` 的 AUTHOR_MAP 里,否则 `check-attribution` 红。

---

## 上游同步(hermes → kopi)

> 本章是**同步专用的附加规则**,不替代上面三步门禁 —— 同步分支照样要跑全量、开 PR、等 CI 全绿。
> 每条都是踩过的坑,后面括号里的 `vN` 是第一次被咬的那次同步。

### 0. 开工前:`git status` 必须干净(v16)

创建同步分支**之前**先看工作区。`batch_merge.py` 直接写工作区,冲突处理会 `git checkout` ——
未提交的在途改动会被**不可恢复地**冲掉。v16 时用户有 257 行在途工作
(office FX:`delegate_tool.py` / `web_server.py` / `OfficePage.tsx` / `web/src/lib/api.ts`)
正好落在同步要重写的文件里。先把在途工作提交到同步分支,再把它加进 `scratchpad/guards.sh`,
每批都验证它还在。

### 1. 合并方式:两种场景,别搞混

**(A) 增量同步 —— 正常情况,v5 之后一直用这个。**
逐文件 3-way:`base` = 上一次的 `synced_to_commit`,`theirs` = hermes 新 HEAD,`ours` = kopi 当前 tip。
对 `git diff --name-status -M base theirs` 里的每个文件,先转换路径+内容(改名规则见第 2 节),
再 `git merge-file` 进 kopi 工作区。工具:scratchpad 的 `batch_merge.py <hermes> <kopi> <base> <theirs>`。
大范围拆成连续小批,**每批都编译+测试**。因为 delta 里只有上游真实改动,不存在静默丢失的风险。

**(B) 整树重新 fork —— 极少用。**
`base` **必须**是 `c1b46d9`(kopi 真正的初始改名 commit,真实共同祖先),不能用合成的 T(fork) ——
base 太新会把上游代码当"我们删的"静默丢掉。🔴 `c1b46d9` **只属于场景 B**,永远不要拿它当增量的 base。

**批边界必须来自 `--first-parent`(v15):**

```bash
git rev-list --reverse --first-parent <base>..origin/main     # ✅
git rev-list --reverse --no-merges    <base>..origin/main     # ❌
```

`--no-merges` 的顺序是跨 PR 分支的拓扑序,第 N/10 个 commit 可能是某侧分支的 tip,
其 tree 早于范围内已合入的改动 —— `git diff base <该 commit>` 会报出几百个幻影删除
(v15 batch1 出现 `DEL=383`,而那些文件两端都存在)。first-parent 的每个 commit 都是真实主线状态。

每批合并前先 sanity check:

```bash
git diff --name-status <prev> <boundary> | awk '{print substr($1,1,1)}' | sort | uniq -c
```

D 的数量远超整个范围的真实删除数 = 边界选错了。

### 2. 改名(rebrand)

保留大小写的 `hermes` → `kopi`,再加一遍后处理 `hermes-agent` / `kopi-agent` → `kopi-ai-agent`(包名/仓库名)。

- **下划线形式也要过**:连字符那一遍**不碰** `kopi_agent`,但真实包名是 `kopi-ai-agent`,
  其构建产物是 `kopi_ai_agent-*.{tar.gz,whl,dist-info}`。任何 glob 到 `kopi_agent-*` 的测试或路径
  都得改成 `kopi_ai_agent-*`(v9 咬过 `tests/test_packaging_build_guard.py`)。
- **例外,别动**:`kopi_agent.plugins`(`kopi_cli/plugins.py` 里的 pip entry-points 组名)和
  内部符号/测试名(`_has_kopi_agent_browser`、`test_*_kopi_agent`)—— 这些是命名空间 ID,不是发行包名。
- **别动真实 npm 包名**:`hermes-parser` / `hermes-estree` 等在 `package.json` /
  `package-lock.json` 里改了会 404。
- 改名不能碰 `skills/**`,也不碰 `-memory` / `-setup` / `-dev` / `-skill-authoring` 后缀。

### 3. 🔴 冲突解法:朴素拼接对代码块是不安全的(v16,一次同步栽两次)

把 ours+theirs 直接粘一起,会把 hunk 边界切断的结构截断。v16 两次都是测试文件:

- `tests/kopi_cli/test_web_oauth_dispatch.py` 在 `try` 块中间结束 →
  `SyntaxError: expected 'except' or 'finally'`
- `apps/desktop/.../gateway-settings.test.tsx` 少一个右花括号 → vitest 报 "no tests"
  (`PARSE_ERROR Expected } but found EOF`)

朴素 union **只对平坦列表安全**(import、frozenset、`.gitignore` 行)。

**有块结构时的可靠做法**:整份取上游,再把 kopi 独有的块**按语法解析**重新插回 ——
Python 用 `ast.parse` + `FunctionDef.lineno/end_lineno` 切出每个 kopi-only 测试;
TS/TSX 从 `it(` / `describe(` 那行开始数花括号,到深度归零为止。
然后**真的把文件跑一遍**(pytest / vitest)—— 光编译检查抓不到 vitest 的 parse error。
v16 靠这招在 `test_web_oauth_dispatch.py` 里救回 12 个 kopi-only 测试(27 passed)。

### 4. 🔴 锁文件冲突:绝不 `git checkout HEAD --`(v16)

锁文件是派生物,批处理循环会不停地用"从 HEAD 恢复"来"解决"它们的冲突 ——
可一旦**某一批**提交了还带冲突标记的锁文件,后面每次恢复都在重新装回那个坏文件。
v16 batch3 提交了带 71 个冲突标记的 `package-lock.json`,npm 于是把 `@assistant-ui/react`
解析成 0.15.1(package.json 钉的是 0.14.24),表现为 4 个幻影 TS2724
(`useComposerRuntime` / `useMessageRuntime` "not exported"),看着像真代码坏了。

**正确做法**:锁文件冲突从**同步分支起点**恢复,不是从 HEAD:

```bash
git checkout <v-start-commit> -- package-lock.json uv.lock   # ✅
git checkout HEAD -- package-lock.json                        # ❌ 会传染
node -e "require('./package-lock.json')"                      # 每批必跑的廉价探测:JSON 解析失败 = 混进标记了
```

收尾时再用 `npm install` / `uv lock` 重新生成。

### 5. 合并后必查

- **恢复被 3-way 删掉的 kopi 自有文件**:base 有、上游没有的文件会被判成删除。
  拿"合并产生的删除"和"上游真实的删除"对比,差集就是要恢复的。
- **test/source skew**:delta 碰到的每个 `tests/` 文件,都要确认对应**源码**也吃到了配套的上游改动。
  合并可能只取了新测试而丢了源码改动,留下 API 不匹配 —— 这会在 Linux CI 上红,不只是本地。
  详见「第 2 步」第 2 条。修法是**从上游补源码**(连同配套 workflow),**不要降级测试**。
  v9:`tests/ci/test_emit_review_status.py` 吃到了新签名
  `build_results(supply_chain=, repo_url=, base_sha=, head_sha=)`,而
  `scripts/ci/emit_review_status.py` + `.github/workflows/review-labels.yml` 还停在旧的三参形式 → TypeError。
  v16 同一类:`tools/lazy_deps.py` 把 pin 提到 `mcp==1.28.1`,`tests/tools/test_computer_use.py`
  的两处断言只跟了一处。
- **union 过的 TS 文件要看符号是否配齐**:上游新增的代码常引用我们这版没 import / 没解构的符号。
  v12 的 `electron/main.ts`:union 保住了我们的 `const {app, BrowserWindow, ...} = electron` 解构,
  却取了上游用裸 `globalShortcut` 的 Quick Entry → TS2304,`apps/desktop / check:lint` 红。
  **只跑 Python 全量是抓不到这类的**,必须按第 1.2 节跑每个 workspace 的 `check`。
- **完整性扫描**:未定制的文件应当与 T(upstream) 逐字相同(模改名)。

### 6. 不可让步的 kopi 侧规则

1. **版本号是我们的**:`pyproject.toml` version、`kopi_cli/__init__.py` `__version__`、
   `package.json` + `apps/desktop/package.json` version 跟 KOPI 产品版本走
   (`scripts/bump-version.sh`),**永远不要接受上游的版本 bump**。
2. **锁文件是派生的**:不手改、不盲目取上游。任何版本/依赖变化后跑 `uv lock` + `npm install`。
3. **安装/更新路径指向我们**:`kopiagent/kopi-ai-agent` 和 `kopiaiagent.com`。
   同步若把 `NousResearch/hermes-agent` 或 `hermes.nousresearch.com` 带回
   `scripts/*` / `kopi_cli/*` / `apps/desktop/electron/*`,必须改回来。
4. **`package.json` 的品牌字段**(第 1.3 节那个 grep **扫不到**它):
   `package.json` 和 `apps/desktop/package.json` 必须保住
   `homepage=https://kopiaiagent.com`、appId `com.kopiaiagent.kopi`、
   maintainer/author `Kopi Ai Agent Pte Ltd`、repository/bugs 指向 `kopiagent/kopi-ai-agent`。
   v9 整份取了上游的 `apps/desktop/package.json`,homepage 丢了 →
   electron-builder fpm 报 `Please specify project homepage` → **Linux deb/rpm 没出包**,mac+win 出了。

   ```bash
   grep -n '"homepage"\|"appId"\|"maintainer"\|"author"' package.json apps/desktop/package.json
   ```

5. **`install.sh`** = 上游 staged Hermes 协议改名 + 一处 kopi 注入
   (config 阶段的 `provision_kopi_proxy_key`)。被重写就重做改名 + 重新注入。
6. **13 个 `tests/test_install_sh_*.py` 必须保持 `pytestmark = skip`**
   (还有 `test_install_{diverged_update,lockfile_churn,no_initial_commit,unmerged_index,autostash_conflict_recovery}`)——
   它们断言的是**旧的**上游线性安装器,KOPI 用的是 staged 版本,覆盖在 `tests/test_install_sh_kopi.py`。
   同步把它们 un-skip 了,CI 就红。
7. **npm ≥ 12(v16 起)**:同步带进了上游的 `.npmrc`(`engine-strict=true` + `min-release-age=14` + 排除表),
   `engines` 要求 `npm >= 12.0.0`。npm 11.10–12.0 认 `min-release-age` 但**不认**
   `min-release-age-exclude`,会静默装错版本。老 npm 上 `npm install` 直接
   `notsup Required: {npm:'>=12.0.0'}`。这是**上游工具链要求,不是合并缺陷** —— 升级 npm
   (`npm i -g npm@12`,或一次性 `npx -y npm@12 install`)。
   本地临时验证可用 `npm install --engine-strict=false`,但 CI 和发版构建必须是真 npm 12。

### 7. 收尾(推送前,顺序有讲究)

```bash
uv lock && npx -y npm@12 install       # 1) 重新生成锁文件(pyproject/package.json 变了就必须)
bash scripts/bump-version.sh           # 2) 复校四处版本一致
npm run fix                            # 3) 全 workspace eslint --fix + prettier
# 4) 第 1 步的全量 + 第 1.3 节的品牌 grep + 上面第 6 条的 package.json 品牌 grep
```

然后更新 `.upstream-sync.json`:bump `synced_to_commit` + `sync_tag` + `synced_date`,
往 `history` 追一行,并在该 marker commit 上打 `hermes-sync-<hash>` tag
(tag 默认只在本地,要推得 `git push origin --tags`)。

🔴 `synced_to_commit` 是"上次同步到哪"的**唯一事实来源** —— 读它,不要信任何散文里写死的 hash。

---

## 发版

**前提**:要发的那个 commit 已经走完整流程进了 main(全量 + PR + CI 全绿)。
此时的 bump 命中「纯版本号 bump」豁免 —— **不必再跑本地全量**。

```bash
bash scripts/bump-version.sh <x.y.z>   # 同步四处版本 + __release_date__ + 重锁 uv.lock
bash scripts/bump-version.sh           # 复校四处一致
uv lock --check                        # 锁文件无漂移
git diff --stat origin/main..HEAD      # 确认只有那 5 个文件,没夹带代码

# → 提 PR,CI 全绿后 squash 合并,然后:
git tag v<x.y.z> && git push origin v<x.y.z>   # 触发 desktop-release 三端构建
```

tag 推送后在 `desktop release` workflow 出包(mac/win/linux)。
mac 包是 ad-hoc 签名未公证,安装需 `xattr -dr com.apple.quarantine /Applications/Kopi.app`
(配齐 `CSC_LINK`/`APPLE_ID` 等 secrets 后 CI 会自动签名+公证,届时无需此步)。

---

## 自检清单(汇报"测试通过"前逐条确认)

> 命中豁免(纯文档 / 纯版本号 bump)时,跳过前 7 条,只需最后两条 + 豁免自身的确认命令。

- [ ] `unset HTTP_PROXY/HTTPS_PROXY` 了
- [ ] Python 全量看到 `100% complete` 的 Summary
- [ ] **每个改动到的 JS/TS workspace 都跑了 `npm run check`(不是只有 lint)**
- [ ] `apps/desktop` 改动时跑了打包测试 `test:desktop:all`
- [ ] uv lock / 版本一致 / ruff / footgun / 品牌 grep 全过
- [ ] 每个失败都归类了:真回归(已修)或已知噪音(有出处)
- [ ] **修完 bug 重跑了全量**,并用数字变化证明
- [ ] PR 已开,`All required checks pass` = pass
- [ ] 用 squash/rebase 合并(无 merge commit)

上游同步分支**额外**加这几条(见「上游同步」章):

- [ ] 批边界来自 `--first-parent`,且每批 D 数量正常
- [ ] 锁文件冲突是从**分支起点**恢复的,`node -e "require('./package-lock.json')"` 能过
- [ ] union 过的文件**跑过**(pytest/vitest),不是只编译过
- [ ] 版本号没被上游 bump 覆盖;`package.json` 品牌字段(homepage/appId/maintainer)还在
- [ ] 13 个 `test_install_sh_*` 仍是 skip
- [ ] `.upstream-sync.json` 的 marker + `history` 已更新,`hermes-sync-<hash>` tag 已打

**任何一条没做到,就如实说"还没跑完",不要说"全绿"。**
