---
name: zeroxcms-form-plugin
description: >-
  Work on or debug the split 0xCMS form system under frameworks/zeroxcms:
  plugin-form is the authenticated Google-Forms-style CMS builder/admin, while
  worker-form is the public form renderer and INSERT-only submission writer.
  Use for form page blocks, custom question types, editor field names, answer
  keys, public validation, published-D1 submissions, ingestion, CSV/admin
  tables, file uploads/downloads, auto-publish, or bugs where answers
  disappear, grids flatten incorrectly, uploads fail, or public and admin
  behavior drift.
---

# 0xCMS Form Builder and Public Worker

## Architecture

The form product is two Workers sharing published D1 and, optionally, an
attachment bucket. They never call each other.

```text
plugin-form -> CMS draft page -> publish -> PUBLISHED_DB -> worker-form
     ^                               ^                         |
     |                               +--- INSERT submission ---+
     +--------- host ingest mirrors submission to draft -------+
```

- Admin/builder:
  `/Users/colin/Documents/code/frameworks/zeroxcms/plugin-form`
- Public renderer/submission writer:
  `/Users/colin/Documents/code/frameworks/zeroxcms/worker-form`
- Current host ingest/publish contract:
  `/Users/colin/Documents/code/workers/cms`

Do not reintroduce public routes into `plugin-form`, and do not give
`worker-form` a CMS secret or Plugin API client.

## File map

Admin plugin:

| File | Role |
| --- | --- |
| `src/fields.ts` | Question model, editor projection, answer keys/columns |
| `src/edit-view.ts` | Bespoke form page editor using CMS field names |
| `src/forms.ts` | Dashboards, pull, submissions, CSV, delete, downloads |
| `src/uploads.ts` | Admin-side attachment key/name checks |
| `src/cms.ts` | SDK wrapper for live status, ingest, and children delete |
| `src/index.ts` | Tenant auth, manifest/views/hooks/edit/admin routing |

Public Worker:

| File | Role |
| --- | --- |
| `src/fields.ts` | Public projection mirroring the admin question contract |
| `src/form.ts` | GET/POST render, validation, answer collection |
| `src/published.ts` | Parameterized form reads from `live_pages` |
| `src/submissions.ts` | INSERT-only `form_submission` rows |
| `src/uploads.ts` | Public upload validation and R2 writes |
| `src/media.ts` | Safe published media proxy |

Views are `plugin-form/views/sections/form-edit.liquid` and
`worker-form/views/templates/public-*.liquid`.

## Form model

A form is a CMS `form` page whose `_blocks` define the form:

| Block | Purpose |
| --- | --- |
| `form-contact` | Submitter name/email |
| `form-inputs` | `custom_input` questions |
| `paragraph`, `picture` | Static content |

One question uses attributes for machine config and localized values for text:

```text
@name @type @required @min @max @accept @max_size
label default_value rows min_label max_label
```

Keep this split consistent in the manifest, edit view, both `fields.ts`
projections, and public templates. In editors, read exact-language values and
use the default language only as a placeholder.

## Answer-key contract

Admin columns and public storage must derive the same keys:

| Question | Posted/stored key |
| --- | --- |
| Single value | `form-<question-slug>` |
| Checkboxes | repeated `form-<slug>`, joined with `", "` |
| Grid row | `form-<slug>__<row-slug>` |
| Contact | `contact-name`, `contact-email`, lifted into submission attrs |

Use explicit `@name` when answers must survive label edits/translations.

- Collect multi-values with `FormData.getAll()`.
- Expand grids to one answer column per row.
- Require every row for a required grid.
- Recover columns from historical stored keys when questions were changed or
  removed.
- Keep the admin and public implementations in step; test both when changing
  slugs, question normalization, options, grids, or required rules.

## Public submission boundary

`worker-form`:

- Reads only published `form` pages from `PUBLISHED_DB`.
- Writes only new `form_submission` rows with negative IDs and fresh UUIDs.
- Never updates/deletes CMS-minted rows.
- Has no `migrations_dir`; Worker CMS owns the published schema.
- Redirects successful POSTs to `?thank-you=1`.

Worker CMS ingests live-only submissions into draft on its scheduled pass or
`POST /__cms/ingest/submissions`, then fires the form plugin's `submission`
hook. The admin only reads mirrored draft submissions.

Current host `src/core/db/submission-ingest.ts` copies the published row's raw
`lect` string verbatim into draft and its first version. It does **not** project
through the plugin's `form_submission` blueprint. Therefore:

- `lect.answers` does not need a manifest `@answers` entry;
- adding one is not a fix for a missing grid answer;
- if the live row has an answer but the mirrored draft row does not, inspect
  the deployed host/version and D1 bindings rather than the blueprint.

Keep ingestion idempotent by UUID. A submission missing from the admin
immediately after POST may simply be waiting for ingest; the dashboard and
"Pull new submissions" trigger bounded sweeps. When debugging, compare the
same UUID's live and draft `lect`, then check `submissionAnswers()` and
`submissionColumns()` in the admin plugin.

## Publishing

A new form must be explicitly published once. `autoPublishTypes: ["form"]`
only republishes a page that is already live after later saves.

The plugin edit view asks `GET /pages/:id?include_live_status=1` and renders the
host's Publish or Unpublish action. It must not implement publishing itself.

## File uploads

`worker-form` owns public validation and writes. `plugin-form` owns authenticated
downloads.

1. Validate extension, MIME consistency, magic bytes, and size. Reject
   script-capable formats.
2. Apply the question's `@accept` and `@max_size`.
3. Store under `form-<formId>/<uuid>-<safeName>` in `UPLOADS`.
4. Store the R2 key as the answer.
5. Never serve attachments publicly.
6. Download only through
   `/admin/plugins/form/forms/<id>/files/<key>`, after
   `keyBelongsToForm()` checks the prefix; force `attachment` and `nosniff`.

Bind the same `UPLOADS` bucket to both Workers. Without it, public file
questions are disabled while the rest of the form remains usable.

## Common failures

- Plain text control: unknown `@type` fell back to `text`; update both field
  projections, editor choices, public Liquid cases, and tests.
- Missing checkbox values: code used `get()`/`entries()` instead of `getAll()`.
- Missing grid columns: code looked for `form-x` rather than row keys.
- Empty translation: attribute/localized shape or exact-language read is wrong.
- Config disappears after a type switch: hidden inputs for inactive panels
  were omitted from the editor POST.
- Upload 404: buckets differ or the answer key is outside `form-<id>/`.
- Public 404: the form has never been published or was unpublished.
- New deploy's editor JS does not run: the changed asset needs re-approval in
  the host.

## Verification

Run both suites:

```bash
cd /Users/colin/Documents/code/frameworks/zeroxcms/plugin-form
npm run typecheck
npm test

cd /Users/colin/Documents/code/frameworks/zeroxcms/worker-form
npm run typecheck
npm test
```

Assert on field names and answer keys, not only surrounding HTML. Cover the
full path for every changed question type: editor model, public render,
validation/storage, admin table, and CSV.
