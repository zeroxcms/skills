---
name: 0xcms-events-plugin
description: >-
  Work on and debug the 0xCMS "events" plugin (cms-plugin-events: events, RSVP
  guest lists, EDM, QR check-in). Use whenever a task touches
  workers/cms-plugin-events, mentions the events plugin admin
  (/admin/plugins/events/...), guest lists / RSVP / EDM / check-in, or
  guest-list CSV import — and ESPECIALLY when an admin action "returns not
  found / 404 / 503" after submit. Captures the architecture, a file map, the
  exact places 404/503/1101/1102 come from, and the non-obvious gotchas
  (blueprint seeding, subrequest budget, canonical-origin guard, import
  idempotency, list pagination caps). Also holds the reusable resumable
  long-running-operation and batch-read/write patterns any plugin doing bulk
  CMS work should follow. Pair with 0xcms-admin-ui for styling the admin
  fragments.
---

# 0xCMS events plugin

## Architecture (read this first)

`cms-plugin-events` is a **separate Cloudflare Worker** from the host CMS.
Two-way wiring:

- **Host → plugin**: the host proxies `/admin/plugins/events/<rest>` to the
  plugin's `/__plugin/admin/<rest>` (`proxyToPlugin`). It forwards the body,
  sets `x-plugin-secret` + `x-cms-user`, and — when the plugin response carries
  `x-cms-chrome: 1` — wraps the HTML fragment in the host admin shell (host CSS,
  strict nonce CSP).
- **Plugin → host**: the plugin reads/writes pages via the host Plugin API at
  `{CMS_URL}/__cms/*` using `x-plugin-secret` (plugin `src/cms.ts` `CmsClient`:
  `get/list/create/update/batchCreate`). Guests, lists, events, and EDMs are all
  CMS **pages** (`page_type` guest / mail_list / event / edm).

Local dev: run BOTH `wrangler dev`s. Plugin `.dev.vars` needs
`CMS_URL=http://localhost:8787` and a `PLUGIN_SECRET` that **matches** the
host's `cms/.dev.vars` PLUGIN_SECRET (mismatch → every call 403s). Host
`wrangler.toml` needs `[[services]] binding=PLUGIN_EVENTS
service=worker-cms-plugin-events` + `PLUGINS="PLUGIN_EVENTS"`.

## File map

Plugin (`workers/cms-plugin-events/src/`):

- `index.ts` — `/__plugin/*` contract + `handleAdmin` dispatch by first segment
  (`events` | `rsvp` | `edm`); `eventDashboard`, adhoc check-in.
- `rsvp.ts` — the big one: `handleRsvpAdmin` routing, guest lists
  (`createGuestList`), guests, and the **import** flow (`previewImportGuests`,
  `confirmImportGuests`, `classifyImport`, `parseImportRows`).
- `cms.ts` — `CmsClient` + lect helpers `attr` / `localized` / `items` /
  `checkins` / `pointer`, `computeGuestListSummary`, `listAll`.
- `manifest.json` — `contentTypes.blueprint` (event/guest/mail_list/edm/label),
  blocks, nav. The `guest` blueprint has a nested `checkin` block — see gotchas.
- `views/sections/*.liquid` + `views/templates/*.json` — admin UI fragments.

Host — **the two live hosts differ**; resolve against the repo you're editing:

| Concern | `workers/cms` (feature-sliced) | `frameworks/zeroxcms/cms` (monolithic) |
| --- | --- | --- |
| `/__cms/*` routes, `createPage`/`updatePage`/`/pages/batch` | `src/features/plugins/routes/cms-api.ts` | `src/routes/cms-api.ts` |
| `proxyToPlugin` | `src/features/plugins/routes/admin-proxy.ts` | `src/routes/admin/plugins.ts` |
| `blueprintToLect` | `src/core/db/lect.ts` | `src/utils/lect.ts` |
| `deliverHooks` | `src/features/plugins/hooks.ts` | `src/plugins/hooks.ts` |
| `canonicalHostResponse`, `checkCrossSite` | `src/core/http/headers.ts` | `src/security/http.ts` |
| submission ingest | `src/core/db/submission-ingest.ts` | `src/utils/submission-ingest.ts` |

