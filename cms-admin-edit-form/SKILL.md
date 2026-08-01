---
name: cms-admin-edit-form
description: >-
  Build or restyle a translatable admin edit form in the HOST Workers CMS
  (/Users/colin/Documents/code/workers/cms) — the tag editor, and any single-
  record admin form that has a base name/slug/weight plus per-language
  translated fields. Use this whenever a task touches
  views/sections/*-form.liquid in the host repo, says "update the tag edit UI",
  "make the edit form look like the page editor", "add a language selector to
  this admin form", or asks to arrange name / auto-slug / weight / taxonomy /
  parent / translated-name on an admin edit page. It captures the canonical
  layout (top card = base Name + auto-slug beneath + weight on the right;
  selector row; translated-name card with a language switcher), the lect
  translation wiring (`_language` reload + `.field|<lang>` names), the Tailwind
  rebuild gotcha, and the no-login way to screenshot-verify the render. Pair
  with cms-plugin-tailwind for the class-purge rules; that skill is for plugin
  fragments, THIS one is for the host's own admin views.
---

# Host CMS admin edit-form UI

The canonical example is the **tag editor**. Any translatable single-record
admin form (a record with a non-translated `name`/`slug`/`weight` plus a `lect`
JSON blob of per-language values) should follow this same shape. It deliberately
mirrors the **page editor** (`/admin/pages/:id/edit`) so the whole admin feels
like one product.

## The three touchpoints

A host admin edit form is split across three files — change the right one:

| Concern | File | What lives here |
|---|---|---|
| Markup / layout | `views/sections/<name>-form.liquid` | The liquid the user sees. **Layout changes go here.** |
| View data (props) | `src/templates/<name>s.ts` (`…FormPage`) | Maps the record → the flat vars the liquid reads. |
| Route + persistence | `src/routes/admin/<name>s.ts` | GET builds props via a `…Form(c, record)` helper; POST reads the form and writes the DB + `lect`. |

For tags these are `views/sections/tag-form.liquid`, `src/templates/tags.ts`
(`tagFormPage`), `src/routes/admin/tags.ts` (`tagForm` + the POST handlers).

## The canonical layout (top → bottom)

Reference the page editor for styling: `views/sections/editor.liquid` (the
header card) and `views/snippets/structured-editor.liquid` (the language
selector row).

1. **Top card — base identity, NOT translated.** A rounded `border bg-white`
   card with a `bg-gray-100` header row, `flex-col sm:flex-row sm:justify-between`:
   - **Left:** the big **Name** input (`text-[2rem]`, transparent, borderless)
     — this is the record's base `name` column, one value, no language variants.
     Directly beneath it, the **auto-slug** on a `text-xs font-mono text-gray-500`
     row prefixed with a literal `/`, plus an optional copy button.
   - **Right:** the **weight** — a `#` glyph then a small right-aligned
     `type="number"` (`text-lg font-bold`).
2. **Selector row.** `grid grid-cols-1 sm:grid-cols-2 gap-4` holding the
   **Taxonomy** `<select>` and the **Parent** *combobox* (see below). This sits
   **above** the translated name.
3. **Translated-name card.** A second `border bg-white` card whose header is a
   `flex justify-between`: a "Display Name" title on the left and the
   **language selector** on the right (label + `<select id="…_language"
   name="_language">`). The translated input sits below.
4. **Action row.** Save / Cancel / (Delete on `sm:ml-auto`), unchanged.

Wrap the form at `max-w-2xl`. See the full worked markup in
`views/sections/tag-form.liquid`.

## Parent selector — searchable combobox, not `<select>`

A self-referential parent picker (parent tag, parent page) can grow unbounded,
so it must be a **server-backed combobox**, never a `<select>` that pre-renders
every row. The route passes only `selectedParent: { id, label }` (resolve the
current parent's display name once) — **not** a full list; drop any `listTags`/
`listAll` call that existed only to feed the old `<select>`. The tag editor's
`[data-parent-tag-combobox]` (endpoint `/api/parent-tags`) is the worked example.

**For the full combobox recipe — endpoint contract, markup skeleton, JS
controller, and the inline-script-vs-core-asset decision — use the
`cms-admin-combobox` skill.**

## The translation wiring (lect) — do not reinvent

The per-language values live in a `lect` JSON column. The form edits **one
language at a time**, chosen by a `?language=<code>` query param.

- **Switching language reloads the page.** The `#…_language` select's `change`
  handler sets `?language=` and navigates. It is inline and needs
  `nonce="{{ nonce }}"` on its `<script>`. Do not try to switch fields
  client-side — the server re-derives the translated value on reload.
- **The translated field name is lect-encoded:** `name="{{ translatedFieldName }}"`
  where the template builds it as `` `.name|${language}` ``. The leading `.`/`@`/
  `*`/`#` prefix is what marks a field as lect-encoded (the page editor's CRDT
  sync keys off the same prefix regex `^[.@*#\d]`).
- **`_language`** is a real form field posted with the rest — the POST handler
  reads it via `languageFromRequest(c, form, config)`.
- **Deriving what the input shows** (in the `…Form` route helper):
  `getLectLocalizedValue(lect, 'name', language)`; when `language` is the
  default language, fall back to the base `name`; otherwise the default-language
  value becomes the input's *placeholder* (`translatedPlaceholder`) so a
  translator sees the source string greyed out.
- **On POST:** `mergeLects(safeParseLect(existing.lect), postToLect(form, language))`
  then `ensureDefaultLectName(lect, name)`, then `stringifyLect(lect)` into the
  column. Merge — never overwrite — so editing one language keeps the others.

Utilities: `src/utils/lect.ts` and `ensureDefaultLectName` in
`src/utils/page-logic.ts`.

## Tailwind gotcha — rebuild after adding classes

The host ships ONE compiled stylesheet, `views/assets/admin.css`, built by
`npm run build:css` (`tailwindcss -i styles/admin.css -o views/assets/admin.css
--minify`, Tailwind v4). It scans the source files, so **any utility class you
add to a `.liquid` that no other host file already uses is absent from
`admin.css` until you rebuild** — the element silently renders unstyled.

After editing a host admin view:

```
npm run build:css
```

(`npm run dev` and `pretest` already run it; a bare `wrangler dev` does not.)
Prefer classes the page editor already uses (`text-[2rem]`, `w-12`,
`min-w-[10rem]`, `bg-gray-100`, …) and rebuild to be safe. This is the host-side
cousin of the purge trap in `cms-plugin-tailwind`.

## How the view actually renders (so edits show up)

Admin pages render **client-side**. `…FormPage` calls
`renderView(views, '/templates/<name>-form.json', props)`; the browser fetches
that JSON manifest (`{"sections":{"main":{"type":"<name>-form"}}}`), then loads
`sections/<name>-form.liquid` and renders it with
`views/assets/liquid.browser.min.js`. So:

- Editing `sections/<name>-form.liquid` is enough — it is served from disk, **no
  liquid recompile step**. The `.json` under `views/templates/` is just a static
  section manifest; only touch it if you add/rename sections.
- Globals every section can use (injected by the admin layout): `nonce`,
  `iconHrefPrefix` (`/assets/icons.svg?…`, used with `<use href="{{ iconHrefPrefix }}#copy">`),
  plus the `| t` translation filter and `l10n_date`.
- User-facing strings are locale keys `view_strings.sections_<name>_form.*`
  resolved with `| t`; add new keys to all of `views/locales/*.json`. The host
  auto-escapes client views — use `| raw` only for intentional HTML.

## Verifying the render without logging in

The admin needs OAuth, and the in-app browser / Claude-in-Chrome may not be
signed in. The in-app preview pane also refuses `file://`. To get a real
screenshot anyway, render the section with the **vendored** liquid engine and
serve the output through the dev server's public `/assets/` path:

1. Load `views/assets/liquid.browser.min.js` in a Node `vm` sandbox
   (`sandbox.window.liquidjs.Liquid`), register a passthrough `t` filter, and
   `engine.render(engine.parse(src), sampleProps)` with representative props
   (an edit record, ≥2 language options, a selected taxonomy).
2. Wrap the output in `<html><link rel="stylesheet" href="/assets/admin.css">…`
   and write it to `views/assets/_preview.html`.
3. `/assets/*` is public (the login page loads `admin.css`), so open
   `http://localhost:8787/assets/_preview.html` in the browser pane and
   screenshot. **Delete `views/assets/_preview.html` when done.**

This both proves the liquid parses under the real engine and shows the true
`admin.css` layout. The admin renders dark in a dark-mode browser — that is
`admin.css`'s own dark scheme, not a bug.

Two traps this preview method hits:

- **The browser caches `/assets/admin.css`.** After `npm run build:css`, the
  preview will still use the *stale* stylesheet, so freshly-added classes render
  wrong (e.g. an `inset-y-0` chevron falls below its input). Link the CSS with a
  cache-buster — `href="/assets/admin.css?cb=<timestamp>"` — or the fix won't show.
- **Inline `<script>` is CSP-blocked in the preview.** The dev server sends a
  strict per-request `script-src 'nonce-…'`; your static file's baked-in
  `nonce="abc"` never matches, so none of the form's JS runs (comboboxes look
  dead). That is a preview artifact — the real app injects the matching nonce.
  To exercise combobox/auto-slug logic anyway, **inject the controller via
  devtools** (`javascript_tool`, which runs privileged and bypasses CSP): mock
  `window.fetch` to return sample rows, paste the handler, then drive it
  (open → type a query → click an option) and assert the hidden input's id and
  the visible input's label. That is how the parent-tag combobox was verified.

## Checklist for an edit-form change

- [ ] Layout edited in `views/sections/<name>-form.liquid`, mirroring the editor.
- [ ] Base `name`/`slug`/`weight` are plain columns; only translated fields use
      `.field|<lang>` names and the `_language` switcher.
- [ ] `…Form` helper derives `translatedName` + `translatedPlaceholder`; POST
      merges lects (never overwrites).
- [ ] Self-referential parent picker is a server-backed combobox
      (`/api/parent-<type>s`), not a `<select>`; route passes `selectedParent`
      only, not the full list.
- [ ] New locale keys added to every `views/locales/*.json` (en, mis, zh-hans,
      zh-hant); `npx vitest run test/i18n.test.ts` passes (key parity).
- [ ] `npm run build:css` run; new classes present in `admin.css`.
- [ ] Rendered + screenshot-verified via the `/assets/` preview trick above
      (cache-bust the CSS; drive JS via devtools injection).
