---
name: SonettoHere
description: A ReAct AI Agent desktop client with multi-LLM support
colors:
  bg-primary: "#ffffff"
  bg-secondary: "#f9fafb"
  bg-card: "#ffffff"
  text-primary: "#1f2937"
  text-secondary: "#6b7280"
  text-tertiary: "#9ca3af"
  accent: "#000000"
  accent-light: "#b9b9b9"
  border: "#e5e7eb"
  user-bubble-bg: "#ffffff"
  status-ok: "#000000"
  status-error: "#ef4444"
  status-warn: "#f59e0b"
typography:
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.6
  message:
    fontFamily: "inherit"
    fontSize: "16px"
    lineHeight: 1.6
  code:
    fontFamily: "'SF Mono', 'Consolas', monospace"
    fontSize: "13px"
  label:
    fontSize: "11px"
    fontWeight: 600
    letterSpacing: "0.5px"
    textTransform: "uppercase"
rounded:
  sm: "6px"
  md: "8px"
  lg: "10px"
  xl: "14px"
  pill: "100px"
  full: "50%"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "48px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "#ffffff"
    rounded: "{rounded.sm}"
    padding: "10px 24px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.text-secondary}"
    borderColor: "{colors.border}"
    rounded: "{rounded.sm}"
    padding: "6px 14px"
  input:
    backgroundColor: "{colors.bg-primary}"
    textColor: "{colors.text-primary}"
    borderColor: "{colors.border}"
    rounded: "{rounded.sm}"
    padding: "8px 12px"
  chat-bubble-user:
    backgroundColor: "{colors.user-bubble-bg}"
    textColor: "{colors.text-primary}"
    borderColor: "{colors.text-primary}"
    rounded: "{rounded.xl}"
  chat-bubble-assistant:
    backgroundColor: "{colors.bg-card}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.xl}"
  nav-item:
    rounded: "{rounded.lg}"
    padding: "8px 12px"
  card-container:
    backgroundColor: "{colors.bg-card}"
    borderColor: "{colors.border}"
    rounded: "{rounded.lg}"
  tool-bubble:
    backgroundColor: "{colors.bg-card}"
    borderColor: "{colors.border}"
    rounded: "{rounded.lg}"
---

# Design System: SonettoHere

## 1. Overview

**Creative North Star: "The Workbench"**

SonettoHere is a workbench. In the center sits the conversation — the piece being crafted. Around it, arranged with intention, sit the tools: session management, provider configuration, memory inspection, environmental controls. The workbench is clean and organized, every tool has its place, and nothing distracts from the work itself.

The design is a deliberate **restrained monochrome** system: black, white, and grays only. The absence of color is the point — it keeps the eye on the content, not the chrome. Black (`--accent: #000000`) serves as the sole accent, used sparingly for primary actions, interactive elements, and wayfinding. The palette is inspired by precision instruments and well-organized workshops: functional, tactile, and quietly confident.

**This system explicitly rejects:** SaaS dashboard clichés (colored side-stripe borders, gradient accents, glassmorphism), generic AI-chat clones (rounded pill inputs, pastel bubbles, avatar-heavy layouts), and any decorative flourish that competes with the conversation.

### Key Characteristics:
- Monochrome palette (chroma 0) with black as the single accent
- Clean, bordered components with generous whitespace
- Tactile interactions — buttons have clear hover and active transformations
- Content-forward layout; UI chrome recedes unless needed
- Dark-on-light for readability; no dark mode by default
- System-adaptive font stack with full CJK support

## 2. Colors

A restrained monochrome palette. Every surface, border, and text color stays on the gray axis (chroma 0). The sole exception is `status-error` (`#ef4444`) and `status-warn` (`#f59e0b`), used exclusively for functional signaling.

### Primary
- **Pure Black** (`#000000`): The only accent color. Used for primary buttons, active navigation states, link text, scroll markers, and status indicators. Its rarity is the point — black draws attention because almost nothing else does.

