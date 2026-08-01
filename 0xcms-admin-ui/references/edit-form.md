# Translatable admin edit forms (host)

For any single-record admin form with a non-translated `name`/`slug`/`weight`
plus a `lect` JSON blob of per-language values. The canonical example is the
**tag editor**; it deliberately mirrors the **page editor**
(`/admin/pages/:id/edit`) so the admin feels like one product.

## The three touchpoints

| Concern | File | What lives here |
|---|---|---|
| Markup / layout | `views/sections/<name>-form.liquid` | The Liquid the user sees. **Layout changes go here.** |
| View data (props) | `src/templates/<name>s.ts` (`…FormPage`) | Maps the record → the flat vars the Liquid reads. |
| Route + persistence | `src/routes/admin/<name>s.ts` | GET builds props via a `…Form(c, record)` helper; POST reads the form and writes the DB + `lect`. |

For tags: `views/sections/tag-form.liquid`, `src/templates/tags.ts`
(`tagFormPage`), `src/routes/admin/tags.ts` (`tagForm` + POST handlers).

## Canonical layout (top → bottom)

Reference `views/sections/editor.liquid` (header card) and
`views/snippets/structured-editor.liquid` (language selector row) for styling.

1. **Top card — base identity, NOT translated.** Rounded `border bg-white` card
   with a `bg-gray-100` header row, `flex-col sm:flex-row sm:justify-between`:
   - **Left:** the big **Name** input (`text-[2rem]`, transparent, borderless) —
     the record's base `name` column, one value, no language variants. Directly
     beneath it the **auto-slug** on a `text-xs font-mono text-gray-500` row
     prefixed with a literal `/`, plus an optional copy button.
   - **Right:** the **weight** — a `#` glyph then a small right-aligned
     `type="number"` (`text-lg font-bold`).
2. **Selector row.** `grid grid-cols-1 sm:grid-cols-2 gap-4` holding the
   **Taxonomy** `<select>` and the **Parent** *combobox*. Sits **above** the
   translated name.
3. **Translated-name card.** Second `border bg-white` card, header is a
   `flex justify-between`: "Display Name" title left, **language selector**
   right (label + `<select id="…_language" name="_language">`). Translated input
   below.
4. **Action row.** Save / Cancel / (Delete on `sm:ml-auto`).

Wrap the form at `max-w-2xl`. Full worked markup: `views/sections/tag-form.liquid`.

## Parent selector — combobox, not `<select>`

A self-referential parent picker (parent tag, parent page) can grow unbounded,
so it must be a **server-backed combobox**. The route passes only
`selectedParent: { id, label }` — resolve the current parent's display name once
— **not** a full list; drop any `listTags`/`listAll` call that existed only to
feed the old `<select>`. Worked example: `[data-parent-tag-combobox]` in the tag
editor, endpoint `/api/parent-tags`. Full recipe in `combobox.md`.

## Translation wiring (lect) — do not reinvent

Per-language values live in a `lect` JSON column. The form edits **one language
at a time**, chosen by `?language=<code>`.

- **Switching language reloads the page.** The `#…_language` select's `change`
  handler sets `?language=` and navigates. It is inline and needs
  `nonce="{{ nonce }}"` on its `<script>`. Do not switch fields client-side —
  the server re-derives the translated value on reload.
- **The translated field name is lect-encoded:** `name="{{ translatedFieldName }}"`,
  built as `` `.name|${language}` ``. The leading `.`/`@`/`*`/`#` prefix is what
  marks a field as lect-encoded (the page editor's CRDT sync keys off the same
  regex `^[.@*#\d]`). Full grammar: `0xcms-plugin-api` → `references/edit-view.md`.
- **`_language`** is a real posted field — the POST handler reads it via
  `languageFromRequest(c, form, config)`.
- **Deriving what the input shows** (in the `…Form` route helper):
  `getLectLocalizedValue(lect, 'name', language)`; when `language` is the
  default, fall back to the base `name`; otherwise the default-language value
  becomes the input's *placeholder* (`translatedPlaceholder`) so a translator
  sees the source string greyed out.
- **On POST:** `mergeLects(safeParseLect(existing.lect), postToLect(form, language))`
  then `ensureDefaultLectName(lect, name)`, then `stringifyLect(lect)`. **Merge —
  never overwrite** — so editing one language keeps the others.

Utilities: `src/utils/lect.ts` (monolithic) / `src/core/db/lect.ts`
(feature-sliced), and `ensureDefaultLectName` in `page-logic.ts`.

## Verifying the render without logging in

The admin needs OAuth and the preview pane refuses `file://`. To get a real
screenshot anyway, render the section with the **vendored** Liquid engine and
serve the output through the dev server's public `/assets/` path:

1. Load `views/assets/liquid.browser.min.js` in a Node `vm` sandbox
   (`sandbox.window.liquidjs.Liquid`), register a passthrough `t` filter, and
   `engine.render(engine.parse(src), sampleProps)` with representative props (an
   edit record, ≥2 language options, a selected taxonomy).
2. Wrap the output in `<html><link rel="stylesheet" href="/assets/admin.css">…`
   and write it to `views/assets/_preview.html`.
3. `/assets/*` is public (the login page loads `admin.css`), so open
   `http://localhost:8787/assets/_preview.html` and screenshot.
   **Delete `views/assets/_preview.html` when done.**

This proves the Liquid parses under the real engine and shows the true
`admin.css` layout. The admin renders dark in a dark-mode browser — that is
`admin.css`'s own dark scheme, not a bug.

Two traps this method hits:

- **The browser caches `/assets/admin.css`.** After `npm run build:css` the
  preview still uses the *stale* sheet, so freshly-added classes render wrong
  (e.g. an `inset-y-0` chevron falls below its input). Cache-bust:
  `href="/assets/admin.css?cb=<timestamp>"`.
- **Inline `<script>` is CSP-blocked in the preview.** The dev server sends a
  strict per-request `script-src 'nonce-…'`; your static file's baked-in nonce
  never matches, so none of the form's JS runs and comboboxes look dead. That is
  a preview artifact — the real app injects the matching nonce. To exercise the
  logic anyway, inject the controller via devtools (`javascript_tool` runs
  privileged and bypasses CSP): mock `window.fetch` to return sample rows, paste
  the handler, drive it (open → type → click), and assert the hidden input's id
  and the visible input's label.

## Checklist

- [ ] Layout edited in `views/sections/<name>-form.liquid`, mirroring the editor.
- [ ] Base `name`/`slug`/`weight` are plain columns; only translated fields use
      `.field|<lang>` names and the `_language` switcher.
- [ ] `…Form` helper derives `translatedName` + `translatedPlaceholder`; POST
      merges lects (never overwrites).
- [ ] Self-referential parent picker is a server-backed combobox, not a
      `<select>`; route passes `selectedParent` only.
- [ ] New locale keys in every `views/locales/*.json`;
      `npx vitest run test/i18n.test.ts` passes.
- [ ] `npm run build:css` run; new classes present in `admin.css`.
- [ ] Screenshot-verified via the `/assets/` preview trick (cache-bust the CSS;
      drive JS via devtools injection).
