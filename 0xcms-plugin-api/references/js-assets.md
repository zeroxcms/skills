# Shipping client-side JS in plugin admin views

## The security model (read this or the script silently won't run)

Plugin admin pages are Liquid fragments client-rendered inside the host admin
shell under a **strict nonce CSP** (no `unsafe-inline`). Before insertion, the
host's client renderer (`views/assets/client-render.js`) sanitizes the rendered
HTML:

- **Inline `<script>` bodies are emptied** (`script.textContent = ''`) and
  **`on*` attributes / `javascript:` URLs are stripped.** Inline JS can never
  run — don't write it.
- **External `<script src>` tags are removed unless** the src points at this
  exact CMS-served path for an asset that is BOTH declared in the plugin
  manifest AND admin-approved:
  `/admin/plugins/<plugin-id>/assets/<file>.js`
- Approved scripts are rewritten in place: the host stamps `integrity` (SRI
  sha384 pinned at approval time), the page `nonce`, and a `?r=<revision>`
  cache-buster. Only then do they execute.

Server side, `servePluginAsset` (in the admin-proxy route — see the
Source authority table in SKILL.md) re-fetches the file from the plugin Worker
and **recomputes the hash on every request**: not approved → 404 "asset not
approved"; bytes differ from the pinned hash → 409 "Asset changed since
approval; re-approval required". It fails closed — an admin never executes bytes
they didn't review.

Consequence: **JS must be progressive enhancement.** Between deploy and
(re-)approval the script does not load, with no console error in your plugin's
control — the page must remain usable without it.

## First: do you need custom JS at all?

The host layout (`views/layout/default.liquid`) already ships CSP-safe global
behaviors any plugin fragment can use declaratively:

- `data-confirm="Are you sure?"` on a `<form>` → confirmation prompt on submit.
- `<table data-reorder="/admin/...">` (+ `data-reorder-handle`,
  `data-reorder-handle-only`, `data-reorder-mode="weight"`, rows with `data-id`)
  → drag-and-drop reorder that POSTs the new order.
- the global double-submit guard (see `0xcms-admin-ui` →
  `references/submit-once.md`).
- `data-autosubmit` on a `_language` select → free language switcher.

If one of these covers the interaction, use it and ship nothing. Structured
add/remove/reorder in a custom editor should also go through full server
round-trips first — see `edit-view.md`.

## The pipeline (4 steps)

Working example: `cms-plugin-event-action` `views/assets/filter-rows.js`
(add/remove filter rows). Also `cms-plugin-events` `views/assets/event-new.js`
(auto-slug) and `import-continue.js` (auto-resubmit).

1. **Write the file** at `views/assets/<name>.js` — plain IIFE, `'use strict'`,
   no imports/bundler — and make sure the plugin Worker's fetch handler serves
   the **bare** `/assets/*` path via `serveViewAsset(env.VIEWS, path)` (plus
   `/__plugin/admin/assets/*` for the admin proxy). The bare path is not
   optional: the host's approval flow and every proxied serve fetch
   `https://<plugin>/assets/<name>.js` directly, with no `/__plugin` prefix and
   no secret. With `run_worker_first = true` the worker answers before the
   static assets binding, so a missing `/assets/` branch means the host gets
   your final 404 — approval fails with "Could not fetch the asset from the
   plugin — approval not changed" (`flash=fetch-failed`).

2. **Declare it in `src/manifest.json`** — declaration alone runs nothing; it
   only makes the path *approvable*:
   ```json
   "assets": [
     { "path": "/assets/filter-rows.js", "label": "Filter rules add/remove buttons" }
   ]
   ```

3. **Reference it from the view** (`views/sections/*.liquid`) with the CMS-side
   URL (plugin id, not worker name), usually gated to editors:
   ```liquid
   {% if canEdit %}<script src="/admin/plugins/<plugin-id>/assets/filter-rows.js" defer></script>{% endif %}
   ```

4. **Approve it in the CMS admin**: Plugins → (plugin) → assets
   (`/admin/plugins-manage/:id/assets/approve`). Approval fetches the current
   bytes and pins their sha384.

## The re-approval gotcha (top support question)

Every deploy that changes the JS file's bytes invalidates the pinned hash.
Symptoms: buttons that used to appear are gone again; the asset URL returns 409.
Fix: re-approve under Plugins → (plugin) → assets (the manage view shows
"drifted" for hash mismatches). Budget for this in every deploy that touches
`views/assets/*.js`. If behavior must work even while unapproved, it has to be
the no-JS fallback, not the script.

The same applies to any plugin that ships browser bundles — e.g. changing the
theme editor's `theme-editor.js` / `theme-preview.js` changes their SRI hashes
and requires re-approval before they run.

## Progressive-enhancement pattern

Render the interactive controls server-side but `hidden`; the script unhides and
wires them. No DOM surgery to inject buttons, nothing breaks when the script is
absent, and the no-JS fallback stays honest:

```liquid
<div data-filter-rows>
  {% for row in rows %}
  <div data-filter-row>
    ...inputs...
    <button type="button" data-filter-remove hidden>Remove</button>
  </div>
  {% endfor %}
</div>
<button type="button" data-filter-add hidden>Add rule</button>
```

```js
(function () {
  'use strict';
  var container = document.querySelector('[data-filter-rows]');
  var addButton = document.querySelector('[data-filter-add]');
  if (!container || !addButton) return; // view without this widget, or view-only user
  // clone-a-blank-row template, unhide buttons, addEventListener — no on* attrs
}());
```

Rules of thumb:

- `type="button"` on non-submit buttons (they live inside the form).
- Positional form arrays (`getAll('field')`-style) stay aligned by removing
  whole rows, never individual inputs.
- `addEventListener` only; `on*` attributes are stripped by the sanitizer.
- Guard every entry point — the script may load on a page without its widget.
- Anything renderable inside a plugin view that needs re-binding after a client
  re-render should expose an idempotent `scan(root)` guarded by a
  `dataset.bound` flag.

## Testing (vitest, no host needed)

- View test: render via the client-view path (`renderView` against
  `x-cms-view-path`) and assert the fragment contains the `data-*` hooks and the
  `/admin/plugins/<id>/assets/<name>.js` script src — and that view-only users
  get neither.
- Asset test: `GET /__plugin/admin/assets/<name>.js` returns 200 with a
  `text/javascript` content-type.
- The approval flow itself is host-side; don't simulate it in plugin tests.

## Debugging "my script doesn't run"

Ordered by likelihood:

0. **Approval itself fails** ("Could not fetch the asset from the plugin —
   approval not changed") — the plugin Worker doesn't serve the bare
   `/assets/<name>.js` path (it only routed `/__plugin/admin/assets/*`). Add the
   `path.startsWith('/assets/')` branch to the fetch handler (step 1) and
   redeploy, then approve again.
1. **Not approved / hash drifted** — open the asset URL directly: 404 "asset not
   approved" or 409 "changed since approval" tells you exactly. Re-approve.
2. **Path mismatch** — the script src must be
   `/admin/plugins/<manifest id>/assets/...` and the manifest `assets[].path`
   must be the `/assets/...` suffix of it, byte-identical.
3. **Inline JS or `on*` attribute** — sanitizer stripped it; move to an external
   declared asset + `addEventListener`.
4. **Fragment not chrome-wrapped** — only responses with `x-cms-chrome: 1` (what
   `adminView`/`clientViewResponse` set) go through this pipeline;
   full-document plugin pages have a different (relaxed) CSP.
