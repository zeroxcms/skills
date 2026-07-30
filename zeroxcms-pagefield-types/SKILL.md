---
name: zeroxcms-pagefield-types
description: >-
  Add or modify a pagefield type (the admin form control behind a blueprint
  entry like `@score:range` or `body:richtext/md`) in the 0xCMS host at
  workers/cms (or the older frameworks/zeroxcms/cms when explicitly targeted).
  Use whenever a task needs an input control the CMS doesn't have yet — star
  rating, slider/linear scale, file attachment, color, a new picker — or says
  "add a field type", "the editor should show a new control", or "make this
  reusable across plugins". Covers the path-based registry, the field
  view-model contract, the Tailwind rebuild, shared plugin resolution, and the
  CSP rule that forces CSS-only or approved-asset interactivity.
---

# Pagefield types in 0xCMS

Treat `/Users/colin/Documents/code/workers/cms` as the current host source.
Use `/Users/colin/Documents/code/frameworks/zeroxcms/cms` only when the task
explicitly targets the older pre-feature-slice copy.

## The registry is the filesystem

`workers/cms/src/templates/editor.ts` → `pageFieldTemplatePath()`:

```ts
const typedPath = trimmed.includes('/') ? trimmed : `${trimmed}/basic`;
return `/snippets/pagefield/${typedPath}.liquid`;
```

There is **no allowlist of type names**. A blueprint entry's type is mapped
straight to a path, with only a `[A-Za-z0-9_-]+` sanity check on each segment:

| Blueprint entry | Renders |
| --- | --- |
| `@score:range` | `views/snippets/pagefield/range/basic.liquid` |
| `body:richtext/md` | `views/snippets/pagefield/richtext/md.liquid` |
| `@when:date/datetime` | `views/snippets/pagefield/date/datetime.liquid` |

So **adding a type = adding one Liquid file**. No TypeScript change, no
migration, no registration list to update. A missing file means the field
simply doesn't render — fail-soft, no crash.

Existing types: boolean, checkbox, color, date (+datetime, range-tz), email,
file, link, number, page, picture, radio, range, rating, richtext/md, select,
switch, tel, text, textarea, time, url.

## The `field` view-model

Every snippet receives a `field` object. The host's own editor populates it
from the blueprint; a plugin edit view builds it by hand, so a snippet should
treat everything past the core four as optional.

```
field.id           DOM id (host derives it from inputName — keep it unique)
field.inputName    the POST name — @attr / .field|lang / #<i>@attr (see
                   zeroxcms-plugin-edit-view for the grammar)
field.label        human label      field.labelKey    i18n key (wins if set)
field.value        current value    field.required    boolean
field.placeholder / field.placeholderKey
field.options[]    {value,label,selected} for select/radio
field.checked      checkbox state   field.defaultValue
```

Conventional shape (copy `text/basic.liquid` and adapt):

```liquid
<label for="{{ field.id }}" class="min-w-0 block">
  <span class="block text-sm font-medium text-gray-700 mb-1">{% if field.labelKey != blank %}{{ field.labelKey | t }}{% else %}{{ field.label }}{% endif %}{% if field.required %} *{% endif %}</span>
  <input id="{{ field.id }}" type="..." name="{{ field.inputName }}" value="{{ field.value }}"
         class="block min-w-0 w-full max-w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
         {% if field.required %}required{% endif %}>
</label>
```

Use `<fieldset>` + `<legend>` instead of `<label>` when the control is a GROUP
of inputs (radio, range, rating) — one `<label for>` can't own several inputs.

**Design for two callers.** The host passes only the core fields, so derive
sane defaults from what's there and let a richer caller override:

```liquid
{%- assign star_max = field.max | default: 5 -%}
{% if field.stars %}…caller-built list…{% else %}…derived from star_max…{% endif %}
```

## Interactivity: CSS only

The admin runs a **strict nonce CSP**: inline `<script>` bodies are emptied and
`on*` attributes are stripped before insertion. A pagefield snippet therefore
cannot ship its own JS. Two ways out:

1. **Pure CSS.** e.g. the star rating in `rating/basic.liquid`: emit the radios
   in DESCENDING order inside `flex-direction: row-reverse`, then a plain
   sibling rule lights up the chosen star and every lower one:
   ```css
   .rating-stars input:checked ~ label,
   .rating-stars label:hover, .rating-stars label:hover ~ label { color: … }
   ```
   Reversed DOM + row-reverse is what makes `~` (which only sees *following*
   siblings) fill leftward. No JS, full hover feedback.
2. **Reuse an approved core asset.** `views/assets/picture-field.js` is loaded
   by the admin layout and wires anything matching its data-attribute contract
   (`[data-picture-field]`, `[data-picture-url]`, `[data-picture-file]`,
   `[data-picture-preview]`, `[data-picture-status]`). `file/basic.liquid`
   reuses it wholesale and only sets `data-upload-dir="files"` to redirect the
   upload away from `pictures/`. Prefer extending that contract over writing a
   second uploader.

Always keep a no-JS fallback: the file/picture fields leave the URL input
hand-editable, so they stay usable if the asset never loads.

## Custom CSS + the rebuild step

Component CSS lives in `cms/assets-source/admin.css` (alongside
`.richtext-md-preview`). Tailwind scans the host templates, views, and feature
sources through the current build config.

**New classes are not real until you rebuild:**

```bash
npm run build:css     # tailwindcss -i styles/admin.css -o views/assets/admin.css --minify
```

Forget this and the class is simply absent — the control renders unstyled with
no error. Verify with `grep -F ".the-class" views/assets/admin.css`.

This matters doubly for plugins: **plugin admin fragments are styled by the
host's compiled `admin.css`**, so a utility the host never emits is purged and
silently dead inside the plugin too. Adding host snippets that use a class also
makes that class available to every plugin. Use `$0xcms-ui` for the surrounding
admin layout and styling conventions.

## Uploads

`POST /admin/upload` is the host's upload endpoint: `media:upload` permission,
IP rate limit, extension allowlist + MIME consistency + magic-byte sniffing
(`/Users/colin/Documents/code/workers/cms/src/features/media/security.ts`),
canonical content type (never the client's), 25 MB cap, a `media_files` row,
and it returns `/media/<key>` URLs.
Script-capable formats (html, svg, xml) are rejected by design.

It is **admin-only**. A public, unauthenticated surface (a public form, an RSVP
page) must NOT call it — implement upload separately against your own bucket
and mirror the validation posture (see the form plugin's `src/uploads.ts`).

## Checklist for a new type

1. `views/snippets/pagefield/<type>/basic.liquid`, `field`-contract shaped.
2. Any component CSS into `styles/admin.css`, then `npm run build:css`.
3. Group controls → `<fieldset>/<legend>`; interactivity → CSS or an existing
   approved asset, never inline JS.
4. Sensible defaults so a bare blueprint entry (`@x:<type>`) works.
5. `npm run type-check && npm test` in the current `workers/cms` host (snippets
   are covered by the view tests; a broken Liquid tag fails there).
