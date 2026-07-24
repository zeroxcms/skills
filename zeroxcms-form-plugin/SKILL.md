---
name: zeroxcms-form-plugin
description: >-
  Work on or debug the 0xCMS form builder (frameworks/zeroxcms/plugin-form) —
  the Google-Forms-style plugin: form pages, the bespoke question editor, the
  public /f/<slug> form, file uploads, and the submissions table / CSV export.
  Use whenever a task touches that repo, mentions the forms admin
  (/admin/plugins/form/...), a form question type (short answer, multiple
  choice, checkboxes, dropdown, linear scale, rating, grids, file upload), the
  public form or its submissions — and ESPECIALLY when an answer "doesn't show
  up", a question renders as a plain text box, or an uploaded file 404s. It
  captures the architecture, the answer-key model that ties editor → public
  form → CSV together, and the traps (localized vs attribute fields, grid row
  keys, multi-value joining, upload key scoping).
---

# 0xCMS form builder (plugin-form)

## Architecture

One Worker, two faces — the events-suite blueprint applied to forms:

- **Admin** `/__plugin/admin/*`, proxied by the host from
  `/admin/plugins/form/*`, returns client-view fragments wrapped in the admin
  chrome: form index, per-form dashboard (share link, open/close, question
  summary, recent submissions), submissions table, CSV export, delete.
- **Editor** `/__plugin/edit` — the manifest declares `editViews: ["form"]`, so
  the CMS hands the page editor for `form` pages to this plugin. See
  zeroxcms-plugin-edit-view for the contract; this plugin is its reference
  implementation.
- **Public** `/f/<slug-or-id>` on the Worker's own domain — reads the published
  D1 (`live_pages`) only, and stores submits as INSERT-only `form_submission`
  rows with NEGATIVE ids (the worker-rsvp "Option B" contract). worker-cms
  ingests them into draft on a cron / on "Pull new submissions" and fires
  `submission` hooks. The public path NEVER calls the Plugin API.

### File map (`src/`)

| File | Role |
| --- | --- |
| `fields.ts` | **the model** — question types, VM projection, answer keys, answer columns, validation. Editor, public form and CSV all read from here. |
| `edit-view.ts` | builds the editor VM (CMS field-name grammar) |
| `forms.ts` | admin routes, submissions table, CSV, delete, file download |
| `public.ts` | public render + submit |
| `uploads.ts` | upload validation + R2 storage + key scoping |
| `submissions.ts` | the INSERT-only published-DB row |
| `published.ts` | published-D1 reader (SELECTs only) |
| `cms.ts` | Plugin API client (acting user, ingest, deleteChildren) |

Views: `views/sections/form-edit.liquid` (the editor),
`views/templates/public-form.liquid` (the public form).

## The data model

A form is a CMS page (`page_type: form`) whose `_blocks` ARE the form:

| Block | Purpose |
| --- | --- |
| `form-contact` | submitter name + email (email optionally required) |
| `form-inputs` | a question list — `custom_input` items |
| `paragraph` / `picture` | static content between questions |

One `custom_input` item = one question:

```
@name @type @required @min @max @accept @max_size    ← config (attributes)
label default_value rows min_label max_label         ← text (localized values)
```

`default_value` holds the OPTIONS (one per line, `value:label`, legacy `|`
also parsed); for grids it holds the COLUMNS and `rows` holds the row labels.

**This split is load-bearing.** Text a respondent reads is a localized value so
it can be translated; config is a plain attribute. Mixing them up is silent —
`attr()` on a localized field yields `"[object Object]"`, and `localized()` on
an attribute yields the right thing only by luck. See zeroxcms-plugin-edit-view.

## Answer keys — the contract between all three surfaces

| Question type | Field name(s) | Stored answer |
| --- | --- | --- |
| single-value (text, radio, select, scale, rating, date, file, …) | `form-<slug>` | the value |
| `checkboxes` (multi-select) | `form-<slug>` posted repeatedly | values joined with `", "` |
| `grid-radio` / `grid-checkbox` | **one field per ROW**: `form-<slug>__<row-slug>` | per-row value (joined for checkbox grids) |
| contact block | `contact-name`, `contact-email` | lifted to the row's `name`/`email` |

`<slug>` comes from the question's explicit `@name` when set, else from its
label — so setting `@name` makes answers survive label edits and translation.