`MAX_BATCH = 100` (both hosts; over-size batches get
`413 {error: 'batch_too_large'}`). Each batch item merges
`blueprintToLect ← stored ← incoming` lect.

## Debugging "submit returns not found / 404 / 503"

The recurring issue. Work the decision tree — don't guess:

1. **HTTP 200 page that shows "CMS responded 404 (not_found)"** → it's
   `errorPanel` (always 200) from a thrown `CmsApiError` inside the handler.
   Means a `cms.*` call got a non-2xx from the host. Usually `cms.update`/`get`
   on a missing page, or a 403 from a **PLUGIN_SECRET mismatch**. Not a routing
   problem.
2. **True HTTP 404 with body "not found"** → the plugin returned
   `new Response('not found', {status:404})`. In `rsvp.ts` this is almost always
   a `guestListContext`/`cms.get` returning a page whose `page_type` isn't what
   the route expects (e.g. list not `mail_list`, event not `event`). Check the
   id actually resolves to that type.
3. **True HTTP 404 on a POST while GETs work, and you're NOT on localhost** →
   the host's `canonicalHostResponse` returns a literal `404 "Not Found"` for
   any non-GET when `url.origin !== CANONICAL_ORIGIN`. Fix: access via
   `localhost` (exempt) or an origin equal to `CANONICAL_ORIGIN`. (GET on a
   mismatch gets a 308 redirect, so GETs "work" while POSTs 404 — a classic
   symptom.)
4. **503 after several seconds on a bulk action** → subrequest budget /
   local-dev timeout. The host does ~5 D1 ops + an audit row **per created
   guest** in one `/pages/batch` request; a big chunk piles up subrequests (or
   just runs slow under miniflare) and fails. Fix: keep `IMPORT_CREATE_BATCH`
   moderate (currently 25) so each CMS request is light; the plugin makes more
   sequential calls instead.
