---
name: zeroxcms-public-site
description: >-
  Build a NEW public-facing website Worker that renders pages published by 0xCMS
  (worker-cms) — a marketing/brand site, a company site, a landing site with a
  news section. Use whenever a task says "new website on the CMS", "site that
  reads the published DB", "render CMS pages on our own domain", or starts a
  fresh repo next to worker-web / worker-rsvp. Also use when ADDING a content
  block, page type, or language to such a site. Covers the scaffold, the
  published-DB read contract, the page_types/block_types seed that gives editors
  the admin UI, the lect→view-model→Liquid section pipeline, and the traps that
  cost the most time (liquidjs asset roots, <details> as a nav, richtext storing
  HTML, PII rows sharing live_pages). NOT for the CMS admin itself (see
  zeroxcms-ui) or for plugin Workers (see zeroxcms-plugin-api).
---

# A new public site on 0xCMS

## What you are building

A standalone Worker on its own domain that only ever **reads** what the CMS
publishes. The CMS owns authoring; the site owns presentation.

```
worker-cms ──publish──▶ cms-published (D1) ──read──▶ your Worker ──HTML──▶ visitor
                        live_pages
                        live_page_tags / live_tags
```

Three existing implementations, in order of how much you should copy:

| Repo | What to take from it |
| --- | --- |
| `projects/colorholicstyling/www` | The **closest template for a brand site**: Liquid sections, block registry, page/block-type seed, multilingual URL prefixes |
| `workers/worker-web` | The generic reader: `data/published.ts`, `data/schedule.ts`, `security/http.ts` |
| `workers/worker-rsvp` | The Liquid-over-assets view system (`src/templates/liquid.ts`), the R2 media proxy, `safeHtml` |

## Step 1 — pick the rendering shape

- **Liquid views** (worker-rsvp / colorholic): each content block is one
  `views/sections/<type>.liquid`. Take this for anything design-driven — it is
  the difference between "add a block" being three small edits or a TS rewrite.
- **TS renderers** (worker-web): a generic walk over the lect. Take this only
  for an internal/utility reader where layout barely matters.

The rest of this skill assumes Liquid.

## Step 2 — scaffold

`wrangler.toml` — the four bindings that matter, and one deliberate omission:

```toml
[assets]                    # Liquid templates + the stylesheet
directory = "./views"
binding = "VIEWS"
run_worker_first = true     # so raw .liquid files are NEVER served publicly

[[d1_databases]]            # the SAME db worker-cms publishes to
binding = "PUBLISHED_DB"
database_name = "cms-published"
database_id = "<the real one>"
# NO migrations_dir — worker-cms owns this schema; never let this Worker migrate it

[[r2_buckets]]              # picture fields store /media/<key> URLs
binding = "MEDIA_BUCKET"
bucket_name = "worker-cms-media"

[version_metadata]
binding = "CF_VERSION_METADATA"
```

`package.json`: one runtime dep (`liquidjs`). **Pin
`@cloudflare/workers-types` to the major that current `wrangler` peer-depends
on** (v5 at time of writing) or `npm install` dies with `ERESOLVE`.

Copy `migrations/published/0001_published_schema.sql` from worker-web (its copy
adds `live_tags`) purely to bootstrap `wrangler dev --local` and tests.

## Step 3 — the read layer (security-critical)

One module owns D1 and issues nothing but parameterized `SELECT`s. Copy
colorholic's `src/published.ts` and change the allowlist.

**`live_pages` is shared.** worker-rsvp writes `rsvp_response` /
`rsvp_registration` rows there, and the events plugin auto-publishes `guest` /
`mail_list` / `edm` / `label` pages. All of them carry PII.

> Filter with an **allowlist** of your own page types, never a denylist of
> known-private ones. worker-web uses a denylist for legacy reasons; a new site
> must not, or the next plugin's type leaks onto the public web by default.

```ts
const PUBLIC_TYPES = ['home', 'page', 'news'] as const;
```

A singleton like `site_settings` stays **out** of that list: it is read by one
dedicated function and has no URL.

## Step 4 — the content model (this is the real deliverable)

Page types and block types are rows in the **CMS admin DB (`cms`)**, not the
published one — `page_types` / `block_types`, converted to blueprint fragments
by `src/utils/page-type-store.ts` / `block-type-store.ts`. Ship them as a seed
file so editors get the admin UI:

```bash
npx wrangler d1 execute cms --remote --file=./seed/cms-content-types.sql
```

Write every statement as `INSERT … ON CONFLICT(slug) DO UPDATE` so re-running is
safe, and validate it before shipping against a throwaway copy of the schema:

```bash
sqlite3 /tmp/t.db < cms/migrations/0001_initial_schema.sql
sqlite3 /tmp/t.db < seed/cms-content-types.sql   # twice — prove idempotency
```

Blueprint grammar (worker-cms `src/utils/lect.ts`):

