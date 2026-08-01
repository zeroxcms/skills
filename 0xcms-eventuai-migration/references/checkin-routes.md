# Eventuai Check-in Route Comparison

Use this reference to choose the target surface for each legacy check-in behavior. Refresh it from source before a migration if `application/routes.mjs`, `classes/controller/Home.mjs`, or target plugin routing changed.

## Legacy Sources

- Routes: `/Users/colin/Documents/code/projects/eventuai/checkin/application/routes.mjs`
- Main controller: `/Users/colin/Documents/code/projects/eventuai/checkin/application/classes/controller/Home.mjs`
- Legacy views: `/Users/colin/Documents/code/projects/eventuai/checkin/views`

## Target Sources

- Worker entry/admin dispatch: `/Users/colin/Documents/code/workers/cms-plugin-checkin/src/index.ts`
- CMS admin surface: `/Users/colin/Documents/code/workers/cms-plugin-checkin/src/admin.ts`
- Public kiosk/direct QR surface: `/Users/colin/Documents/code/workers/cms-plugin-checkin/src/public.ts`
- Domain logic: `/Users/colin/Documents/code/workers/cms-plugin-checkin/src/checkin-actions.ts`
- CMS data helpers: `/Users/colin/Documents/code/workers/cms-plugin-checkin/src/cms.ts`
- Views: `/Users/colin/Documents/code/workers/cms-plugin-checkin/views`

## Route Families

| Legacy route/action | Current or intended plugin surface | Notes |
| --- | --- | --- |
| `GET /` -> `action_index` | Admin `dashboard` in `src/admin.ts`; public `/kiosk/:eventId` starts at passcode/scan | Legacy auto-selected current events. Plugin admin lists events; kiosk is explicit per event. |
| `GET /check-in`, `/events/:event_id/check-in` -> `action_check_in` | Public `/kiosk/:eventId/scan` and `/kiosk/:eventId/search` | Legacy template combined scanner and search. Plugin splits scan/search templates. |
| `GET /events/:event_id/scan` -> `action_scan` | Public `handleScan` in `src/public.ts` | Legacy parses native `EAI...` codes and scans every mail-list SQLite DB. Plugin resolves cms-plugin-events direct links separately and scans guest `qrcode`/`barcode` across event lists. |
| `POST /events/:event_id/guest-search` -> `action_guest_search` | Public `handleSearch` across event lists; admin `guestSearch` within one list | Preserve surface-specific scope. Extend `searchGuests` if legacy plus-guest/custom-field matching is required. |
| `POST /events/:event_id/custom-field-search` -> `action_custom_field_search` | Not yet first-class in plugin | Add only when requested; validate field names and search CMS guest lect/latest-response shape deliberately. |
| `GET /events/:event_id/guest-lists` -> `action_guest_list` | Admin `eventDashboard`; public kiosk navigation | Plugin currently has lighter list summaries. Port legacy confirmed/declined/plus/session totals into `src/cms.ts` or `src/checkin-actions.ts` if needed. |
| `GET /events/:event_id/guest-lists/:mail_list_id` -> `action_guest_list_details` | Admin `guestSearch` or a future list-detail view | Current plugin has search results, not the full legacy guest-list-detail screen. |
| `GET /events/:event_id/guest-lists/:mail_list_id/guests/:guest_id` -> `action_attendee_details` | Public `/kiosk/:eventId/guests/:guestId` -> `renderGuestDetail`; admin search rows | Legacy included profile, registration details, named plus guests, session state, history, RFID, and custom fields. Port missing display data to `renderGuestDetail` plus views. |
| `GET .../check-in`, `.../check-in-main`, `.../check-in-plus`, `.../check-in-session` | Public guest actions in `performGuestAction`; admin `manualCheckin` for main only | Keep check-in mutation helpers in `src/checkin-actions.ts`; add admin route support separately if staff need plus/session controls inside CMS chrome. |
| `GET .../undo-check-in`, `.../undo-main-attendee`, `.../undo-session-check-in`, `.../undo-plus-guests`, `.../undo-plus-guest` | Public guest actions in `performGuestAction`; admin `manualUndo` for main only | Current undo removes most recent matching parsed message. Legacy `undo-check-in` cleared all entries; use `undoAllCheckins` only when that behavior is requested. |
| `GET .../save-rfid` -> `action_save_rfid` | Public guest action `save-rfid` | Plugin stores the tag in guest `barcode`, not legacy `rfid`. |
| `POST .../add-adhoc-guest`, `POST .../guest-lists/add-adhoc-guest` | Public `/kiosk/:eventId/adhoc-guest` -> `handleAdhocGuest` | Current plugin creates a confirmed guest in the existing `Adhoc` list. Legacy could create an adhoc list; plugin should align with cms-plugin-events' `Adhoc` list contract. |
| `GET /settings` -> `action_settings` | Public `/kiosk/:eventId/settings` | Current settings page is kiosk-scoped and minimal. |
| `/imagefly/*` | Do not port by default | Legacy image resizing/static media concern, outside check-in plugin core. |
| `/login`, `/logout` | Do not port by default | CMS plugin auth and kiosk passcode replace legacy standalone auth. |

