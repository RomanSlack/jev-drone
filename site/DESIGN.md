# DESIGN.md - jev-drone site

## Context (from discovery)

- Artifact type: research project page (single long-form technical article with figures). Closest catalog types: blog/editorial + docs.
- Positioning: technical, research-grade, honest.
- Audience: robotics and ML engineers, people evaluating TypeSafe Jev | Primary action: open the GitHub repo.
- Adjectives: exact, measured, quiet, honest, technical.
- Visual word translations:
  - exact -> hairline rules, 2px radius, tabular mono numerals, figures drawn from recorded data
  - measured -> numbered figures with captions, tables over cards, stated caveats given equal visual weight to results
  - quiet -> pure white, one accent, no shadows, no decorative motion
  - honest -> caveat block uses the same rule weight as the abstract; baseline is always drawn next to Jev
  - technical -> mono labels, plain engineering grotesque headings, serif body as in a paper
- Aesthetic essence: white lab notebook.
- Single-minded proposition: a narrow claim, carefully shown.
- References: admire distill.pub (figures carry the argument), Swiss timetables (rules and mono labels); avoid startup landing pages and dark "AI" gradients.
- Mode: light only | Density: airy prose, dense figures.
- Constraints: Next.js App Router, plain CSS custom properties, no UI library, WCAG 2.2 AA, must work at 375px.

## Aesthetic

- Direction: "Flight Log" (Swiss base + editorial paper structure).
- Defining trait: text, rules and numbered figures on a paper column. No cards as content containers; the only boxed things are figures.
- Signature move: two-ink figures. Everything that is ordinary code is blue, everything that is Jev is orange, in every diagram, so the page's central claim (the model is one small layer) is visible at a glance. The orange appears almost nowhere else.

## Typography

- Display: IBM Plex Sans 500/600, normal width | Google Fonts | OFL
- Body: Source Serif 4 | Google Fonts | OFL
- Mono: IBM Plex Mono (labels, numerals, code) | OFL
- Scale: ratio 1.25, base 17px

| step | size | line-height | use |
|------|------|-------------|-----|
| h1 | clamp(2.1rem, 1.2rem + 3.6vw, 3.6rem) | 1.04 | page title |
| h2 | 1.65rem | 1.15 | section |
| lead | 1.3rem | 1.45 | standfirst |
| h3 | 1.2rem | 1.3 | subsection |
| body | 1.0625rem | 1.62 | text |
| small | 0.72-0.9rem | 1.5 | captions, mono labels |

- Measure: 42rem prose, 62rem figures. Headings tracked -0.02em. Mono labels uppercase, +0.06em.

## Color

- Strategy: white paper, near-black ink with a slight blue cast, one signal orange taken from the project's own HUD. Blue is reserved for "code" in diagrams. No indigo, no gradients.
- Distribution: ~90 neutral / 5 blue / 5 orange.
- Palette (role -> OKLCH | hex approx):
  - bg: #ffffff
  - surface: oklch(0.975 0.003 255) | #f7f8f9
  - fg / rule: oklch(0.21 0.02 255) | #121921
  - muted: oklch(0.47 0.02 255) | #535c66 (6.8:1 on white)
  - border: oklch(0.89 0.006 255) | #dcdee2
  - jev (fills, marks): oklch(0.66 0.19 48) | #ea6300 (3.3:1, graphics only)
  - jev-ink (text): oklch(0.53 0.17 42) | #b73d00 (5.7:1 on white)
  - jev-wash: oklch(0.96 0.03 60)
  - code: oklch(0.52 0.11 240) | #1870a1 (5.4:1 on white)
  - code-wash: oklch(0.95 0.02 240)
- No semantic success/error colors: the page has no forms or status.

## Spacing, radius, shadow

- Spacing base 4px: 4, 8, 12, 16, 24, 40, 64, 104. Tight inside figures, 64px between sections.
- Radius: 2px only.
- Shadow approach: defined edge. 1px borders and rules, no shadows anywhere.

## Layout and composition

- Grid: >=1160px a sticky contents rail (11rem) plus article column; figures run wider (62rem) than prose (42rem), left-aligned, never centered. Below that, one column with 20px (32px >=640) gutters.
- Signature layout move: the header and article share the rail offset, so the title hangs on the same left edge as the prose and the contents rail sits in the margin like a paper's running index.
- Responsive: mobile-first. Breakpoints 640, 900, 1160.
- Mobile rules: diagrams built in HTML/CSS reflow (rate ladder, loop, bars, budget). Only the course map scrolls sideways (min-width 680px) and says so. The 5-column flight log table scrolls; every other table wraps.

## Components and states

- Buttons: primary filled ink (hover jev-ink, active ink), quiet outlined (hover ink border). 44px min height, 36px small. One primary per view.
- Links: ink text, orange underline; hover text goes jev-ink.
- Tables: text left, numerals right in tabular mono, 1px row separators, ink rule under the header.
- Details (FAQ): native details/summary, +/- marker, 44px target.
- Focus ring: box-shadow 0 0 0 2px bg, 0 0 0 4px jev-ink, on every interactive element. Skip link present.
- No forms, overlays or loading states exist on this page.

## Motion

- 140ms ease-out color transitions on links and buttons only. Smooth anchor scroll. Nothing animates on scroll or on load.
- prefers-reduced-motion: transitions and smooth scroll off.

## Iconography

- One icon: the GitHub mark, 16px, currentColor. Favicon is a custom four-rotor glyph with an orange core.

## Imagery and illustration

- Mode: real artifacts only. Video and stills are frames from the recorded run; the course map, the example judgment and the 82% figure are computed from `data/flight.json`, exported from the flight tape.
- Dark HUD screenshots sit in a near-black frame so their edges do not flare against white.
- Avoid: generated imagery, 3D renders, decorative drone art.

## Accessibility

- AA contrast verified for fg, muted and jev-ink on white. Color is never the only signal: Jev vs baseline bars differ by hatch, code vs Jev nodes are labelled, plot lines differ by dash.
- SVG figures carry title and desc. Video has controls, is muted, does not autoplay. Scrollable code blocks are focusable.
- Heading order h1 > h2 > h3 with no skips.

## Tokens (source of truth)

See `app/globals.css` `:root`. Adapter: plain CSS custom properties. If they drift, this file wins.

## SEO

- One indexable page, canonical `/`, site URL from `NEXT_PUBLIC_SITE_URL`.
- Metadata, Open Graph and Twitter card (`public/og.png`, rendered from `og/og.html` with headless Chrome at 1200x630), apple touch icon, `robots.ts`, `sitemap.ts`, `public/llms.txt`.
- JSON-LD: TechArticle, SoftwareSourceCode (codeRepository = GitHub), VideoObject, FAQPage.

## Slop audit

- Date: 2026-09-21 | Result: pass after 3 fixes.
- Fixed: course-map legend collided with axis labels; numeric table columns touched the next column; tables hid their value column on phones.
- Checked at 375px and 1440px. No gradient text, no cards grid, no eyebrow pill, no shadows, single accent outside the violet band, no em dashes in copy. Figure numbers are sequential by nature.

## Changelog

- 2026-09-21: initial system and build.
- 2026-09-21: headings moved from wide Archivo to IBM Plex Sans (the expanded width read as styled, not technical); mono to IBM Plex Mono to match. Flight path figure promoted to Fig. 2, directly under the video.