Consequences you must respect:
- `collectAnswers()` iterates **unique keys with `getAll()`**, not `entries()` —
  using `entries()` would keep only the last checked box.
- `answerColumns()` expands a grid into one column PER ROW. A grid can never be
  one column; anything building headers must go through this function.
- `missingRequiredFields()` treats a required grid as answered only when EVERY
  row has a value.
- Columns for answers whose question was since edited/removed are recovered
  from the stored keys, so historical data stays visible in the table and CSV.

## File uploads

Optional `UPLOADS` R2 binding. Unbound → file questions render **disabled**
with a note and the rest of the form still works (and the form doesn't ask for
a multipart body). Bound:

1. Public POST is `multipart/form-data`; each file is validated against the
   extension allowlist + MIME consistency + magic bytes + size cap
   (`uploads.ts`, mirroring the host's `security/media.ts`; html/svg/xml are
   absent by design), tightened further by the question's `@accept` /
   `@max_size`.
2. Stored at `form-<formId>/<uuid>-<safeName>`; the **R2 key is the answer**.
3. **Never served publicly.** The only path back is
   `/admin/plugins/form/forms/<id>/files/<key>` — reachable only through the
   authenticated host admin — which checks `keyBelongsToForm()` before serving,
   so a crafted key can't reach another form's attachments, and sends
   `nosniff` + `attachment`.
4. A rejected file leaves the answer UNSET, so `required` still bites; CSV
   exports the original filename, never the storage key.

## Debugging

- **A question renders as a plain text box** → its `@type` isn't in
  `QUESTION_TYPES` (`fields.ts`); `normalizeType()` falls back to `text` for
  unknown/legacy values. Check spelling, and that the editor's dropdown and the
  public template's `{% case %}` both know the type.
- **An answer is missing from the table/CSV but visible in the row's JSON** →
  the column name doesn't match the answer key. Grid answers live under
  `form-x__row`, not `form-x`; go through `answerColumns()`.
- **Only the last checkbox of a multi-select is stored** → something is reading
  `form.entries()`/`get()` instead of `getAll()`.
- **Editor field looks empty after switching language** → it's a localized
  field being read with `attr()`, or vice-versa (see the model split above).
  Editors intentionally use exact-language reads, showing the default
  language's text as a *placeholder* only.
- **Question config disappears after changing a question's type** → the
  editor must post hidden inputs for the panels it isn't showing; the CMS save
  handler writes exactly what it receives.
- **Uploaded file 404s in the admin** → `UPLOADS` unbound, or the key isn't
  under this form's `form-<id>/` prefix (that check is deliberate).
- **"Submission missing" right after a public submit** → it's in the published
  DB but not yet mirrored into draft. The dashboard calls `ingestSubmissions()`
  best-effort on every visit; "Pull new submissions" sweeps it explicitly.
  Nothing is lost — ingest is idempotent by uuid.
- Host publish/unpublish/trash REFUSE submission page types, and the whole
  submission-storage contract is shared with the events plugin — see
  cms-events-plugin's "Public submission storage" section.

## Conventions

- Add/remove/reorder questions are **server round-trips** through the CMS save
  handler; the only JS is the approved `editor-scroll.js` (scroll restore +
  drag reorder), which must be re-approved under Plugins → form → assets after
  any deploy that changes its bytes (cms-plugin-js-assets).
- New form pages seed a contact block + one sample question, then open the
  editor. `form` is in `autoPublishTypes`, so saving publishes and the public
  link works immediately.
- Deleting a form trashes its submissions server-side via
  `cms.deleteChildren()` (`DELETE /__cms/pages/children`) before removing the
  form — never `batchRemove` a whole child collection.
- Public styling is self-contained in `public-form.liquid` (inline `<style>`,
  no framework); admin fragments are host-subset Tailwind (cms-plugin-tailwind).

## Testing

`test/index.test.ts` drives the Worker directly: a stubbed global `fetch`
standing in for `{CMS_URL}/__cms/*`, a fake `PUBLISHED_DB` (prepare/bind/first/
run) and a fake R2 bucket. Admin responses are re-rendered through `renderView`
so assertions run against real HTML. Assert on **field names and answer keys** —
they're the contract. `npx tsc --noEmit && npm test` from the plugin directory
(watch the shell's cwd — it is easy to typecheck the host by mistake).
