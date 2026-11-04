# ComfyUI handoff: H3 with community Turbo LoRA

## Scope and sources

This is an offline configuration recipe, not a complete executable node graph.
Resolve the actual graph against the user's installed ComfyUI when they later
request rendering. Do not connect to a service during a planning-only task.

- Base model and license: [MiniMaxAI/MiniMax-H3](https://huggingface.co/MiniMaxAI/MiniMax-H3).
- Supported templates and model placement: [ComfyUI H3 guide](https://docs.comfy.org/tutorials/video/minimax/minimax-h3).
- Community LoRA weights: [larryvrh/MiniMax-H3-Turbo-Lora](https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora).
- Required custom nodes and wiring: [Larryvrh/ComfyUI-MiniMax-H3-Turbo](https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo).

The base model is substantial: hardware suitability depends on precision,
offloading, resolution and clip length. No GPU-memory or wall-clock guarantee
is made here. Do not bundle weights in Kopi's desktop installer.

## Offline recipe

Read `../assets/turbo-presets.json`. Select `preview_6` by default. Copy the
selected values into the project's `workflow-recipe.json`, with requested mode,
reference paths and these unresolved items:

- A supported base checkpoint, text encoder and audio/video VAE filenames.
- An official H3 template appropriate for the chosen mode.
- Installed ComfyUI and Turbo-node revisions; exact weight revisions/hashes.
- Actual node IDs for model patching, sampler, scheduler, prompt, seed and outputs.
- Valid dimensions, frame count and audio settings from that template.

Leave absent values null or list them under `unresolved_bindings`. Do not create
fake node IDs or plausible-looking model filenames. Preserve
`execution_enabled: false` and `validation: "not_run"` in the handoff.

## Node configuration to apply later

1. Begin with the official H3 text-to-video or image-to-video template. Resolve
   its required checkpoint, encoders and audio/video components first.
2. Add `MiniMaxH3TurboLoRA` to the template's model path. Set `lora_name` to
   `minimax_h3_turbo_v4_step600_ema.safetensors`, `strength` to `1.0`, and
   `low_vram` to `false` initially. Route the patched MODEL to consumers that
   previously used the base model. Inspect the installed node schema before
   applying these names and values.
3. Feed `MiniMaxH3TurboSampler`'s SAMPLER output into
   `SamplerCustomAdvanced.sampler`. The custom sampler supplies the Turbo
   schedule behavior; an arbitrary stock sampler is not a substitute.
4. Set the template's `BasicScheduler` to `scheduler: simple`, `steps: 6`.
   Preserve the template's other settings and audio/video conditioning paths.
   `motion_8` changes the step count to eight for a quality comparison, not a
   promise to fix all motion artifacts.
5. Preserve the native audio path through decoding and saving. Verify the final
   save node includes both video and audio; a silent MP4 is not an AV success.
6. First/last-frame and reference-video modes require separate compatibility
   checks. Do not apply this base recipe blindly to Ref2VA or another checkpoint.

`low_vram` is an optional tradeoff in the community node; verify its behavior
with the installed quantization and model before changing it. Record any change
in the project's recipe. Six steps describes a sampling budget, not a speedup
factor or a six-second render promise.

## Later execution through the existing comfyui skill

This section is a handoff for a future rendering request. First load `comfyui`
with `skill_view` and obtain its actual installed directory. Use its hardware
and health checks; follow its installation and dependency guidance. Do not
create a second network client or store service credentials in the recipe.

Export the configured graph in **API format**: a dictionary of node IDs with
`class_type` and `inputs`, not the editor's `nodes`/`links` document. Save the
graph separately as `workflow_api.json`. Never feed `turbo-presets.json` or
`workflow-recipe.json` to the executor.

Through the terminal tool, replace `<comfyui-skill>` with the discovered absolute
directory and `<host>` with the user's configured service:

```text
python "<comfyui-skill>/scripts/extract_schema.py" workflow_api.json --output schema.json
python "<comfyui-skill>/scripts/check_deps.py" workflow_api.json --host "<host>" --strict
```

Inspect `schema.json`: each parameter must map to the actual `node_id` and
`field`. The existing executor warns and skips unknown parameter names, so a
command completing does not prove the H3 prompt or sampling settings changed.
Map prompt, seed, steps and any input-image fields explicitly, and preserve
connections rather than overwriting link-valued inputs.

Only after a rendering request and successful prerequisite checks, submit one
representative shot using the existing executor:

```text
python "<comfyui-skill>/scripts/run_workflow.py" --workflow workflow_api.json --schema schema.json --args @shot-001.args.json --host "<host>" --output-dir outputs/shot-001 --timeout 900
```

Use `--input-image name=path` when needed, with `name` from the verified schema.
Review the saved clip and listen to its audio before scheduling further shots.
Record workflow JSON, model/node revisions, reference hashes, seed, settings,
elapsed time and actual output paths in a render manifest. Failures remain
failures; do not report an unreviewed or absent output as a finished video.
