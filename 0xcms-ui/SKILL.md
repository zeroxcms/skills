---
name: 0xcms-ui
description: 0xCMS admin UI conventions for Cloudflare Worker CMS and plugins. Use when editing 0xCMS/CMS admin Liquid views, shared reusable snippets such as the color tag picker, templates, or plugin-rendered edit, create/new, read, or client-rendered views that involve list headers, action buttons, mobile button labels, responsive spacing, scrollable or paginated tables, edit-form action footers, or visual consistency between CMS core views and plugin views such as events and contacts.
---

# 0xCMS UI

Use this skill to preserve the established 0xCMS admin interface patterns while editing CMS core and plugin views. Prefer matching the existing good view over inventing a new local variation.

Treat `/Users/colin/Documents/code/workers/cms` as the current host source.
Use `/Users/colin/Documents/code/frameworks/zeroxcms/cms` only when the task
explicitly targets the older pre-feature-slice copy.

## Core Workflow

1. Identify the closest good existing view before editing. Common references:
   - Events list: `/admin/plugins/events/events` for list headers with the primary action on the right.
   - Page edit: `/admin/pages/:id/edit` for edit-form action button position and styling.
   - Page new: `/admin/pages/new?page_type=<type>` for create-form layout and plugin `newViews` behavior.
   - Event dashboard guest lists: `/admin/plugins/events/events/:id` for a card heading that stays visible while only the table scrolls horizontally.
   - Profile credit ledger: `/admin/profile` for the standard table-pagination footer.
   - Worker CMS content wrapper: `px-4 py-5 sm:px-6 sm:py-8 lg:px-8`.
2. Search for sibling views with the same pattern and update them together when the user asks for consistency.
3. Keep changes surgical. Preserve route behavior, permissions, labels, and existing data bindings unless the user asked for behavior changes.
4. Verify with the relevant type check:
   - `cms`: `npm run type-check`
   - `cms-plugin-events`: `npm run typecheck`
   - Other plugins: use the package's existing typecheck script if present.

## Page Wrappers

For CMS admin sections and plugin-rendered sections, use the standard content wrapper unless the parent renderer already supplies it:

```html
<div class="px-4 py-5 sm:px-6 sm:py-8 lg:px-8">
  ...
</div>
```

When a plugin view is rendered client-side inside the CMS shell, ensure the plugin content receives the same wrapper spacing as Worker CMS views.

## List Headers

Use a compact single-row header with the title on the left and primary actions on the right:

```html
<div class="flex items-center justify-between gap-4 mb-4">
  <div>
    <h1 class="text-2xl font-bold text-gray-900">Title</h1>
    <p class="mt-1 text-sm text-gray-500">Optional description.</p>
  </div>
  <a class="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 text-sm font-semibold text-white hover:bg-indigo-700">
    ...
  </a>
</div>
```

Apply this to list/admin index views such as taxonomies, page types, block types, tags, roles, plugins, and similar plugin sections. Avoid reverting to `flex-col ... sm:flex-row` for headers when the requested pattern is the Events list layout.

## Buttons

Use icon plus text for action buttons, with text hidden on mobile:

```html
<a title="New page" aria-label="New page" class="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 text-sm font-semibold text-white hover:bg-indigo-700">
  <svg class="h-4 w-4" ...></svg>
  <span class="hidden lg:inline">New page</span>
</a>
```

Use an icon-only button for search/filter submit buttons when space matters:

```html
<button title="Search" aria-label="Search" class="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-50">
  <svg class="h-4 w-4" ...></svg>
</button>
```

Button rules:
- Keep primary create actions right-aligned in the header.
- Use `title` and `aria-label` whenever visible text may be hidden.
- Keep button height at `h-10`.
- Use `gap-2` for icon+text actions.
- Use existing icon sprites or icon conventions in the file; do not introduce a new icon system for one button.
- Use `hidden lg:inline` for labels that should disappear on mobile.

## Shared Plugin Snippets

Prefer shared CMS snippets over plugin-local copies when the control is common across plugins.

### Pagefield Renderers

Common plugin form fields should use Worker CMS pagefield snippets under
`/Users/colin/Documents/code/workers/cms/views/snippets/pagefield/<type>/<variant>.liquid`.
Field view models should set `templateName` to the shared snippet path, and
plugin Liquid views should render it directly:

```liquid
{% render field.templateName, field: field %}
```

Do not add plugin-local wrapper snippets such as `render-field`/`editor-field`, and do not guard on blank `templateName`; a missing template should fail visibly so the field resolver or shared snippet can be fixed.