| Entry | Stored as | Read with |
| --- | --- | --- |
| `"@theme:select"` | `lect.theme` — one value, **not translated** | `attr(lect,'theme')` |
| `"title:text"` | `lect.title = {en:…, "zh-hant":…}` | `localized(lect,'title',chain)` |
| `"*event"` | `lect._pointers.event` | `pointer(lect,'event')` |
| `"link__label:text"` | `lect.link.label` (nested — `__` is a path) | `localized(lect.link,'label',chain)` |
| `{"rows":["name:text","@n:number"]}` | `lect.rows[]` — `@` works inside rows | `items(lect,'rows')` |

The `:type` suffix picks the admin control only
(`views/snippets/pagefield/<type>/…`); it never changes storage. `richtext/md`
**stores HTML**, not markdown — sanitise, do not parse.

`block_lists` on a page type decides which blocks that type offers in the editor.

A workable starting set of blocks, all sharing `@anchor` / `@theme` / `@align`
plus `eyebrow` / `title` / `body`:

`hero` · `rich-text` · `media-text` · `features` · `services` · `steps` ·
`gallery` · `testimonials` · `stats` · `faq` · `team` · `logos` · `contact` ·
`cta` · `news-list` · `divider`

## Step 5 — the block pipeline

lect → view model → template. Adding a block is **three coordinated edits**:

1. `seed/cms-content-types.sql` — a `block_types` row (what editors fill in).
2. `src/blocks.ts` — the type in `BLOCK_TYPES` + a `case` in `blockViewModel()`.
3. `views/sections/<type>.liquid` — markup, plus CSS.

Dispatch dynamically instead of a 16-arm `case` in Liquid, but only from a
validated type:

```ts
if (model) models.push({ ...model, template: `/sections/${model.type}` });
```
```liquid
{% for section in sections %}{% render section.template, block: section %}{% endfor %}
```

The `BLOCK_TYPES` allowlist is what keeps an editor-supplied `_type` out of a
file path. Say so in a comment at both ends.

## Step 6 — the escaping rule

Templates escape everything with `| escape`. **The only exception is a
view-model key ending in `Html`**, which holds rich text already through
`safeHtml()`. Make that the written convention; it plus the strict CSP is the
stored-XSS boundary. Also normalise editor URLs (`safeUrl`) so `javascript:` and
`data:` collapse to `""` and the link simply is not rendered.

## Step 7 — multilingual routing

First code in the `LANGUAGES` var is the default and owns unprefixed URLs;
others live under `/<code>/…`. Resolve the language by splitting the first path
segment, then read every field through a **fallback chain**
(`requested → site default → other configured → mis → en`) so a partly
translated page renders text instead of blanks. `mis` is the CMS's "language
unspecified" default — never emit it as `<html lang>`.

## Traps

- **liquidjs asset roots.** The worker-rsvp `fs` adapter's `resolve()` prefixes
  only `sections/` and `snippets/`, so multi-root lookups 404-probe (one wasted
  subrequest per miss, per render) and `{% layout %}` never resolves at all. In
  a new site use `root: ['/']` and reference partials by full path
  (`{% render '/sections/hero' %}`, `{% layout '/layout/default' %}`).
- **`<details>` cannot be a desktop nav.** A closed `<details>` hides every
  non-`<summary>` child no matter what CSS you put on it, so the menu vanishes
  above the mobile breakpoint. Use a hidden checkbox + `<label>` +
  `:checked ~ .site-nav`. Keep it CSS-only: a scripted toggle would force
  `'unsafe-inline'` into the CSP for the whole site. `<details>` is still right
  for FAQ accordions.
- **Media 404s.** Picture fields store `/media/<key>`, which only resolves if you
  proxy R2 yourself. Copy worker-rsvp `src/media.ts`: its own
  `default-src 'none'; sandbox` header, and force-download anything that is not
  a safely-inlineable image/video/audio (an uploaded SVG must never execute on
  your origin).
- **Stylesheet caching.** One same-origin CSS file served with a long
  `max-age` will not refresh on deploy. Append
  `?v={CF_VERSION_METADATA.id.slice(0,8)}`, falling back to `Date.now()` when
  version metadata is absent so local edits show up on reload.
- **Anchor links in the nav.** `/#services` shares its path with `/`, so naive
  active-matching lights up every anchor item at once. Treat a link carrying a
  fragment as never-current.
- **Scheduling.** `start`/`end` are wall-clock times in the page's `timezone`
  (offset or IANA). A page outside its window must be indistinguishable from a
  missing one — 404, never a hint. For news, let `start` double as the publish
  date so scheduling and dating are one action.

## Verify before claiming done

```bash
npm run typecheck && npm run test
npm run db:setup:local && npm run dev
for p in / /en /news /en/news /<slug> /news/<future-post> /nope /sitemap.xml /robots.txt /assets/site.css; do
  printf '%-28s %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' localhost:8787$p)"
done
curl -sI localhost:8787/ | grep -i 'content-security\|x-frame\|strict-transport'
```

The scheduled-future post must 404 and must be absent from the sitemap. Then
look at it: screenshot the home page, and check geometry in the browser rather
than by eye —

```js
document.documentElement.scrollWidth > innerWidth            // horizontal overflow
[...document.querySelectorAll('main > *')].map(e => [e.className, e.offsetHeight])
```

Seed dev content that exercises **every** block type at least once, in every
language, so `wrangler dev --local` alone proves the whole pipeline.
