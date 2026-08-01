---
name: 0xcms-theme-editor
description: Maintain the 0xCMS visual theme editor at frameworks/zeroxcms/plugin-theme-editor. Use for theme discovery/storage, R2-backed themes, theme manifests, JSON/Liquid templates, Shopify-style section schema, browser preview rendering, block/value editing, template binding overrides, section visibility, theme publishing/apply/sync scripts, GitHub clone/push, approved assets, or tenant-scoped theme configuration.
---

# 0xCMS Theme Editor

## Architecture

Source:
`/Users/colin/Documents/code/frameworks/zeroxcms/plugin-theme-editor`

This is an authenticated admin plugin, not the public site renderer. It:

- lists readable CMS pages through `/__cms`;
- loads themes from an R2 library or a staged development asset;
- sends page context and a theme bundle to an approved browser renderer;
- edits CMS page lect through the normal versioned `/__cms/pages/:id` API;
- layers template settings/visibility in KV;
- publishes those layers into writable themes;
- clones/pushes themes through GitHub's HTTP API.

The manifest requests wildcard delegated reads/writes inside
`contentTypes.readTypes`/`writeTypes`. The host must approve them, and the
plugin enumerates concrete types from `/__cms/content-meta`; never send `"*"`
as an actual page type.

## Request and tenant boundary

- Leave manifest, declared assets, and plugin view files public.
- Handle tenant enroll/revoke outside the normal gate.
- Set manifest `autoTenant: true` when the CMS Connect button is expected.
  Enrollment routes without the manifest flag work only when called directly;
  the flag without the routes advertises a broken connection flow.
- Authenticate `/__plugin/admin` with `requireTenant`, then use
  `tenantClientEnv`.
- Gate viewing with `theme-editor:view` and mutations/GitHub pushes with
  `theme-editor:write`.
- Pass the signed-in user to CMS updates for acting-user attribution.
- `TENANTS` KV is the tenant registry. `THEME_OVERRIDES` KV is now legacy-only
  (see Overrides and publishing); overrides themselves live in host plugin
  state.

For multi-tenant deployments, put tenant-specific `GITHUB_TOKEN` or other
settings in the tenant record's `vars`; `tenantClientEnv` overlays them last.
Prefer a Worker secret when one token serves the entire deployment because KV
values are readable to operators.

## Theme format and storage

A theme root contains:

```text
theme-manifest.json
layout/
sections/
snippets/
templates/
assets/
```

Templates may be Liquid or JSON. JSON templates declare layout, sections,
section order, settings bindings, and optional blocks. Section Liquid can
declare editor metadata with `{% schema %}...{% endschema %}`.

Every theme operation works through `ThemeStore`:

- `R2ThemeStore`: production library, one top-level folder per theme, writable.
- `AssetThemeStore`: staged development theme, immutable at runtime.
- `VirtualThemeStore`: overlays editor-only wrappers/sources.

Do not special-case storage inside renderer/schema/template logic. Test against
the `ThemeStore` contract.

`theme-manifest.json` names the theme and available templates. Development
`theme:sync` generates it when absent and prunes removed source files. Build
assets from a clean destination so an ignored local theme cannot leak into a
production deploy.

## Preview renderer

The preview frame starts empty. The approved `theme-preview.js` runs in the CMS
editor page, fetches `/preview/data` and `/preview/bundle` once, and writes the
same-origin iframe document.

Do not move the renderer into the frame: host sanitization strips scripts from
plugin HTML documents. Do not ship a second LiquidJS. The browser bundle uses
the host's `/assets/liquid.browser.min.js`, including the CMS `schema` tag.

Keep one rendering implementation:

- browser bundle imports `renderThemePreview` and editor projection code from
  `src/`;
- tests load the host Liquid bundle via `npm run liquid:sync`;
- `ThemeRuntime` carries only plain values plus a `ThemeStore`;
- later input/focus/visibility renders are local and preserve frame head/scroll.

Changing `/assets/theme-editor.js` or `/assets/theme-preview.js` changes its
SRI hash; re-approve the asset in CMS plugin settings before expecting it to
run. The full manifest→approval→SRI pipeline is in `0xcms-plugin-api` →
`references/js-assets.md`.

## Values versus template schema

Keep the two edit modes separate:

- **Values** changes the selected page's lect and saves through the CMS API.
- **Schema** changes the Liquid bindings declared by a template section and
  stores only differences, in host plugin state.

