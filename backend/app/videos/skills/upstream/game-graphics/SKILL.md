---
name: game-graphics
description: >
  Game graphics and visual art reference covering pixel art, sprite creation, character design,
  animation, concept art, tilesets, UI/HUD design, VFX, and art direction. Includes color theory,
  shading techniques, sprite sheet specifications, animation cycles, sub-pixel animation,
  anti-aliasing, outline styles, parallax, lighting, and style guide creation. Tool guidance for
  Aseprite, Pyxel Edit, Piskel, Krita, and Photoshop. Use when creating game art, designing
  characters, making pixel art, building sprite sheets, animating sprites, creating tilesets,
  designing game UI, establishing art direction, or answering questions about 2D game graphics.
---

# Game Graphics & Visual Art Reference

## Art Production Pipeline

Every game art project follows this flow — scale steps to your scope:

```
1. Art Direction    → Define style, palette, resolution, proportions
2. Concept Art      → Silhouettes, thumbnails, turnarounds, expression sheets
3. Asset Production → Sprites, tiles, UI elements, backgrounds, VFX
4. Animation        → Keyframes, in-betweens, timing, state machines
5. Polish           → Anti-aliasing, sub-pixel animation, particles, lighting
6. Export & Integration → Sprite sheets, atlases, engine import
```

## Tool Recommendations

| Task | Primary Tool | Free Alternative |
|------|-------------|-----------------|
| Pixel art & animation | **Aseprite** ($20, one-time) | Piskel (browser), LibreSprite |
| Tileset creation | Aseprite, Pyxel Edit | Piskel, GIMP |
| Concept art / painting | Krita (free), Photoshop | GIMP, MediBang |
| Tile map editing | Tiled, LDtk | Built-in engine editors |
| Sprite sheet packing | TexturePacker | Free alternatives in engines |
| Vector art | Inkscape (free), Illustrator | — |

**Aseprite** is the gold standard for pixel art. Key features: onion skinning, timeline tagging, integrated tilemap editor, palette management, live preview, indexed color mode.

## Pixel Art Fundamentals

### Resolution & Canvas Size

Choose resolution based on target style:

| Style | Sprite Size | Tile Size | Color Count |
|-------|------------|-----------|-------------|
| 8-bit (NES) | 8x8 – 16x16 | 8x8, 16x16 | 4–16 |
| 16-bit (SNES) | 16x16 – 32x32 | 16x16 | 16–32 |
| Hi-bit (modern) | 32x32 – 64x64 | 16x16, 32x32 | 32–256+ |
| HD pixel | 64x64 – 128x128 | 32x32, 64x64 | Unlimited |

Use **power-of-2 dimensions** (16, 32, 64, 128, 256) for GPU texture optimization. Always scale with **integer multiples** (1x, 2x, 4x) using nearest-neighbor filtering.

### Color Palettes

Start limited — constraints drive creativity:

- **Per character**: 4–8 base colors + 2–3 shading levels each
- **Per tile set**: 8–16 colors for visual cohesion
- **Global palette**: Share shadow/highlight colors across all assets

Build palettes with purpose:
1. Pick a **base hue** for the character/element
2. Add **1–2 darker values** for shadows (shift hue toward cool/purple)
3. Add **1 lighter value** for highlights (shift hue toward warm/yellow)
4. Add **accent color** for contrast and focal points
5. Define **outline color** (pure black, dark tone, or selective)

**Hue shifting**: Don't just darken/lighten the same hue. Shift shadows toward blue/purple and highlights toward yellow/orange for richer, more natural color.

### Shading Techniques

| Technique | Description | When to Use |
|-----------|-------------|-------------|
| **Flat** | No shading, base colors only | Minimalist/retro styles |
| **Cel shading** | 2–3 hard-edged value steps | Most pixel art styles |
| **Dithering** | Alternating pixels of two colors | Faux gradients, retro look |
| **Anti-aliased** | Intermediate colors at edges | Smooth curves, large sprites |
| **Sub-pixel** | Color shifts suggesting detail smaller than 1px | Small sprites, animation |

Pick a single **light source direction** (typically top-left at ~45 degrees) and apply consistently across all assets.

### Outline Styles

