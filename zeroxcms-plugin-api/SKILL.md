---
name: 0xcms-plugin-api
description: Create and maintain 0xCMS Worker plugins and the plugin-facing /__cms APIs, including plugin scaffolding, manifests, Cloudflare KV tenant registries, tenant authentication, admin views, server-to-server page read/write/search, delegated readTypes/writeTypes, batching, credits/limits, and tests. Use when starting or reviewing a cms-plugin-* project, setting up multi-tenant plugin KV, editing src/routes/cms-api.ts or src/utils/search.ts, or changing plugin API behavior under /Users/colin/Documents/code/workers.
---

# 0xCMS Plugin API

## Core Context

The plugin-facing API is mounted at `/__cms` in `src/routes/cms-api.ts`. It sits outside `/admin` auth and uses server-to-server plugin auth:

- Require `x-plugin-id` and the resolved plugin's own `x-plugin-secret`.
- Use `authenticatePlugin(c)` before any endpoint work.
- Enforce page-type scope with `pageTypeScopeAllows`.
- Writes use `auth.allowedTypes`; reads use `auth.readableTypes`.
- `readTypes` and `writeTypes` from plugin manifests only count after admin approval in `plugin_page_type_approvals`.
- A wildcard approval is `"*"`, but callers must never request `"*"` as an actual page type.

The API is trusted between cooperating plugins, not browser-authenticated. Keep all mutation behavior versioned, audited, and hook-aware like the existing create/update/delete paths.

## Workflow

1. Inspect the current endpoint, helper utilities, and tests first:
   - `src/routes/cms-api.ts`
   - `src/utils/plugin-page-types.ts`
   - `src/utils/search.ts` for advanced search behavior
   - `test/cms-api.test.ts`
2. Reuse existing helpers instead of duplicating SQL/auth/query logic.
3. Register more specific routes before parameter routes such as `/pages/:id`.
4. Keep request parsing strict enough to reject malformed bodies, but plugin-friendly for common shapes.
5. Add focused tests in `test/cms-api.test.ts` for auth, scope, result shape, and the main behavior.
6. Run at least:
   - `npm test -- test/cms-api.test.ts`
   - `npm run type-check`

## Creating a New Worker Plugin

Treat `cms/` as the contract authority and use a current SDK-based sibling as the implementation reference. Do not clone `cms-plugin-rsvp` (retired into Events), the old `cms/examples/plugin-events`, or the Wrangler 3 publish-target examples as a general scaffold. Choose the nearest current shape:

- Admin/content plugin: `cms-plugin-mindmap` or `cms-plugin-wedding-planner`.
- Companion/integration plugin using delegated types: `cms-plugin-event-action`, `cms-plugin-eventbrite`, or `cms-plugin-google-sheet`.
- Large suite with custom views, hooks, assets, limits, and credits: `cms-plugin-events`.
- Publish-only adapter: use the three `/__plugin/publish/*` routes documented in `cms/README.md`, but bring authentication, dependencies, tests, and Wrangler config up to the current baseline.

Build the minimum plugin shape needed:

1. Create a separate `cms-plugin-<slug>` repository with `src/index.ts`, `src/manifest.json` when the manifest is static, `test/`, strict `tsconfig.json`, `package.json`, `wrangler.toml`, and `views/` only when the plugin renders UI.
2. Use `@lionrockjs/worker-cms-plugin` for `CmsClient`, neutral `lect` readers, tenant resolution, client-view responses, redirects, and asset serving. Add a local `src/cms.ts` wrapper only for plugin-specific API methods or `x-acting-user-id`; do not fork the shared client.
3. Include `dev`, `deploy`, `test`, and `typecheck` scripts and current compatible Cloudflare Workers, TypeScript, Wrangler, and Vitest dependencies. Use the current sibling compatibility date and only the bindings/flags the plugin needs.
4. If UI is needed, bind `views/` as `VIEWS` with `run_worker_first = true`, serve `/__plugin/views/*`, and add `[version_metadata]` so the manifest can expose `CF_VERSION_METADATA` and invalidate cached views. Use the `0xcms-ui` skill for CMS-consistent Liquid UI work.

Manifest rules:

- Keep `id`, package/client constants, permission prefixes, nav links, and `/admin/plugins/<id>` paths identical. IDs must match `^[a-z][a-z0-9-]{0,63}$`.
- Prefer a static `src/manifest.json`, served publicly and overlaid only with deploy metadata. Build it dynamically only when an environment setting genuinely changes declarations, as in Google Sheet's scoped page-type list.
- Put owned page types in `contentTypes.blueprint`. Put access to another plugin's types in `readTypes`/`writeTypes`; request only what is needed and expect admin approval before use. Never send `"*"` as a concrete `page_type`.
- Declare only implemented hooks, view overrides, assets, permissions, credits, and limits. Namespace permission values and translation keys by plugin id. Use `publishLect` to keep private or unnecessary fields out of published data.
- Keep durable business content in CMS pages using `lect`; use plugin KV/D1/R2 only for secrets, external-provider state, queues, caches, or data that does not belong in CMS content.