## Data Shape Mapping

| Legacy concept | Target plugin concept |
| --- | --- |
| `Lead` rows in `/mail-lists/{id}/lead.sqlite` | CMS `guest` pages parented under `mail_list` pages |
| `ModelPage` page type `event` | CMS `event` pages from cms-plugin-events |
| Legacy mail list / RSVP page | CMS `mail_list` page with `_pointers.event` |
| `original.attributes.plus_guests` | `guest.lect.plus_guests` |
| `original.items.checkin[]` | `guest.lect.checkin[]` |
| `original.items.session_checkin[]` | Encoded `guest.lect.checkin[].message` with `session {id} "{name}" checked-in from kiosk` |
| `original.attributes.rfid` | `guest.lect.barcode` |
| `original.attributes.latest_response.rsvp-custom-*` | CMS guest lect/custom response fields; inspect actual migrated data before relying on a shape |
| Legacy `EAI{rsvpCode}:{guestCode}:{plus}:{sig}` scanner codes | Direct links minted by cms-plugin-events plus optional scanner compatibility in `findGuestByCodeInEvent`/QR parsing |

## View Mapping

| Legacy template area | Target plugin views |
| --- | --- |
| `templates/event-list.json`, `sections/event-list/*` | `views/templates/dashboard.json`, `views/sections/dashboard.liquid` |
| `templates/guest-list.json`, `sections/guest-list/*` | `views/templates/event-dashboard.json`, `views/sections/event-dashboard.liquid` |
| `templates/guest-list-details.json`, `sections/guest-list-details/*` | No exact current equivalent; likely admin list-detail/search enhancement |
| `templates/check-in.json`, `sections/check-in/*` | `views/templates/kiosk-scan.liquid`, `views/templates/kiosk-search.liquid` |
| `templates/attendee-details.json`, `sections/attendee-details/*` | `views/templates/kiosk-guest.liquid`, `views/templates/checkin-confirm.liquid` |
| `templates/settings.json`, `sections/settings/*` | `views/templates/kiosk-settings.liquid` |

## Compatibility Hotspots

- QR compatibility: legacy `generateCheckinQRCodeText` signs `qrcode{rsvpId}{leadId}{plus}` and encodes IDs in base32-ish segments. Current direct links use cms-plugin-events HMAC signatures.
- Check-in message parsing: plus/session/main behavior depends on `parseCheckinEntry`. Add tests before changing message formats.
- Headcount summaries: legacy distinguishes main capacity, plus guest counts, unique plus check-ins, confirmed/declined/not-sent totals, and sessions. Current `computeGuestListSummary` is simpler.
- Named plus guests: legacy reads `plus_guest_details`, `plus_guest_names`, and `latest_response` keys. Current plugin mostly uses a numeric cap.
- Adhoc guests: legacy accepts custom fields and optional immediate check-in of main/plus guests. Current plugin only captures basic fields and optionally checks in the main attendee.
- Permissions: legacy event login checks `checkin_require_login`, `users`, creator, and roles. Current admin surface uses CMS plugin permissions; kiosk uses `checkin_lite_passcode`.
