# Design System Inspired by Apple (Ludens Mobile UI)

## 1. Visual Theme & Atmosphere

The design philosophy for the Ludens Compose Multiplatform app is reductive to its core: every pixel
exists in service of the product, and the interface itself retreats until it becomes invisible. This
is not minimalism as aesthetic preference; it is minimalism as reverence for the object and
gameplay.

The typography anchors everything. **Plus Jakarta Sans** is used for display and headings, offering
a geometric, clean look that feels machined rather than typeset — precise, confident, and
unapologetically direct. At display sizes (56sp), weight SemiBold (600) with a tight line-height
creates headlines with billboard-like impact. For body text, **Inter** provides exceptional
readability. At body sizes (17sp), the rhythm is comfortable without ever feeling slack.

The color story is starkly binary, implemented via Material 3 color schemes (`Theme.kt` /
`Color.kt`). Sections alternate between pure black (`#000000`) backgrounds with white text and light
gray (`#F5F5F7`) backgrounds with near-black text (`#1D1D1F`). This creates a cinematic pacing —
dark themes feel immersive and premium, light themes feel open and informational. The only chromatic
accent is Ludens Primary Blue (`#0071E3`), reserved exclusively for interactive elements: links,
buttons, and focus/pressed states. This singular accent color gives every interactive element
unmistakable visibility.

**Key Characteristics:**

- **Typography**: `Plus Jakarta Sans` for titles/headings; `Inter` for body and small UI. Use
  `MaterialTheme.typography` slots.
- **Binary Rhythm**: Sections alternate between Pure Black (`#000000`) and Light Gray (`#F5F5F7`),
  mapped to `colorScheme.background` and `colorScheme.surfaceContainerLowest`.
- **Accent**: `Primary Blue (#0071E3)` reserved exclusively for `colorScheme.primary` and
  interactive elements.
- **Subtle Roundness**: Buttons use `RoundedCornerShape(8.dp)`; Cards use
  `RoundedCornerShape(11.dp)`.
- **Providers**: Use `LocalSpacing.current` for distances and `LocalRadius.current` (wrapped in
  `RoundedCornerShape`) for consistency.
- **Atmosphere**: Cinematic pacing with high contrast and tight typography.

## 2. Color Palette & Roles

| Role                | Material 3 Property                   | Light Theme | Dark Theme | Use Case                   |
|---------------------|---------------------------------------|-------------|------------|----------------------------|
| **Background**      | `colorScheme.background`              | `#F5F5F7`   | `#000000`  | Main background mode       |
| **Surface Lowest**  | `colorScheme.surfaceContainerLowest`  | `#FFFFFF`   | `#000000`  | Flat sections, pure canvas |
| **Surface Low**     | `colorScheme.surfaceContainerLow`     | `#F9F9FB`   | `#242426`  | Subtle containers          |
| **Surface High**    | `colorScheme.surfaceContainerHigh`    | `#EDEDF2`   | `#272729`  | Elevated sections          |
| **Surface Highest** | `colorScheme.surfaceContainerHighest` | `#E8E8ED`   | `#2A2A2D`  | Highest contrast sections  |
| **Primary**         | `colorScheme.primary`                 | `#0071E3`   | `#0071E3`  | Main CTA background        |
| **Tertiary**        | `colorScheme.tertiary`                | `#0066CC`   | `#2997FF`  | Inline links / Actions     |

### Text Roles

