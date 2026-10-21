# Sprite Animation Deep Dive

## Animation Principles for Games

### Keyframes vs In-Betweens

**Keyframes** define the extreme poses of an action — the essential positions that communicate the movement. **In-betweens** (tweens) fill the gaps for smoothness.

For pixel art, work keyframe-first:
1. Draw the contact/extreme poses (keyframes)
2. Test the animation with just keyframes
3. Add in-betweens only where needed for readability
4. Remove frames that don't add information

### Timing and Spacing

Timing (how long each frame holds) matters more than frame count:

```
Even timing:    ●───●───●───●───●    (mechanical, robotic)
Ease-in:        ●─●──●───●────●      (accelerating — start of jump)
Ease-out:       ●────●───●──●─●      (decelerating — landing)
Ease both:      ●─●──●───●──●─●      (natural — most organic motion)
```

Use **hold frames** — frames displayed longer than others — to add weight and emphasis:
- Hold the anticipation pose 2–3 frames before a fast strike
- Hold the impact frame 1–2 extra frames on landing
- Hold the peak of a jump for 1 frame for floaty feel

### Frame Rate Guidelines

| Animation Type | FPS | Reasoning |
|---------------|-----|-----------|
| Idle | 4–6 | Slow, ambient; shouldn't distract |
| Walk | 8–10 | Natural walking cadence |
| Run | 10–15 | Faster without being frantic |
| Attack/VFX | 12–20 | Snappy, responsive game feel |
| UI animations | 15–30 | Smooth polish elements |

Different animations on the same character can run at different frame rates.

## Walk Cycle Anatomy

### 4-Frame Walk (Small Sprites)

```
Frame 1: Contact      Frame 2: Passing       Frame 3: Contact      Frame 4: Passing
(right foot forward)  (right foot passing)   (left foot forward)   (left foot passing)

  ○                     ○                      ○                     ○
 /|\                   /|\                    /|\                   /|\
 / \                   ||                     / \                   ||
L   R                  R L                   R   L                 L R
```

Key principles:
- **Contact pose**: Legs at widest extension, body at lowest point
- **Passing pose**: Weight on one leg, other leg passing, body at highest point
- The up-down bounce (2–3 pixels) sells the walk
- Arms swing opposite to legs
- Head bobs with the body — don't keep it static

### 6–8 Frame Walk (Larger Sprites)

Add in-between frames:
1. Contact (right forward)
2. Down/Recoil (body drops, absorbs step)
3. Passing (weight transfers)
4. Up/Reach (body rises, extends next step)
5. Contact (left forward)
6. Down/Recoil
7. Passing
8. Up/Reach

### Walk Cycle Checklist

- [ ] Body bobs up and down (not just legs moving)
- [ ] Arms swing opposite to legs
- [ ] Torso has subtle lean in movement direction
- [ ] Head follows body bob (not floating independently)
- [ ] Loops seamlessly (last frame flows into first)
- [ ] Works when mirrored for opposite direction

## Run Cycle

Run differs from walk in key ways:

| Aspect | Walk | Run |
|--------|------|-----|
| Contact | Always one foot on ground | Both feet leave ground (flight phase) |
| Body lean | Slight | Pronounced forward lean |
| Arm swing | Small | Exaggerated, bent arms |
| Bounce | 2–3 px | 3–5 px |
| Stride | Short | Long |

### Run Cycle Structure (6 Frames)

1. **Contact** — Front foot strikes ground, body compressed
2. **Push-off** — Back leg extends, body launches
3. **Flight up** — Both feet airborne, body at highest point
4. **Reach** — Front leg extends forward for next contact
5. **Contact** (opposite leg)
6. **Flight** (opposite side)

## Attack Animations

### Three-Phase Structure

Every attack needs three distinct phases:

```
ANTICIPATION (wind-up)  →  ACTION (strike)  →  RECOVERY (follow-through)
   2–3 frames               1–2 frames            2–3 frames
   Slow, builds tension      Fast, impactful        Returns to idle
```

**Anticipation**: Movement opposite to strike direction. Sword raised behind, fist pulled back.

**Action**: The actual strike. Keep this SHORT (1–2 frames) for snappy game feel. Use smear frames or motion trails.

**Recovery**: Follow-through after the hit. Can be shortened or cancelled for combo systems.

### Smear Frames

A smear frame stretches the weapon/limb across the arc of motion in a single frame, creating a motion blur effect:

```
Normal frames:    Smear frame:
  /                 ╱╱╱╱
 ○                 ○
```

Use smear frames for:
- Fast weapon swings
- Punch/kick arcs
- Projectile launches
- Rapid turns/dashes

### Hit Feedback

Reinforce attacks with visual feedback:
- **Hitstop**: Freeze both attacker and target for 2–5 frames on impact
- **Screen shake**: 1–3 pixel displacement for 3–5 frames
- **Flash white**: Target flashes white/bright for 1 frame
- **Knockback**: Target pushed away from hit direction
- **Particles**: Spawn impact sparks, slash trails, debris

