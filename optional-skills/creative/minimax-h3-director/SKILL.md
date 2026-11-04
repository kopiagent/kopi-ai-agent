---
name: minimax-h3-director
description: Plan narrative videos with MiniMax H3, including scripts, storyboards, camera direction, character continuity, dialogue, sound, editing and a community Turbo LoRA six-step ComfyUI recipe. Use for ads, shorts, trailers and music videos, or when asked for H3 video direction. Defaults to planning and configuration without a generation service.
version: 1.0.0
author: [LINYIQ66, Kopi Agent]
license: MIT
platforms: [linux, macos, windows]
metadata:
  kopi:
    tags: [video, director, minimax, h3, storyboard, comfyui, turbo-lora]
    related_skills: [comfyui]
---

# MiniMax H3 Video Director

Turn a brief into a coherent film plan and an inspectable ComfyUI configuration.
This release delivers directing instructions and configuration recipes. It does
not provision a service, download weights or generate video automatically.
The Turbo LoRA is a community project, separate from MiniMax's hosted APIs.

## When to Use

Use for multi-shot ads, short films, trailers, product stories and music videos,
or for a single H3 shot requiring precise camera, action and sound direction.
For an existing clip's simple conversion or trimming, use the existing media
tools instead of creating a new production plan.

## Prerequisites

Planning needs only a brief and a writable project directory. Do not require a
GPU, credentials or ComfyUI connection to deliver the planning package.

For a later rendering handoff, load the existing `comfyui` skill and follow
[the workflow guide](references/comfyui-workflow.md). Models, custom nodes,
hardware and their licenses are separate prerequisites; this skill's MIT
license covers its own instructions, not third-party model weights.

## How to Run

Example requests:

- “用 MiniMax H3 导演技能，为咖啡品牌设计 30 秒竖屏广告，先交付分镜和 6 步工作流配置。”
- “Plan a 45-second mystery trailer with consistent characters and a sound-led edit.”
- “Prepare an H3 image-to-video shot with a slow dolly-in and Chinese dialogue.”

Use `skill_view` to load this skill, then read both linked reference files.
Read [the preset](assets/turbo-presets.json) when preparing workflow settings.
The preset is a recipe for the agent to apply; it is not a ComfyUI API graph
and is not automatically read by Kopi or ComfyUI.

## Quick Reference

| Deliverable | Purpose |
| --- | --- |
| `brief.md` | Audience, message, duration, aspect ratio, tone and constraints |
| `storyboard.md` | Timed shots, action, framing, camera, sound and transitions |
| `continuity.md` | Stable character, wardrobe, prop, lighting and geography notes |
| `prompts/shot-001.md` | Per-shot H3 prompts, references and exact spoken text |
| `workflow-recipe.json` | Selected preset, model requirements and unresolved bindings |
| `edit-plan.md` | Timeline, selected takes, subtitles, sound mix and export targets |

Six steps means diffusion sampling steps, not six seconds of generation time.
Use `preview_6` for the initial configuration; offer `motion_8` for difficult
motion. Neither preset guarantees speed, identity consistency or output quality.

## Procedure

1. **Scope.** Infer what is already known. Ask only for missing facts that affect
   the result: subject/message, audience, duration/aspect ratio, references and
   required dialogue. State reasonable assumptions and keep working.
2. **Find the story.** Write the central change or reveal. Structure the film
   into an opening, development and payoff before assigning shots. Use
   [directing.md](references/directing.md) for narrative and camera decisions.
3. **Build continuity.** Assign stable character and prop IDs. Record wardrobe,
   screen direction, time of day and reference provenance. Mark absent reference
   images as needed; never claim they were supplied or inspected.
4. **Storyboard.** Give every shot a purpose, timeline range, duration, framing,
   one dominant camera move, action beats, sound and cut motivation. Split a
   long film into model-sized shots. Separate generation duration from the
   trimmed editorial duration; the edit's durations must sum to the target.
5. **Write prompts.** Prepare one prompt per shot, using the appropriate H3 mode
   and ordered sections in the directing reference. Keep dialogue and visible
   text in the requested language. Avoid stuffing the whole film into one prompt.
6. **Prepare configuration.** Copy the chosen preset into `workflow-recipe.json`.
   Add the requested mode and a list of missing models, references and node
   bindings. Leave `execution_enabled: false` and `validation: "not_run"`.
   Follow the workflow guide; never invent node IDs or submit this recipe as
   an executable graph. With no installed workflow, deliver the recipe and
   explicit binding checklist as the configuration handoff.
7. **Plan the edit.** Specify rhythm, shot order, sound bridges, subtitle timing,
   music entry/exit and export targets. Include a review checklist for future
   generated takes. Keep all take selections pending until footage exists.
8. **Deliver.** Link the saved files, summarize creative choices and list only
   the missing prerequisites relevant to rendering. Say “planning package
   ready”; do not say “video generated” or invent output links or benchmarks.

## Pitfalls

- Community H3 Turbo LoRA settings do not configure a hosted MiniMax API.
- Matching a seed helps reproducibility, but does not lock character identity.
- Reference-video or first/last-frame plans require matching supported models
  and workflows; their existence in H3 does not prove Turbo compatibility.
- Native audio still needs a listening review for speech, sync and cut seams.
- Do not install custom nodes, download large weights, provision GPUs or submit
  paid jobs merely because the user requested a storyboard or configuration.

## Verification

Before delivery, check the actual files: valid JSON; resolvable local reference
links; shot IDs matching prompt filenames; no gaps or overlaps in the edit;
dialogue that fits its time; stable character descriptions; and explicit
unresolved model/node bindings. Check that every deliverable describes planning
status accurately. GPU inference and audiovisual quality remain unverified
until a later, explicitly requested rendering pass succeeds.
