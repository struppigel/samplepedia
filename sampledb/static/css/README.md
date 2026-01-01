# CSS Architecture - Samplepedia

This directory contains modular CSS files for better maintainability. Files are loaded in a specific order to ensure proper cascading.

## File Structure

### 1. `variables.css` (67 lines)
**Purpose:** CSS variables/custom properties for theming
**Contains:**
- Primary theme colors (red accent, grays, blues)
- Context-aware variables that change in dark mode
- Color palettes for alerts, forms, tables, etc.

**When to edit:** When adding new colors or theme-wide properties

### 2. `dark-mode.css` (159 lines)
**Purpose:** Dark mode variable overrides and dark-mode-specific styles
**Contains:**
- `.dark-mode` class variable overrides
- Dark mode component styling (cards, tables, forms)
- Dark mode button and interaction states

**When to edit:** When adjusting dark mode appearance or adding dark-mode-specific styles

### 3. `layout.css` (50 lines)
**Purpose:** Site-wide layout and structure
**Contains:**
- Body typography (Inter font family)
- Heading styles
- Link colors and hover states
- Navbar styling
- Footer styling

**When to edit:** When changing overall site layout, typography, or structural elements

### 4. `components.css` (200+ lines)
**Purpose:** Reusable UI components
**Contains:**
- Cards (headers, titles)
- Badges (success, warning, danger, info)
- Alerts (alert-info styling and links)
- Buttons (primary, success, outline variants)
- Spoilers (reveal animations)
- Solution items (even/odd rows, hover states, highlight animation)
- Favorite buttons

**When to edit:** When modifying component appearance or adding new UI components

### 5. `forms.css` (95 lines)
**Purpose:** Form controls and input styling
**Contains:**
- Form input backgrounds, borders, focus states
- Autofill styling (WebKit and Firefox)
- Placeholder text styling
- SHA256 readonly field states
- Image selection cards for task submission

**When to edit:** When changing form appearance or adding new form components

### 6. `tables.css` (30 lines)
**Purpose:** Table and pagination styling
**Contains:**
- Table striping (alternating row colors)
- Table hover states
- Table borders
- Pagination links and active states

**When to edit:** When modifying table appearance or pagination styling

## Load Order (IMPORTANT)

Files **must** be loaded in this order in `base.html`:

```html
<link rel="stylesheet" href="{% static 'css/variables.css' %}">      <!-- 1. Define variables first -->
<link rel="stylesheet" href="{% static 'css/dark-mode.css' %}">      <!-- 2. Override variables for dark mode -->
<link rel="stylesheet" href="{% static 'css/layout.css' %}">         <!-- 3. Base layout -->
<link rel="stylesheet" href="{% static 'css/components.css' %}">     <!-- 4. Components -->
<link rel="stylesheet" href="{% static 'css/forms.css' %}">          <!-- 5. Forms -->
<link rel="stylesheet" href="{% static 'css/tables.css' %}">         <!-- 6. Tables -->
```

## Benefits of This Structure

1. **Easier maintenance** - Find styles quickly by category
2. **Reduced merge conflicts** - Team members can work on different files
3. **Faster debugging** - Narrow down issues to specific files
4. **Better organization** - Logical grouping by functionality
5. **Selective loading** - Could load only needed files per page (future optimization)

## Migration Notes

The original `custom.css` (586 lines) has been split into 6 focused files totaling ~600 lines. No functionality was changed - this is a pure refactor for maintainability.

### Original file location
- **Old:** `static/css/custom.css` (can be safely deleted after testing)
- **New:** Six modular files in `static/css/`

## Adding New Styles

**For new colors/variables:**
→ Add to `variables.css` (both `:root` and `.dark-mode`)

**For dark mode specific styles:**
→ Add to `dark-mode.css`

**For buttons, badges, alerts, cards:**
→ Add to `components.css`

**For input fields, textareas, selects:**
→ Add to `forms.css`

**For layout changes (header, footer, nav):**
→ Add to `layout.css`

**For tables or pagination:**
→ Add to `tables.css`
