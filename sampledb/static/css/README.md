# CSS architecture

Samplepedia is styled with **Bootstrap 5.3** (CDN) plus a thin project layer.
Every design decision (colors, fonts, sizes, radii, shadows, motion, dark mode) lives in
**one file: `tokens.css`**. Everything else only references those tokens via `var(--sp-*)`.

To change the look of the site, change `tokens.css`.

## Files and load order

`samples/templates/samples/base.html` loads, in this order:

| # | File | Contains |
|---|------|----------|
| 1 | Bootstrap 5.3 (CDN) | framework |
| 2 | `tokens.css` | **all raw design values**: `:root` (light theme + shared values) and `[data-bs-theme="dark"]` (dark overrides) |
| 3 | `bootstrap-theme.css` | maps tokens onto Bootstrap's own variables (`--bs-*`), per component (`.btn-primary`, `.card`, `.table`, …) |
| 4 | `base.css` | element defaults (headings, links, labels, `hr`) and small utilities (`.text-strong`, `.text-difficulty-*`, `.theme-when-light/dark`, …) |
| 5 | `layout.css` | app shell: navbar, page header, content area, footer |
| 6 | `components.css` | project components: card headers, callouts, badges (difficulty, tags, medals), spoilers, solutions, comments, articles, markdown tabs/panes and the editor page |
| 7 | `forms.css` | project form widgets: SHA256 field, image picker, selected-draft summary |
| 8 | `prose.css` | rendered markdown (`.prose`, `.prose-article`) |
| 9 | `pages/*.css` | page-specific styles, loaded only by their page via `{% block extra_css %}` |
| 10 | highlight.js theme | code highlighting (light/dark stylesheet switched by `js/theme-init.js`) |

Our files win over Bootstrap through **load order at equal specificity**, so they must load after
`bootstrap.min.css`.

## Rules

These are enforced by `samples/tests/test_design_system.py`:

1. **Raw values only in `tokens.css`.** No hex/`rgb()`/`hsl()`/named colors elsewhere, including in
   custom properties such as `--bs-*` overrides (`rgba(var(--sp-brand-rgb), 0.1)` is fine: the color
   comes from a token). `font`, `font-family`, `font-size`, `font-weight`, `line-height`,
   `border-radius`, `box-shadow`, `z-index`, `transition` and `animation` outside `tokens.css` must use
   `var(--sp-*)` (or a keyword such as `0`, `none`, `inherit`).
2. **Every token is defined and used.** A `var(--sp-*)` that `tokens.css` doesn't define fails, and so
   does a token nothing uses. The dark theme only overrides tokens that exist in `:root`.
3. **No `!important`.** Not in CSS files and not in inline styles.
4. **Dark mode = token overrides.** `[data-bs-theme` appears only in `tokens.css` (and in the
   root mapping selector of `bootstrap-theme.css`). Components never have dark-mode rules.
5. **No `<style>` blocks in templates** (the e-mail base template `registration/_email_base.html`
   excepted). Put page CSS in `pages/<page>.css`.
6. **Inline `style=""` only for layout or data**: widths or `--prop: {{ value }}`, in templates and in
   HTML built by JavaScript. Never colors or font sizes. Hide elements with the `hidden` attribute
   (`sp.show()` in `js/utils.js`), not `display: none`; JavaScript never sets design values through
   `element.style`.
7. **Modifiers re-point tokens** instead of restating values, e.g.
   `.prose-article { font-size: var(--sp-fs-article); }`.
8. **No AdminLTE, Bootstrap 4 classes, or jQuery.** Use `bootstrap.Modal.getOrCreateInstance(el)`
   and plain DOM APIs.

## Tokens

- **Primitives** are the palette (`--sp-brand`, `--sp-white`, `--sp-secondary`, …, with `-rgb` triplets
  where Bootstrap utilities need them) and the type, shape, spacing and motion scales.
- **Component tokens** refer to primitives instead of repeating literals:
  `--sp-dropdown-bg: var(--sp-surface-raised)`, `--sp-table-hover: var(--sp-brand-tint)`. A palette
  change then reaches every component, and a component only needs a dark override when its dark
  value differs from what its alias already gives.
- **Naming:** `--sp-on-<color>` is text on a palette color; `--sp-<component>-fg`, `-bg`, `-border` are
  a component's foreground, background and border; `--sp-fs-*`, `--sp-lh-*`, `--sp-fw-*` are font size,
  line height and weight.
- **Breakpoints** can't be tokens (custom properties don't work in media queries). Use Bootstrap's:
  `@media (max-width: 767.98px)` for "below md".

## Theme (light / dark)

- The theme is the `data-bs-theme` attribute on `<html>` (`light` or `dark`).
- `js/theme-init.js` runs in `<head>` before the page renders. It reads `localStorage['samplepedia-theme']`,
  migrates the legacy `adminlte-dark` key, and sets the attribute plus the highlight.js stylesheet.
- `js/theme-toggle.js` flips the theme via `window.spTheme.set()`. The toggle's icon and label switch
  through `.theme-when-light` / `.theme-when-dark` (no JS needed).
- Bootstrap 5.3 components pick up dark mode by themselves. Our tokens redefine the rest.

## How to…

**Change a color, font, or size site-wide** - edit the token in `tokens.css` (both the `:root` value
and, if it differs, the `[data-bs-theme="dark"]` value).

**Restyle a Bootstrap component** - set its component variables in `bootstrap-theme.css`, e.g.

```css
.btn-primary {
  --bs-btn-bg: var(--sp-brand);
  --bs-btn-hover-bg: var(--sp-brand-hover);
}
```

**Change a Bootstrap utility's color** (utilities use `!important`) - re-point the variable the
utility reads instead of overriding it, e.g. `.text-muted` reads `--bs-secondary-color`:

```css
a.text-muted:hover { --bs-secondary-color: var(--sp-brand-hover); }
```

**Add a page-specific stylesheet**

```django
{% block body_class %}page-my-page{% endblock %}
{% block extra_css %}<link rel="stylesheet" href="{% static 'css/pages/my-page.css' %}">{% endblock %}
```

The file is only loaded by that page; scope rules under `.page-my-page` where a selector could
also match shared markup.

**Add or change a difficulty level** - add the level to `Difficulty` in `samples/models.py`,
`--sp-difficulty-<level>` to `tokens.css` and a `.badge-difficulty-<level>` rule to
`components.css`. `samples/design_tokens.py` reads the color from `tokens.css` for Discord embeds,
and the tests fail if a level lacks a color or badge class.

**Page header** - pages fill `{% block page_title %}`, optionally `{% block page_subtitle %}` and
`{% block page_actions %}` (buttons on the right). A page whose content isn't full width aligns the
title through `{% block page_header_class %}` (default `container-fluid`). Override
`{% block page_header %}` only for special layouts.

## Static files in production

`STORAGES` uses WhiteNoise's `CompressedManifestStaticFilesStorage`. File names get a content hash
and are cached forever, and every deploy busts the browser cache. A `{% static %}` path that doesn't
exist raises an error in production, and the tests check that every referenced file exists.
