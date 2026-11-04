# MiniMax H3 导演技能交付与验证缺口

这份文档记录 v1.23.0 候选内容已交付什么，以及渲染和发布前还需验证什么。

## 本次范围

用户选择先交付导演技能与工作流配置，暂不接实际生成服务。
入口为 `optional-skills/creative/minimax-h3-director/SKILL.md`，预设为
`assets/turbo-presets.json`。这是供代理应用的配置方案，不是可直接提交的 ComfyUI API 图。
执行开关保持关闭，没有安装节点、下载权重、开通服务或提交生成任务。

## 已做的离线验证

- 实际 `OptionalSkillSource` 能搜索到技能并取回全部四个文件。
- 在临时 `KOPI_HOME` 中走实际 quarantine/install 流程成功，参考文件和预设完整保留。
- 取回的文件可写入临时目录，内部 Markdown 引用可解析，预设 JSON 有效。
- Kopi 扩展元数据通过项目解析器；通用 skill validator 对去掉 Kopi 专有
  `version`、`author`、`platforms` 的临时副本通过校验，仓库原文件保留这些字段。
- `scripts/bump-version.sh` 校验通过，四处产品版本一致。
- `uv lock --check --offline` 通过；npm 根目录、桌面 workspace 与锁文件版本一致。

## 待处理事项

| 证据指针 | 为什么本次没完成 | 后续判据 |
| --- | --- | --- |
| `tests/tools/test_skills_hub.py:778`，`TestOptionalSkillSourceBinaryAssets.test_fetch_preserves_binary_assets` | Windows 上现有测试按 `/` 查找 bundle key，而 `OptionalSkillSource.fetch` 使用本机路径字符串。本次未改动该代码或测试；定向测试结果为 3 passed / 1 failed。 | 在 Windows 用 `scripts/run_tests.sh tests/tools/test_skills_hub.py -k OptionalSkillSource` 重现；后续独立修复需验证二进制文件和安装路径仍完整。 |
| `optional-skills/creative/minimax-h3-director/references/comfyui-workflow.md` | 用户明确暂不连接服务，未验证具体 GPU、模型文件、节点版本及音画输出。 | 用户选择生成环境后导入匹配模板、验证依赖与参数绑定，再生成并审看一个含声音的代表镜头。 |
| `CLAUDE.md` 的合并门禁；`.github/workflows/desktop-release.yml` | 此次完成离线技能与版本准备，未运行完整 Python/桌面构建测试，也未发布安装包。定向检查不等同于全量通过。 | 合并/发版前完成适用的全量门禁与 CI；成功构建并核对各平台产物后再发布。 |

`RELEASE_NOTES_v1.23.0.md` 是候选版本说明。发布前刷新实际发布日期；不要把
README、版本号或草稿 PR 的变更描述为已经上线的新版本。
