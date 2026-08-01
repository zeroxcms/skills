# Double-submit protection

## Why this exists

2026-07-16: "Create event" at `/admin/pages/new?page_type=event` was clicked
twice while the worker cold-started → two events created. Every mutation button
in the host admin and the plugin fragments had the same exposure.

## The client guard (host layout — covers everything)

`views/layout/default.liquid` has a **delegated, document-level submit guard**
(look for `// Double-submit guard`). Because plugin admin fragments (events,
checkin, contacts, event-action, …) are client-rendered INTO the host shell,
this one handler covers the host's own forms AND every chrome-wrapped plugin
form. Plugins need no per-plugin JS asset — and so no approval pipeline — for
basic protection.

Behavior on first real submit:

- one tick later (`setTimeout 0`): sets `data-submit-guard="1"` + `aria-busy` on
  the form, disables every button in `form.elements` (including buttons outside
  the form associated via `form="id"`), stamps them
  `data-submit-guard-disabled`, styles cursor:wait / opacity .65.
- repeat submits while guarded (Enter key, `requestSubmit()`, another click) are
  `preventDefault`ed by the synchronous attribute check.
- `pageshow` with `event.persisted` (bfcache) releases the guard and re-enables
  ONLY the buttons it disabled.

## The server layer: single-use `_cms_once` tokens

The client guard can't stop a browser resubmit dialog, a network-level retry, or
two POSTs racing a slow worker. The host also enforces a single-use token on
plugin admin POSTs — plugins do nothing.

Implementation: `src/core/auth/form-once.ts` + `src/core/durable-objects/form-once.ts`
(feature-sliced) or `src/utils/form-once.ts` (monolithic). Claims are held in a
**sharded Durable Object** (`FormOnceDO`, `FORM_ONCE` namespace), not a D1 table.

- `buildBaseProps()` mints a signed page token (HMAC with JWT_SECRET, TTL,
  stateless on GET) into `cmsOnce`; the guard IIFE in `default.liquid`
  interpolates it (`'{{ cmsOnce }}'` — head metas do NOT survive
  `replaceDocument()`, which only swaps body, hence the interpolation).
- At first submit the guard **synchronously** stamps
  `<input type=hidden name=_cms_once value="<pageToken>:<random suffix>">`. Sync
  add is safe — the entry list is built after the submit event; only *disabling*
  must be deferred. Skipped for `data-allow-resubmit` forms and when
  `event.defaultPrevented` is already true (kiosk fetch forms) — those
  legitimately re-submit and must not share one dedupe key.
- `proxyToPlugin()` (`src/features/plugins/routes/admin-proxy.ts` or
  `src/routes/admin/plugins.ts`) extracts the field from urlencoded/multipart
  bodies and claims it. Duplicate → flash redirect back to the referring page,
  never forwarded to the plugin. The claim is **released** when the plugin
  returns ≥500 or the fetch/queue path throws, so retries after failures aren't
  misread as duplicates. Missing or unverifiable tokens pass through — this is
  soft enforcement, dedupe not auth.
- `pageshow` (bfcache) removes stamped inputs: back-button + resubmit is a
  deliberate new submission and gets a fresh suffix.
- Host-form POSTs (pages, users, …) carry the token but are NOT yet enforced —
  only the plugin proxy claims it. `claimFormOnceToken` is ready to reuse for
  host routes.
- Tests: `test/form-once.test.ts` (unit) and the `_cms_once` cases in
  `test/plugins.test.ts` (proxy integration).

## The two rules that make it correct (don't "simplify" them away)

1. **Never disable the submitter synchronously in a submit handler.** The
   browser builds the POST entry list AFTER the submit event finishes; a
   submitter disabled during dispatch is DROPPED from the body. Concrete bug
   this caused: the archive form's `action=apply|skip` — the server defaults a
   missing `action` to `apply`, so "Archive only (no merge)" would run a full
   merge. Always defer the disable one tick; the sync `preventDefault` attribute
   check is what actually blocks the double submit.
