---
name: cms-plugin-tailwind
description: >-
  Style Cloudflare Workers CMS plugin admin views with the host CMS's Tailwind
  ("host-subset Tailwind"). Use this whenever you are writing or converting the
  HTML/liquid markup of a CMS plugin's admin UI — plugins that return fragments
  with the `x-cms-chrome: 1` header and get wrapped in the host admin shell, or
  any task that says "convert this plugin's CSS to Tailwind", "style the plugin
  admin pages", "make the plugin match the CMS theme", or touches a plugin's
  `views/sections/*.liquid` / `views/layout/default.liquid`. The key trap this
  skill exists to prevent: the host compiles Tailwind by scanning only its OWN
  files, so utility classes the host never uses are PURGED and silently do
  nothing in the plugin — you must restrict yourself to the host's emitted class
  set. Reach for this skill even if the user just says "use tailwind here" while
  working in a Workers CMS plugin repo.
---

# Host-subset Tailwind for Workers CMS plugins

## The architecture (why this is different from normal Tailwind)

A CMS plugin is a separate Cloudflare Worker. Its admin pages are liquid
fragments. When the plugin returns HTML with the header `x-cms-chrome: 1`, the
**host CMS** wraps that fragment in its own admin layout, which loads the host's
single compiled stylesheet (`/assets/admin.css` — Tailwind v4). So the plugin
never ships its own CSS; it borrows the host's.

This has one consequence that drives everything below:

> The host compiles Tailwind by scanning **only its own source files**
> (`@source "../../views"`, etc.). Any utility class that does not appear in the
> host's own templates is **purged from `admin.css`** and will silently have no
> effect when the plugin uses it.

So you cannot freely write any Tailwind class. You must use the **subset the host
already emits**. Reasonable-looking classes like `grid-cols-3`, `w-1/3`,
`items-start`, `no-underline`, `box-border`, or arbitrary values like
`min-h-[18rem]` are often **missing**. Using them produces a page that looks
broken in ways that are invisible in the markup — there is no error, the style
just doesn't apply.

A bonus of borrowing the host stylesheet: the host's `@theme` remaps color tokens
(e.g. it may reskin `indigo`/`gray` to a custom palette). Because v4 utilities
resolve `var(--color-*)`, using `text-indigo-600` / `bg-gray-50` makes the plugin
**inherit the host theme automatically**. Prefer the host's color vocabulary over
hardcoded hex.

## Workflow

### 1. Find the host's compiled stylesheet

It is the file the host admin layout links as `/assets/admin.css`. In the host
repo it is the build output, typically `views/assets/admin.css` (source lives in
something like `src/styles/admin.css` with `@import "tailwindcss"` + `@source`).
If you don't know where the host repo is, ask the user — you need this file to
know what's available.

### 2. Extract the available class set

Run the bundled script against the compiled CSS. It lists every utility class the
host emits, and can check a candidate list for you:

```bash
# Dump the whole available set (grouped):
python scripts/check_classes.py path/to/admin.css

# Check specific candidates (space- or comma-separated, or via --file):
python scripts/check_classes.py path/to/admin.css --check "grid-cols-3 w-1/3 max-w-[9rem] divide-y"
```

Treat the script's output as ground truth. **Never assume a class exists** — if
`--check` reports it MISSING, pick a substitute that's present.

### 3. Convert the markup, class by class

Replace any bespoke stylesheet / custom classes with host-available utilities.
See `references/class-map.md` for a ready-made mapping from common UI pieces
(page header, card, table, button, form field, badge) to the exact utility
strings, plus the standard substitutions for the classes that are usually purged.

Because the old descendant-selector stylesheet (`.table td {…}`, `.table a {…}`)
is gone, you must put utilities on **every** `th`, `td`, and table `<a>`
directly. This is verbose but it's how the host's own views are written — match
them.

### 4. Handle the genuinely-unavailable cases

A few needs have no host-emitted utility. Don't force a purged class; instead:

- **Responsive grids** (`grid-cols-3`/`6` usually absent): use what's present,
  e.g. `grid grid-cols-2 sm:grid-cols-3`.
- **Arbitrary one-off sizes** (`min-h-[18rem]`, exotic `max-w-[…]`): prefer an
  HTML attribute (`rows="16"` on a `<textarea>`) or keep a small inline
  `style="max-width:54rem"`. Inline `style` is fine — the host CSP allows
  `style-src 'self' 'unsafe-inline'`. Note arbitrary-value classes are JIT-only,
  so unless the host happens to emit that exact value, it'll be purged.
- **Things Tailwind preflight already does**: the host loads preflight, which
  strips `<a>` underlines and sets `box-sizing: border-box` globally. So you do
  NOT need `no-underline` or `box-border` (both commonly purged anyway).

### 5. Verify

- `grep -rn "ev-\|<style" views` (or the project's old class prefix) to confirm no
  stale custom classes / stylesheet blocks remain.
- Re-run `check_classes.py --file` with every distinct class you used to confirm
  all are present.
- Run the plugin's `typecheck` and `test` scripts.

## Pitfalls

- **Silent purging is the #1 failure.** If a style "isn't working," your first
  suspicion should be that the class isn't in `admin.css`, not that the markup is
  wrong. Check it.
- **Don't add the plugin to the host's `@source`** unless the user explicitly
  wants to couple the repos and rebuild the host CSS — that's a different
  approach. This skill is the no-host-changes path.
- **Don't ship a second Tailwind/preflight** from the plugin; the host already
  provides preflight, and a duplicate inline reset can override the host theme
  tokens (showing default colors instead of the themed ones).
- **Never use `| escape` in plugin admin views** (since 2026-07: host auto-escape).
  The host's browser renderer runs LiquidJS with `outputEscape: 'escape'`, so
  every `{{ }}` output is HTML-escaped automatically — an explicit `| escape`
  now DOUBLE-escapes (users see literal `&amp;`). For pre-rendered, sanitized
  HTML passed in as data (server-built SVG, diff HTML), opt out per-output with
  `| raw`. Exception: views rendered by a plugin's own SERVER-side engine
  (e.g. cms-plugin-events' MJML email set, cms-plugin-checkin's
  checkin-confirm.liquid) are NOT auto-escaped and keep explicit `| escape` —
  see the "two engines, two contracts" note in each plugin's
  src/templates/liquid.ts.
