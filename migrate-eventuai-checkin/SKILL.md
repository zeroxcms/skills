---
name: migrate-eventuai-checkin
description: Migrate legacy Eventuai check-in routes, controllers, models, QR/RFID/session/plus-guest flows, kiosk views, and Liquid templates into the cms-plugin-checkin Cloudflare Worker plugin. Use when comparing legacy check-in files from /Users/colin/Documents/code/projects/eventuai/checkin/application and /Users/colin/Documents/code/projects/eventuai/checkin/views with the cms-plugin-checkin routes, TypeScript handlers, manifest, tests, or plugin views in /Users/colin/Documents/code/workers/cms-plugin-checkin.
---

# Migrate Eventuai Check-in

## Sources

Use these source roots unless the user gives newer paths:

- Legacy application: `/Users/colin/Documents/code/projects/eventuai/checkin/application`
- Legacy views: `/Users/colin/Documents/code/projects/eventuai/checkin/views`
- Target plugin: `/Users/colin/Documents/code/workers/cms-plugin-checkin`

Read `references/route-comparison.md` before planning a route migration. Refresh it from source if route files have changed.

## Workflow

1. Re-read the current files before editing. Start with legacy `application/routes.mjs`, then the relevant `classes/controller/Home.mjs` action, model/helper files, and Liquid templates. In the plugin, read `src/index.ts`, `src/admin.ts`, `src/public.ts`, `src/checkin-actions.ts`, `src/cms.ts`, `src/manifest.json`, and the matching `views/` templates.
2. Compare behavior before copying route shape. The legacy app is a standalone Express-style check-in site; the plugin splits CMS-session-gated admin routes under `/__plugin/admin` from own-domain public/kiosk routes under `/kiosk/*` and `/checkin/*`.
3. Preserve plugin boundaries. Admin links render through `/admin/plugins/checkin`; Worker admin requests enter at `/__plugin/admin`; public kiosk pages and direct QR links live on the check-in Worker's own origin. Do not add check-in-only content types unless the user explicitly changes the data model.
4. Preserve the target data model. Events, mail lists, guests, and labels are CMS pages defined by cms-plugin-events. This plugin reads and writes `event`, `mail_list`, `guest`, and `label` pages through `CmsClient`, `lect` attributes, and `_pointers`; it does not use the legacy per-mail-list SQLite `Lead` databases.
5. Migrate one route family at a time. Keep check-in domain logic in `src/checkin-actions.ts`, request routing in `src/public.ts` or `src/admin.ts`, CMS-shape helpers in `src/cms.ts`, and Liquid rendering in `views/templates` or `views/sections`.
6. Validate with focused tests or local smoke checks. Prefer existing npm tests, and add narrow tests when changing QR compatibility, check-in message parsing, session/plus-guest undo behavior, search, walk-in guest creation, RFID/barcode matching, permissions, or CMS update payloads.

## Useful Searches

Use these as starting points:

```bash
rg -n "RouteList.add" /Users/colin/Documents/code/projects/eventuai/checkin/application/routes.mjs
rg -n "async action_|generateCheckinQRCodeText|verifyEAISignature|getCheckinSessions|saveBase64Image" /Users/colin/Documents/code/projects/eventuai/checkin/application/classes/controller/Home.mjs
rg -n "class Lead|LeadState|LeadTag|LeadType|HelperHash" /Users/colin/Documents/code/projects/eventuai/checkin/application/classes
rg -n "handleCheckinAdmin|handlePublicCheckin|handleKiosk|handleDirectCheckin|performGuestAction" /Users/colin/Documents/code/workers/cms-plugin-checkin/src
rg -n "formatMainMessage|formatPlusMessage|formatSessionMessage|parseCheckinEntry|findGuestByCode|createWalkInGuest|saveRfid" /Users/colin/Documents/code/workers/cms-plugin-checkin/src/checkin-actions.ts
rg -n "kiosk|guest-search|checkin-confirm|dashboard|event-dashboard" /Users/colin/Documents/code/workers/cms-plugin-checkin/views
```

## Migration Notes

- Treat legacy `Lead` records as target `guest` pages. Guest-list membership is the guest page parent plus `_pointers.mail_list`; event membership comes from the parent mail list's `_pointers.event`.
- Treat legacy `rsvp`/mail-list concepts as target `mail_list` pages. Walk-in guests should go to the CMS Events plugin's auto-managed `Adhoc` list when available.
- Keep direct QR links compatible with cms-plugin-events' minted `/checkin/{listId}/{guestId}[/{index}]/{sig}` links. Legacy `EAI...` QR parsing belongs only in scanner compatibility work and should be covered by tests if reintroduced.
- The legacy app stored session check-ins in a separate `session_checkin` item block. The current plugin encodes main, plus-guest, and session check-ins in `guest.lect.checkin[].message` so cms-plugin-events' guest summaries continue to work without a new blueprint.
- The legacy app stores RFID in `original.attributes.rfid`; the current plugin reuses the guest `barcode` attribute and matches scans against `qrcode` or `barcode`.
- Search behavior differs by surface. Admin plugin search currently searches within one list; public kiosk search scans every mail list on the event. Preserve that split unless the user explicitly asks for a global admin search.
- Do not port legacy login/session pages directly. CMS-authenticated staff use host plugin auth and permissions; public kiosk access uses the event `checkin_lite_passcode` and signed kiosk cookie.
- Do not port legacy ImageFly, standalone auth, local filesystem image upload, or old SQLite database wiring unless a migration task explicitly depends on them.
