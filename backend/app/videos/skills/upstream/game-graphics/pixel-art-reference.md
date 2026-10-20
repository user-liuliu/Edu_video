# Pixel Art Deep Dive

## Color Theory for Pixel Art

### Hue Shifting

Never shade by adding black/white. Instead, shift hue as you change value:

```
Highlights → shift toward WARM (yellow/orange), increase saturation slightly
Midtones   → base hue, full saturation
Shadows    → shift toward COOL (blue/purple), decrease saturation slightly
```

This produces vibrant, natural-looking pixel art. Compare:
- Bad: Red → Dark Red → Near Black (just darkening)
- Good: Orange-Red → Red → Blue-Red → Dark Purple (hue shifting)

### Building Color Ramps

A color ramp is a sequence of colors from light to dark for a single material:

```
4-step ramp (minimum for most styles):
  Highlight → Base → Shadow → Dark Shadow

6-step ramp (smooth shading for larger sprites):
  Bright Highlight → Highlight → Light Base → Base → Shadow → Dark Shadow
```

Ramp construction rules:
- 3–6 steps per ramp depending on sprite size
- Adjacent colors should be visually distinct (if you squint and they merge, increase contrast)
- Share shadow/highlight ramp endpoints across materials for palette cohesion
- Test ramps at 1x zoom — if values merge, increase contrast

### Palette Construction Methods

**Complementary**: Base hue + opposite on color wheel for accents. High contrast, energetic.

**Analogous**: 2–3 adjacent hues. Harmonious, natural. Good for environments.

**Triadic**: Three evenly spaced hues. Balanced, vibrant. Good for characters.

**Temperature-based**: Warm foreground subjects, cool backgrounds. Creates natural depth.

### Emotional Color Associations

| Color | Mood/Use |
|-------|----------|
| Red | Danger, health, fire, aggression |
| Blue | Water, ice, calm, sadness, magic |
| Green | Nature, healing, poison, money |
| Yellow | Energy, light, electricity, caution |
| Purple | Magic, royalty, mystery, corruption |
| Orange | Fire, warmth, autumn, energy |
| Pink | Love, charm, whimsy |
| Brown/Tan | Earth, wood, leather, mundane |
| Gray | Metal, stone, neutrality, technology |

## Advanced Shading

### Dithering Patterns

Dithering simulates gradients by alternating pixels of two colors:

```
50% dither (checkerboard):     25% dither:              Stylized dither:
■□■□■□                         ■□□□■□                   ■□□□□□
□■□■□■                         □□□□□□                   □□■□□□
■□■□■□                         □□■□□□                   □□□□■□
□■□■□■                         □□□□□□                   ■□□□□□
```

When to dither:
- Retro aesthetic (NES/Game Boy style)
- Large color gradients with limited palette
- Sky/water backgrounds
- Material textures (metal sheen, fabric)

When NOT to dither:
- Modern hi-bit pixel art (use more color steps instead)
- Very small sprites (dithering becomes noise)
- Areas requiring clean readability

### Anti-Aliasing (AA)

Manual AA smooths jagged edges by placing intermediate-color pixels:

```
Without AA:          With AA:
■■■■                 ·■■■■
    ■■■■               ░■■■■
        ■■■■             ░■■■■

■ = outline color    ░ = intermediate color    · = lighter intermediate
```

AA rules:
- Use max 2 intermediate colors between outline and background/fill
- Only AA curves and diagonals — never straight horizontal/vertical lines
- Don't AA the outer edge if using transparent backgrounds (AA against unknown bg = halo artifacts)
- AA internal color boundaries for smooth shapes within sprites
- At small resolutions (16x16 and below), AA is often counterproductive

### Selective Outlining

Instead of uniform black outlines, vary outline color based on context:

```
Top edge (lit side):     Use lighter dark tone or skip outline entirely
Bottom edge (shadow):    Use darkest value
Interior boundaries:     Use darker shade of fill color, not black
Background-facing edge:  Use contrasting dark for separation
```

This creates depth and volume that uniform outlines cannot achieve.

## Sub-Pixel Animation

Sub-pixel animation creates the illusion of movement smaller than one pixel by shifting anti-aliasing colors rather than moving the sprite's silhouette.

### How It Works

For a 2-pixel-wide arm that needs to "shift" half a pixel right:

```
Frame 1 (centered):     Frame 2 (shifted right):
  ██                       ░█
  ██                       ░█

█ = full color    ░ = anti-aliased intermediate
```

The silhouette stays the same, but the visual weight shifts. At game speed, the eye perceives smooth sub-pixel movement.

### Applications

- **Idle breathing**: Subtle chest/belly expansion on small characters
- **Head bobbing**: Slight vertical motion during walk cycles
- **Floating objects**: Smooth hovering motion
- **Cloth/hair sway**: Wind or movement secondary motion
- **Eye blinking**: On sprites too small for actual pixel changes

### Implementation Tips

- Works best at small resolutions (8x8 to 32x32) where individual pixels matter most
- Requires understanding of which colors blend at your target display resolution
- Test at 1x zoom — the effect should be subtle, not distracting
- Classic examples: Metal Slug idle animations, Super Metroid Samus breathing

## Readability Guidelines

### The Squint Test

Squint at your sprite (or zoom to 25%). You should still be able to:
1. Identify what the character/object IS
2. Distinguish it from the background
3. Tell which direction it faces
4. Recognize the current action/pose

If any fail, increase contrast, simplify detail, or strengthen the silhouette.

### Readability by Sprite Size

| Size | Detail Level | Tips |
|------|-------------|------|
| 8x8 | Iconic, 2–3 colors | Every pixel defines shape; no room for detail |
| 16x16 | Simple features, basic animation | Face = 2–4 pixels; suggest detail, don't render it |
| 32x32 | Clear features, good animation | Room for expression; hands/feet still simplified |
| 64x64 | Detailed, near illustration | Can include facial expressions, clothing detail |

### Background Contrast

Ensure sprites read against ALL backgrounds they'll appear on:
- Test against lightest and darkest backgrounds in your game
- Use outline or rim lighting if backgrounds vary dramatically
- Reserve your brightest/most saturated colors for foreground gameplay elements
- Backgrounds should be lower contrast and less saturated than gameplay sprites

## Common Pixel Art Mistakes

1. **Pillow shading** — Shading radiates from center outward (like a pillow). Fix: pick a consistent light direction
2. **Banding** — Equal-width strips of color running parallel. Fix: vary band widths, use dithering
3. **Jaggies** — Inconsistent stair-step patterns on curves/diagonals. Fix: maintain consistent pixel runs (e.g., 3-2-1 not 3-1-2)
4. **Too many colors** — Using the full RGB spectrum. Fix: limit palette, share colors
5. **Noise** — Single stray pixels that don't contribute to form. Fix: every pixel must serve shape, shading, or detail
6. **Mixels** — Mixing pixel resolutions (e.g., 1x outline with 2x fill). Fix: pick one resolution and stick to it
7. **Overshading** — Too many shading levels making sprites look muddy. Fix: 2–4 values per color ramp
