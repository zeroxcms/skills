---
name: zeroxcms-plugin-edit-view
description: >-
  Give a 0xCMS plugin a bespoke page editor — replacing the host's generic
  blueprint-driven form with your own UI — via the manifest `editViews` /
  `newViews` / `readViews` contract and the `/__plugin/edit` endpoint. Use this
  whenever a task says "the edit screen for <page type> should look like X",
  "make the editor match <product>", "custom editor for my plugin's pages", or
  when you are writing a plugin view that must POST back into the CMS save
  handler. It captures the dispatch contract, the CMS field-name grammar
  (@attr, .field|lang, #<block>, custom-item arrays, block-add/delete actions),
  the localization rule that decides `@name` vs `name`, the co-authoring
  presence bar (live multi-editor avatars + per-field editing highlight via
  `cmsEditPresence`) that every edit view should render, and the failure modes
  (silent fallback to the built-in editor, double-escaping, lost config on type
  switch). Pair with zeroxcms-pagefield-types for the field controls themselves
  and cms-plugin-tailwind for styling.
---

# Plugin-rendered page editors in 0xCMS

## The contract

Declare the page types you want to own in `src/manifest.json`:

```json
"editViews": ["form"],     // replaces the EDIT screen for `form` pages
"newViews":  ["event"],    // replaces the CREATE screen
"readViews": ["report"]    // replaces the read-only screen
```

The host (`cms/src/plugins/edit-view.ts`) then POSTs an `EditViewContext` JSON
body to your Worker's `/__plugin/edit` (or `/__plugin/read`) and wraps whatever
you return in the admin chrome. Legacy note: an `editViews` entry also owns the
create screen unless a `newViews` entry says otherwise.

The context carries everything you need:

```ts
{ mode: 'new' | 'edit', action, backHref, language, uiLocale, pageType,
  page: { id, name, slug, pageType, weight, start, end, timezone, editors,
          lect /* STRINGIFIED json */ },
  versions: [{ id, created_at, action }], flash?, errors? }
```

Return a **client view** (`clientViewResponse(title, '/sections/x.liquid', data)`
from `@lionrockjs/worker-cms-plugin`) or a plain HTML fragment with
`content-type: text/html`.

**Your editor is a VIEW, not a controller.** Its `<form>` posts to
`ctx.action` — the CMS's own create/update handler — so saving, versioning,
publish hooks and auto-publish stay host-side and you never reimplement them.

### Auth

`/__plugin/edit` is secret-authenticated: include it in the `secretRequired`
set in your fetch handler so `requireTenant` runs before dispatch.

```ts
const secretRequired = path.startsWith('/__plugin/hooks/')
  || path.startsWith('/__plugin/admin')
  || path === '/__plugin/edit';
```

## Field-name grammar (what the save handler parses)

This is the whole API. Get a name wrong and the value silently vanishes on save.

| Name | Writes |
| --- | --- |
| `name`, `slug`, `weight`, `page_type` | native page columns |
| `@key` | `lect.key` — a plain scalar **attribute** |
| `.key\|<lang>` | `lect.key[lang]` — a **localized value** |
| `*key` | `lect._pointers.key` — a pointer to another page |
| `#<i>@_type` | block *i*'s type (always emit this — see gotchas) |
| `#<i>@_weight` | block *i*'s display order |
| `#<i>@key` / `#<i>.key\|<lang>` | a field on block *i* |
| `#<i>.<item>[<j>]@key` | a field on nested item *j* of block *i* |
| `#<i>.<item>[<j>]@_weight` | that item's order |
| `_language` | switches the editing language (with `data-autosubmit`) |
| `return_to` | where the CMS returns after save |

### Structured operations — `name="action"` on the submit button

| Value | Effect |
| --- | --- |
| `update` | normal save |
| `block-add` (+ a `block-select` input) | append a block of the selected type |
| `block-delete:<i>` | remove block *i* |
| `block-item-add:<i>\|<item>` | append a nested item |
| `block-item-delete:<i>\|<item>\|<j>` | remove nested item *j* |
| `item-add:<item>` / `item-delete:<item>\|<j>` | same, for page-level items |

These are **full server round-trips** — add/remove/reorder needs no client JS,
which matters because the admin runs a strict nonce CSP. Ship the interaction
this way first; treat JS as enhancement only (see cms-plugin-js-assets).

## `@attr` vs `.field|lang` — the rule that bites

**Anything a visitor or translator reads is a localized value; only machine
config is an attribute.**

```
@name @type @required @min @max @accept @max_size     ← config: attributes
label default_value rows min_label max_label          ← text: localized values
```

Getting this wrong is a *silent* bug: the editor posts `.rows|mis` while your
reader calls `attr(row, 'rows')`, which stringifies the `{mis: …}` object to
`"[object Object]"` — or posts `@rows` while the reader calls `localized()` and
sees an empty field after every language switch. Decide per field, then make
the editor's input name and the reader agree.

Reading them back:

```ts
attr(lect, 'type')                     // scalar
localized(lect, 'label', lang)         // localized, falls back across languages
locExact(lect, 'label', lang)          // EXACT language — use this in editors
```

Editors want `locExact`: a translator must SEE that a field is empty in the
language they're editing, not the English text bleeding through. Use the
default language's value as the input's `placeholder` instead.

For readers that must tolerate both shapes (legacy data written as an attr,
new data written as a localized value), try localized first:

```ts
const value = localized(input, 'default_value', language) || attr(input, 'default_value');
```

## Escaping

Client views render through the HOST's LiquidJS with `outputEscape: 'escape'`.
**Never write `| escape` in a client view** — it double-escapes. Mark
pre-sanitized HTML `| raw`. (A plugin's own server-rendered templates — email,
public pages — use `renderLiquid` WITHOUT auto-escape and DO keep `| escape`.)

## Gotchas

- **A 404 or any error makes the CMS silently fall back to its built-in
  editor.** So "my custom editor isn't showing" is usually: the manifest isn't
  refreshed (host caches it on a TTL — re-save the plugin row under Admin →
  Plugins), the plugin has no secret configured, your handler returned 404
  because it type-checked `ctx.pageType` against the wrong string, or the
  response wasn't HTML / a valid client view. Check the host logs: it prints
  `Plugin <id> edit view returned <status>`.
- **Always emit `#<i>@_type` as a hidden input.** A block whose type isn't
  posted is saved as `default`, and the block silently loses its renderer. (The
  events plugin still carries recovery code for picture blocks corrupted this
  way.)
- **Config for the type a question ISN'T currently showing must still be
  posted as hidden inputs.** The save handler writes exactly what it receives,
  so a conditional panel that renders nothing wipes those keys the next time
  the user saves — switch a question from "Linear scale" to "Rating" and back,
  and the scale bounds are gone. Render every non-visible panel's values as
  `<input type="hidden">`.
- **Display in weight order, but keep array indices in the names.**
  `#<i>` must be the ORIGINAL index in `lect._blocks`; sort only for display.
  Same for nested items.
- **Blueprint seeding**: the host seeds one empty item per nested block on
  create, so a "new" page already has `custom_input: [{}]`. Filter empties when
  counting, and don't let "delete last item" leave a repeater at zero if your
  reader assumes one.
- **`data-autosubmit` on the `_language` select** gives you the language
  switcher for free (the host layout wires it CSP-safely).
- **Presence bar**: add it to every edit view — see [Co-authoring
  presence](#co-authoring-presence-live-multi-editor) below.

## Co-authoring presence (live multi-editor)

Every plugin **edit** view should show the presence bar: avatars of everyone on
the page, a per-field "who's editing this input" highlight, and best-effort CRDT
sync of the field values. Add it to each editor you build — it is one markup
block, and the host does everything else.

**What the host gives you for free** (`cms/src/plugins/edit-view.ts`), no
manifest or asset entry required:

- For `mode: 'edit'` with a real `page.id`, it injects a `cmsEditPresence`
  object — `{ pageId, currentUserId, userAvatar }` — into your client-view
  `data` (it resolves the current user + avatar itself; you pass nothing).
- It loads `editor-sync.js` through the admin chrome (`editorSync: !!editPresence`).
- The page is served under the **CMS origin**, so the script's heartbeat
  (`POST/GET/DELETE /admin/api/presence/:id`) and the live-sync WebSocket
  (`/admin/api/sync/:id`) reach the host, which keys a Durable Object per page.

**What you must do — render the bar.** A **client view** must emit the markup
itself (the host only auto-injects a bar for raw-`text/html` fragments). Put it
in the editor's top bar, guarded so it is absent on the `new` screen:

```liquid
{% if cmsEditPresence.pageId != blank %}
  <div id="presence-bar"
       class="flex items-center gap-1.5 shrink-0"
       data-page-id="{{ cmsEditPresence.pageId }}"
       data-user-id="{{ cmsEditPresence.currentUserId }}"
       data-user-avatar="{{ cmsEditPresence.userAvatar }}">
    <div id="presence-avatars" class="flex items-center gap-1"></div>
    <div id="sync-indicator" title=""
         style="width:8px;height:8px;border-radius:50%;background:#9ca3af;flex-shrink:0;transition:background .4s,opacity .4s;display:none"></div>
  </div>
{% endif %}
```

The ids are the contract — `editor-sync.js` finds the bar by `#presence-bar`
and fills `#presence-avatars` / `#sync-indicator`. Keep them exactly.

**Field sync needs no extra work** *because* you followed the field-name
grammar above: the script watches every `input/textarea/select` whose `name`
starts with `. @ * #` or a digit (`/^[.@*#\d]/`) — i.e. exactly the `@attr`,
`.field|lang`, and `#<block>…` fields. Native page columns (`name`, `slug`,
`weight`) intentionally don't sync. For the highlight and value merge to line
up, both editors must render the **same field `name` on matching inputs** —
which they do, since the view is a pure function of the context.

**Requirements to keep it working:**

- The record must be a real host page — the presence/sync endpoints validate the
  draft page exists, so this is for plugin page types (`editViews`), not for
  bespoke non-page admin screens.
- Only `mode: 'edit'` gets `cmsEditPresence` (a `new` page has no id yet); the
  `!= blank` guard handles that.
- Don't add `editor-sync.js` to your manifest `assets` — the host supplies it;
  a duplicate would double-bind.

**Test it** by re-rendering the section with an injected `cmsEditPresence`
(mirrors what the host does), asserting the bar appears — and does *not* without
it:

```ts
const data = await response.clone().json() as Record<string, unknown>;
expect(await renderView(views(), '/sections/x-edit.liquid', data))
  .not.toContain('id="presence-bar"');
const html = await renderView(views(), '/sections/x-edit.liquid', {
  ...data, cmsEditPresence: { pageId: '301', currentUserId: '42', userAvatar: '' },
});
expect(html).toContain('id="presence-bar"');
expect(html).toContain('data-page-id="301"');
```

## Verifying without clicking through the admin

The editor is a pure function of the context, so drive it directly:

```bash
curl -s localhost:<plugin-port>/__plugin/edit \
  -H 'content-type: application/json' -H "x-plugin-secret: $SECRET" \
  -d '{"mode":"edit","action":"/admin/pages/1/edit","language":"mis",
       "pageType":"form","page":{"id":1,"name":"X","slug":"x","weight":0,
       "lect":"{\"_blocks\":[]}"},"versions":[]}'
```

Then render the returned `{template, data}` with the plugin's own `renderView`
(it mirrors the host's auto-escape) and, for a screenshot, inline the host's
compiled `cms/views/assets/admin.css`. In tests, assert on the field NAMES —
they are the contract — not on the surrounding markup.