### Neutral
- **Crisp White** (`#ffffff`): Main application background (`--bg-primary`), card surfaces (`--bg-card`), and user message bubbles. The dominant surface color.
- **Cloud Gray** (`#f9fafb`): Sidebar background, secondary surfaces, hover state backgrounds (`--bg-secondary`). The subtlest depth cue.
- **Ink** (`#1f2937`, gray-800): Body text (`--text-primary`). Near-black for comfortable reading, softer than pure black.
- **Mist Gray** (`#6b7280`, gray-500): Secondary text, labels, descriptive information (`--text-secondary`). For metadata and hints.
- **Silver Gray** (`#9ca3af`, gray-400): Tertiary text, placeholder text (`--text-tertiary`). The most muted legible gray.
- **Line Gray** (`#e5e7eb`, gray-200): Borders, dividers, section separators (`--border`). Thin, unobtrusive.
- **Pewter** (`#b9b9b9`): Light accent, running-state borders on tool bubbles (`--accent-light`).

### Status
- **Alert Red** (`#ef4444`): Error states, destructive actions, error banners.
- **Amber** (`#f59e0b`): Warning states, private-mode indicators, auto-approve indicators.

### Named Rules
**The One Voice Rule.** Black is the single accent. No secondary accent color competes with it. Status colors (red, amber) appear only for their functional purpose and never as decoration.

**The Gray Gradient Rule.** The neutral ramp (white → cloud → line → silver → mist → ink) covers exactly six stops. Each stop has a distinct role. No mid-tone grays are added for "texture" or "atmosphere."

## 3. Typography

**Body Font:** System UI stack — `-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif`
**Code Font:** `'SF Mono', 'Consolas', monospace`

**Character:** A single humanist sans-serif stack adapted for bilingual content (English + CJK). The pairing is the OS's own native type — familiar, fast-loading, and guaranteed to render well in Chinese. No custom fonts, no web font overhead. The confidence comes from clarity, not typographic novelty.

### Hierarchy
- **Body** (400 weight, 15px, 1.6 line-height): Default application text. Navigation items, labels, descriptions, tool content. Max line length is unconstrained by design but components self-limit via max-width on chat and content areas.
- **Message** (400 weight, 16px, 1.6 line-height): Chat conversation text. Slightly larger than body for comfortable reading. Always rendered in markdown.
- **Code / Mono** (400 weight, 13px): Inline code, code blocks, version labels, timestamps, monospace data.
- **Label** (600 weight, 11px, 0.5px letter-spacing, uppercase): Section headers in sidebar, popup headers, metadata labels. Always uppercase for wayfinding.
- **Headings (in Markdown)** (600 weight, 1.5em/1.3em/1.15em/1em/0.9em/0.85em, 1.3 line-height): Only appear in rendered markdown content. Not used in UI chrome.

### Named Rules
**The No-Webfont Rule.** All type is system-native. Zero font downloads, zero FOIT, zero layout shift from type loading. The application loads and renders instantly regardless of network.

**The Size-On-Demand Rule.** Font sizes are not a modular scale. Components pick the size that fits their information density. Chat messages are 16px for readability; sidebar items are 14px for density; labels are 11px for metadata. No fixed ratio binds them.

## 4. Elevation

