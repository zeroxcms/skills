# Host-subset Tailwind: class map & patterns

Ready-made utility strings for the common admin-UI pieces, using only classes the
host CMS typically emits. Always confirm with `scripts/check_classes.py` against
the specific host `admin.css` — the available set varies with what the host's own
views use. The strings below match the host's own view vocabulary (cards, tables,
buttons styled the same way the host admin styles them), which is why they're
both present in the compiled CSS and visually consistent.

## Layout / page chrome

| Piece | Utilities |
|---|---|
| Page wrapper | `max-w-5xl mx-auto px-4 py-5` |
| Page header row | `flex items-center justify-between gap-4 mb-4` |
| Back link (`<a>`) | `inline-block text-xs text-gray-500 mb-1 hover:text-indigo-700` |
| H1 | `text-2xl font-bold text-gray-900` |
| H2 | `text-lg font-bold text-gray-900` |
| Subtitle / muted `<p>` | `mt-1 text-sm text-gray-500` |
| Action button row | `flex flex-wrap gap-2` |

Note: `items-start` is often purged — use `items-center` (the only reliably
present align utility) or omit. Headings need no `m-0`; preflight zeroes them.

## Card

- Plain card: `bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden`
- Padded content card: `bg-white rounded-xl shadow-sm border border-gray-200 p-6`
- Card wrapping a wide table: swap `overflow-hidden` → `overflow-x-auto`

## Table (descendant selectors are gone — annotate every cell)

```html
<div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-x-auto">
  <table class="w-full text-left text-sm">
    <thead class="bg-gray-50 border-b border-gray-200">
      <tr>
        <th class="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Name</th>
        <th class="px-6 py-3"></th> <!-- empty/action header: padding only -->
      </tr>
    </thead>
    <tbody class="divide-y divide-gray-100">
      <tr>
        <td class="px-6 py-3 text-sm text-gray-700">
          <a class="text-indigo-600 font-medium hover:text-indigo-800" href="…">…</a>
        </td>
        <td class="px-6 py-3 text-right">…</td> <!-- right-aligned action cell -->
      </tr>
      <!-- empty state -->
      <tr><td colspan="N" class="px-6 py-10 text-center text-sm text-gray-400">No rows yet.</td></tr>
    </tbody>
  </table>
</div>
```

`divide-y divide-gray-100` on `<tbody>` replaces per-row `border-top` and avoids
needing a `border-collapse` utility (often absent).

## Buttons (links or `<button>`)

Base: `inline-block px-4 py-2 rounded-lg text-sm font-semibold border border-transparent`
(add `cursor-pointer` on `<button>`).

| Variant | Append |
|---|---|
| Primary | `bg-indigo-600 text-white hover:bg-indigo-700` |
| Secondary | `bg-white text-gray-700 border-gray-300 hover:bg-gray-50` |
| Danger | `bg-red-600 text-white hover:bg-red-700` |
| Bare text button | `border-0 bg-transparent p-0 text-xs font-semibold text-indigo-600 cursor-pointer` |

## Forms

| Piece | Utilities |
|---|---|
| Field label (block) | `block mb-3` |
| Field label inside a flex grid | `block mb-3 flex-1 min-w-[10rem]` |
| Label caption `<span>` | `block text-sm text-gray-700 mb-1` |
| Input / select / textarea | `block w-full px-3 py-2 border border-gray-300 rounded-lg text-sm` |
| "Form grid" container | `flex flex-wrap gap-3` (children get `flex-1 min-w-[10rem]`) |
| Inline form row | `flex flex-wrap items-center gap-1.5` |

`min-w-[10rem]` is an arbitrary value — verify it's emitted; if not, drop it or
pick a present one. Preflight gives `box-sizing: border-box`, so no `box-border`.

## Small bits

| Piece | Utilities |
|---|---|
| Badge / pill | `inline-block px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-700` |
| Stat tile | `border border-gray-200 rounded-lg p-3 text-center` |
| Inline `<code>` chip | `bg-gray-100 px-1 py-0.5 rounded text-xs font-mono` |
| Code/SVG textarea | add `font-mono`; control height with `rows="…"`, not `min-h-[…]` |

## Standard substitutions for usually-purged classes

| You want | Often purged | Use instead |
|---|---|---|
| 3/6-col responsive grid | `grid-cols-3`, `grid-cols-6`, `sm:grid-cols-6` | `grid grid-cols-2 sm:grid-cols-3` |
| Fraction width | `w-1/3`, `w-1/2`, `w-1/6` | a present fixed `w-*`, or flex `flex-1` |
| Top-align flex | `items-start` | `items-center` or omit |
| No underline | `no-underline` | nothing (preflight already removes it) |
| Border box | `box-border` | nothing (preflight sets it globally) |
| Tall min-height | `min-h-[18rem]` | `rows="N"` on textarea, or inline `style` |
| One-off max-width | `max-w-[54rem]` etc. | nearest present `max-w-*`, or inline `style="max-width:54rem"` |

Inline `style` for arbitrary one-off measurements is acceptable — the host CSP
permits `style-src 'self' 'unsafe-inline'`. Reserve it for true one-offs; use
utilities for everything with a present equivalent.