For client-rendered plugin views, redirect `/snippets/pagefield/...` lookups to the CMS host views. When moving a bespoke plugin field into core CMS, add the missing CMS pagefield snippet first, preserve the field contract (`value`, `required`, `options`, `checked`, etc. as applicable), update the plugin resolver to emit the shared `templateName`, then remove the plugin-local duplicate.

### Color Tag Picker

Use the CMS snippet at `/Users/colin/Documents/code/workers/cms/views/snippets/color-tag-picker.liquid` for guest/contact/event color labels. Call it from plugin Liquid views like this:

```liquid
{% render "color-tag-picker",
  value: item.color_tag,
  action: item.colorAction,
  returnTo: item.returnTo,
  label: "Color tag"
%}
```

Keep this UI contract:
- The trigger is a borderless `h-7 w-7` swatch. The menu opens as a horizontal panel to the right, vertically centered (`left-5 top-1/2 -translate-y-1/2`) with slight overlap so hover/focus stays connected.
- Do not put the picker inside a clipped table cell. Truncate inner text nodes instead of the parent cell, and use `items-center` when the picker sits beside name/email text.
- Color variables and the empty-state dashed dot live in
  `cms/assets-source/admin.css`; rebuild `cms/views/assets/admin.css` with
  `npm run build:css` after style or utility-class changes.
- Behavior lives in `cms/views/assets/color-tag.js`; keep
  `data-color-tag-*` attributes intact so AJAX submit updates the swatch and
  nearby `data-filter-color` rows.

For client-rendered plugin views, redirect Liquid lookup aliases to the shared CMS snippet instead of copying the snippet into the plugin. Liquid may request any of these paths: `/color-tag-picker.liquid`, `/sections/color-tag-picker.liquid`, or `/snippets/color-tag-picker.liquid`.

```ts
if ([
  '/color-tag-picker.liquid',
  '/snippets/color-tag-picker.liquid',
  '/sections/color-tag-picker.liquid',
].includes(viewPath)) {
  return redirect(`/admin/views/snippets/color-tag-picker.liquid${url.search}`);
}
```

Add a regression test for the alias paths and run the plugin tests plus the relevant typecheck.

## Scrollable Tables

If a card has its own heading/actions above a table, keep the card header outside the scroll container and wrap only the table:

```html
<div class="bg-white rounded-xl shadow-sm border border-gray-200 mt-4">
  <div class="flex items-center justify-between gap-4" style="padding:1rem 1rem 0;margin-bottom:.75rem">
    <div>
      <h2 class="text-lg font-bold text-gray-900">Section</h2>
      <p class="mt-1 text-sm text-gray-500">Description.</p>
    </div>
  </div>
  <div class="overflow-x-auto w-full">
    <table class="w-full min-w-[560px] text-left">
      ...
    </table>
  </div>
</div>
```

For a simple table-only card, `overflow-x-auto` on the card is acceptable:

```html
<div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-x-auto">
  <table class="w-full min-w-[560px] text-left">...</table>
</div>
```

Use `min-w-[560px]` for ordinary tables and a larger minimum only when the columns genuinely need it.

## Table Pagination

Match the Profile credit ledger at `/admin/profile` and the Pages list at `/admin/pages/list`. Keep pagination outside the table's `overflow-x-auto` container so its controls remain visible while the table scrolls.

Use this footer layout:

- Put a localized `Showing {from}-{to} of {total}` summary on the left.
- Put Previous, `Page {page} of {pageCount}`, and Next controls on the right.
- Use `flex flex-wrap items-center justify-between gap-3` so the summary and controls wrap cleanly on narrow screens.
- Separate the footer from the table with `border-t border-gray-100 pt-4`; use `mt-4` when the table does not already provide spacing.
- Render unavailable Previous/Next controls as non-interactive `<span>` elements instead of hiding them. This preserves alignment and makes the disabled state clear.
- Use `h-9`, `px-3`, `text-xs`, and `font-semibold` for navigation controls. Put a `h-3.5 w-3.5` left arrow before Previous and a right chevron after Next.
- Preserve active filters, searches, and other query parameters in pagination links.
- Apply Liquid `| t` to every visible label. Use `common.previous` and `common.next` for navigation and the section's localized keys for Showing, Page, and of.
- Show the pagination footer only when navigation is useful, normally when `pageCount > 1`. Do not add first/last controls unless the workflow specifically needs them.

