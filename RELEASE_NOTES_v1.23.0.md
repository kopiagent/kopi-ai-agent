# Kopi Desktop v1.23.0 — release candidate notes

## MiniMax H3 视频导演 / Video Director

新增可选技能 `minimax-h3-director`：从创意简报到故事结构、分镜、景别与运镜、
角色连续性、对白音效、逐镜头提示词和剪辑交付方案。

Adds an optional video director skill for narrative planning, shot design,
camera movement, character continuity, dialogue, sound and editing handoff.

- Community MiniMax H3 Turbo LoRA recipe: six-step preview and eight-step motion comparison.
- Planning works without a GPU or service credentials.
- Offline configuration includes explicit unresolved model and node bindings.
- Future execution reuses the existing `comfyui` skill; no new backend client.
- English and Chinese README usage examples.

Install after upgrading to a version containing this skill:

```bash
kopi skills install official/creative/minimax-h3-director
```

## Scope of this candidate

本次交付导演技能与配置方案，暂不连接实际视频生成服务。
6 步是采样设置，不是出片耗时保证；模型权重不随安装包分发。

This candidate contains instructions and configuration recipes, not a prewired
generation service or an executable ComfyUI graph. GPU inference, model/node
compatibility on a user's installation and final audiovisual quality require
a later rendering validation. MiniMax model and community-node licenses apply
separately from this repository's license.

These are candidate notes, not evidence that installers have been published.
Desktop builds and release publication follow the repository's release workflow.
