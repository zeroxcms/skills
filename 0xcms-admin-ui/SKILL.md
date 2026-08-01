---
name: 0xcms-admin-ui
description: >-
  Admin UI for 0xCMS (Cloudflare Worker CMS) and its plugins — layout,
  styling, form controls, and field types. Use when editing admin Liquid views
  in the host (views/sections/*.liquid, snippets, layout) or in any plugin
  fragment served with `x-cms-chrome: 1`; when a task says "style the plugin
  admin pages", "make it match the CMS theme", "convert this to Tailwind",
  "update the tag edit UI", "add a language selector to this form", "replace
  this select with search / autocomplete / typeahead", "add a field type" (star
  rating, slider, color, file, picker), or touches list headers, action
  buttons, mobile labels, scrollable or paginated tables, edit-form footers, or
  double-submit protection on a mutation form. Covers the two traps that cost
  the most time: Tailwind classes the host never emits are silently PURGED, and
  client views are auto-escaped so an explicit `| escape` double-escapes.
---

# 0xCMS admin UI

Preserve the established admin interface patterns. Prefer matching the closest
existing good view over inventing a local variation.

## Source authority

Two 0xCMS hosts are live and both carry current code. They have **different
internal layouts** — resolve every path against the repo you are actually
editing.

| | `workers/cms` | `frameworks/zeroxcms/cms` |
| --- | --- | --- |
| Shape | feature-sliced | monolithic |
| Code | `src/core/`, `src/features/`, `cms.features.json`, `tools/` | `src/plugins/`, `src/utils/`, `src/security/`, `src/publish/` |
| Tailwind source | `assets-source/admin.css` | `styles/admin.css` |

Both share `src/routes/admin/`, `src/templates/`, `views/`, `migrations/`.
Roots are under `/Users/colin/Documents/code/`. Treat code and tests as
authoritative when a doc drifts.

## Rule 1 — Tailwind: the class set is fixed, and you must rebuild

The host ships **one** compiled stylesheet, `views/assets/admin.css`
(Tailwind v4), built by scanning **only the host's own source files**. Two
consequences, and they are the #1 cause of "my style isn't working":

- **In the host:** a utility class you add to a `.liquid` that no other host
  file already uses is absent from `admin.css` until you rebuild. Run
  `npm run build:css` after editing any admin view. (`npm run dev` and
  `pretest` run it; a bare `wrangler dev` does not.)
- **In a plugin:** plugin admin fragments are wrapped in the host shell and
  borrow the host's `admin.css`. A class the host never emits is **purged and
  silently dead** — and you cannot fix it by rebuilding, because the host does
  not scan the plugin. You must restrict yourself to the host's emitted set.

Verify before trusting a class. Use `grep -a` — the minified `admin.css`
contains a byte that trips grep's binary detection, and without `-a` grep exits
silently with no output, which reads exactly like "class absent":

```bash
grep -aF ".the-class" views/assets/admin.css
python3 scripts/check_classes.py path/to/admin.css --check "grid-cols-3 w-1/3 max-h-60"
```

`references/tailwind-class-map.md` maps common UI pieces (header, card, table,
button, form field, badge) to exact host-available utility strings, plus
substitutions for the classes that are usually purged.

Measured against both hosts' `views/assets/admin.css` (2026-08-02) — re-check
rather than trusting this list, it moves with the host's own markup:

- **Missing:** `grid-cols-4`, `grid-cols-6`, `w-1/3`, `w-1/2`, `min-h-[18rem]`,
  `bg-amber-100`, `line-through`.
- **Unnecessary:** `no-underline`, `box-border` — also missing, but preflight
  already does both, so you never need them.
- **Present, despite looking exotic:** `grid-cols-3`, `sm:grid-cols-3`,
  `items-start`, `max-h-60`, `inset-y-0`, `pr-9`, and the arbitrary values this
  skill recommends (`min-w-[560px]`, `text-[2rem]`, `min-w-[10rem]`).

Arbitrary-value classes are JIT-only, so one works **only** if the host happens
to emit that exact value — check before using a new one.

Substitutes when a class genuinely isn't available: use a present grid
(`grid grid-cols-2 sm:grid-cols-3`), an HTML attribute (`rows="16"` on a
textarea), or a small inline `style=""` — the host CSP allows
`style-src 'self' 'unsafe-inline'`.

Because the host's `@theme` remaps color tokens, using the host's color
vocabulary (`text-indigo-600`, `bg-gray-50`) makes a plugin inherit the host
theme automatically. Prefer it over hardcoded hex. Never ship a second
Tailwind/preflight from a plugin — a duplicate reset overrides the host's theme
tokens. Don't add a plugin to the host's `@source` unless the user explicitly
wants the repos coupled.

Component CSS lives in the host's Tailwind source file (see the table above),
alongside `.richtext-md-preview`; rebuild after touching it.

## Rule 2 — escaping: client views auto-escape

Since 2026-07 the host's browser renderer runs LiquidJS with
`outputEscape: 'escape'`, so every `{{ }}` in an admin **client view** is
HTML-escaped automatically.

- **Never write `| escape` in a host admin view or a plugin admin fragment** —
  it double-escapes and users see literal `&amp;`.
- Use `| raw` for pre-rendered, sanitized HTML passed in as data (server-built
  SVG, QR markup, diff HTML).
- **Exception — two engines, two contracts:** views rendered by a plugin's own
  *server-side* engine (`renderLiquid`: MJML email sets, QR templates,
  check-in confirmation pages) are NOT auto-escaped and keep explicit
  `| escape`. Each plugin's `src/templates/liquid.ts` documents which is which.
  A public site Worker rendering its own Liquid is also explicit-escape — see
  `0xcms-public-site`.

## Core workflow

1. Find the closest good existing view before editing:
   - **List with primary action right:** `/admin/plugins/events/events`
   - **Edit-form footer and styling:** `/admin/pages/:id/edit`
   - **Create form / plugin `newViews`:** `/admin/pages/new?page_type=<type>`
   - **Card heading that stays put while the table scrolls:**
     `/admin/plugins/events/events/:id`
   - **Table pagination footer:** `/admin/profile`, `/admin/pages/list`
2. Search for sibling views with the same pattern and update them together when
   the user asks for consistency.
3. Keep changes surgical — preserve route behavior, permissions, labels, and
   data bindings unless behavior changes were requested.
4. `npm run build:css`, then type-check: host `npm run type-check`;
   `cms-plugin-events` `npm run typecheck`; other plugins use their existing
   script.

## Page wrappers

Standard content wrapper, unless the parent renderer already supplies it:

```html
<div class="px-4 py-5 sm:px-6 sm:py-8 lg:px-8">…</div>
```

Client-rendered plugin views must receive the same wrapper spacing as host
views.

## List headers

Compact single row, title left, primary action right:

```html
<div class="flex items-center justify-between gap-4 mb-4">
  <div>
    <h1 class="text-2xl font-bold text-gray-900">Title</h1>
    <p class="mt-1 text-sm text-gray-500">Optional description.</p>
  </div>
  <a class="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 text-sm font-semibold text-white hover:bg-indigo-700">…</a>
</div>
```

Apply to taxonomies, page types, block types, tags, roles, plugins, and plugin
sections. Don't revert to `flex-col … sm:flex-row` when the Events list layout
is what was asked for.

## Buttons

Icon plus text, text hidden on mobile:

```html
<a title="New page" aria-label="New page" class="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 text-sm font-semibold text-white hover:bg-indigo-700">
  <svg class="h-4 w-4" …></svg>
  <span class="hidden lg:inline">New page</span>
</a>
```

Icon-only for search/filter submits when space matters:

```html
<button title="Search" aria-label="Search" class="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-50">
  <svg class="h-4 w-4" …></svg>
</button>
```

Rules: primary create actions right-aligned; `title` + `aria-label` whenever
visible text may be hidden; height `h-10`; `gap-2` for icon+text; `hidden
lg:inline` for mobile-hidden labels; reuse the file's existing icon sprite
conventions rather than introducing a second icon system.

## Scrollable tables

If a card has its own heading above a table, keep the header **outside** the
scroll container:

```html
<div class="bg-white rounded-xl shadow-sm border border-gray-200 mt-4">
  <div class="flex items-center justify-between gap-4" style="padding:1rem 1rem 0;margin-bottom:.75rem">
    <div>
      <h2 class="text-lg font-bold text-gray-900">Section</h2>
      <p class="mt-1 text-sm text-gray-500">Description.</p>
    </div>
  </div>
  <div class="overflow-x-auto w-full">
    <table class="w-full min-w-[560px] text-left">…</table>
  </div>
</div>
```

For a table-only card, `overflow-x-auto` on the card is fine. Use
`min-w-[560px]` for ordinary tables; a larger minimum only when the columns
genuinely need it.

Because the old descendant-selector stylesheet (`.table td {…}`) is gone, put
utilities on **every** `th`, `td`, and table `<a>` directly. Verbose, but it is
how the host's own views are written.

## Table pagination

Match `/admin/profile` and `/admin/pages/list`. Keep pagination **outside** the
table's `overflow-x-auto` container so controls stay visible while the table
scrolls.

- Localized `Showing {from}-{to} of {total}` on the left; Previous,
  `Page {page} of {pageCount}`, Next on the right.
- `flex flex-wrap items-center justify-between gap-3` so it wraps cleanly.
- Separate from the table with `border-t border-gray-100 pt-4`; add `mt-4` when
  the table provides no spacing.
- Render unavailable Previous/Next as non-interactive `<span>`, never hidden —
  preserves alignment and makes the disabled state clear.
- `h-9`, `px-3`, `text-xs`, `font-semibold`; `h-3.5 w-3.5` left arrow before
  Previous, right chevron after Next.
- Preserve active filters, searches, and other query parameters in links.
- `| t` on every visible label; `common.previous` / `common.next` for
  navigation.
- Show the footer only when navigation is useful (normally `pageCount > 1`). No
  first/last controls unless the workflow needs them.

```liquid
{% if pagination.hasPrevious %}
  <a href="{{ pagination.previousHref }}"
     class="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 text-xs font-semibold text-gray-700 hover:bg-gray-50">
    <svg class="h-3.5 w-3.5" aria-hidden="true"><use href="{{ iconHrefPrefix }}#arrow-left"></use></svg>
    {{ "common.previous" | t }}
  </a>
{% else %}
  <span class="inline-flex h-9 cursor-not-allowed items-center justify-center gap-1.5 rounded-lg border border-gray-200 bg-gray-50 px-3 text-xs font-semibold text-gray-400">
    <svg class="h-3.5 w-3.5" aria-hidden="true"><use href="{{ iconHrefPrefix }}#arrow-left"></use></svg>
    {{ "common.previous" | t }}
  </span>
{% endif %}
```

Mirror the same enabled/disabled treatment for Next. Page indicator between
both, `text-xs font-medium text-gray-500`.

## Edit form actions

Match the Page edit footer: Save/Cancel together as the primary group,
destructive actions visually separate and consistently styled, same height /
radius / weight / color treatment. Don't let action footers drift into
page-specific layouts without a real workflow difference.

**Preserve scroll during structural edits.** When an edit-form action reloads
the page to add or remove structured content, keep the vertical scroll
position. The contract in `views/sections/editor.liquid`:

- Mark the main form `data-editor-form`.
- Store the offset in `sessionStorage` under `cms-editor-scroll:<pathname>`
  before actions whose value prefix is `block-add`, `block-delete`, `item-add`,
  `item-delete`, `block-item-add`, or `block-item-delete`.
- On next load, remove the stored value and restore with
  `requestAnimationFrame` + `window.scrollTo`.
- Detect the action from the submit event's `submitter`; do not preserve scroll
  for ordinary Save, Publish, or Delete.
- Plugin-rendered edit views do **not** inherit the built-in editor's inline
  script. Reuse an approved plugin editor-scroll asset or add an external one
  with the same contract, declared in the manifest — never inline JS in a
  plugin fragment (see `0xcms-plugin-api`).

For the full translatable edit-form layout (base name + auto-slug + weight,
selector row, translated-name card, language switcher, lect wiring), see
**`references/edit-form.md`**.

## Form controls

- **Searchable pickers.** A `<select>` is fine for a small fixed set (taxonomy,
  status, language). The moment the option set can grow unbounded — pages,
  tags, users, any entity reference — use a combobox. Full recipe in
  **`references/combobox.md`**.
- **Field types.** The pagefield registry is the filesystem: a blueprint entry
  like `@score:range` renders `views/snippets/pagefield/range/basic.liquid`, so
  adding a type is adding one Liquid file. Contract, CSS-only interactivity
  rules, and uploads in **`references/pagefield-types.md`**.
- **Double submit.** The host layout carries a global submit-once guard that
  covers host forms and every chrome-wrapped plugin form; normal
  navigate-on-POST forms need nothing. The rules you must not "simplify away",
  and the escape hatches (`data-allow-resubmit`, `data-stop-continue`), are in
  **`references/submit-once.md`** — read it before adding any new mutation
  form or button.

## Shared snippets — prefer over plugin-local copies

### Pagefield renderers

Plugin form fields should use the host snippets under
`views/snippets/pagefield/<type>/<variant>.liquid`. Field view models set
`templateName` to the shared path; plugin views render it directly:

```liquid
{% render field.templateName, field: field %}
```

Do not add plugin-local wrappers (`render-field`/`editor-field`), and do not
guard on a blank `templateName` — a missing template should fail visibly so the
resolver or shared snippet gets fixed.

For client-rendered plugin views, redirect `/snippets/pagefield/...` lookups to
the host views. When moving a bespoke plugin field into core: add the host
snippet first, preserve the field contract, update the plugin resolver to emit
the shared `templateName`, then delete the plugin-local duplicate.

### Color tag picker

Use `views/snippets/color-tag-picker.liquid` for guest/contact/event color
labels:

```liquid
{% render "color-tag-picker",
  value: item.color_tag, action: item.colorAction,
  returnTo: item.returnTo, label: "Color tag" %}
```

Keep this contract:

- Trigger is a borderless `h-7 w-7` swatch; the menu opens horizontally to the
  right, vertically centered (`left-5 top-1/2 -translate-y-1/2`) with slight
  overlap so hover/focus stays connected.
- Never put the picker inside a clipped table cell — truncate inner text nodes
  instead of the parent cell, and use `items-center` when it sits beside text.
- Color variables and the empty-state dashed dot live in the host's Tailwind
  source; rebuild with `npm run build:css`.
- Behavior lives in `views/assets/color-tag.js`; keep `data-color-tag-*`
  attributes intact so AJAX submit updates the swatch and nearby
  `data-filter-color` rows.

For client-rendered plugin views, redirect the Liquid aliases rather than
copying the snippet:

```ts
if ([
  '/color-tag-picker.liquid',
  '/snippets/color-tag-picker.liquid',
  '/sections/color-tag-picker.liquid',
].includes(viewPath)) {
  return redirect(`/admin/views/snippets/color-tag-picker.liquid${url.search}`);
}
```

Add a regression test for the alias paths.

## How admin views render (so your edits show up)

Admin pages render **client-side**. A `…Page` template calls
`renderView(views, '/templates/<name>.json', props)`; the browser fetches that
JSON section manifest, loads `sections/<name>.liquid`, and renders it with
`views/assets/liquid.browser.min.js`. So:

- Editing `sections/<name>.liquid` is enough — served from disk, no Liquid
  recompile. Touch the `.json` under `views/templates/` only to add or rename
  sections.
- Globals injected by the admin layout: `nonce`, `iconHrefPrefix`
  (`<use href="{{ iconHrefPrefix }}#copy">`), the `| t` filter, and
  `l10n_date`.
- User-facing strings are locale keys resolved with `| t`; add new keys to
  **all** of `views/locales/*.json` (en, mis, zh-hans, zh-hant) and keep
  `npx vitest run test/i18n.test.ts` (key parity) passing.

## Plugin page views

Plugin-owned page views share one rendering contract, three manifest keys:

- `editViews` — edit forms at `/admin/pages/:id/edit`
- `newViews` — create forms at `/admin/pages/new?page_type=<type>`
- `readViews` — read-only views at `/admin/pages/:id/read`

For `newViews` the plugin endpoint stays `/__plugin/edit`; the host sends
`mode: "new"`, `action: "/admin/pages"`, an empty page id, and the same editor
context. Preserve the host's create handler — no plugin-local save logic. Keep
the `?native=1` / `?editor=cms` escape hatch intact. Legacy: an `editViews`
entry also owns the create screen unless `newViews` says otherwise; add
regression coverage for create-only, edit-only, and fallback-to-built-in when
that ownership changes.

The full contract — context shape, CMS field-name grammar, presence bar — lives
in `0xcms-plugin-api` (`references/edit-view.md`).

## Review checklist

Scan the touched area for sibling views with the same pattern — core (taxonomies,
page types, block types, tags, roles, users, plugins, pages, trash), events
(events, dashboards, guest lists, guests, sessions, labels, EDM templates,
imports), contacts (lists, records, imports, settings). Then verify:

- [ ] Primary action on the right; mobile labels hidden where space matters;
      search/filter submits icon-only when requested.
- [ ] Card headings don't scroll away from their tables; pagination sits
      outside the scroll container and uses range summary, stable disabled
      controls, page indicator, localized labels, and parameter-preserving links.
- [ ] Plugin content padding matches host content padding.
- [ ] No `| escape` in client views; `| raw` only for intentional HTML.
- [ ] `npm run build:css` run; every new class confirmed present in
      `admin.css` (`grep -F` or `check_classes.py`).
- [ ] New locale keys in every `views/locales/*.json`; i18n test passes.
- [ ] Type checks pass, or unrelated failures reported clearly.
