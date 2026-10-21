# Vendored animation guidance

These are existing upstream skills. The generation service reads selected original sections into the single whole-HTML model request, together with an application runtime adapter. Downloaded scripts are never executed. There is no online discovery, additional model call, video AI review, or teacher storyboard approval.

## Sources

| Skill | Repository | Pinned commit | License |
|---|---|---|---|
| animation-principles | https://github.com/iart-ai/motion-design-skills | 3c129f769d90a1328c209c386492333c9ac62312 | MIT |
| svg-animation | https://github.com/iart-ai/web-animation-skills | b6dba3eb759726845a44163ff0bad70dd9e7fbb6 | MIT |
| diagram-animation | https://github.com/iart-ai/explainer-video-skills | 3e2d411b725d9a72939cf8e5eb81579e751373e7 | MIT |
| javascript-animation | https://github.com/iart-ai/javascript-animation-skills | f7d0882a313249cbd43f0e4e9e209b1622870253 | MIT |
| 2d-character-rig-animation | https://github.com/calesthio/generative-media-skills | 8c85352d5d75d4dcbe58480bd138e37b9742bab1 | MIT |
| game-graphics | https://github.com/fenre/skills | 84bdc1dc884290ad78f4607e0e8f2068695377e7 | Apache-2.0 |

The new character reference is from skills/production/creative-direction/2d-character-rig-animation; game-graphics is from the repository directory of that name. sources.json records SHA256 for every unchanged source document and LICENSE. Apache-2.0 source retains its full license; the pinned upstream root and skill directory contain no separate NOTICE file. No upstream files have been modified. Preserve attribution and exact bytes when updating. The loader rejects missing, changed, oversized or escaping files and unsupported license identifiers.

## Runtime selection

Motion principles and SVG techniques are common. Science subjects add diagrams. Narrative subjects add existing JavaScript/character references. People described in the teacher request, frozen narration, whole-film visual prompt, section visual prompts or revision instructions add character construction, contacts and acting references. Character stories default to detailed pixel art and add pixel readability plus simple walk/idle guidance, including stories outside narrative subjects. Formulas, graphs and experiments retain clear diagram references; mixed stories can load both. Explicit teacher or local style requests take precedence; negative pixel requests suppress pixel-specific chapters. Automatically written whole-film prompts cannot silently override the configured default.

The adapter explicitly overrides incompatible upstream instructions. The model authors its own complete HTML/CSS/JS/Canvas/SVG, reuses its character definitions internally, keeps proportions and contacts stable, and favors simple readable gestures with anticipation and holds. References do not install a fixed renderer, skeleton engine, action whitelist, game state machine, external framework or approval step. Pixel density stays consistent without forcing low resolution. Narration, absolute-time renderFrame(t), natural transitions and the existing sandbox remain authoritative.

Content-level style defaults are saved in new version snapshots and sent to both the whole-film expression pass and the HTML writer as visual_style. Initial generation and checkpoint code repair use the same request builder and reference selection. Repair preserves frozen narration and verified audio. Only relevant sections are included, bounded to 23,500 serialized characters including metadata and adapter.

Version snapshots record bundle commits and digest. New generation uses current references; an existing raw-HTML checkpoint and voice-only revisions may reuse sealed HTML. This change does not force existing previews to regenerate or change their playback/compiler digest. Audio fingerprints do not depend on the reference bundle. Historical completed movies remain unchanged.

## Packaging and verification

The backend Dockerfile copies app/ including the registry, references and licenses. No extra dependency, database migration or port change is required. Test selection, negative styles, license/integrity checks and context budgets in tests/test_animation_skills.py; real pipeline request injection, checkpoint repair, audio reuse and export behavior in tests/test_direct_pipeline.py. These tests prove request wiring and technical compatibility; artistic quality still requires inspecting generated animation.
