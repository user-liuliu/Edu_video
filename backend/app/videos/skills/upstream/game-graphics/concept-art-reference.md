# Concept Art & Character Design

## The Concept Art Process

Concept art translates ideas into visual blueprints that guide production. Work from broad to specific:

```
Research & References → Thumbnails → Silhouettes → Rough Sketches → Refined Design → Turnaround → Production Spec
```

### Step 1: Research & Moodboards

Before drawing, collect references:
- **Visual references**: Real-world objects, animals, architecture, clothing for the setting
- **Tonal references**: Games/films with the mood you want
- **Historical references**: Armor, weapons, clothing from the appropriate era/culture
- **Color inspiration**: Photos, paintings, palettes from nature

Organize into a mood board with annotations on what specifically you're referencing (silhouette from A, color from B, texture from C).

### Step 2: Thumbnail Exploration

Draw 10–20 tiny (2–3 cm) sketches exploring vastly different designs. Focus on:
- Overall shape and proportions
- Pose and attitude
- Key identifying features
- Silhouette readability

Spend 1–3 minutes per thumbnail. Quantity over quality at this stage.

### Step 3: Silhouette Design

Fill thumbnails as solid black shapes. The **5-second scan rule**: if the character isn't recognizable as a solid silhouette at thumbnail size, the design needs more distinct shapes.

Strong silhouettes have:
- Clear head-body-limb separation
- Recognizable gear/props breaking the outline
- Asymmetry (more interesting than symmetrical shapes)
- A distinct "skyline" — the outline contour tells a story

Weak silhouettes:
- Generic human outline without distinguishing features
- All detail is internal (visible only with color/shading)
- Overly complex — reads as noise at small sizes

## Shape Language

Shapes communicate personality before the player reads any detail:

| Shape | Association | Character Types |
|-------|-------------|----------------|
| **Circle** | Friendly, soft, approachable, round | Healers, companions, cute creatures |
| **Square** | Stable, sturdy, reliable, strong | Tanks, guards, builders, robots |
| **Triangle** | Aggressive, fast, dangerous, sharp | Villains, rogues, predators, spikes |

### Applying Shape Language

- Build the **overall silhouette** from the primary shape
- Use **secondary shapes** for complexity (triangle villain with circular soft spot)
- Apply to **face design** (round face = friendly, angular face = threatening)
- Extend to **props and gear** (round shield = defensive, jagged sword = aggressive)

### Size and Proportion as Character

| Proportion | Feeling | Common For |
|-----------|---------|------------|
| 1–2 heads tall | Cute, chibi, mascot | Puzzle games, casual |
| 3–4 heads tall | Stylized, cartoonish | Platformers, adventure |
| 5–6 heads tall | Semi-realistic, heroic | RPGs, action |
| 7–8 heads tall | Realistic, mature | Realistic games |
| 8+ heads tall | Heroic, exaggerated | Power fantasy |

Pick a head-to-body ratio and use it consistently across all characters in your game.

## Character Turnaround Sheets

A turnaround sheet is the production blueprint for a character.

### Essential Views

```
Front (0°)  →  ¾ Front (45°)  →  Side (90°)  →  ¾ Back (135°)  →  Back (180°)
```

At minimum: Front, Side, Back. For 3D modelers or detailed 2D: add ¾ views.

### Turnaround Construction

1. Draw **proportion guides** (horizontal lines at key landmarks: head top, chin, shoulders, waist, hips, knees, feet)
2. Start with **front view** — establish proportions and symmetry
3. Draw **side view** on same guides — maintain all height landmarks
4. Draw **back view** — mirror front for symmetry, show back details (hair, cape, backpack)
5. Add **¾ view** — most challenging, shows volume and depth
6. Clean line art pass with consistent stroke weight
7. Flat color pass (no shading) in separate layer groups

### Turnaround Checklist

- [ ] Consistent proportions across all views (use alignment guides)
- [ ] All design elements visible in at least one view
- [ ] Clean line art, consistent stroke weight
- [ ] Flat color (no shading) — shading is a production decision, not a design decision
- [ ] Call-out notes for hidden details (underside of hat, back of belt)
- [ ] Scale reference (generic human outline or object for size comparison)

### Export Specs

| Use | Format | Resolution |
|-----|--------|-----------|
| Working file | PSD/KRA | 300 DPI, layers intact |
| Review/sharing | PNG | 4000 px wide, sRGB |
| Portfolio | PNG/PDF | High-res, annotated |
| Quick reference | JPG | 800 px, < 150 KB |

## Expression Sheets

