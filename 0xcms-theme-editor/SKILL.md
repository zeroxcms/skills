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
- Keep `TENANTS` and `THEME_OVERRIDES` as separate KV bindings.

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
  stores only differences in `THEME_OVERRIDES`.

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

Key overrides by tenant CMS origin, theme id, and template id:

```text
sections:<cms-origin>:<theme-id>:<template-id>
```

Store:

- hidden section keys, not a stale copy of the entire order;
- changed section setting bindings only.

Reads degrade to no overrides when `THEME_OVERRIDES` is unbound. Writes must
fail visibly and point to:

```bash
npm run kv:setup -- --binding=THEME_OVERRIDES
```

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
  write failures that must leave KV overrides intact;
- tenant isolation;
- GitHub clone/push and base-tree preservation;
- missing bindings/tokens and permission failures.
