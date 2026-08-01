---
name: cms-admin-combobox
description: >-
  Build a searchable dropdown / autocomplete / typeahead / entity picker in the
  HOST Workers CMS admin (/Users/colin/Documents/code/workers/cms) and its
  reusable pagefields. Use this whenever a `<select>` would list an unbounded or
  growing set — parent page/tag pickers, page-reference fields, user/editor
  pickers, tag assignment — or when a task says "make this a searchable combo
  box", "replace this select with search", "add autocomplete/typeahead", "this
  dropdown will have too many options", or "picker that searches as you type".
  Covers both flavors (server-backed search vs client-side filter over
  pre-rendered options), single-select (hidden id) vs multi-select (chips), the
  `/admin/api/...` search-endpoint contract, the data-attribute markup skeleton,
  the JS controller contract, and the one trap that bites: WHERE the wiring
  script must live (inline section script vs the external core asset that
  survives client re-render and plugin sanitizing). Pair with
  cms-admin-edit-form when the combobox is the parent selector on an edit form.
---

# Admin comboboxes (searchable pickers) in Workers CMS

A `<select>` is fine for a small, fixed set (taxonomy, status, language). The
moment the option set can grow unbounded — pages, tags, users, any entity
reference — use a **combobox**: a text input that searches, a dropdown of option
buttons, and a **hidden input that carries the real value** the form posts.

## In-repo references — copy one, don't invent

| Picker | Markup | Wiring | Endpoint |
|---|---|---|---|
| Parent **page** (page editor) | `views/sections/editor.liquid` `[data-parent-combobox]` | inline section `<script>` | `GET /admin/api/parent-pages?q=&exclude=` |
| Parent **tag** (tag editor) | `views/sections/tag-form.liquid` `[data-parent-tag-combobox]` | inline section `<script>` | `GET /admin/api/parent-tags?q=&exclude=` |
| **Editors** multi-select (page editor) | `views/sections/editor.liquid` `[data-editors-combobox]` | inline section `<script>` | `GET /admin/api/users?q=` |
| **Tag** assignment multi-select | `views/sections/editor.liquid` `[data-tags-combobox]` | inline section `<script>` | *(none — client-side filter)* |
| **Page-reference** field (reusable) | `views/snippets/pagefield/page/basic.liquid` `[data-page-ref]` | **external** `/assets/page-ref.js` | `GET /admin/api/pages/:type?q=&id=` |

All endpoints live in `src/routes/admin/api.ts`.

## Two data flavors

- **Server-backed search** (default; scales): fetch the endpoint on focus/input,
  render option buttons from the JSON. Use for pages, tags, users — anything that
  can grow. The route passes only the *current selection's* label, never the full
  list.
- **Client-side filter** (bounded sets only): the server pre-renders every option
  button; the JS just toggles `.hidden` by substring match. Only justified when
  the set is small and already loaded (e.g. the tags of one taxonomy). Don't
  reach for this to "avoid an endpoint" on a set that can grow.

## Single-select vs multi-select

- **Single** (parent picker, page-ref): one `<input type="hidden" name="…">`
  holds the chosen id; picking an option writes id→hidden and label→text input; a
  static empty-id row (or a clear "×" button) resets it.
- **Multi** (editors, tags): a hidden input **per chosen chip** (or one
  comma-joined hidden field); picking appends a removable chip, Backspace on an
  empty search removes the last chip. Use a `<template>` for the chip.

## The search-endpoint contract

Model new endpoints on `/api/parent-pages`:

```ts
apiRoutes.get('/api/parent-tags', requirePermission('content:read'), async (c) => {
  const query = c.req.query('q')?.trim() ?? '';
  const excludeId = num(c.req.query('exclude'), 0);
  const conditions: string[] = []; const params: unknown[] = [];
  if (query) { const term = `%${query.replaceAll(' ', '%')}%`;
    conditions.push('(name LIKE ? OR slug LIKE ?)'); params.push(term, term); }
  if (excludeId) { conditions.push('id != ?'); params.push(excludeId); }
  const whereSql = conditions.length ? `WHERE ${conditions.join(' AND ')}` : '';
  const rows = await c.env.DB.prepare(
    `SELECT id, name, slug FROM tags ${whereSql} ORDER BY weight ASC, name ASC LIMIT 20`
  ).bind(...params).all();
  return c.json(rows.results.map((r) => ({ id: r.id, name: r.name, slug: r.slug })));
});
```