A **layered shadow system**. Depth is conveyed exclusively through box-shadows, never through tonal background shifts or color overlays (the sidebar's background blur is the single intentional exception). Shadows are subtle — low opacity, warm-tinted black — and increase in spread as the elevation grows.

### Shadow Vocabulary
- **Ambient Glow** (`--shadow-xs`: `0 1px 3px rgba(0, 0, 0, 0.04)`): The lightest touch. Used for hairline seperation of grouped elements.
- **Surface Soft** (`--shadow-soft`: `0 8px 24px rgba(0, 0, 0, 0.06)`): Large-area glow under elevated surfaces like the chat input.
- **Card Rest** (`--shadow-sm`: `0 1px 4px rgba(0, 0, 0, 0.06)`): Default card elevation. Tool bubbles, provider cards, empty-state cards.
- **Card Elevated** (`--shadow-md`: `0 2px 8px rgba(0, 0, 0, 0.08)`): Active/hover card states, message bubbles.
- **Dropdown Lift** (`--shadow-lg`: `0 4px 16px rgba(0, 0, 0, 0.12)`): Settings popup, drop-down menus, hover cards, context menus.
- **Modal Float** (`--shadow-xl`: `0 6px 28px rgba(0, 0, 0, 0.18)`): Constify cards, heavy floating elements, confirmation dialogs.

### Named Rules
**The Flat-By-Default Rule.** Surfaces are flat at rest. Shadows appear only as a response to state (hover, focus, elevation) or to distinguish layered chrome (dropdowns, popups). A card at rest uses `shadow-sm` as its resting elevation, not zero — the subtle separation is the baseline, not an effect.

**The One-Blur Exception.** The sidebar uses a blurred background image with a white overlay (`#ffffffd3`). This is the only decorative blur in the system. It adds texture without breaking the monochrome discipline. No other surface uses backdrop-filter.

## 5. Components

### Buttons
- **Shape:** Gently rounded corners (6px radius). The send button is an exception — circular (34×34px, 50% radius).
- **Primary (`--accent` black bg):** For primary actions ("前往模型设置", "+ 添加提供商", confirm actions). Black background (`--accent`), white text, 10px 24px padding. Hover reduces opacity to 85% — no color shift, no shadow addition. The black is the statement.
- **Ghost (`transparent` bg):** For secondary/inline actions. Transparent background, `--text-secondary` text, 1px solid `--border` on hover reveals the hit area. Active: `--bg-secondary` background.
- **Circle Send (`--accent` bg, 50% radius):** Chat send button. 34×34px. Black bg, white icon. Hover: scale 1.08, subtle shadow, background shifts to blue (`#1d4ed8`) — the one chromatic exception in the system, signaling "send to the outside world."
- **Stop Circle (`#ef4444` red bg, 50% radius):** Stop streaming. Red background, white icon. Hover darkens to `#dc2626`.

### Inputs / Fields
- **Style:** Clean bordered fields. 1px solid `--border`, `--bg-primary` background, 6px radius. Internal padding: 8px 12px. Font inherited from body (15px).
- **Focus:** Border shifts to `--accent` (black). No glow, no ring — just a crisp black outline. The least decorative focus treatment that meets the visibility bar.
- **Placeholder:** `--text-tertiary` (#9ca3af). Left-aligned, standard weight.
- **Textarea (Chat Input):** Transparent background inside a bordered container (20px radius pill-like shape). The container has `--shadow-soft` at rest and gains a focus ring (`0 0 0 1px color-mix(in srgb, var(--accent) 10%, transparent)`) when focused.
- **Error / Disabled:** No dedicated error style. Disabled inputs use 0.4 opacity. Validation is handled via context (inline messages), not field-border color shifts.

### Navigation (Sidebar)
- **Container:** 220px wide (`--bg-secondary`), right border (`--border`). Can collapse to 58px icon-only mode.
- **Items:** 14px font, 8px 12px padding, 10px radius. Default: `--text-secondary` text on transparent bg.
- **Hover:** `--bg-card` background, `--text-primary` text.
- **Active:** `--bg-card` background, `--accent` (black) text, `font-weight: 600`.
- **Collapsed transition:** Width, padding, label visibility — all animated with 0.25s ease. Labels slide left and fade; icons center.
- **Settings area:** Pinned to the bottom via `margin-top: auto`. Opens a popup with `--shadow-lg`, `--bg-card` bg, 10px radius.

### Chat Messages (Bubbles)
- **Style:** Both user and assistant bubbles share: max-width 72%, 10px 16px padding, 14px border-radius, 16px font, `--shadow-md` elevation.
- **User bubble:** White (`--user-bubble` = `--bg-card`), 1px solid `rgba(0,0,0,0.2)`. Bottom-right corner reduced to 4px (asymmetric to denote origin).
- **Assistant bubble:** `--bg-card` background, no border. Bottom-left corner reduced to 4px.
- **Ref chips:** Small pill labels below the bubble text for file references, tool calls, cited sources.

### Chips / Tags
- **File tags:** Pill shape (`border-radius: 100px`), `--bg-secondary` background, 1px `--border` border, 11px font. Source badge inside: 9px uppercase pill with a tinted accent background. Removable via × button.
- **Model tags (Providers):** Small inline pills, `--bg-secondary` on dark, or transparent on white. 12px font, 4px radius.
- **Sub-badge (Session):** Tiny label (9px, 600 weight), border, 3px radius. `--text-secondary` on `--bg-secondary`.

### Cards / Containers
- **Tool bubbles:** 1px `--border` border, 10px radius, `--bg-card` background, `--shadow-sm` at rest. Collapsible header + body. Running state: `--accent-light` border.
- **Provider cards:** Full-width cards in a stacked layout. Headers with label + toggle switch, URL display, model tag list, action buttons at bottom.
- **Settings popup:** `position: fixed` overlay, 10px radius, `--shadow-lg`, 6px internal padding. Small header (11px uppercase) and divider-separated items.
- **Hover cards:** Used in sidebar for session details. `position: fixed`, 8px radius, `--shadow-lg`, `--bg-card` background. Appear on mouse hover with 0.15s fade-in transition.

### Toggle / Switch
- **Private mode & Auto-approve toggles:** Inline button toggle, 62px min-width, 26px height, 1px `--border` border, 6px radius. Inactive: transparent with a black dot indicator. Active: amber border+background tint, amber text+dot.
- **Provider enable toggle:** Circle switch, styled per card. Active state: black fill.

## 6. Do's and Don'ts

### Do:
- **Do** use black (`--accent: #000000`) as the single accent color. It is the only voice for primary actions, active states, and wayfinding.
- **Do** use the neutral ramp consistently: white for surfaces, cloud-gray for secondary backgrounds, ink for body text, mist-gray for labels, silver-gray for placeholders.
- **Do** keep buttons tactile — hover effects (scale, opacity shift, background fill) signal interactivity clearly.
- **Do** use asymmetric corner radii on chat bubbles (one flat corner) to distinguish speaker origin.
- **Do** use the shadow vocabulary by elevation role: card-rest → shadow-sm, popup → shadow-lg, modal → shadow-xl.
- **Do** collapse sidebar items gracefully — labels slide and fade, icons center. A single 0.25s ease curve ties the whole collapse animation.
- **Do** use the system font stack. No custom fonts, no web font loading.

### Don't:
- **Don't** use colored accents beyond black. No blue links, no green success banners, no purple branding. (Exception: red for errors, amber for warnings — functional only.)
- **Don't** use side-stripe borders (`border-left`/`border-right` at >1px as a colored accent). The system uses full borders or nothing.
- **Don't** use gradient text (`background-clip: text`) for emphasis. Use weight or size instead.
- **Don't** use glassmorphism (backdrop-filter blur on cards) as a default. The sidebar's background blur is the system's only decorative blur.
- **Don't** copy ChatGPT/Claude chat UI patterns — no pastel bubble colors, no rounded-rectangle avatar placements, no pill-shaped input bars with gradient send buttons.
- **Don't** use SaaS dashboard templates: no metric cards with big numbers + small labels, no icon+heading+text card grids, no colored left border accents.
- **Don't** add dark mode unless deliberately designed. The current system is light-mode only; dark would require rebalancing the entire neutral ramp.
- **Don't** animate layout properties (width, height, top, left). Animate transform and opacity only.
- **Don't** use numbered section markers (01/02/03) as decorative scaffolding. Numbers earn their place only when the content is an actual sequence.
- **Don't** use tiny uppercase tracked labels above every section ("ABOUT", "PROCESS", "PRICING"). One as a deliberate system is voice; on every section it's AI grammar.
