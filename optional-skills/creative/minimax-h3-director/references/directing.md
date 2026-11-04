# Directing a coherent H3 film

## Story before shots

Write the audience's starting belief and the change by the end. Each shot must
introduce information, increase tension, reveal a response or deliver the payoff.
Remove shots that repeat a point without adding emotion or clarity.

For an ad, connect the opening problem to a visible product action and a credible
result. For a trailer, escalate questions without giving away the whole ending.
For a music video, give repeated motifs a changing meaning across musical sections.

## Director's controls

| Control | What to specify |
| --- | --- |
| Blocking | Who starts where, what changes, where the action ends |
| Coverage | Establishing shot, action shot, reaction, insert and payoff |
| Framing | Wide/medium/close-up, subject position, headroom and depth |
| Lens feel | Perspective and depth of field; avoid contradictory lens requests |
| Camera | Static, pan, tilt, dolly, tracking, handheld, crane or orbit; one primary move |
| Motivation | Why the camera moves now and what new information it reveals |
| Continuity | Identity, wardrobe, props, lighting, eyelines and screen direction |
| Performance | Intention, restrained gestures, expression and timed reaction |
| Art direction | Palette, material, location, era and practical light sources |
| Sound | Dialogue, action sounds, ambience, silence and music separately |
| Editing | Cut on action, match cut, reaction cut, J/L cut or deliberate pause |
| Delivery | Target ratio, safe text area, subtitles, duration and export format |

Keep geography understandable: establish positions before close coverage and
avoid unintended screen-direction reversals. For adjacent shots, record the
outgoing pose and incoming pose. A last-frame reference is a proposed continuity
tool, not a guarantee that an unsupported checkpoint can accept it.

## Shot record

Use one row per shot with these fields:

`id | timeline | generation_duration | edit_duration | story_purpose | mode |
references | framing | camera | action_beats | dialogue | sound | transition |
continuity | prompt_file | preset | seed | status`

Model-sized shots may need trimming. For a 30-second edit, for example, plan six
five-second editorial shots, each with its own dramatic job. Check the selected
workflow's frame-count rules before calculating generation frames; do not assume
every workflow accepts exactly `seconds * fps` frames.

## H3 prompt handoff

Use the upstream [H3 prompt-writing guide](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing)
for the full syntax. Write visual/action prose in English while preserving the
original language of dialogue, lyrics and on-screen text. Do not translate a
Chinese spoken line into English unless the user requests it.

For base text/image/first-last modes, preserve this section order:

1. `integrated_multimodal_description`
2. `overall_soundscape`
3. `non_diegetic_music`

Describe action, camera and synchronized sound together in the first section;
put sustained ambience in the second and non-diegetic music in the third.
Make “no music” explicit when the edit needs clean production sound.

Reference mode uses a different ordered structure:

1. `subject_definitions`
2. `summary`
3. `retention_analysis`
4. `detailed_description`
5. `overall_soundscape`
6. `non_diegetic_music`

Associate reference labels such as `<Picture 1>` with the actual supplied files.
Describe what each reference must preserve and what may change. Do not use a
reference-mode prompt as proof that the selected Turbo model supports that mode.

## Editing and review

Plan dialogue before cutting: leave room for breath and reactions. Use sound
bridges to connect locations, and avoid simultaneous full-volume narration,
dialogue and music. Prefer captions added in the edit when exact typography matters.

When footage eventually exists, review each take for story readability, identity,
hands/props, temporal stability, camera motion, speech accuracy, lip sync and audio
seams. Record keep/revise/reject with a concrete reason. Change one main variable
between comparable takes and retain their seed, prompt, model and workflow versions.

Do not mark these checks passed during planning. Deliver an edit decision plan
with pending media paths, not a fabricated final film or a timeline claiming
nonexistent shots have rendered.