- `requirePermission('content:read')` — read gate, matching the siblings.
- `q` → `%q%` with spaces turned into `%` (loose match); search name **and** slug.
- `exclude` drops the record being edited (no self-parenting).
- **`LIMIT 20`** always — the point is to never ship the whole table.
- Return the localized display name where relevant
  (`getLectLocalizedValue(safeParseLect(row.lect), 'name', cmsConfig.defaultLanguage) || row.name`).

## Markup skeleton (data-attribute contract)

```html
<div class="relative min-w-0" data-combobox data-exclude="{{ excludeId }}">
  <input type="hidden" name="parent_tag" value="{{ selectedId }}" data-value>
  <input type="text" value="{{ selectedLabel }}" placeholder="{{ '…none…' | t }}"
         autocomplete="off" role="combobox" aria-expanded="false"
         aria-controls="cb_results" aria-autocomplete="list"
         class="block w-full rounded-lg border border-gray-300 px-3 py-2 pr-9 text-sm focus:border-indigo-500 focus:outline-none"
         data-search>
  <button type="button" class="absolute inset-y-0 right-0 flex items-center px-2 text-gray-400 hover:text-gray-700"
          data-toggle aria-label="…"><svg …><use href="{{ iconHrefPrefix }}#chevron-down"></use></svg></button>
  <div id="cb_results" class="absolute left-0 top-full z-20 mt-1 hidden max-h-60 w-full overflow-y-auto rounded-lg border border-gray-200 bg-white py-1 shadow-lg" data-results>
    <button type="button" class="block w-full px-3 py-2 text-left text-sm text-gray-500 hover:bg-gray-50" data-option data-id="" data-label="">{{ '…none…' | t }}</button>
    <p class="hidden px-3 py-2 text-sm text-gray-400" data-empty>{{ '…no matches…' | t }}</p>
  </div>
</div>
```

- `pr-9` on the input reserves room for the chevron; the toggle is
  `absolute inset-y-0 right-0` so it vertically centers.
- Dynamic option buttons get a `data-*-dynamic` marker so a re-render can clear
  only them and keep the static "None"/empty rows.

## JS controller contract

- **focus / input** → open results + `loadOptions()`; on input, clear the hidden
  value if the text is emptied.
- **toggle click** → open (and focus) if closed, else close.
- **loadOptions()** → bump a `requestId`, fetch `?q=&exclude=`, and **ignore the
  response if `requestId` changed** (stale-response race guard) or `!res.ok`.
- **render** → remove old `[data-*-dynamic]`, insert a button per row (primary =
  name, secondary = `/slug`), hide the "None" row when a query is present, toggle
  the empty message on visible count.
- **select(option)** → hidden `= option.dataset.id`, text `= option.dataset.label`
  (single); or append a chip + hidden input (multi); then close.
- **keyboard** → Escape closes; Enter selects the first visible option
  (`event.preventDefault()` so it doesn't submit the form); Backspace on empty
  search removes the last chip (multi).
- **click-outside** (`document` listener) → close when the target is outside the
  combobox.

## WHERE the script lives — the trap

Two delivery mechanisms; picking the wrong one means the combobox is dead in
production even though it "worked" locally.

- **Inline `<script nonce="{{ nonce }}">` at the end of a host `section`** — fine
  for the page editor and tag form. The client renderer re-executes nonce'd
  scripts after it swaps the DOM, so listeners re-attach.
- **External core asset** (like `views/assets/page-ref.js`, loaded once by
  `views/layout/default.liquid` with `defer`) — **required** for any reusable
  field snippet (`snippets/pagefield/*`) or anything that can render inside a
  **plugin** view: `sanitizePluginHtml` strips all inline scripts, so an inline
  handler there simply never runs. The asset must expose an idempotent
  `scan(root)` that binds every `[data-…]` not yet bound (guard with a
  `dataset.bound` flag) and be safe to call repeatedly, because the client
  re-render calls it again for newly rendered fields. New JS assets also need the
  SRI/manifest approval flow — see `cms-plugin-js-assets`.

Rule of thumb: **section-scoped picker → inline script; reusable field / plugin-
renderable picker → core asset with `scan()`.**

## Gotchas

- Every option/toggle/clear is `type="button"` — a bare `<button>` submits the
  form. (This also keeps it clear of the `submit-once` guard; see
  `cms-admin-submit-once`.)
- The **hidden input** is what posts. The visible text input is unnamed (or its
  value is ignored server-side); never rely on the typed text as the value.
- New utility classes (`inset-y-0`, `pr-9`, `max-h-60`, `rounded-r-lg`) must be
  in the host's compiled `admin.css` — run `npm run build:css` after editing the
  liquid (see `cms-admin-edit-form` for the rebuild + preview method).
- Verify the endpoint is wired with a quick `curl` — a 401 (auth) means
  registered; a 404 means the route didn't load.