## Idle Animation

The most-seen animation. Keep it subtle:

### Simple Idle (2–3 Frames)
- Frame 1: Base pose
- Frame 2: Slight chest expansion (1 px up) — breathing in
- Frame 3: Optional transitional frame back to base

### Detailed Idle (4–6 Frames)
Add personality: weight shifting, blinking, looking around, hair/cape sway.

Rules:
- Must loop seamlessly
- Should not be distracting during gameplay
- Play at 3–6 FPS (slower than other animations)
- Show character personality (warrior: weapon ready; mage: magic particles)

## Jump Animation

Jumps are often **pose-based** rather than frame-animated — the game state drives which pose is shown:

```
State: ASCENDING     → Show crouch/launch frame
State: PEAK          → Show stretched/reaching frame
State: DESCENDING    → Show falling/bracing frame
State: LANDING       → Show impact squash (2–3 frames, then idle)
```

Squash and stretch sells the jump:
- **Crouch before jump**: Character squashes down 1–2 pixels
- **Peak**: Character stretches 1–2 pixels taller
- **Landing**: Character squashes again, then returns to normal height

## Directional Sprites

### How Many Directions?

| Facing System | Directions | Assets Needed | Common In |
|---------------|-----------|---------------|-----------|
| Side-only | 1 (+flip) | 1 set | Platformers |
| 4-directional | 4 | 3 sets (side is mirrored) | Top-down RPGs |
| 8-directional | 8 | 5 sets (mirror 3) | Isometric, tactical |

**Mirror trick**: Draw right-facing sprites only; flip horizontally in code for left-facing. Saves 50% of directional work. Exception: asymmetric characters (shield on one arm).

### Drawing Order for Directions

Start with the **side view** — it shows the most character profile and is easiest to animate. Then:
1. Side view (primary)
2. Front view (down-facing)
3. Back view (up-facing)
4. Diagonals (if using 8-direction)

## Animation State Machine

Structure character animations as a state machine:

```
         ┌─────────┐
         │  IDLE   │◄──────────────────────┐
         └────┬────┘                        │
              │ move input                  │ no input + grounded
              ▼                             │
         ┌─────────┐                        │
         │  WALK   │────────────────────────┤
         └────┬────┘                        │
              │ speed > threshold           │
              ▼                             │
         ┌─────────┐                        │
         │   RUN   │────────────────────────┤
         └────┬────┘                        │
              │ jump pressed                │
              ▼                             │
         ┌─────────┐    landed              │
         │  JUMP   │───────────────────────►│
         └────┬────┘                        │
              │ attack pressed              │
              ▼                             │
         ┌─────────┐    anim complete       │
         │ ATTACK  │──────────────────────►─┘
         └─────────┘
```

### Transition Rules

- **Interruptible**: Idle, Walk, Run can be immediately interrupted by any action
- **Non-interruptible**: Attack plays to completion (or to a defined cancel window for combos)
- **Priority**: Hurt/Death override all other animations
- **Blending**: For smooth transitions, last frame of current anim should visually connect to first frame of next anim

## Sprite Sheet Organization

### Layout Conventions

```
Row 0: Idle (all directions)
Row 1: Walk (all directions)
Row 2: Run (all directions)
Row 3: Attack (all directions)
Row 4: Jump phases
Row 5: Hurt / Death
```

### Export Checklist

- [ ] Consistent frame size across all animations (even if sprite doesn't fill frame)
- [ ] 1–2 px padding between frames
- [ ] Transparent background (alpha channel)
- [ ] Character centered/grounded consistently in each frame
- [ ] Total sheet dimensions are power-of-2 (or engine handles packing)
- [ ] Accompanying JSON/XML metadata with frame rects and animation definitions
- [ ] Named animation tags (idle, walk, run, attack) in metadata

## Onion Skinning

Onion skinning displays previous/next frames as transparent overlays while drawing:

- **Previous frames** (typically red-tinted): Shows where you came from
- **Next frames** (typically blue/green-tinted): Shows where you're going
- Display 1–2 frames in each direction for most work
- Essential for smooth transitions between keyframes
- Available in Aseprite, Krita, Piskel, and most animation tools

## Production Tips

- **Animate before detailing**: Get the motion right with rough shapes, then refine the pixel art
- **Test at game speed early**: An animation that looks great frame-by-frame may not work at 10 FPS
- **Reuse frames**: Walk and run cycles can share some contact poses
- **Mirror trick**: Draw one direction, mirror for the other (saves ~50% work)
- **Modular characters**: Separate head/torso/legs for mix-and-match or procedural animation
- **Reference videos**: Record yourself performing the action for timing reference
- **Study games you admire**: Frame-step through animations in your favorite pixel art games