Show the character's personality through facial expressions:

### Core Expressions (minimum 6)

1. **Neutral/default** — resting face
2. **Happy/smiling** — genuine warmth
3. **Angry/determined** — combat or confrontation
4. **Sad/worried** — defeat or empathy
5. **Surprised/shocked** — discovery moments
6. **Confident/smirk** — victory or swagger

### Drawing Expressions

Focus on three areas:
- **Eyebrows**: Most expressive feature — angle and curve drive emotion
- **Eyes**: Wide vs narrow, pupil position, eyelid shape
- **Mouth**: Curve, opening, teeth visibility

For pixel art expressions at small resolutions:
- 16x16 faces: Eyebrows and mouth shape do all the work (2–3 px each)
- 32x32 faces: Can add eye detail and slight head tilt
- 64x64+ faces: Full expression range with nuance

## Creature & Enemy Design

### Design Process

1. **Define the role** first (what does this enemy DO in gameplay?)
2. **Silhouette communicates threat level** — larger, spikier = more dangerous
3. **Color signals danger** — red/purple = threatening; green/brown = ambient
4. **Animate the most important action** first (usually attack or approach)

### Enemy Readability Hierarchy

Players must instantly identify:
1. **Is this an enemy?** (color/shape contrast with friendlies/environment)
2. **How dangerous is it?** (size, color intensity, shape complexity)
3. **What attack does it use?** (visual telegraphing — wind-up animation)
4. **What is its weak point?** (glowing spot, different color, exposed area)

### Common Enemy Archetypes

| Type | Behavior | Design Notes |
|------|----------|-------------|
| Fodder | Walks toward player, low HP | Small, simple, round shapes |
| Ranged | Stays back, shoots | Distinct "weapon" appendage |
| Charger | Rushes player | Streamlined, triangular, forward-leaning |
| Tank | Slow, high HP, blocks | Large, square, armored |
| Flying | Aerial movement | Wings prominent in silhouette |
| Boss | Multi-phase, special attacks | 2–4x player size, unique palette |

## Props, Weapons & Items

### Weapon Design

- Silhouette should communicate weapon type at a glance
- In pixel art, exaggerate size (a 2-pixel sword reads as a stick — make it 4–6 px wide)
- Match weapon shape language to wielder (angular weapons for angular characters)
- Design the held pose first — the weapon must read correctly in the character's hand

### Item & Pickup Design

Items must be recognizable at game resolution against any background:
- Use strong, saturated colors (distinct from environment palettes)
- Add a subtle glow, bob, or sparkle animation for pickups
- Standardize a size for inventory icons vs world sprites
- Group similar items with shared visual elements (all potions are bottles, all gems are faceted)

### Icon Design for Inventory/UI

| Size | Detail Level | Tips |
|------|-------------|------|
| 8x8 | Silhouette only | One recognizable shape, 2–3 colors |
| 16x16 | Basic detail | Add small defining features |
| 24x24 | Good detail | Room for highlights and material suggestion |
| 32x32 | Rich detail | Full shading, material quality visible |

## NPC & Party Member Design

### Visual Differentiation

Players must distinguish characters at a glance. Use at least 2 of these differentiators per character:
- **Color**: Each character owns a primary color
- **Silhouette**: Different body type, posture, or gear outline
- **Size**: Height and bulk variation
- **Props**: Signature weapon or accessory
- **Animation style**: Movement personality (bouncy vs rigid vs flowing)

### Role Signaling

Design should communicate gameplay role:
- **Healer**: Soft colors (white/green), rounded shapes, staff or book
- **Warrior**: Bold colors (red/silver), square shapes, heavy weapon
- **Rogue**: Dark colors (purple/black), triangular shapes, daggers
- **Mage**: Saturated colors (blue/purple), flowing shapes, orb or wand

## Style Consistency Across Characters

### Creating a Character Style Sheet

Document these rules before your second character:
1. **Head-to-body ratio** (e.g., 1:2.5 for all characters)
2. **Eye style** (dots, circles, detailed?)
3. **Hand style** (mitts, fingers, claws?)
4. **Outline treatment** (black, dark tone, none?)
5. **Shading steps** (2-step, 3-step?)
6. **Palette rules** (shared shadow colors? max colors per character?)

### Common Consistency Mistakes

- Protagonist has 32 colors, enemies have 8 (jarring contrast)
- One character has detailed eyes, another has dot eyes
- Mixing 1x and 2x pixel resolution in the same scene
- Different outline colors/weights between characters
- Inconsistent light direction on different characters
