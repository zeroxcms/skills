---
name: cms-admin-submit-once
description: Double-submit protection for Workers CMS admin forms (host cms + events/checkin/contacts and all chrome-wrapped plugin fragments). Use whenever a form submit could fire twice — "clicked twice, two records created", duplicate events/guests/pages after a slow worker response — or when ADDING any new mutation form/button ("Create X", "Add Y", import/confirm/send flows) to the host admin or a plugin view, so the new form inherits or opts out of the guard correctly. Covers the global submit-once guard in the host layout, the deferred-disable rule (disabling the clicked submitter synchronously drops its name/value from the POST body), the data-allow-resubmit / data-stop-continue escape hatches, and how it interacts with the events plugin's long-running-submit.js spinner.
---

# Double-submit protection in Workers CMS admin

## Why this exists

2026-07-16: "Create event" at `/admin/pages/new?page_type=event` was clicked
twice while the worker cold-started → two events created. Every mutation
button in the host admin and the plugin fragments had the same exposure.

## The guard (host layout — covers everything)

`cms/views/layout/default.liquid` has a **delegated, document-level submit
guard** (look for `// Double-submit guard`). Because plugin admin fragments
(events, checkin, contacts, event-action, …) are client-rendered INTO the host
shell, this one handler covers the host's own forms AND every chrome-wrapped
plugin form. Plugins need no per-plugin JS asset (no approval pipeline) for
basic protection.

Behavior on first real submit:
- one tick later (`setTimeout 0`): sets `data-submit-guard="1"` +
  `aria-busy` on the form, disables every button in `form.elements`
  (includes buttons outside the form associated via `form="id"`), stamps them
  `data-submit-guard-disabled` and styles cursor:wait / opacity .65.
- repeat submits while guarded (Enter key, `requestSubmit()`, another click)
  are `preventDefault`ed by the synchronous attribute check.
- `pageshow` with `event.persisted` (back/forward cache) releases the guard
  and re-enables ONLY the buttons it disabled.

## Server-side layer: single-use `_cms_once` tokens (added 2026-07-16)

The client guard can't stop a browser resubmit dialog, a network-level retry,
or two POSTs racing a slow worker. The host now also enforces a single-use
token on plugin admin POSTs — plugins do nothing:

- `buildBaseProps()` mints a signed page token (`utils/form-once.ts`, HMAC
  with JWT_SECRET, 12h TTL, stateless on GET) into `cmsOnce`; the guard IIFE
  in `default.liquid` interpolates it (`'{{ cmsOnce }}'` — head metas do NOT
  survive `replaceDocument()`, which only swaps body, hence the interpolation).
- At first submit the guard **synchronously** stamps
  `<input type=hidden name=_cms_once value="<pageToken>:<random suffix>">`
  (sync add is safe — the entry list is built after the submit event; only
  *disabling* must be deferred). Skipped for `data-allow-resubmit` forms and
  when `event.defaultPrevented` is already true (kiosk fetch forms) — those
  legitimately re-submit and must not share one dedupe key.
- `proxyToPlugin()` (routes/admin/plugins.ts) extracts the field from
  urlencoded/multipart bodies and claims it in D1 `used_form_tokens`
  (INSERT … ON CONFLICT DO NOTHING RETURNING, migration 0014). Duplicate →
  flash redirect back to the referring page, never forwarded to the plugin.
  Claim is **released** when the plugin returns ≥500 or the fetch/queue path
  throws, so retries after failures aren't misread as duplicates. Missing or
  unverifiable tokens pass through (soft enforcement — dedupe, not auth).
- `pageshow` (bfcache) removes stamped inputs: back-button + resubmit is a
  deliberate new submission and gets a fresh suffix.
- Host-form POSTs (pages, users, …) carry the token too but are NOT yet
  enforced — only the plugin proxy claims it. `claimFormOnceToken` is ready
  to reuse for host routes.
- Tests: `test/form-once.test.ts` (unit) and the two `_cms_once` cases in
  `test/plugins.test.ts` (proxy integration).

## The two rules that make it correct (don't "simplify" them away)

1. **Never disable the submitter synchronously in a submit handler.** The
   browser builds the POST entry list AFTER the submit event finishes; a
   submitter disabled during dispatch is DROPPED from the body. Concrete bug
   this caused: the archive form's `action=apply|skip` — server defaults a
   missing `action` to `apply`, so "Archive only (no merge)" would run a full
   merge. Always defer the disable one tick; the sync `preventDefault`
   attribute check is what actually blocks the double submit.
