---
name: 0xcms-plugin-api
description: >-
  Create and maintain 0xCMS Worker plugins and the plugin-facing /__cms API —
  scaffolding, manifests, SDK clients, automatic multi-tenant enrollment,
  Cloudflare KV setup, authenticated admin/views/hooks, delegated
  contentTypes.readTypes/writeTypes, batches, limits, credit decorators,
  publish targets, and tests. Also covers the two things every plugin with a UI
  needs: shipping client-side JavaScript through the manifest→approval→SRI
  pipeline (use when a plugin button "does nothing" or a script "was stripped /
  doesn't run"), and bespoke page editors via editViews/newViews/readViews and
  /__plugin/edit (use for "custom editor for my plugin's pages" or any plugin
  view that must POST back into the CMS save handler). Use for cms-plugin-*
  projects, frameworks/zeroxcms/plugin-*, @lionrockjs/worker-cms-plugin, or host
  API work under the plugins feature.
---

# 0xCMS Plugin API

## Source authority

Two 0xCMS hosts are live and both carry current code, with **different internal
layouts**. Resolve every path against the repo you are actually editing.

| | `workers/cms` (feature-sliced) | `frameworks/zeroxcms/cms` (monolithic) |
| --- | --- | --- |
| Plugin API routes | `src/features/plugins/routes/cms-api.ts` | `src/routes/cms-api.ts` |
| Admin proxy (`proxyToPlugin`, `servePluginAsset`) | `src/features/plugins/routes/admin-proxy.ts` | `src/routes/admin/plugins.ts` |
| Lifecycle hooks | `src/features/plugins/hooks.ts` | `src/plugins/hooks.ts` |
| Sanitize / proxy / edit-view | `src/features/plugins/{sanitize,proxy,edit-view}.ts` | `src/security/plugin-{proxy,sanitize}.ts`, `src/plugins/edit-view.ts` |
| lect helpers (`blueprintToLect`) | `src/core/db/lect.ts` | `src/utils/lect.ts` |
| Submission ingest | `src/core/db/submission-ingest.ts` | `src/utils/submission-ingest.ts` |
| Form-once tokens | `src/core/auth/form-once.ts` | `src/utils/form-once.ts` |
| Canonical-origin guard | `src/core/http/headers.ts` | `src/security/http.ts` |
| Tailwind source | `assets-source/admin.css` | `styles/admin.css` |

Shared by both: `src/routes/admin/`, `src/templates/`, `views/`, `migrations/`.
Roots under `/Users/colin/Documents/code/`. Treat code and tests as
authoritative when a doc drifts. Never edit `src/generated/` or generated
migrations by hand.

Other sources to read before editing:

- Plugin SDK: `workers/cms-plugin`
- Credits decorator: `workers/cms-plugin-decorator-credits`
- Current plugins: `workers/cms-plugin-*`, `frameworks/zeroxcms/plugin-*`

For host `/__cms` changes also start with the plugins feature's `api/`
(`index.ts`, `auth.ts`, `pages.ts`, `content.ts`, `create.ts`, `limits.ts`,
`ingest.ts`), `page-types.ts`, `registry.ts`, `types.ts`, `src/core/db/search.ts`
(shared search engine), and `test/cms-api*.test.ts`, `test/plugin-limits.test.ts`,
plus the route-order tests.

## New plugin workflow

1. Pick the nearest current sibling:
   - Admin/content plugin: `cms-plugin-mindmap` or `cms-plugin-wedding-planner`.
   - Delegated integration: `cms-plugin-event-action`, `cms-plugin-eventbrite`,
     or `cms-plugin-google-sheet`.
   - Large UI/hook/limit/credit suite: `cms-plugin-events`.
   - Publish adapter: `cms-plugin-publish-ipfs` or `cms-plugin-publish-webhook`;
     bring older examples up to the current SDK and tenant baseline.
   - Framework reference: `plugin-form` or `plugin-theme-editor`.
2. Create `src/index.ts`, `src/manifest.json`, tests, strict `tsconfig.json`,
   `package.json`, `wrangler.toml`, and `views/` only when UI is required.
3. Use `@lionrockjs/worker-cms-plugin` for `CmsClient`, lect readers, tenant
   resolution, client views, redirects, and view assets. Keep a local
   `src/cms.ts` only for domain methods. Never fork the base client.
4. Include `dev`, `deploy`, `test`, `typecheck`, `kv:setup`, and
   `kv:setup:preview` scripts. Use the versions from a current sibling.
5. Run `npm run typecheck` and `npm test`.

## Manifest rules

- Keep the manifest `id`, `CmsClient` plugin id, permission prefix, and
  `/admin/plugins/<id>` routes identical. IDs match `^[a-z][a-z0-9-]{0,63}$`.
- Prefer a static `src/manifest.json`; overlay `CF_VERSION_METADATA` only when
  serving it. Build dynamically only when declarations truly depend on env.
- Put owned types in `contentTypes.blueprint`. Put delegated access inside
  `contentTypes.readTypes` and `contentTypes.writeTypes`. Both require explicit
  host approval, including `"*"`.
- Never use `"*"` as an actual `page_type`. Expand it through host metadata or
  call a scoped API that performs the expansion.
- Declare only implemented hooks, `editViews`/`newViews`/`readViews`, assets,
  permissions, limits, credits, `publishTarget`, and i18n. Namespace permission
  and translation keys by plugin id.
- Use `contentTypes.publishLect` to minimize fields copied into published data.
- Keep durable content in CMS pages and lect. Use plugin KV/D1/R2 for secrets,
  provider state, queues, caches, attachments, or other plugin-owned data.

**Blueprint seeding gotcha.** `blueprintToLect` sets `lect[block] = [emptyItem]`
for every nested blueprint block, and `createPage` merges it UNDER the plugin's
lect — so a freshly created page already has one empty item in each nested
block. Never count raw items to decide whether real data exists (the events
plugin's `guest` blueprint has a `checkin` block, so every new guest carries a
seeded empty `checkin:[{}]`); filter to rows with a real field set. Same trap
for any nested block, and for "delete last item" leaving a repeater at zero when
your reader assumes one.

## Routing and authentication

Leave only discovery resources public:

- `GET /__plugin/manifest`
- `/__plugin/views/*`
- declared `/assets/*`
- `POST /__plugin/tenants/enroll` (the ticket callback authenticates it)

Authenticate `/__plugin/admin`, `/hooks`, `/publish`, `/edit`, and `/read`:

```ts
const tenant = await requireTenant(request, baseEnv);
if (tenant instanceof Response) return tenant;
const env = tenantClientEnv(baseEnv, tenant);
```

- Authenticate before parsing `x-cms-user` or performing work.
- `requireTenant` binds `x-cms-tenant`, the pairwise secret, and the resulting
  CMS URL to the same registry row. Never accept a CMS URL from request input.
- `CMS_URL` plus `PLUGIN_SECRET` remains the single-tenant fallback.
- Build `CmsClient(env, MANIFEST.id)` after tenant resolution. It sends both
  `x-plugin-id` and `x-plugin-secret`.
- Gate admin mutations with plugin permissions. Pass `actingUserId` for real
  signed-in admin work; do not invent attribution for public/cron flows.
- Give public callbacks their own signatures and tenant ref (`?t=`) selection.
  Share a separate `signKey` between cooperating Workers, never a pairwise
  plugin secret.
- Return client views through `adminView`/`clientViewResponse`.

**Canonical-origin trap:** the host returns a literal `404 "Not Found"` for any
non-GET when `url.origin !== CANONICAL_ORIGIN` (GET gets a 308 redirect). So a
POST 404s while GETs "work" — a classic symptom. Access via `localhost` (exempt)
or an origin equal to `CANONICAL_ORIGIN`.

## Tenant setup

For a reusable plugin, bind a plugin-specific KV namespace as `TENANTS`:

```json
"kv:setup": "cms-plugin-kv-setup",
"kv:setup:preview": "cms-plugin-kv-setup --preview"
```

```bash
npm run kv:setup
npm run kv:setup:preview
```

The SDK CLI derives an account-unique namespace title from the Worker name and
binding, then updates the matching `[[kv_namespaces]]` block. Do not create
every plugin namespace with the literal title `TENANTS`; Cloudflare titles are
account-unique even though the binding name is shared.

Prefer automatic enrollment:

1. Set `"autoTenant": true`.
2. Handle `/__plugin/tenants/enroll` with
   `handleTenantEnroll(request, env, { pluginId: MANIFEST.id })`.
3. Handle `/__plugin/tenants/revoke` with `handleTenantRevoke`.
4. Keep both routes outside the normal tenant gate.
5. Optionally restrict enrollment with `TENANT_ENROLL_ORIGINS`.

Enrollment routes without the manifest flag work only when called directly; the
flag without the routes advertises a broken connection flow. Enrollment redeems
a single-use host ticket and preserves operator-managed `signKey`,
`publicBaseUrl`, and `vars` on rotation. Expect the registry's 60-second isolate
cache after enrollment/rotation.

For manual fallback, store one `tenant:<canonical CMS origin>` JSON value:

```json
{
  "secret": "pairwise host/plugin secret",
  "signKey": "separate public-token key",
  "publicBaseUrl": "https://public.example.com",
  "vars": { "EMAIL_FROM": "events@example.com" }
}
```

Never put secret-bearing JSON in source, `wrangler.toml`, command arguments,
logs, or committed fixtures. Prefer a Worker secret over tenant `vars` when one
credential serves the whole deployment — KV values are readable to operators.

## CMS client and optional decorators

Use `CmsClient` for generic page operations. Paginate lists (host cap 500), send
`count=0` after the first page where supported, use multi-pointer filters
instead of N lists, and chunk writes/deletes at 100.

Optional host features extend the stable `CmsApiTransport.request()` contract.
For credits:

```ts
import { CmsClient } from '@lionrockjs/worker-cms-plugin';
import { withCredits, creditShortfall } from '@lionrockjs/worker-cms-plugin-decorator-credits';

const cms = withCredits(new CmsClient(env, MANIFEST.id));
```

- Let the host charge `page_create` costs.
- Quote/charge `metered` costs with the real acting user.
- Report `recurring` usage rather than deducting it directly.
- Handle HTTP 402 with `creditShortfall`.
- Respect the manifest `currency`; omitted means credits, `diamond` is a
  separate premium wallet.

Keep decorators structurally coupled to `CmsApiTransport`, not SDK internals.

## Client-side JavaScript and custom editors

- **Shipping JS in a plugin admin view** — the strict CSP means inline JS never
  runs and external scripts execute only when declared in the manifest AND
  admin-approved with a pinned SRI hash. Read **`references/js-assets.md`**
  BEFORE writing any `<script>` tag, inline handler, or `views/assets/*.js`, and
  whenever a script "doesn't run" or "was stripped".
- **Replacing the host's generic page editor** with your own UI via
  `editViews`/`newViews`/`readViews` and `/__plugin/edit` — the dispatch
  contract, the CMS field-name grammar, and the co-authoring presence bar are in
  **`references/edit-view.md`**.

For admin markup and styling conventions, use `0xcms-admin-ui`. For host
architecture and feature boundaries, use `0xcms-core-features`.

## Host `/__cms` changes

The plugin platform is a removable feature. Keep its API inside the plugins
feature; core must not import it.

- Authenticate with `authenticatePlugin`.
- Reads use `auth.readableTypes`; writes use `auth.allowedTypes`.
- Apply `pageTypeScopeAllows` to every requested/concrete type.
- Register static `/pages/*` routes before `/pages/:id`.
- Reuse core page/search/publish helpers. Preserve versions, audit rows, limits,
  optional credit reservations/refunds, lifecycle hooks, and publish behavior.
- Use the generated feature-service boundary for optional credits/jobs. An
  absent optional feature must be inert, not an import failure.
- Batch with `DB.batch()`, keep indexed per-item errors, and preserve one
  version/audit record per page. Count D1 bindings, not logical items.
- Do not introduce a domain endpoint when generic search, multi-pointer reads,
  batch create/update/delete, children delete, duplicate, or publish expresses
  the operation.

After host changes run `npm run type-check` and `npm test`. The test command
also checks every feature profile, import boundaries, and generated files.

## Test matrix

Cover:

- public manifest/discovery and protected-route rejection;
- plugin id/secret and tenant isolation;
- owned, delegated, wildcard, unapproved, and forbidden types;
- permissions and acting-user propagation;
- manifest-declared assets and client views;
- auto-enrollment/revocation when implemented;
- callbacks, signatures, and idempotency;
- limits, credit shortfalls/refunds, and optional-feature absence;
- exact batch maximums and route ordering;
- version/audit/hook behavior for every mutation.

Deploy the plugin first, register it disabled, review the manifest, connect or
configure its tenant, approve only needed assets and delegated types, enable it,
then smoke-test one authenticated read and write.
