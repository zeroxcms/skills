---
name: migrate-eventuai-events
description: Migrate legacy Eventuai admin event, RSVP, EDM, guest-list, label, QR, check-in, and public RSVP behavior into the cms-plugin-events Cloudflare Worker plugin. Use when comparing legacy Eventuai admin routes, controllers, or Liquid views from /Users/colin/Documents/code/projects/eventuai/admin/application and /Users/colin/Documents/code/projects/eventuai/admin/views with the cms-plugin-events routes, manifest, TypeScript handlers, or plugin views in /Users/colin/Documents/code/workers/cms-plugin-events.
---

# Migrate Eventuai Events

## Sources

Use these source roots unless the user gives newer paths:

- Legacy application: `/Users/colin/Documents/code/projects/eventuai/admin/application`
- Legacy views: `/Users/colin/Documents/code/projects/eventuai/admin/views`
- Target plugin: `/Users/colin/Documents/code/workers/cms-plugin-events`

Read `references/route-comparison.md` before planning a route migration. Refresh it from source if route files have changed.

## Workflow

1. Re-read the current files before editing. Start with legacy `application/routes.mjs`, then the relevant legacy controller and view templates. In the plugin, read `src/index.ts`, the delegated handler module (`src/rsvp.ts`, `src/edm.ts`, `src/labels.ts`, or `src/public-rsvp.ts`), `src/manifest.json`, and the matching `views/` templates.
2. Compare route intent before copying route shape. Legacy `addPageRoutes(...)` and `HelperCRUD.add(...)` routes usually map to the CMS host page editor plus plugin dashboard links, not one-for-one Worker routes.
3. Preserve plugin boundaries. Authenticated plugin admin requests enter the Worker at `/__plugin/admin`; user-facing admin links use `/admin/plugins/events`; EDM page editing enters through `/__plugin/edit`; CMS page creation/edit/delete should remain with the host CMS when possible.
4. Preserve the target data model. Events are CMS `event` pages. Guest lists are `mail_list` pages grouped to events by `lect._pointers.event`. Guests are `guest` pages parented under a `mail_list`, with event/list pointers in `lect._pointers`. EDMs are `edm` pages grouped by the event pointer. Labels are `label` pages parented under an event.
5. Migrate one route family at a time. Keep route handlers small, add or update the plugin Liquid view that backs the route, and wire the route into existing admin navigation only after the handler works.
6. Validate behavior with focused tests or local smoke checks. Prefer existing npm scripts and tests in the target repo, and add narrow tests when a migration changes shared helpers, signatures, imports, email rendering, or guest state transitions.

## Long-running Operations

For imports or other work likely to exceed a Worker invocation limit, follow the resumable guest-import pattern in `src/rsvp.ts` instead of attempting all work in one request:

1. Preview and classify without writing. On confirmation, re-parse and re-classify the original input against current CMS state; do not trust a client-carried write plan.
2. Make classification idempotent so completed rows become unchanged on the next pass. Fetch the complete relevant dataset with pagination before classifying; a host page-size cap must not create duplicates.
3. Apply a bounded amount of work per invocation, leaving headroom below runtime subrequest and execution limits. Batch creates conservatively, split batches on transient host pressure, and count every host read/write that consumes the budget.
4. When work remains, render an intermediate progress page that resubmits the same source input and options to the confirm route. Show per-pass progress and remaining work. Auto-continue only if the pass actually wrote something; otherwise require a manual retry so a stuck operation cannot loop forever.
5. Treat a runtime subrequest-limit error as an incomplete pass after preserving successful writes, not as total failure. Never auto-retry ambiguous non-idempotent operations.
6. Detect imported ID collisions explicitly, including IDs already used by CMS and IDs repeated in the file. Stop on a conflict and explain that prior writes were saved. Offer an explicit retry that lets CMS assign fresh IDs only to conflicting rows, while warning that old QR codes or signed links tied to replaced IDs may no longer match.
7. Preserve collision-resolution state across every continuation. Add focused tests for the pass budget, mid-pass runtime caps, zero-progress/manual continuation, multi-group deferral, repeated-file idempotency, datasets beyond one host page, and ID-conflict recovery.

Use `views/sections/guest-import-progress.liquid`, `views/sections/guest-import-conflict.liquid`, and `views/assets/import-continue.js` as the UI reference.

## Batch Reads and Writes

Prefer the fewest bounded CMS calls that preserve versioning and retry safety:

- Read related pages across many groups with one multi-pointer query (`pointer: { key, values }`) instead of one `/pages` chain per list. Keep pagination because the host caps page responses; follow-up pages should skip recounting.
- Group mutations by target before writing. For event archive, aggregate all guest activity per contact, create each unmatched contact once with every `_ref`-keyed history entry inline, update each existing contact once, and batch-stamp guests afterward.
- Use generic create/update/delete batch endpoints in chunks of at most 100. Do not fall back to per-page creates or updates after an ambiguous batch failure; rediscover state and rely on `_ref` plus `contact_merged_at` idempotency.
- Expect one page version and audit row per page even when transport and D1 work are batched. Confirm batching from the HTTP route/call count, not from the number of audit records.
- A stopped archive may have contact activity already written but guest stamps pending. On retry, dedupe history by guest UUID before stamping; do not classify an unstamped guest as fully merged solely because its contact matches by email or name.

Add focused tests that assert multi-pointer reads replace per-list reads, batch routes replace single-page routes, duplicate guests produce one contact mutation, and interrupted retries do not duplicate history.

## Useful Searches

Use these as starting points:

```bash
rg -n "RouteList.add|addPageRoutes|HelperCRUD.add" /Users/colin/Documents/code/projects/eventuai/admin/application/routes.mjs
rg -n "class Event|class RSVP|class Edm|class Lead|action_" /Users/colin/Documents/code/projects/eventuai/admin/application/classes/controller
rg -n "handleAdmin|handleRsvpAdmin|handleEdmAdmin|handleLabelsAdmin|handlePublicRsvp" /Users/colin/Documents/code/workers/cms-plugin-events/src
rg -n "ADMIN_BASE|segments\\[" /Users/colin/Documents/code/workers/cms-plugin-events/src
```

## Migration Notes

- Treat legacy `Lead` records as target `guest` pages unless a future migration note says otherwise.
- Treat legacy `rsvp` pages as target `mail_list` guest lists in most admin flows.
- Be cautious with public RSVP URL compatibility. Legacy URLs use `event_slug`, `edm_id`, `view_id`, and `sign`; the current plugin uses signed numeric `eventId`, `listId`, and `guestId`.
- For plugin guest/admin text search, delegate the query to Worker CMS search with `cms.list(..., { q })` or the equivalent CMS search API. Do not re-apply local substring matching to `q` afterward, because CMS search may return normalized matches such as Traditional/Simplified Chinese variants. Keep local filtering for plugin-only facets such as RSVP status, color tags, custom fields, or per-list/event membership.
- Do not port unrelated legacy admin areas such as contacts, reports, settings, email quality, or HX search unless the event migration explicitly depends on them.
