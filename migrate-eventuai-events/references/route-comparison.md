# Eventuai Event Route Comparison

This snapshot was built from:

- Legacy routes: `/Users/colin/Documents/code/projects/eventuai/admin/application/routes.mjs`
- Legacy event views: `/Users/colin/Documents/code/projects/eventuai/admin/views/templates/admin/page/page_types/event/*`
- Target plugin routes: `/Users/colin/Documents/code/workers/cms-plugin-events/src/index.ts`
- Target delegated handlers: `src/rsvp.ts`, `src/edm.ts`, `src/labels.ts`, `src/public-rsvp.ts`
- Target manifest and views: `src/manifest.json`, `views/`

Refresh this file when either route table changes.

## Target Plugin Route Model

The Worker exposes plugin infrastructure routes directly:

- `/__plugin/manifest`
- `/__plugin/views/*`
- `/__plugin/hooks/*`
- `/__plugin/edit` POST, currently for the EDM edit view
- `/__plugin/admin/*`, mapped to user-facing links under `/admin/plugins/events`

Public guest routes currently live at the Worker origin:

- `/rsvp/:eventId/:listId/:guestId/:signature`
- `/:language/rsvp/:eventId/:listId/:guestId/:signature`
- `/rsvp/thank-you`
- `/qr?data=...&sig=...`
- `/sign?data=...`

## Route Family Map