Routing and security rules:

- Leave discovery resources (`GET /__plugin/manifest` and view files) public. Authenticate `/__plugin/admin`, `/hooks`, `/publish`, `/edit`, and `/read` before reading `x-cms-user` or doing work.
- For new reusable plugins, call `requireTenant(request, env)` and then `tenantClientEnv(env, tenant)`. This verifies `x-cms-tenant` and `x-plugin-secret` against the same tenant row and prevents a caller-selected CMS URL. The `CMS_URL` plus `PLUGIN_SECRET` fallback remains valid for a single-tenant deployment.
- Use the plugin's dedicated secret for both host-to-plugin authentication and plugin-to-host `/__cms` calls; always send both `x-plugin-id` and `x-plugin-secret` through `CmsClient`. Do not reuse another plugin's pairwise secret; share a separate `signKey` when cooperating Workers must verify public tokens.
- Parse the server-derived `x-cms-user` only after authentication. Gate each admin mutation explicitly. When an admin action creates pages or reports metered usage, propagate the user id as `x-acting-user-id` so host credits are attributed correctly; public/cron flows should remain unattributed unless a real acting user exists.
- Give public callbacks their own scoped signature/token verification and tenant selection. Never accept a CMS URL, raw shared secret, or authoritative content directly from callback input.
- Return client-rendered Liquid views with CMS chrome where practical. Serve executable assets at their declared `/assets/*` paths and assume they must be admin-approved and hash-pinned. Avoid inline scripts because CMS chrome uses a strict CSP.

### Cloudflare KV tenant registry

Use one `TENANTS` KV namespace per plugin deployment and environment. Do not share a production namespace with staging or local development.

1. Create and bind the namespace from the plugin directory with current Wrangler:

   ```bash
   npx wrangler kv namespace create <plugin-id>-tenants --binding TENANTS --update-config
   ```

   Verify that `wrangler.toml` contains a `[[kv_namespaces]]` entry whose binding is exactly `TENANTS`, and add `TENANTS?: KVNamespace` to the Worker environment type. Commit the binding id; it is an identifier, not a secret.
2. Register the plugin URL in the CMS while disabled and copy that registration's dedicated shared secret. Set the CMS `CANONICAL_ORIGIN` to its normalized public origin; the host sends that exact value as `x-cms-tenant`.
3. Store one KV record per CMS. Use the exact normalized origin, without a trailing slash, as both the key suffix and default CMS API URL:

   ```text
   key: tenant:https://cms.example.com
   value: {"secret":"<CMS registration secret>","signKey":"<separate public-token key>","publicBaseUrl":"https://public.example.com","vars":{"EMAIL_FROM":"events@example.com"}}
   ```

   Only `secret` is required. `cmsUrl` may override the key's origin when the Plugin API lives elsewhere. `signKey` defaults to `secret`, but always make it distinct when another Worker verifies public QR, RSVP, purchase, unsubscribe, or webhook tokens. Use `vars` for tenant-specific provider credentials/configuration.
4. Put the JSON in an ignored mode-0600 temporary file outside the repository and write it with `--path`; do not put secrets in `wrangler.toml`, shell history, command arguments, logs, or committed fixtures:

   ```bash
   npx wrangler kv key put --binding TENANTS --remote --path <secure-tenant-json-path> "tenant:https://cms.example.com"
   npx wrangler kv key list --binding TENANTS --remote --prefix "tenant:"
   ```

   Use `--env <name>` with an environment-specific binding when applicable. Avoid `kv key get --text` during routine verification because it prints the full secret-bearing record.
5. Deploy the plugin, enable it in the CMS, approve only required page types/assets, then smoke-test one secret-authenticated admin request and one plugin-to-CMS read/write. A tenant mismatch or stale secret must fail with 403.

For local multi-tenant tests, write the same record with `--local --persist-to .wrangler/state` and run `wrangler dev --persist-to .wrangler/state`. For ordinary single-tenant development, `CMS_URL` plus `PLUGIN_SECRET` in an uncommitted `.dev.vars` remains simpler and exercises the SDK fallback.