5. **Cloudflare error 1101 in prod on import/confirm, retries make progress** →
   the plugin Worker blew its per-invocation subrequest cap (50 free / 1000
   paid): each `cms.*` call is one `globalThis.fetch`, and `fetch` throws "Too
   many subrequests" → unhandled → 1101. Retries got further each time because
   classify is idempotent. Fixed 2026-07-08: confirm passes are budgeted
   (`IMPORT_PASS_WRITE_BUDGET` = 40 write calls) and cap errors are caught
   (`isSubrequestLimitError`); leftover work renders the `guest-import-progress`
   view, which auto-resubmits the same CSV (`views/assets/import-continue.js`,
   only when the pass made progress — zero-progress passes show manual retry so
   a stuck import can't auto-loop).

Things that are NOT the cause (ruled out, don't chase them):

- **Read-after-write lag**: the host D1 has no read replication → strongly
  consistent. A page you just created/updated is immediately readable.
- `errorPanel` is **HTTP 200**, never 404 — so a 404 *status* is never
  errorPanel.

## Non-obvious gotchas

- **Blueprint seeds one empty item per nested block on create.**
  `blueprintToLect` sets `lect[block] = [emptyItem]` for every nested blueprint
  block, and `createPage` merges it UNDER the plugin's lect. The `guest`
  blueprint has a `checkin` block, so every new guest gets a seeded empty
  `checkin:[{}]`. NEVER test check-in with `items(lect,'checkin').length` — use
  `checkins(lect)` (`cms.ts`), which filters to rows with a real `status`/`date`.
  Same trap for any nested block.
- **`cms.list` returns `ORDER BY updated_at DESC, id DESC`** — newest first, not
  creation order. Don't assume list order matches insertion/CSV order.
- **The host clamps `/__cms/pages` to 500 rows per call**, so
  `cms.list(..., {limit: 500})` silently truncates collections past 500 — guest
  lists looked "stopped at 500" and imports re-created the unfetched tail as
  duplicates. Fixed 2026-07-08: use `cms.listAll(pageType, opts)` (pages by
  offset until `total`) for anything that needs a WHOLE guest list — classify,
  list views, exports, EDM queueing, contact/registration dedupe. **Never add a
  new `list('guest', {limit: 500})` call.**
- **Cloudflare 1102 (host CPU exceeded) on a paginated guest GET** → the host
  pointer filter was an unindexed `json_extract` full scan + serialized 500 fat
  rows + reran COUNT(*) per page. `listAll` halves its page size
  (500→250→…→50) on transient 5xx and retries the same offset. Lists with
  thousands of rows are usually DUPLICATES minted by the pre-pagination import;
  clean up with the guest list's "Remove duplicates" button
  (`/rsvp/<id>/dedupe`, `findDuplicateGuests`): groups only rows identical in
  name + every imported/custom field, always keeps copies with check-ins /
  responses / registration_ref, soft-deletes the rest to trash in budgeted
  batches. Host-side fixes APPLIED 2026-07-08: expression indexes on
  `json_extract(lect,'$._pointers.{mail_list,event,edm,contact}')`; `GET /pages`
  inlines the (validated) pointer path as a SQL literal — SQLite ignores
  expression indexes if the expression holds a bound parameter — and honors
  `count=0` (returns total: -1, skips the COUNT scan). The plugin's `listAll`
  sends `count=0` on follow-up pages via its own raw `listPage` (the published
  SDK `list()` has no count knob).
  **Where those indexes live now:** in the feature-sliced host they are the
  droppable `plugin-pointer-indexes` feature
  (`src/features/plugin-pointer-indexes/schema.sql`), assembled into the
  generated `migrations/0001_initial_schema.sql` — there is no numbered
  migration for them. On an existing database, enable them additively with
  `npm run build:migrations -- --enable plugin-pointer-indexes` and then
  `wrangler d1 migrations apply cms --remote`. In the monolithic host they are
  part of the baseline schema.
- **Never bulk-delete a whole child collection with `batchRemove`** — use
  `cms.deleteChildren(selector, pageType)` → host `DELETE /pages/children`:
  server-side, bounded (1000/call, plugin loops while `done=false`), trashes in
  `DB.batch` chunks, no per-page unpublish, hooks detached. The old
  `deleteGuestList` streamed ids through `DELETE /pages/batch`, whose per-page
  `unpublishPageFromTargets` fanout (100-wide) hung big lists after the first
  chunk ("only 100 deleted, spinner forever"). Fixed 2026-07-08: delete-list
  uses `deleteChildren` (like event delete), and the host batch route now calls
  bulk `unpublishPagesFromTargets` — so `batchRemove` for targeted id sets (e.g.
  dedupe copies) is safe too.
- **Host 1102 on big bulk deletes — fixed 2026-07-08 (later same day)**: the
  host used to fire one lifecycle-hook POST **per deleted page** (a 1000-guest
  children-delete = 1000 service-binding fetches from one invocation) and
  `trashDraftPages` did `SELECT *` (deserializing every fat lect row just for
  hook metadata). Now `deliverHooks` chunks 100 pages per POST — the payload
  carries `pages: [...]` with `page` still = first entry for old single-page
  handlers; the plugin's `/__plugin/hooks/*` route iterates
  `payload.pages ?? [page]`. `trashDraftPages` returns light `TrashedPageRef`
  (id/uuid/name/slug/page_type — no lect).
- **`fields=` projection on `GET /__cms/pages` (added 2026-07-08)**: e.g.
  `fields=id` selects only whitelisted columns and skips lect entirely —
  criteria (pointer/page_id/q) + limit/offset/count=0 all still apply; returned
  page objects carry ONLY the requested fields. Plugin:
  `cms.listAll(type, {fields})` / `cms.listAllIds(type, opts)`.
  `deleteEventCascade` and `listByEvent` now use the indexed `event` pointer
  server-side (`listByEvent` used to fetch ALL pages of the type and filter
  client-side, capped at 500); cascade fetches ids only.
- **Partial update merges**: host `PUT /pages/:id` partial-merges lect and keeps
  the existing `name` when omitted — so `cms.update(id,{lect:{phone:'x'}})` only
  touches phone. `last_name` is localized, send `{last_name:{en:value}}`; other
  guest value fields (email/phone/organization/job_title/plus_guests/status/
  prefer_language/cc/remarks) are plain scalars.
- **Text search**: delegate to the host with `cms.list(..., { q })`. Do **not**
  re-apply local substring matching to `q` afterward — CMS search may return
  normalized matches such as Traditional/Simplified Chinese variants. Keep local
  filtering for plugin-only facets (RSVP status, color tags, custom fields,
  per-list/event membership).
- **Styling and escaping** are covered by `0xcms-admin-ui`: plugin fragments use
  the host's purged Tailwind class set (verify with
  `grep -aF ".the-class" cms/views/assets/admin.css` — `-a` matters, the
  minified CSS trips grep's binary detection; `bg-amber-100` and `line-through`
  are NOT emitted, `bg-amber-50` is), and admin client views are
  auto-escaped so `| escape` double-escapes. The server-rendered email/QR set
  (`templates/edm-mjml.liquid`, `layout/mjml.liquid`, `sections/mjml/*`,
  `templates/qr.liquid`) goes through `renderLiquid` WITHOUT auto-escape and
  keeps explicit `| escape`. `renderView` in `src/templates/liquid.ts` mirrors
  the host for tests.

## Guest CSV import flow (per-list)

Route: `POST /rsvp/<listId>/import` → preview (no writes);
`POST /rsvp/<listId>/import/confirm` → applies. Both end by redirecting to
`/admin/plugins/events/rsvp/<listId>`.

- `parseImportRows` → `IncomingGuest[]` with RAW values (no defaults, so an
  absent column never reads as a change). Column aliases: name/first_name,
  last_name, email, phone|mobile, organization|company, job_title|title,
  plus_guests, status, prefer_language|language, cc, remarks|notes,
  checkin_status/checkin_date/checkin_message.
- `classifyImport` matches each row to an existing guest by `guestMatchKey`
  (email if present, else lowercased name), classifying new / update(+diff) /
  unchanged. It **consumes** each existing guest once and prefers a zero-diff
  match within a key group — so re-importing the same file is **idempotent even
  with duplicate emails** (duplicate emails create one guest per row on the
  first import; naive "first match" would then show the 2nd row as a spurious
  update).
- The preview carries the **raw CSV** (small) in a hidden field, NOT an expanded
  plan; confirm re-parses + re-classifies server-side (keeps the POST body small
  and stops the client smuggling writes to other pages).
- Confirm honors a `mode`: `new_and_update` (default) / `new_only` /
  `update_only`. Creates run in `IMPORT_CREATE_BATCH` (25) batches; updates run
  per guest. Both confirms (per-list and event-level
  `/events/<id>/import/confirm`) are **resumable** — see the pattern below.
- Defaults (status → "to be invited", plus_guests → "0") apply only when
  CREATING (`incomingToCreateInput`), never in the diff.
- A CSV `id` column becomes the requested page id on create. If the id is taken
  (host `id_conflict`, batch per-item or 409 on single create), confirm renders
  `guest-import-conflict` (`ImportIdConflictError`) with an "Assign new IDs and
  continue" button that resubmits with `assign_new_ids=1`; the retry recreates
  ONLY the conflicting rows with the id stripped (rows whose id is free keep
  it). Non-conflict batch errors still throw.

Legacy eventuai exports need preprocessing first: rename `primary_email`→`email`
and `cc_email`→`cc`, strip Excel `="..."` armor, read as utf-8-sig, and split by
`guest_list_name` into per-list files. Check-in carries over via the
`checkin_status`/`date`/`message` columns (`checked-in`/`session-checked-in`
count; blanks and `undo-*` ignored). Cleaned files:
`sample/eventuai-import/NN_<list>.csv`.

## Reusable pattern: resumable long-running operations

For imports or any work likely to exceed a Worker invocation limit, follow the
guest-import pattern in `src/rsvp.ts` rather than attempting all work in one
request. This generalizes to any plugin doing bulk CMS writes.

1. Preview and classify without writing. On confirmation, re-parse and
   re-classify the original input against current CMS state; do not trust a
   client-carried write plan.
2. Make classification idempotent so completed rows become unchanged on the next
   pass. Fetch the complete relevant dataset **with pagination** before
   classifying; a host page-size cap must not create duplicates.
3. Apply a bounded amount of work per invocation, leaving headroom below
   subrequest and execution limits. Batch creates conservatively, split batches
   on transient host pressure, and count every host read/write against the
   budget.
4. When work remains, render an intermediate progress page that resubmits the
   same source input and options to the confirm route. Show per-pass progress
   and remaining work. **Auto-continue only if the pass actually wrote
   something**; otherwise require a manual retry so a stuck operation cannot
   loop forever.
5. Treat a runtime subrequest-limit error as an incomplete pass *after*
   preserving successful writes, not as total failure. Never auto-retry
   ambiguous non-idempotent operations.
6. Detect imported ID collisions explicitly, including IDs already used by CMS
   and IDs repeated within the file. Stop on a conflict and explain that prior
   writes were saved. Offer an explicit retry that lets CMS assign fresh IDs
   only to conflicting rows, warning that old QR codes or signed links tied to
   replaced IDs may no longer match.
7. Preserve collision-resolution state across every continuation.

UI reference: `views/sections/guest-import-progress.liquid`,
`views/sections/guest-import-conflict.liquid`, `views/assets/import-continue.js`.

Tests to add: pass budget, mid-pass runtime caps, zero-progress/manual
continuation, multi-group deferral, repeated-file idempotency, datasets beyond
one host page, and ID-conflict recovery.

## Reusable pattern: batch reads and writes

Prefer the fewest bounded CMS calls that preserve versioning and retry safety:

- Read related pages across many groups with **one multi-pointer query**
  (`pointer: { key, values }`) instead of one `/pages` chain per list. Keep
  pagination because the host caps page responses; follow-up pages should skip
  recounting (`count=0`).
- Group mutations by target before writing. For event archive: aggregate all
  guest activity per contact, create each unmatched contact once with every
  `_ref`-keyed history entry inline, update each existing contact once, and
  batch-stamp guests afterward.
- Use generic create/update/delete batch endpoints in chunks of at most 100. Do
  not fall back to per-page creates or updates after an ambiguous batch failure;
  rediscover state and rely on `_ref` plus `contact_merged_at` idempotency.
- Expect one page version and audit row per page even when transport and D1 work
  are batched. Confirm batching from the HTTP route/call count, not from the
  number of audit records.
- A stopped archive may have contact activity already written but guest stamps
  pending. On retry, dedupe history by guest UUID before stamping; do not
  classify an unstamped guest as fully merged solely because its contact matches
  by email or name.

Add focused tests asserting that multi-pointer reads replace per-list reads,
batch routes replace single-page routes, duplicate guests produce one contact
mutation, and interrupted retries do not duplicate history.

## Public submission storage (Option B, built 2026-07-07)

worker-rsvp stores public submits as INSERT-only rows in the published D1
(`live_pages`): `rsvp_response` (page_id = guest id) and `rsvp_registration`
(page_id = event id), with NEGATIVE ids and their own uuids — so a CMS republish
(upsert by uuid) can never overwrite them. worker-rsvp never calls the Plugin
API on submit anymore (only unsubscribe still does).

Flow: worker-cms ingests new rows into the draft DB as pages (submission-ingest,
cron */5 + `POST /__cms/ingest/submissions`, same uuid → idempotent, fires
`create` hooks) → this plugin's create hook applies `rsvp_response` pages to
guests (`src/submissions.ts` `applyResponsePage`: status/plus_guests/response-log
append with `_ref: <submission uuid>`, page stamped `applied_at`) →
`rsvp_registration` pages wait in `/events/:id/registrations` (convert → Adhoc-list
guest with `registration_ref`, dedupe by email; discard → soft-delete; "Pull new
submissions" button → host ingest + pending sweep).

Gotchas:

- Host publish/unpublish/trash REFUSE submission page types
  (`PublishOutcome.refused`) — publishing would upsert the original live row;
  unpublish/trash would DELETE it (worker-rsvp reads response rows for its
  already-responded check).
- worker-web excludes the types in `getPageBySlug`/`listAllPages`
  (`NOT_A_SUBMISSION`, COALESCE for NULL types) — submission rows hold emails.
- The `/__cms/ingest/submissions` caller must own BOTH submission types in its
  manifest scope; plugin client method: `cms.ingestSubmissions()`.
- Tests: `test/submissions.test.ts`; the shared `redirect` helper returns 302.

## Testing

`test/index.test.ts` drives the plugin Worker directly (no host) with a mocked
`fetch` standing in for `{CMS_URL}/__cms/*`. Pattern: stub `fetch`, match on
`url.pathname` (`/__cms/pages/<id>`, `/__cms/pages?...`, `/__cms/pages/batch`,
`PUT /__cms/pages/<id>`), assert on the recorded request bodies and the
`Location`/HTML response. Run `npx tsc --noEmit && npm test` in the plugin repo.
