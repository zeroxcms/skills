---
name: 0xcms-eventuai-migration
description: >-
  Migrate legacy Eventuai behavior into the 0xCMS Worker plugins — admin
  events, RSVP, EDM, guest lists, labels, QR, and public RSVP into
  cms-plugin-events; and check-in routes, controllers, models, QR/RFID/session/
  plus-guest flows, and kiosk views into cms-plugin-checkin. Use when comparing
  legacy routes, controllers, or Liquid views under
  projects/eventuai/{admin,checkin} with the plugin routes, manifests,
  TypeScript handlers, or views in workers/cms-plugin-events and
  workers/cms-plugin-checkin.
---

# Eventuai → 0xCMS plugin migration

Two migration targets share one workflow. Pick the track you need:

| Track | Legacy source | Target plugin | Route table |
| --- | --- | --- | --- |
| **Admin / events** | `projects/eventuai/admin/{application,views}` | `workers/cms-plugin-events` | `references/events-routes.md` |
| **Check-in** | `projects/eventuai/checkin/{application,views}` | `workers/cms-plugin-checkin` | `references/checkin-routes.md` |

Roots are under `/Users/colin/Documents/code/` unless the user gives newer
paths. Read the relevant route table before planning a route migration, and
refresh it from source if the legacy route files have changed.

## Workflow (both tracks)

1. **Re-read the current files before editing.** Start with legacy
   `application/routes.mjs`, then the relevant controller and view templates.
   - Events: plugin `src/index.ts`, the delegated handler module (`src/rsvp.ts`,
     `src/edm.ts`, `src/labels.ts`, `src/public-rsvp.ts`), `src/manifest.json`,
     and the matching `views/` templates.
   - Check-in: legacy `classes/controller/Home.mjs` action, model/helper files,
     and Liquid templates; plugin `src/index.ts`, `src/admin.ts`, `src/public.ts`,
     `src/checkin-actions.ts`, `src/cms.ts`, `src/manifest.json`, `views/`.
2. **Compare route intent before copying route shape.** Legacy
   `addPageRoutes(...)` and `HelperCRUD.add(...)` routes usually map to the CMS
   host page editor plus plugin dashboard links, not one-for-one Worker routes.
   The legacy check-in app is a standalone Express-style site; the plugin splits
   CMS-session-gated admin routes under `/__plugin/admin` from own-domain
   public/kiosk routes under `/kiosk/*` and `/checkin/*`.
3. **Preserve plugin boundaries.** Authenticated plugin admin requests enter the
   Worker at `/__plugin/admin`; user-facing admin links use
   `/admin/plugins/<id>`; page editing enters through `/__plugin/edit`; CMS page
   creation/edit/delete should remain with the host CMS when possible. Public
   kiosk pages and direct QR links live on the check-in Worker's own origin.
4. **Preserve the target data model.** Events are CMS `event` pages. Guest lists
   are `mail_list` pages grouped to events by `lect._pointers.event`. Guests are
   `guest` pages parented under a `mail_list`, with event/list pointers in
   `lect._pointers`. EDMs are `edm` pages grouped by the event pointer. Labels
   are `label` pages parented under an event. cms-plugin-checkin reads and
   writes these through `CmsClient` — it does not use the legacy per-mail-list
   SQLite `Lead` databases, and should not add check-in-only content types
   unless the user explicitly changes the data model.
5. **Migrate one route family at a time.** Keep route handlers small, add or
   update the backing Liquid view, and wire the route into admin navigation only
   after the handler works. For check-in, keep domain logic in
   `src/checkin-actions.ts`, request routing in `src/public.ts` / `src/admin.ts`,
   CMS-shape helpers in `src/cms.ts`, and rendering in `views/`.
6. **Validate with focused tests or local smoke checks.** Prefer existing npm
   scripts. Add narrow tests when a migration changes shared helpers,
   signatures, imports, email rendering, guest state transitions, QR
   compatibility, check-in message parsing, session/plus-guest undo behavior,
   search, walk-in guest creation, RFID/barcode matching, permissions, or CMS
   update payloads.

