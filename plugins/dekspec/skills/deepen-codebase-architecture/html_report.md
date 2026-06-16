# HTML Report Format

A single self-contained HTML file in the OS temp dir. Tailwind + Mermaid from
CDNs. Mermaid for graph-shaped diagrams; hand-built divs / inline SVG for
editorial visuals (mass diagrams, cross-sections). Mix the two.

## Scaffold

`<!doctype html>` with `<script src="https://cdn.tailwindcss.com"></script>` and
a Mermaid ESM import from
`https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs`, then
`mermaid.initialize({startOnLoad:true,theme:"neutral",securityLevel:"loose"})`.
A small custom CSS layer (`.seam` dashed, `.leak` red, `.deep` dark gradient).
`body bg-stone-50`; `main max-w-5xl mx-auto`; a `header` plus `#candidates` and
`#top-recommendation` sections.

## Header

Repo name, date, a compact legend (solid box = module, dashed line = seam, red
arrow = leakage, thick dark box = deep). No intro paragraph.

## Candidate card

Each candidate is one `<article>`:

- **Title** — names the deepening.
- **Badge row** — recommendation strength (Strong = emerald / Worth exploring =
  amber / Speculative = slate) + a dependency-category tag (in-process /
  local-substitutable / ports & adapters / mock).
- **Files** — `font-mono text-sm`.
- **Before/After diagram** — the centrepiece, two columns.
- **Problem** — one sentence.
- **Solution** — one sentence.
- **Wins** — bullets ≤6 words, in [language.md](language.md) terms (locality and
  leverage; how tests improve).
- **ADR callout** — an amber box when the candidate contradicts an existing ADR
  under `dekspec/adrs/`.

No paragraphs of explanation.

## Diagram patterns

- **Mermaid graph** (the workhorse for dependencies / call flow) — `classDef` to
  colour leakage red + the deep module dark; sequence diagrams for round-trips.
- **Hand-built boxes-and-arrows** (when Mermaid's layout fights you) — a
  thick-bordered deep module with greyed internals.
- **Cross-section** (layered shallowness) — stacked horizontal bands.
- **Mass diagram** (interface as wide as implementation) — two rectangles per
  module.
- **Call-graph collapse** (a tree of calls → one box with faded internals).

## Style guidance

Editorial, not corporate-dashboard. Generous whitespace, serif optional for
headings. Colour sparingly: one accent (emerald / indigo) + red leakage + amber
warnings. Diagrams ~320px tall. `text-xs uppercase tracking-wider` module
labels. Only scripts: Tailwind CDN + Mermaid ESM; otherwise static.

## Top recommendation section

One larger card: candidate name, one sentence why, anchor link.

## Tone

Plain English, concise; architectural nouns / verbs straight from
[language.md](language.md). Use exactly: module / interface / implementation /
depth / deep / shallow / seam / adapter / leverage / locality. Never substitute
component / service / unit, API / signature, boundary, layer / wrapper. Wins
bullets name the gain in glossary terms. No hedging or throat-clearing.