The inactive panel must be a disabled `fieldset` so its inputs cannot compete
with the active panel. Preserve the `settings` URL mode and selected block.

Schema setting ids name projected view-model values, not necessarily raw lect
keys. Resolve hints through `resolveThemeBinding` using the same preview data.
Reject undeclared schema settings. Clearing a binding removes it; do not store
a copy of the theme's unchanged binding because that would mask later theme
updates.

An intentional override must continue to outrank later source changes. To adopt
a new source binding, blank/reset the Schema field (or save the now-current
source value) so the delta is removed. Do not silently let source updates win
over a genuine stored override.

## Overrides and publishing

**Overrides live in host-owned plugin state, not plugin KV** (`src/theme/overrides.ts`,
`pluginState` from `@lionrockjs/worker-cms-plugin` → `/__cms/state`). The record
belongs to the CMS that owns the theme configuration, so it stays visible to
that host's admins and does not outlive the host in plugin KV.

**One key per theme**, holding every template's overrides:

```text
theme.overrides.<theme-id>
```

One key per theme rather than per template makes reading them all a point read
instead of a scan, keeps a read-modify-write to a single row, and bounds the key
count by themes rather than themes × templates — which matters against the
100-key-per-plugin cap (see `0xcms-plugin-api` → "Where state belongs").

Each template entry stores deltas only:

```ts
{ hidden: string[],                              // section keys dropped from compiled order
  settings: Record<string, Record<string,string>>, // per section, changed setting bindings
  order: string[],                               // explicit editor order; new theme keys merged in
  added: Record<string, { type: string }>,       // sections created before publish
  deleted: string[] }                            // source sections removed before publish
```

Nothing is cached on read: an override is read right back after it is written
and must never be served stale, so a Hide toggle handled by one isolate is
visible to the next request whichever isolate takes it.

Two distinct failures — keep them distinct, the fixes differ:

- `MissingOverrideStoreError` — the owning CMS could not be reached.
- `UnknownTenantError` — the request carries no CMS connection at all, so there
  is nothing to store against.

**Legacy KV migration.** The pre-migration key was
`sections:<tenant ref>:<theme-id>:<template-id>` in the plugin's own
`THEME_OVERRIDES` KV. That binding still exists and is read **only** to migrate
old records forward, deleting them afterward; `npm run theme:migrate-prefix`
drives it. Do not write new overrides there, and do not treat an unbound
`THEME_OVERRIDES` as an error on the write path any more.

Publishing folds overrides into theme JSON and clears only what was applied.
It is allowed only for writable R2 themes. `npm run theme:apply` is the local
equivalent for a checked-out theme; it writes first and clears afterward so a
failed filesystem write cannot lose the override.

A staged development theme uses immutable Worker assets, so publish returning
409 is correct. Apply the override to the checkout with `theme:apply` and
resync, or upload/clone the theme into `THEMES` R2 before publishing. Never make
`AssetThemeStore` writable.

## GitHub

A Worker has no git binary or filesystem checkout. Use `GitHubClient` and the
Git Data API:

```text
clone: ref -> commit -> recursive tree -> blobs -> R2 theme
push:  blobs -> tree on base_tree -> commit -> move ref
```

Keep the existing allowlist of theme file types and the selected subdirectory.
Build pushes on the current `base_tree` so unrelated repository files survive.
Require a fine-grained token with Contents read/write and a `THEMES` bucket.

## Verification

Run:

```bash
CMS_ASSETS_DIR=/Users/colin/Documents/code/workers/cms/views/assets npm run liquid:sync
npm run build
npm run typecheck
npm test
```

Cover:

- R2/asset/virtual stores and manifest discovery;
- JSON and Liquid templates;
- schema parsing and invalid schema;
- browser build against the real host Liquid bundle;
- DOM behavior against the real editor markup;
- value saves and acting-user attribution;
- override diffing, hidden keys, publish/apply clear order;
- source changes while an override exists, reset-to-source behavior, and
  write failures that must leave stored overrides intact;
- legacy `THEME_OVERRIDES` KV records migrating forward into plugin state, and
  being deleted only after a successful write;
- unreachable-host vs unknown-tenant errors staying distinct;
- tenant isolation;
- GitHub clone/push and base-tree preservation;
- missing bindings/tokens and permission failures.