2. **Check `event.defaultPrevented` inside the deferred tick.** Forms whose
   scripts intercept submit with `preventDefault()` + `fetch` (the check-in
   kiosk forms in `cms-plugin-checkin/views/assets/js/kiosk.js`) must stay
   enabled and repeat-submittable — the guard must not engage on them.

Ordering note: the host's `data-confirm` handler runs first (capture phase,
`stopImmediatePropagation` on cancel), so a cancelled confirm never reaches
the guard — the form stays usable.

## Escape hatches

- `data-allow-resubmit` on a `<form>` → guard skips it entirely. Use for any
  form that legitimately submits repeatedly without navigating (e.g. a POST
  that returns a file download — the page never reloads, so the guard would
  freeze it forever). As of 2026-07-16 no such form exists: all exports/print
  are GET links or JS `type="button"` flows.
- `data-stop-continue` on a button/link → never disabled. Used by the
  import/delete/archive progress pages, where "Stop" must stay clickable
  while an auto-continuing pass is in flight.
- `data-autosubmit` controls call `form.submit()`, which fires no submit
  event — they bypass the guard (and `data-confirm`) by design.

## Relationship to long-running-submit.js (events plugin)

`cms-plugin-events/views/assets/long-running-submit.js` is the OPT-IN
heavyweight variant for `form[data-long-running-form]` (import/confirm/
delete/archive/progress views): it freezes ALL buttons and links on the page
(not just the form's) and swaps the submitter for a spinner with
`data-loading-label`. It uses its own `data-submitting` flag, also defers its
disable one tick (same rule 1), and unlocks itself if the submit was
defaultPrevented. The host guard runs alongside it harmlessly.

It is a plugin JS asset → any byte change requires **re-approval** in
Plugins → events → assets after deploy (see cms-plugin-js-assets skill). The
host-layout guard has no such step — it ships with the host.

## When adding a new mutation form

- Normal navigate-on-POST form: do nothing, the guard covers it.
- Long/slow multi-pass action in the events plugin: add
  `data-long-running-form` (+ `data-loading-label` on the submitter) for the
  spinner UX.
- Form that submits without navigation (fetch-intercepted): fine as-is if
  your script calls `preventDefault()` synchronously; the guard stays out.
- Form that POSTs a download / stays on the page without preventDefault: add
  `data-allow-resubmit` (and accept that double-click protection is on you).
- Buttons that must survive the freeze: `data-stop-continue`.

## Mutation-button inventory (as of 2026-07-16)

Host cms (`views/sections/`): editor.liquid Create/Save + publish/unpublish/
restore-version/delete (the `/admin/pages/new` case above), page-type-form,
block-type-form, tag-form, taxonomy-form, role-form, user-form, plugin-form
(Save/Approve/Re-approve/Rotate secret), plugin-credits (Grant/Send/Donate/
Adjust), plugin-limits, menu-settings, trash (Restore/Empty), users (invite).

cms-plugin-events: event-new "Create event", guest-list-form "Create guest
list", edm-form "Create and edit", label-form "Create label", adhoc-checkin
"Add and check in", guest-list-contacts "Add selected to list",
event-registrations "Pull new submissions"/"Convert to guest", import flows
(Preview/Confirm/Continue/Assign new IDs), edm-edit "Add block"/"Add row"/
"Send test email", guest-table Send/Re-send, guest-list Auto Send,
event-archive Merge&archive/Archive-only, guest-dedupe "Remove duplicates",
event-delete.

cms-plugin-checkin: kiosk-scan + event-dashboard "Add & check in" (both
fetch-intercepted by kiosk.js → guard intentionally inert), check-in/undo
buttons.

cms-plugin-contacts: contact-import "Preview import", contact-import-preview
"Apply import".

## Verifying changes to the guard

Harness pattern (no dev stack needed): a tiny node server with a ~6s `/slow`
POST endpoint + a page embedding the guard script extracted from
`default.liquid` and `long-running-submit.js` verbatim; drive it in the
browser pane. Assert: (a) double-click + `requestSubmit()` → exactly ONE
request logged, (b) the submitter's `name=value` is present in the body,
(c) a preventDefault+fetch form stays enabled and submits repeatedly.