| Legacy route family | Current plugin equivalent | Main target files | Notes |
| --- | --- | --- | --- |
| `addPageRoutes('events', 'controller/admin/Event')` plus generic create/list/import/search/new/update/delete/block/item routes | `/admin/plugins/events/events`, CMS page editor links such as `/admin/pages/:id/edit?return_to=...` | `src/index.ts`, `src/manifest.json`, `views/sections/events.liquid` | The plugin should not recreate all generic CRUD routes. Use CMS page editor and the event blueprint unless a custom workflow is required. |
| `/admin/events/adhoc-checkin/:id` GET/POST and `/admin/events/adhoc-checkin/:event_id/:lead_id...` | `/admin/plugins/events/events/:eventId/adhoc-checkin` GET/POST | `src/index.ts`, `src/rsvp.ts`, `views/sections/adhoc-checkin.liquid` | Current plugin creates or reuses an `Adhoc` mail list, then creates a confirmed checked-in guest. RFID success JSON is not currently mirrored. |
| `/admin/events/reorder-guest-lists` and `/admin/events/reorder-sessions` | `/admin/plugins/events/events/:eventId/reorder-guest-lists` POST and `/admin/plugins/events/events/:eventId/reorder-sessions` POST | `src/index.ts`, `src/rsvp.ts` | Plugin scopes reorder routes by event id instead of using only POST body context. |
| `/admin/events/:id/add/mail_list`, `/admin/events/:id/import/guest-lists`, `/admin/events/:id/export/guest-lists`, `/admin/events/:id/all-guests` | `/events/:eventId/lists`, `/rsvp/new?event_id=...`, `/events/:eventId/import`, `/events/:eventId/export`, `/events/:eventId/all-guests` under `/admin/plugins/events` | `src/index.ts`, `src/rsvp.ts`, `views/templates/guest-lists.json`, `views/templates/event-import.json`, `views/templates/all-guests.json` | Legacy guest-list import/export names differ from plugin route names, but the intent is present. |
| `/admin/events/:id/archive` | No direct current plugin equivalent | To decide | Legacy archive views exist in the admin source. Add only if archive behavior is required for the plugin migration. |
| `/admin/events/label/:event_id...`, `/admin/events/label-token/:rsvp_id/:lead_id.json`, `/admin/events/:id/save-label-template`, `/admin/events/:id/load-label-template.json` | `/events/:eventId/labels`, `/events/:eventId/labels/new`, `/events/:eventId/labels/:labelId`, `/events/:eventId/labels/:labelId/preview` under `/admin/plugins/events` | `src/index.ts`, `src/labels.ts`, `views/templates/labels.json`, `views/templates/label-form.json` | Current plugin stores label templates as `label` pages under the event. Legacy label-token and save/load-template JSON routes are not one-for-one. |
| `addPageRoutes('rsvp', 'controller/admin/RSVP')` | `/admin/plugins/events/rsvp`, `/admin/plugins/events/rsvp/new`, `/admin/plugins/events/rsvp/:listId` | `src/rsvp.ts`, `views/templates/guest-lists.json`, `views/templates/guest-list.json` | In the plugin, legacy RSVP pages mostly become `mail_list` pages. |
| `/admin/rsvp/:id/send/:lead_id`, `/preview/:lead_id`, `/assign-status/:lead_id/:status.json`, `/toggle-not-send/:lead_id.json`, `/update-from-contact/:lead_id`, `/update-all-from-contacts` | `/rsvp/:listId/guests/:guestId/send` POST, `/preview`, `/status` POST, `/update-from-contact` POST, `/rsvp/:listId/update-from-contacts` POST under `/admin/plugins/events` | `src/rsvp.ts`, `src/edm.ts`, `views/templates/guest-form.json`, `views/templates/guest-qr.json` | Legacy `lead_id` maps to plugin `guestId`. Assign-color, assign-custom-field, and custom-field-values do not have direct routes yet. |
| `/admin/rsvp/:id/add-contacts`, `/remove-contacts`, `/remove-contacts-csv`, `/add`, `/import-v2/:id`, `/import-accept/:id/:file`, `/export/:id` | `/rsvp/:listId/guests/new`, `/rsvp/:listId/import`, `/rsvp/:listId/import/confirm`, `/rsvp/:listId/export` under `/admin/plugins/events` | `src/rsvp.ts`, `views/templates/guest-import.json`, `views/templates/guest-import-preview.json` | Contact-backed import/update behavior should be checked against legacy controller details before widening. |
| `/admin/rsvp/:rsvp_id/edit/:id`, `/update/:id`, `/delete/:id`, `/move/:id`, `/qrcode/:id`, `/checkin/:id`, primary guest JSON routes | `/rsvp/:listId/guests/:guestId`, `/delete`, `/move`, `/qrcode`, `/checkin` under `/admin/plugins/events` | `src/rsvp.ts` | Primary guest routes are not currently mirrored. Guest edit is a plugin form, not the generic CMS editor. |
| `addPageRoutes('edm', 'controller/admin/Edm')`, `/admin/events/:event_id/add/edm`, `/admin/events/:id/duplicate/edm/:edm_id`, `/admin/edm/preview/:id`, `/admin/edm/html/:id` | `/admin/plugins/events/edm`, `/edm/new?event_id=...`, `/edm/:id/preview`, `/edm/:id/duplicate` POST, `/__plugin/edit` POST | `src/edm.ts`, `views/templates/edm-list.json`, `views/templates/edm-form.json`, `views/sections/edm-edit.liquid` | The plugin routes standalone EDM list/create/preview actions. Editing is delegated to the CMS page editor through the plugin edit view. |
| Legacy EDM send/test/list actions in controller methods rather than obvious route names | `/edm/:id/send-test`, `/edm/:id/assign-list`, `/edm/:id/send-list`, `/rsvp/:listId/send-edm` under `/admin/plugins/events` | `src/edm.ts`, `src/rsvp.ts` | Verify exact legacy behavior in `controller/admin/Edm.mjs` and `controller/admin/RSVP.mjs` before porting email edge cases. |
| `/qrcode/:rsvp_id/:lead_id/:sign.png`, plus plus-one and URL variants | `/qr?data=...&sig=...`; guest admin QR at `/rsvp/:listId/guests/:guestId/qrcode` | `src/index.ts`, `src/rsvp.ts`, `src/qr.ts`, `src/crypto.ts` | The plugin currently uses signed payloads and an SVG QR renderer path. Legacy plus-one QR compatibility is not direct. |
| Public `/rsvp/:event_slug/:edm_id/:view_id/:sign` GET/POST, language-prefixed variants, `/thank-you`, `/preview`, `/new`, `/create` | Public `/rsvp/:eventId/:listId/:guestId/:signature` GET/POST, language-prefixed variants, `/rsvp/thank-you` | `src/public-rsvp.ts`, `src/edm.ts`, `views/templates/public-rsvp.liquid`, `views/templates/public-thank-you.liquid` | This is a major compatibility gap. Decide whether to preserve legacy URL signatures or migrate sent links to the new numeric signed payload. Public self-registration routes are not currently mirrored. |
| `/admin/hx/*`, contact API, contacts, reports, settings, email quality | Mostly out of scope for the events plugin | Usually do not port | Port only the pieces directly required by an event migration task. |

## Data Shape Reminders

- Event: `page_type: "event"`.
- Guest list: `page_type: "mail_list"`, grouped to event by `lect._pointers.event`.
- Guest: `page_type: "guest"`, parented by `page_id` under the mail list, with `lect._pointers.event` and `lect._pointers.mail_list` where needed.
- EDM: `page_type: "edm"`, grouped to event by `lect._pointers.event`.
- Label: `page_type: "label"`, parented under an event.
- RSVP response history uses `lect.response[]`; check-in history uses `lect.checkin[]`.

## First Checks For A New Migration Task

1. Identify whether the requested legacy route is admin-only, public guest-facing, email-rendering, import/export, or CMS editor behavior.
2. Check whether the plugin already has a route with the same intent under `/admin/plugins/events`.
3. If no route exists, decide whether the host CMS editor should own the behavior before adding a Worker route.
4. Read the matching legacy controller method and Liquid views before editing TypeScript.
5. Add or update the target Liquid template JSON and section files together with the handler.
