---
name: 0xcms-core-features
description: Maintain the feature-sliced 0xCMS host in /Users/colin/Documents/code/workers/cms. Use when editing cms.features.json, src/core, src/features, feature manifests/routers/services/extensions, schema fragments, generated registries, migrations, optional-feature behavior, dependency boundaries, or making a CMS capability installable/droppable. Covers core-versus-feature placement, generated code, schema assembly, additive enable migrations, and profile/boundary validation.
---

# 0xCMS Core Features

## Source authority

Use `/Users/colin/Documents/code/workers/cms` for the current feature-sliced
host. `/Users/colin/Documents/code/frameworks/zeroxcms/cms` is the older
monolithic copy; do not copy its paths or imports into the current host.

Read before changing architecture:

- `README.md` sections **Feature profiles** and **Project structure**
- `cms.features.json`
- `src/core/feature.ts` and `src/core/extensions.ts`
- `src/features/routers.ts` and `src/features/services.ts`
- the target `src/features/<id>/`
- `tools/build-features.mjs`, `build-migrations.mjs`,
  `check-boundaries.mjs`, and `check-profiles.mjs`

Treat code and tests as authoritative if comments or README tables drift.

## Placement rule

Use one question first: must every valid CMS deployment have this behavior?

- Put mandatory platform behavior and neutral contracts in `src/core/`.
- Put optional capability implementation in `src/features/<id>/`.
- Keep ordinary always-on admin routes in `src/routes/`.
- Keep feature-owned Liquid renderers/queries inside the feature; shared chrome
  and rendering contracts stay core.

Nothing outside `src/features/` may import a feature implementation. A feature
must not import a sibling unless the architecture explicitly declares and
validates that dependency. Type-only imports still violate droppability.

## Feature anatomy

A code feature normally has:

```text
src/features/<id>/
├── feature.ts       # one exported CmsFeature
├── routes.ts        # or routes/*.ts exporting *Routes
├── template.ts      # optional server renderer
├── service.ts       # optional implementation
├── extensions.ts    # optional module-load registration
└── schema.sql       # optional fragment
```

`feature.ts` stays light: id, genuine `requires`, nav keys, and bounded
`baseProps`. Do not import routers into it; that creates chrome/import cycles.

The build discovers feature manifests, route exports, services, and fragments
from convention. Add the feature key to `cms.features.json`, then run
`npm run build`; never edit `src/generated/*` directly.

## Choosing the composition boundary

Use `src/core/extensions.ts` for platform-wide hooks that core calls without
knowing who implements them, such as contributed navigation/content types,
publish adapters, page events, plugin-owned views, permissions, limits, and
background job enqueue/dispatch.

Use `src/features/services.ts` for named operations between optional features,
such as credit reservation or an admin-screen contribution. Callers depend on
the neutral structural interface/dispatcher, not on the providing feature.

An absent optional feature must be inert:

- no import failure;
- no route mounted;
- no UI entry;
- no charge/limit/job side effect;
- a documented inline/free/hidden fallback where applicable.

Register extension implementations at module load from the feature's
`feature.ts` import chain. Keep contracts in core or the local dispatcher, not
in the provider.

## Routes and UI

- Export admin feature routers as `*Routes`; generated entries mount them under
  `/admin`.
- Export public routers separately; they mount at Worker root without admin
  auth/chrome.
- Declare every sidebar key in the feature manifest so the chrome hides it
  when the feature is absent.
- Keep feature view files discoverable through the host view source. Turning a
  feature off excludes code, but bundled view assets and tests may still need
  explicit cleanup if source is deleted.

For plugin platform work, also use `$0xcms-plugin-api`. For admin markup, use
`$0xcms-ui`.

## Schema and migrations

Feature schema fragments live beside their code and begin with:

```sql
-- feature: <id>
-- requires: <other-id>  -- only when the schema genuinely requires it
```

Use idempotent DDL/data (`IF NOT EXISTS`, `INSERT OR IGNORE`) because fragments
serve fresh baselines and additive enable migrations.

`npm run build:migrations` assembles:

```text
src/core/schema.sql + enabled feature fragments -> migrations/0001_initial_schema.sql
src/core/publish/schema.sql                     -> migrations/published/0001_published_schema.sql
```

Generated baseline changes only affect fresh databases. Enabling a feature on
an existing database needs:

```bash
npm run build:migrations -- --enable <id>
```

This writes a new additive migration. Keep migration filenames globally unique
across all features, preferably prefixed by feature id. Turning a feature off
never drops existing tables.

Do not hand-edit generated baseline SQL. Change the owning core/feature
fragment, rebuild, and review the generated diff.

## Safe workflow

1. Identify the owner and whether the capability is truly optional.
2. Inspect callers and the import graph with `rg`.
3. Define or extend the neutral contract before moving implementation.
4. Add/update the feature implementation and exports.
5. Update `cms.features.json` only when installation selection changes.
6. Rebuild generated registries/migrations.
7. Test the enabled path and the absent-feature fallback.
8. Review generated files and boundary results.

If deleting a feature, remove its directory and its `cms.features.json` key.
Also remove feature-owned views/tests intentionally. Never use a recursive
delete without resolving the exact feature directory and confirming the task.

## Verification

Run:

```bash
npm run build
npm run type-check
npm run check:boundaries
npm run check:profiles
npm run check:generated
npm test
```

`npm test` repeats several checks, but running focused commands makes failures
easier to attribute. Add tests for at least:

- the feature enabled;
- the feature disabled;
- every declared dependency/profile combination;
- route mount/non-mount behavior;
- optional service/extension fallback;
- schema assembly and additive migration when relevant.
