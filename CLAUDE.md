# CLAUDE.md — 合并门禁(强制)

> 本文件对**所有 AI 助手**具有强制约束力。任何要进 `main` 的改动,必须按此执行,不得跳步。
> 上游同步的细则见 `.upstream-sync.json`(conflict_policy / green_ci_runbook / known_noise_failures),
> 本文件只管**门禁流程**,不重复那里的内容。

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

**任何一条没做到,就如实说"还没跑完",不要说"全绿"。**