- **High Emphasis**: `colorScheme.onSurface` (#1D1D1F on light, #FFFFFF on dark).
- **Medium Emphasis**: `colorScheme.onSurfaceVariant` (#86868B).
- **Disabled**: `colorScheme.outline` (#D2D2D7).

### Elevation (Shadows)

- **Product Card**: Soft diffused shadow using `Modifier.shadow` with `elevation = 8.dp`.
- **Color**: `Color.Black.copy(alpha = 0.22f)`.

## 3. Typography Rules

### Font Family

- **Display**: `Plus Jakarta Sans` (Geometry and precision for headings)
- **Body**: `Inter` (Readability and optical balance for body/UI text)
- Plus Jakarta Sans is used at 20sp and above; Inter is optimized for 19sp and below.

### Hierarchy

| Role                | Material 3 Slot  | Font              | Size | Weight | Line Height |
|---------------------|------------------|-------------------|------|--------|-------------|
| **Display Hero**    | `displayLarge`   | Plus Jakarta Sans | 56sp | 600    | 60sp        |
| **Section Heading** | `displayMedium`  | Plus Jakarta Sans | 40sp | 600    | 44sp        |
| **Tile Heading**    | `displaySmall`   | Plus Jakarta Sans | 28sp | 400    | 32sp        |
| **Nav Heading**     | `headlineLarge`  | Plus Jakarta Sans | 34sp | 600    | 50sp        |
| **Sub-nav**         | `headlineMedium` | Plus Jakarta Sans | 24sp | 300    | 36sp        |
| **Card Title**      | `titleLarge`     | Plus Jakarta Sans | 21sp | 700    | 25sp        |
| **Body**            | `bodyLarge`      | Inter             | 17sp | 400    | 25sp        |
| **Caption**         | `bodyMedium`     | Inter             | 14sp | 400    | 20sp        |
| **Micro**           | `bodySmall`      | Inter             | 12sp | 400    | 16sp        |
| **Label Bold**      | `labelSmall`     | Inter             | 12sp | 600    | 16sp        |

### Principles

- **Functional assignment**: Plus Jakarta Sans is used for large Display text, giving it a modern
  geometric punch; Inter takes over for smaller text where legibility is paramount.
- **Weight restraint**: The scale spans Light (300) to Bold (700), but most text lives at Regular (
  400) and SemiBold (600).
- **Negative tracking at all sizes**: Subtle negative letter-spacing is applied even at body sizes (
  -0.37sp at 17sp) to create universally tight, efficient text.
- **Extreme line-height range**: Headlines compress to 1.07 while body text opens to 1.47. This
  dramatic range creates clear visual hierarchy through rhythm alone.

## 4. Component Stylings

### Buttons

**Primary Blue (CTA)**

- Background: `MaterialTheme.colorScheme.primary`
- Text: `MaterialTheme.colorScheme.onPrimary`
- Padding: `8.dp` vertical, `15.dp` horizontal
- Shape: `RoundedCornerShape(LocalRadius.current.standard)` (8.dp)
- Border: none
- Typography: `MaterialTheme.typography.bodyLarge`
- Use: Main action ("Start", "Play")

**Primary Dark / Secondary**

- Background: `MaterialTheme.colorScheme.secondary`
- Text: `MaterialTheme.colorScheme.onSecondary`
- Shape: `RoundedCornerShape(LocalRadius.current.standard)` (8.dp)
- Use: Secondary actions, dark theme alternatives

**Subtle / Link Action**

- Background: `Color.Transparent`
- Text: `MaterialTheme.colorScheme.tertiary`
- Shape: `RoundedCornerShape(LocalRadius.current.standard)` (8.dp)
- Border: `1.dp` solid `MaterialTheme.colorScheme.outlineVariant`
- Typography: `MaterialTheme.typography.bodyMedium`
- Use: Inline links, tertiary actions

**Media / Control Action**

- Background: `Color.Black.copy(alpha = 0.64f)`
- Shape: `RoundedCornerShape(LocalRadius.current.pill)` (980.dp)
- Use: Joysticks, floating media controls

### Cards & Containers

- Background: `MaterialTheme.colorScheme.surfaceContainerLowest`
- Shape: `RoundedCornerShape(LocalRadius.current.comfortable)` (11.dp)
- Shadow: `Modifier.shadow(elevation = 8.dp)`
- Use: Game tiles, settings sections, elevated content

### Navigation

- Background: Translucent dark `Color(0xCC000000)` with `Modifier.blur(20.dp)` (Glassmorphism
  effect)
- Height: `48.dp` (compact top bar) or `56.dp` (standard top bar)
- Text: `MaterialTheme.colorScheme.onSurface`, weight 400
- Active: Highlighted icon/text
- Logo: App icon centered or left-aligned
- Navigation Paradigm: Bottom Navigation for main sections, Top App Bar for contextual actions, or
  full-screen overlays (Dialog/BottomSheet) for settings.
- The navigation floats above content, maintaining its translucent glass regardless of section
  background.

### Image Treatment

- Products/Game elements on solid-color fields (black or white) — no backgrounds, no context, just
  the object.
- Edge-to-edge images that span the entire screen width.
- Lifestyle/Contextual images confined to rounded-corner containers (`12.dp`+ corner radius).

### Distinctive Components

**Main Screen Hero**

- Full-screen-width section with solid background (black or `#F5F5F7`).
- Game/App name as the primary headline (Plus Jakarta Sans, 56sp, weight SemiBold).
- Two CTA buttons side by side or stacked vertically depending on screen size.

**Game/Content Grid Tile**

- Square or near-square card on contrasting background (`Card` composable).
- Image dominating 60-70% of the tile.
- Title + one-line description below.

**Settings List**

- Vertical scroll of setting options (`LazyColumn`).
- Each setting as a row with an icon, title, and a control (Switch, Slider) aligned to the end.
- Minimal chrome — the controls speak for themselves.

## 5. Layout Principles

### Spacing System

Access via `LocalSpacing.current`.

| Property      | Value   | Use Case                   |
|---------------|---------|----------------------------|
| `hairline`    | `2.dp`  | Micro separators           |
| `extraSmall`  | `4.dp`  | Tight grouping             |
| `small`       | `8.dp`  | Standard element spacing   |
| `comfortable` | `11.dp` | Input padding              |
| `medium`      | `14.dp` | Standard component padding |
| `large`       | `17.dp` | Section spacing            |
| `extraLarge`  | `24.dp` | Major screen margins       |

### Radius System

Access via `LocalRadius.current`.

| Property      | Value    | Use Case                  |
|---------------|----------|---------------------------|
| `micro`       | `5.dp`   | Small tags                |
| `standard`    | `8.dp`   | Buttons, small cards      |
| `comfortable` | `11.dp`  | Standard cards, inputs    |
| `large`       | `12.dp`  | Large containers          |
| `pill`        | `980.dp` | Joysticks, circular icons |

## 6. Depth & Elevation

| Level                 | Treatment                                        | Use                                  |
|-----------------------|--------------------------------------------------|--------------------------------------|
| Flat (Level 0)        | No shadow, solid background                      | Standard content sections, text rows |
| Glass (Level 1)       | `Modifier.blur(20.dp)` on translucent background | Top bars or floating menus           |
| Subtle Lift (Level 2) | `elevation = 8.dp` / `shadow`                    | Product cards, elevated buttons      |
| Focus (Level 3)       | Primary Blue border or glow                      | Active selection or keyboard focus   |

**Elevation Philosophy**: Use elevation sparingly. Most depth comes from background contrast rather
than heavy shadows. When shadows are used, they should be soft and diffused (`spotColor` with low
alpha).

## 7. Do's and Don'ts

### Do

- Use **Plus Jakarta Sans** at 20sp+ and **Inter** below 20sp.
- Apply negative letter-spacing at all text sizes — keep typography tight.
- Use **Primary Blue (`#0071E3`)** ONLY for interactive elements.
- Alternate between `background` and `surfaceContainerHigh` for cinematic rhythm.
- Use `LocalRadius.current.standard` (8.dp) for standard buttons.
- Keep game/product imagery on solid-color fields with no competing visual elements.
- Use the translucent glass effect (`Modifier.blur`) for sticky navigation bars.
- Compress headline line-heights — keep headlines billboard-like.

### Don't

- Don't introduce additional accent colors — stick to the blue chromatic budget.
- Don't use heavy shadows or multiple shadow layers.
- Don't use borders on cards or containers (use elevation or color contrast instead).
- Don't apply wide letter-spacing to the primary fonts.
- Don't use weight Black or ExtraBold unless for massive hero titles (SemiBold/700 is the standard
  max).
- Don't add textures, patterns, or gradients to backgrounds — solid colors only.
- Don't center-align body text — body copy is left-aligned.

## 8. Responsive Behavior (Mobile & Tablet)

### Breakpoints (dp)

| Name             | Width     | Key Changes                                      |
|------------------|-----------|--------------------------------------------------|
| Small Mobile     | <360dp    | Compact single column, reduced padding           |
| Standard Mobile  | 360-480dp | Single column, standard padding                  |
| Tablet Portrait  | 600-840dp | 2-column grids begin, expanded typography        |
| Tablet Landscape | >840dp    | 3-column grids, maximum content width maintained |

### Touch Targets

- **Primary CTAs**: Minimum height `48.dp` for comfortable tapping.
- **Navigation links**: `48.dp` height with adequate horizontal spacing.
- **Media controls**: Circular buttons, minimum `44.dp x 44.dp`.

### Scaling Strategy

- **Headlines**: Scale from 56sp (Tablet) -> 40sp (Mobile) -> 28sp (Small Mobile).
- **Grids**: 3-column (Landscape) -> 2-column (Portrait) -> single column stacked (Mobile).
- **Images**: Maintain aspect ratio; products should never be cropped.

## 9. Agent Prompt Guide (Compose Multiplatform)

### Quick Reference

- **Primary**: `MaterialTheme.colorScheme.primary` (#0071E3)
- **Background**: `MaterialTheme.colorScheme.background` (#000000 / #FFFFFF)
- **Spacing**: `LocalSpacing.current.medium` (14.dp)
- **Radius**: `LocalRadius.current.standard` (8.dp) for buttons, `comfortable` (11.dp) for cards.
- **Typography**: `MaterialTheme.typography.displayLarge` (56sp SemiBold).

### Example Prompts

- "Create a hero Box on background. Headline displayLarge, white. Two buttons in a Row: Primary (
  standard radius) and Secondary (outlined standard radius)."
- "Design a product Card using surfaceContainerLowest, comfortable radius, and 8.dp elevation.
  Content uses bodyLarge for title."
- "Build a list of settings rows using LocalSpacing.current.medium for padding and labelSmall for
  secondary text."

### Iteration Guide

1. **Interactive Accent**: Only use `colorScheme.primary` (#0071E3) for interactivity. No other
   chromatic colors allowed.
2. **Binary Backgrounds**: Alternate sections between pure Black and `surfaceContainerLowest` (
   #F5F5F7).
3. **Typography Rules**: `Plus Jakarta Sans` for titles (20sp+); `Inter` for body and small text.
   Never mix these roles.
4. **Spacing Integrity**: Always use `LocalSpacing.current.*` properties. Avoid hardcoded `dp` for
   padding/margins.
5. **Radius Consistency**: Use `LocalRadius.current.standard` (8.dp) for buttons and `comfortable` (
   11.dp) for cards.
6. **The Glass Effect**: Top bars and overlays MUST use `Modifier.blur(20.dp)` with translucent
   backgrounds.
7. **Minimalist Shadows**: Shadows are only for elevated cards. Use soft alpha (0.22) and high blur.
8. **Product Focus**: Game elements or product images must sit on solid-color fields, never on
   complex backgrounds.