Use these state styles:

```liquid
{% if pagination.hasPrevious %}
  <a href="{{ pagination.previousHref }}"
     class="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 text-xs font-semibold text-gray-700 hover:bg-gray-50">
    <svg class="h-3.5 w-3.5" aria-hidden="true"><use href="{{ iconHrefPrefix }}#arrow-left"></use></svg>
    {{ "common.previous" | t }}
  </a>
{% else %}
  <span class="inline-flex h-9 cursor-not-allowed items-center justify-center gap-1.5 rounded-lg border border-gray-200 bg-gray-50 px-3 text-xs font-semibold text-gray-400">
    <svg class="h-3.5 w-3.5" aria-hidden="true"><use href="{{ iconHrefPrefix }}#arrow-left"></use></svg>
    {{ "common.previous" | t }}
  </span>
{% endif %}
```

Mirror the same enabled/disabled treatment for Next, placing its chevron after the label. Place the localized page indicator between both controls with `text-xs font-medium text-gray-500`.

## Edit Form Actions

For edit/create forms, match the Page edit footer pattern:
- Keep Save/Cancel together as the primary action group.
- Keep destructive actions such as Delete visually separate and consistently styled.
- Use the same button height, border radius, font weight, and color treatment as page edit.
- Do not allow action footers to drift into page-specific layouts unless the view has a real workflow difference.

### Preserve Scroll During Structural Edits

Preserve the current vertical scroll position when an edit-form action reloads
the same page to add or remove structured content. Match the Worker CMS editor
contract in
`/Users/colin/Documents/code/workers/cms/views/sections/editor.liquid`:

- Mark the main edit form with `data-editor-form`.
- Store the scroll offset in `sessionStorage` under `cms-editor-scroll:<pathname>` before actions whose value prefix is `block-add`, `block-delete`, `item-add`, `item-delete`, `block-item-add`, or `block-item-delete`.
- On the next load, remove the stored value and restore it with `requestAnimationFrame` plus `window.scrollTo`.
- Detect the action from the submit event's `submitter`; do not preserve scroll for ordinary Save, Publish, or Delete submissions.
- Remember that plugin-rendered edit views do not inherit the script inside the built-in editor section. Reuse an existing approved plugin editor-scroll asset, or add an external asset with the same contract, declare it in the plugin manifest, and load it from the edit view. Do not add inline JavaScript to plugin fragments.
- Add regression coverage for the form marker, approved asset declaration and inclusion, structured action prefixes, and the pathname-scoped storage key.

## Plugin Page Views

Plugin-owned page views use one rendering contract but separate manifest keys:
- `editViews`: existing-page edit forms at `/admin/pages/:id/edit`.
- `newViews`: create/new forms at `/admin/pages/new?page_type=<type>`.
- `readViews`: read-only views at `/admin/pages/:id/read`.

For `newViews`, keep the plugin endpoint as `/__plugin/edit`; the CMS sends `mode: "new"`, `action: "/admin/pages"`, an empty page id, and the same editor context shape as edit views. Preserve the normal CMS create handler rather than adding plugin-local save logic. Keep the `?native=1` / `?editor=cms` escape hatch behavior intact.

When adding or changing plugin page-view behavior:
- Prefer explicit `newViews` for create-only overrides.
- Preserve backwards compatibility where `editViews` still owns the new form unless a plugin declares `newViews` for that page type.
- Add regression coverage for create-only, edit-only, and fallback-to-built-in behavior when the ownership distinction changes.
- Keep plugin-rendered create/edit forms visually aligned with the Page edit footer and standard CMS wrapper spacing.

## Review Checklist

Before finishing, scan the touched area for sibling views with the same UI pattern:
- Core CMS: taxonomies, page types, block types, tags, roles, users, plugins, pages, trash.
- Events plugin: events, event dashboard sections, guest lists, guests, sessions, labels, EDM templates, imports.
- Contacts plugin: contact lists, contact records, imports, settings.

Then verify:
- Primary action is on the right.
- Mobile button labels are hidden where space matters.
- Search/filter submits are icon-only when requested.
- Card headings do not horizontally scroll away from their tables.
- Paginated tables use the range summary, stable disabled controls, page indicator, localized labels, and navigation links that preserve active query parameters.
- Pagination controls stay outside the horizontally scrollable table container.
- Plugin content padding matches Worker CMS content padding.
- Plugin create/new view overrides use `newViews` and still post to the CMS create action.
- Type checks pass or any unrelated failures are reported clearly.
