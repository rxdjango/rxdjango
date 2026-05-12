# Design: examples frontend

This document records the first visual and typographic decisions for the **Create React App** under `examples/frontend/`. It is a working reference for tokens and intent, not a full design system.

## Typography

- **UI and body text:** [Inter](https://fonts.google.com/specimen/Inter), loaded from Google Fonts with weights **400, 500, 600, 700** and `display=swap` to limit layout shift.
- **Default stack:** `Inter`, `system-ui`, `sans-serif` (see `examples/frontend/tailwind.config.js` → `fontFamily.sans`).
- **Code in prose / `<code>`:** the CRA stack in `index.css` — `source-code-pro`, Menlo, Monaco, Consolas, `Courier New`, monospace.
- **Code blocks in the doc column:** `font-mono` with small size and relaxed line height; line numbers in a sticky gutter for horizontal scroll of long lines.

Rationale: Inter is neutral, readable at small sizes, and works well for dense technical UIs. Monospace for snippets matches developer expectations and stays distinct from body copy.

## Color system

Colors are defined in Tailwind `theme.extend.colors` and named for **role**, not for raw hex in components.

| Token | Value | Role |
|--------|--------|------|
| `primary` (50–900 scale) | anchored at **500 = `#377771`** | Brand teal: navigation emphasis, buttons, section labels, and dark code-block backgrounds (`primary-900` with light text). |
| `primary.DEFAULT` | `#377771` | Same as 500; optional shorthand. |
| `surface` | `#F5F5F0` | App chrome: sidebar and neutral panels; warm off-white to reduce harsh contrast with white cards. |
| `ink` | `#100B00` | Primary text and borders; near-black with a slight warm bias. |

**Meta / PWA:** `theme-color` in `public/index.html` is set to **#377771** to align the browser UI with the brand.

### Usage notes

- **Borders** often use `ink` with reduced opacity (e.g. `border-ink/68`) so dividers stay subtle.
- **Page background** behind the main column uses a light primary tint (e.g. `bg-primary-100/50`) to separate content from the sidebar `surface`.
- **Active sidebar item:** primary border and light primary background (`primary-200/50` / `primary-500` accent) for a clear but calm selected state.
- **Usage column** is a white card (`bg-white`) with shadow to lift it from the doc column.

The primary scale (100–900) is available for hover states, dark code surfaces, and future components; we started from a single brand hue and stepped lightness for flexibility.

## Layout (high level)

- **Shell:** full viewport height (`h-dvh`) with **no document-level scroll** for the app chrome; the **main** pane scrolls so `position: sticky` on the Usage card behaves predictably.
- **Breakpoints:** mobile stacks documentation and Usage; from `lg` upward, two columns with documentation on the left and Usage on the right, Usage sticky within the scrollport.

These layout choices are implementation detail in `Main.tsx`; this file only captures why colors and type were chosen.

## Related files

| Area | Location |
|------|-----------|
| Tokens | `examples/frontend/tailwind.config.js` |
| Base styles | `examples/frontend/src/index.css` |
| Font loading | `examples/frontend/public/index.html` |
| Layout / composition | `examples/frontend/src/app/Main.tsx` |

When extending the palette or typography, update this document in the same change so the examples app stays intentional.