2. **Check `event.defaultPrevented` inside the deferred tick.** Forms whose
   scripts intercept submit with `preventDefault()` + `fetch` (the check-in
   kiosk forms in `cms-plugin-checkin/views/assets/js/kiosk.js`) must stay
   enabled and repeat-submittable — the guard must not engage on them.

Ordering note: the host's `data-confirm` handler runs first (capture phase,
`stopImmediatePropagation` on cancel), so a cancelled confirm never reaches the
guard and the form stays usable.

## Escape hatches

- `data-allow-resubmit` on a `<form>` → guard skips it entirely. For any form
  that legitimately submits repeatedly without navigating (e.g. a POST returning
  a file download — the page never reloads, so the guard would freeze it
  forever). As of 2026-07-16 no such form exists: all exports/print are GET
  links or JS `type="button"` flows.
- `data-stop-continue` on a button/link → never disabled. Used by the
  import/delete/archive progress pages, where "Stop" must stay clickable while
  an auto-continuing pass is in flight.
- `data-autosubmit` controls call `form.submit()`, which fires no submit event —
  they bypass the guard (and `data-confirm`) by design.

## Relationship to long-running-submit.js (events plugin)

`cms-plugin-events/views/assets/long-running-submit.js` is the OPT-IN heavyweight
variant for `form[data-long-running-form]` (import/confirm/delete/archive/
progress views): it freezes ALL buttons and links on the page (not just the
form's) and swaps the submitter for a spinner with `data-loading-label`. It uses
its own `data-submitting` flag, also defers its disable one tick (same rule 1),
and unlocks itself if the submit was defaultPrevented. The host guard runs
alongside it harmlessly.

It is a plugin JS asset → any byte change requires **re-approval** after deploy
(see `0xcms-plugin-api` → `references/js-assets.md`). The host-layout guard has
no such step — it ships with the host.

## When adding a new mutation form

| Situation | What to do |
|---|---|
| Normal navigate-on-POST form | Nothing — the guard covers it |
| Long/slow multi-pass action (events plugin) | `data-long-running-form` + `data-loading-label` on the submitter |
| Fetch-intercepted form (no navigation) | Fine as-is if your script calls `preventDefault()` synchronously |
| POSTs a download / stays on the page without preventDefault | `data-allow-resubmit` (double-click protection is then on you) |
| Buttons that must survive the freeze | `data-stop-continue` |

## Mutation-button inventory (snapshot, 2026-07-16 — re-check before relying on it)

- **Host** (`views/sections/`): editor Create/Save + publish/unpublish/
  restore-version/delete, page-type-form, block-type-form, tag-form,
  taxonomy-form, role-form, user-form, plugin-form (Save/Approve/Re-approve/
  Rotate secret), plugin-credits, plugin-limits, menu-settings, trash
  (Restore/Empty), users (invite).
- **cms-plugin-events**: event-new, guest-list-form, edm-form, label-form,
  adhoc-checkin, guest-list-contacts, event-registrations, import flows
  (Preview/Confirm/Continue/Assign new IDs), edm-edit (Add block/row/Send test),
  guest-table Send/Re-send, guest-list Auto Send, event-archive
  (Merge&archive/Archive-only), guest-dedupe, event-delete.
- **cms-plugin-checkin**: kiosk-scan + event-dashboard "Add & check in" (both
  fetch-intercepted by kiosk.js → guard intentionally inert), check-in/undo.
- **cms-plugin-contacts**: contact-import Preview, contact-import-preview Apply.

## Verifying changes to the guard

Harness pattern (no dev stack needed): a tiny node server with a ~6s `/slow`
POST endpoint plus a page embedding the guard script extracted from
`default.liquid` and `long-running-submit.js` verbatim; drive it in the browser
pane. Assert: (a) double-click + `requestSubmit()` → exactly ONE request logged,
(b) the submitter's `name=value` is present in the body, (c) a
preventDefault+fetch form stays enabled and submits repeatedly.