For rotation, disable the plugin registration, rotate the CMS secret, replace the full KV record while preserving its optional fields, then wait for KV propagation and the SDK's 60-second tenant cache (or deploy a new Worker version) before re-enabling and smoke-testing. The registry supports one active pairwise secret per tenant, so do not attempt an uncoordinated live rotation.

For removal, disable or delete the CMS registration first, then remove only that tenant key:

```bash
npx wrangler kv key delete --binding TENANTS --remote "tenant:https://cms.example.com"
```

Wait for propagation/cache expiry and confirm other tenant keys remain. Never delete the namespace while it still serves another tenant.

Data and test rules:

- Prefer generic `/__cms` operations and package helpers. Paginate reads, batch writes/deletes, preserve `lect` semantics and pointers, and make imports/sync/webhooks idempotent.
- Test the public manifest, protected-route rejection, correct plugin id/secret headers, owned and delegated scope failures, tenant isolation when supported, permission gates, view/asset serving, and the main read/write behavior with mocked CMS calls. Add callback signature and idempotency tests for public integrations.
- Before handoff run `npm run typecheck` and `npm test` in the plugin. For host changes also run `npm test -- test/cms-api.test.ts` and `npm run type-check` in `cms/`.

Deployment order: deploy the plugin, register its HTTPS base URL disabled, review the manifest, copy the generated dedicated secret into the plugin (or tenant registry), approve only required assets and delegated page types, enable it, and exercise one authenticated read and write.

## Advanced Search Pattern

For plugin advanced search, prefer a POST endpoint such as `/__cms/pages/search` with a JSON body rather than mirroring the admin query string. Accept:

```json
{
  "page_type": "guest",
  "page_types": ["guest"],
  "criteria": [
    { "term": "Acme", "path": "affiliations[*].company", "tags": ["777"] }
  ],
  "operator": "AND",
  "limit": 20,
  "page": 1,
  "sort": "updated_at",
  "order": "DESC"
}
```

Implementation expectations:

- Normalize `page_type` plus `page_types`, dedupe, and reject forbidden types.
- If allowing `all`, expand only to page types from resolved config that are allowed by `auth.readableTypes`.
- Normalize criteria to `AdvancedSearchCriterion[]`.
- Accept `term` or `search` for the text term.
- Accept numeric tag ids as strings or comma-separated strings; dedupe them.
- Drop empty criteria, but reject non-array or malformed criteria.
- Use `advancedSearchOperator`, `advancedSearchSort`, `advancedSearchOrder`, and `performAdvancedSearch`.
- Serialize returned `Page` rows with `serializePage`.
- Return `pages`, `total`, `limit`, `offset`, `pagination`, and the resolved `page_types`.

Tests should cover:

- Path criteria, including wildcard JSON paths like `items[*].field`.
- Criteria combining `term`/`path` with `tags`.
- Delegated `readTypes`: blocked before approval, allowed after approval.
- Page-type scope for owned, delegated, wildcard, and forbidden types when relevant.

## Bulk API Pattern

Use batching wherever page jobs would otherwise spend one Worker/D1 subrequest per page:

- Register batch routes before `/pages/:id`. Authenticate and resolve config once, validate write/read scope per item, return indexed per-item errors, and commit valid writes with `DB.batch()`.
- Keep batch lect updates generic. Merge partial lect using the single-page semantics, create a distinct page version for every page, and emit audit records and lifecycle hooks in bulk. Omit per-page Page Sync Durable Object notifications for server-side bulk jobs when they would recreate N subrequests.
- Allocate generated page/version ids in memory, collision-check candidates together, then use explicit ids so page rows and versions can commit in one transaction. Count SQL bindings, not logical ids: a draft-plus-trash collision query binds each id twice, so use chunks of 50 to stay at 100 variables in local D1/SQLite.
- Test the exact maximum batch size (100), not only the rejected size (101). Verify first/last payload isolation and that every page's `current_page_version_id` points to a version with identical lect.
- Deliver hooks in chunks (currently 100 pages per subscribed plugin). Preserve one audit/version record per page; batching reduces round trips and does not consolidate the audit trail.
- Batch related reads with `pointer_values` instead of one request chain per pointer. Retain bounded pagination (currently 500 pages) and send `count=0` after the first page.

Do not introduce a domain-specific CMS endpoint when a generic multi-pointer read, batch create, batch lect update, duplicate, or delete operation can express the workflow safely.

## Safety Notes

- Do not let plugin search bypass readable scope.
- Do not build SQL by concatenating raw request path or sort values; use existing normalizers and parameterized SQL helpers.
- Keep page-create/update/delete code charging credits and checking limits where the existing path already does.
- If tests need generated Wrangler state and disk is full, `.wrangler` is generated cache and can be cleared with approval.