| Style | Look | Best For |
|-------|------|----------|
| **Black outline** | Strong silhouette, classic pixel art | Small sprites, busy backgrounds |
| **Dark-tone outline** | Softer, uses darker shade of fill color | Larger sprites, painterly feel |
| **Selective outline** | Outline only on exterior/shadow side | Natural look, advanced technique |
| **No outline** | Shapes defined by color contrast alone | Painterly, hi-bit styles |

## Character Design Quick Start

1. **Silhouette first** — Must be recognizable at thumbnail size
2. **Shape language** — Circles = friendly, Squares = sturdy, Triangles = aggressive
3. **Readable at 1x** — If the sprite is 32x32, it must read clearly at 32x32 pixels
4. **Consistent proportions** — Define head-to-body ratio and use across all characters
5. **Color identity** — Each major character gets a distinct primary color

### Standard Character Sprite Sizes

| Game Type | Recommended Size | Notes |
|-----------|-----------------|-------|
| Platformer | 16x16 to 32x32 | Celeste: 16x16, Shovel Knight: 28x32 |
| RPG (top-down) | 16x16 to 24x32 | Stardew Valley: 16x32 |
| Fighting | 48x48 to 128x128 | Larger for detail and animation |
| Strategy | 16x16 to 32x32 | Must read clearly when zoomed out |

## Animation Essentials

### Frame Counts by Action

| Action | Frames | FPS | Notes |
|--------|--------|-----|-------|
| Idle | 2–4 | 4–6 | Subtle breathing/bobbing |
| Walk | 4–8 | 8–10 | 4 for small sprites, 6–8 for larger |
| Run | 6–8 | 10–15 | Faster timing, not necessarily more frames |
| Jump | 3–5 | — | Ascend, peak, descend (often pose-held) |
| Attack | 3–6 | 12–20 | Anticipation → strike → recovery |
| Death | 4–8 | 8–12 | Often non-looping |
| Hurt/Hit | 2–3 | 12–15 | Quick flash or knockback |

### The 12 Principles (Applied to Pixel Art)

Focus on these for 2D games:
- **Squash & Stretch** — Compress on land, elongate on jump
- **Anticipation** — Wind-up before actions (attack pullback)
- **Follow-through** — Hair, cape, weapon continue after body stops
- **Ease in/out** — Slow start and end, fast middle
- **Timing** — Fewer frames = snappy; more frames = fluid
- **Exaggeration** — Push poses beyond reality for game feel

### Sprite Sheet Export Specs

```
Format:      PNG (lossless, alpha channel)
Padding:     1–2px between frames (prevents texture bleed)
Layout:      Horizontal strip or grid
Dimensions:  Power-of-2 total sheet size preferred
Scaling:     Integer only (1x, 2x, 4x) with nearest-neighbor
Mobile alt:  WebP (40% smaller than PNG)
```

Include JSON/XML metadata with frame rectangles and animation definitions for engine import.

## Art Direction & Style Guide

Before creating your second asset, lock down these six pillars:

1. **Resolution** — Sprite and tile pixel dimensions
2. **Palette** — Exact colors (hex codes), max count per asset
3. **Outline rules** — Style, color, thickness
4. **Shading style** — Technique, number of value steps, light direction
5. **Animation timing** — Default FPS, frame counts per action
6. **Proportions** — Head-to-body ratio, limb thickness, stylization level

Create a **calibration asset** (one finished character + one finished tile) as the visual benchmark. All subsequent assets must match this reference.

### Common Style Inconsistencies to Avoid

- Mixing outline styles (black on some sprites, none on others)
- Inconsistent shadow colors or light direction
- Different sprite resolutions in the same scene
- Varying levels of detail between foreground and background
- Mismatched animation frame rates

## Additional Resources

Detailed deep-dives for each topic area:

- [pixel-art-reference.md](pixel-art-reference.md) — Advanced pixel art: dithering patterns, hue shifting, anti-aliasing, sub-pixel animation, color ramps, readability
- [animation-reference.md](animation-reference.md) — Walk/run/attack cycles, state machines, onion skinning, frame timing, directional sprites, animation principles
- [concept-art-reference.md](concept-art-reference.md) — Character turnarounds, expression sheets, silhouette design, shape language, creature design, props and weapons
- [environment-ui-reference.md](environment-ui-reference.md) — Tilesets, autotiling, parallax, lighting, particles, UI/HUD design, backgrounds, VFX