Bulk work (imports, archives, cascades) must follow the resumable
long-running-operation and batch read/write patterns documented in
`0xcms-events-plugin` — don't re-derive them here.

## Useful searches

```bash
# events
rg -n "RouteList.add|addPageRoutes|HelperCRUD.add" /Users/colin/Documents/code/projects/eventuai/admin/application/routes.mjs
rg -n "class Event|class RSVP|class Edm|class Lead|action_" /Users/colin/Documents/code/projects/eventuai/admin/application/classes/controller
rg -n "handleAdmin|handleRsvpAdmin|handleEdmAdmin|handleLabelsAdmin|handlePublicRsvp" /Users/colin/Documents/code/workers/cms-plugin-events/src
rg -n "ADMIN_BASE|segments\[" /Users/colin/Documents/code/workers/cms-plugin-events/src

# check-in
rg -n "RouteList.add" /Users/colin/Documents/code/projects/eventuai/checkin/application/routes.mjs
rg -n "async action_|generateCheckinQRCodeText|verifyEAISignature|getCheckinSessions|saveBase64Image" /Users/colin/Documents/code/projects/eventuai/checkin/application/classes/controller/Home.mjs
rg -n "class Lead|LeadState|LeadTag|LeadType|HelperHash" /Users/colin/Documents/code/projects/eventuai/checkin/application/classes
rg -n "handleCheckinAdmin|handlePublicCheckin|handleKiosk|handleDirectCheckin|performGuestAction" /Users/colin/Documents/code/workers/cms-plugin-checkin/src
rg -n "formatMainMessage|formatPlusMessage|formatSessionMessage|parseCheckinEntry|findGuestByCode|createWalkInGuest|saveRfid" /Users/colin/Documents/code/workers/cms-plugin-checkin/src/checkin-actions.ts
```

## Migration notes — shared

- Treat legacy `Lead` records as target `guest` pages unless a future migration
  note says otherwise.
- Treat legacy `rsvp` / mail-list concepts as target `mail_list` pages.
- For plugin guest/admin text search, delegate to Worker CMS search with
  `cms.list(..., { q })`. Do **not** re-apply local substring matching to `q`
  afterward — CMS search may return normalized matches such as Traditional/
  Simplified Chinese variants. Keep local filtering for plugin-only facets
  (RSVP status, color tags, custom fields, per-list/event membership).
- Do not port unrelated legacy admin areas — contacts, reports, settings, email
  quality, HX search — unless the migration explicitly depends on them.

## Migration notes — events

- Be cautious with public RSVP URL compatibility. Legacy URLs use `event_slug`,
  `edm_id`, `view_id`, and `sign`; the current plugin uses signed numeric
  `eventId`, `listId`, and `guestId`.

## Migration notes — check-in

- Guest-list membership is the guest page parent plus `_pointers.mail_list`;
  event membership comes from the parent mail list's `_pointers.event`.
- Walk-in guests should go to the events plugin's auto-managed `Adhoc` list when
  available.
- Keep direct QR links compatible with cms-plugin-events' minted
  `/checkin/{listId}/{guestId}[/{index}]/{sig}` links. Legacy `EAI...` QR parsing
  belongs only in scanner-compatibility work and should be covered by tests if
  reintroduced.
- The legacy app stored session check-ins in a separate `session_checkin` item
  block. The current plugin encodes main, plus-guest, and session check-ins in
  `guest.lect.checkin[].message` so the events plugin's guest summaries keep
  working without a new blueprint.
- The legacy app stores RFID in `original.attributes.rfid`; the current plugin
  reuses the guest `barcode` attribute and matches scans against `qrcode` or
  `barcode`.
- Search behavior differs by surface: admin plugin search searches within one
  list; public kiosk search scans every mail list on the event. Preserve that
  split unless the user explicitly asks for a global admin search.
- Do not port legacy login/session pages directly. CMS-authenticated staff use
  host plugin auth and permissions; public kiosk access uses the event
  `checkin_lite_passcode` and a signed kiosk cookie.
- Do not port legacy ImageFly, standalone auth, local filesystem image upload,
  or old SQLite database wiring unless a task explicitly depends on them.
