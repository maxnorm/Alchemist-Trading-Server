# Terminal/Print Theme Component Library

## Overview

This component library implements a monochrome terminal/print aesthetic with orange accent colors. All components are built on top of shadcn/ui primitives and support density variants for ZEEX-like compact layouts.

## Theme System

### Color Palette

**Dual Mode Support:**
The theme supports both dark mode (primary) and light mode with automatic switching via CSS variables.

**Dark Mode (Primary):**
- `mono-100` to `mono-800`: Grayscale from darkest (#141414) to brightest (#F2F2F2)
- `orange-400`: #E38B29 (Primary accent - 53% lightness)
- Used for backgrounds, text, borders

**Light Mode:**
- `mono-100` to `mono-800`: Inverted grayscale from lightest (#FAFAFA) to darkest (#1A1A1A)
- `orange-400`: Adjusted to 45% lightness for better contrast on light backgrounds
- Maintains same semantic meaning as dark mode

**Orange Accent System:**
- `#FDEEDC` (orange-100): Lightest
- `#FFD8A9` (orange-200): Light
- `#F1A661` (orange-300): Medium
- `#E38B29` (orange-400): Primary accent (dark mode)
- `#C77321` (orange-400): Primary accent (light mode - darker for contrast)

**Usage:**
- Orange is reserved for: focus states, primary CTAs, active navigation, key deltas, highlights
- Never use hard-coded hex values in components - always use CSS variables or Tailwind tokens
- All components automatically adapt to theme via CSS variables

### Theme Toggle

```tsx
import { useUI } from '@/contexts/UIContext'

function ThemeToggle() {
  const { theme, toggleTheme } = useUI()
  
  return (
    <button onClick={toggleTheme}>
      {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
    </button>
  )
}
```

**Features:**
- Persists to localStorage
- Defaults to dark mode
- Smooth transitions between themes
- All components adapt automatically

### Typography

- **Data/Numbers**: Use `font-mono-data` class for tabular numerics
- **Technical Labels**: Use `text-technical` utility for uppercase, tracked labels
- **Body**: Default system font with tabular number support

### Spacing & Density

Three density variants available across components:
- `comfortable`: Standard spacing (1.5rem)
- `dense`: Compact spacing (1rem) - **default for most components**
- `ultra-dense`: Minimal spacing (0.5rem)

### Textures

**Halftone/Dot Patterns** (use sparingly):
- `halftone-texture`: Visible dot pattern
- `halftone-texture-subtle`: Subtle dot pattern

**Allowed zones:**
- Page headers
- Hero backdrops
- Empty states
- Side panel backgrounds

**Forbidden zones:**
- Tables
- Chart plot areas
- Dense text blocks

## Core Components

### PageHeader

Consistent page header with title, description, breadcrumbs, and actions.

```tsx
import { PageHeader } from '@/components/common'

<PageHeader
  title="Command Center"
  description="Real-time portfolio monitoring"
  breadcrumbs={[
    { label: 'Home', href: '/' },
    { label: 'Dashboard' }
  ]}
  actions={<Button>Create New</Button>}
/>
```

**Props:**
- `title`: string (required)
- `description`: string (optional)
- `breadcrumbs`: Array<{ label: string, href?: string }> (optional)
- `actions`: ReactNode (optional)
- `className`: string (optional)

### KPICard

Dense metric display with deltas, sparklines, and status indicators.

```tsx
import { KPICard } from '@/components/common'

<KPICard
  label="Total P&L"
  value="$123,456"
  delta={{
    value: "+12.5%",
    status: "positive"
  }}
  icon={<TrendingUp className="h-4 w-4" />}
  density="dense"
  status="positive"
/>
```

**Props:**
- `label`: string (required)
- `value`: string | number (required)
- `delta`: { value: string | number, status?: KPIStatus } (optional)
- `icon`: ReactNode (optional)
- `sparkline`: ReactNode (optional)
- `density`: 'comfortable' | 'dense' | 'ultra-dense' (default: 'dense')
- `status`: 'positive' | 'negative' | 'neutral' | 'warning' (default: 'neutral')
- `loading`: boolean (default: false)

### DenseCard

Wrapper around shadcn Card with density variants.

```tsx
import { DenseCard, DenseCardHeader, DenseCardContent } from '@/components/common'

<DenseCard density="dense" hover>
  <DenseCardHeader
    title="System Status"
    description="Current health"
    actions={<Button size="sm">Refresh</Button>}
  />
  <DenseCardContent>
    {/* Content */}
  </DenseCardContent>
</DenseCard>
```

**Props:**
- `density`: 'comfortable' | 'dense' | 'ultra-dense' (default: 'dense')
- `hover`: boolean - adds hover border effect (default: false)

### StatusBadge & HealthDot

Status indicators with severity variants.

```tsx
import { StatusBadge, HealthDot } from '@/components/common'

<StatusBadge severity="success" dot>
  Trading Active
</StatusBadge>

<HealthDot status="ok" label="System Healthy" />
```

**StatusBadge Props:**
- `severity`: 'success' | 'warning' | 'error' | 'info' | 'neutral' (required)
- `dot`: boolean - show colored dot (default: false)

**HealthDot Props:**
- `status`: 'ok' | 'warn' | 'error' | 'unknown' (required)
- `label`: string (optional)

### DataTable

Dense table with sticky headers and density variants.

```tsx
import { 
  DataTable, 
  DataTableHeader, 
  DataTableBody, 
  DataTableRow, 
  DataTableCell 
} from '@/components/common'

<DataTable density="dense" stickyHeader>
  <DataTableHeader>
    <tr>
      <DataTableCell header>Symbol</DataTableCell>
      <DataTableCell header align="right" mono>Price</DataTableCell>
    </tr>
  </DataTableHeader>
  <DataTableBody>
    <DataTableRow onClick={() => handleClick()}>
      <DataTableCell>EURUSD</DataTableCell>
      <DataTableCell align="right" mono>1.0850</DataTableCell>
    </DataTableRow>
  </DataTableBody>
</DataTable>
```

**Props:**
- `density`: 'comfortable' | 'dense' | 'ultra-dense' (default: 'dense')
- `stickyHeader`: boolean (default: true)
- `mono`: boolean - use monospace font for numbers (default: false)

### FilterBar

Combined search, filter chips, and actions.

```tsx
import { FilterBar } from '@/components/common'

<FilterBar
  search={{
    value: searchTerm,
    onChange: setSearchTerm,
    placeholder: "Search experiments..."
  }}
  filters={activeFilters}
  onRemoveFilter={handleRemove}
  onClearFilters={handleClear}
  actions={
    <>
      <Button variant="outline">Export</Button>
      <Button>Create New</Button>
    </>
  }
/>
```

### EmptyState, ErrorState, LoadingState

Consistent state displays.

```tsx
import { EmptyState, ErrorState, LoadingState } from '@/components/common'

<EmptyState
  icon={<Inbox className="h-12 w-12" />}
  title="No experiments yet"
  description="Create your first experiment to get started"
  action={<Button>Create Experiment</Button>}
/>

<ErrorState
  title="Failed to load"
  message={error.message}
  action={<Button onClick={retry}>Retry</Button>}
/>

<LoadingState message="Loading experiments..." />
```

## Animation System

### Motion Tokens

Centralized animation configuration in `src/styles/motion.ts`:

```typescript
import { motion } from '@/styles/motion'

// Duration tokens
motion.duration.fast // 0.2s
motion.duration.normal // 0.3s

// Easing tokens
motion.ease.out // 'power2.out'
motion.ease.subtle // 'power1.out'

// Presets
motion.presets.panelEnter
motion.presets.hoverEmphasis
```

### AnimatedPanel & AnimatedList

GSAP-powered entrance animations with cleanup.

```tsx
import { AnimatedPanel, AnimatedList } from '@/components/common'

<AnimatedPanel delay={0.1}>
  <Card>Content enters with fade + slide</Card>
</AnimatedPanel>

<AnimatedList stagger={0.1}>
  {items.map(item => (
    <KPICard key={item.id} {...item} />
  ))}
</AnimatedList>
```

**Props:**
- `delay`: number - delay in seconds (default: 0)
- `stagger`: number - stagger between items (default: 0.1)
- `disabled`: boolean - disable animations (default: false)

**Respects `prefers-reduced-motion`** - animations are automatically disabled if user prefers reduced motion.

## Best Practices

### 1. Density

Use `dense` as default for dashboard layouts. Reserve `comfortable` for forms and detail pages.

```tsx
// Dashboard - use dense
<KPICard density="dense" />

// Form page - use comfortable
<DenseCard density="comfortable">
```

### 2. Color Usage

- **Never hard-code colors** - use CSS variables or Tailwind tokens
- **Orange accent** - use for focus, active states, primary actions only
- **Status colors** - use semantic tokens (success, warning, destructive)

```tsx
// ✅ Good
<div className="text-orange-400 bg-mono-300">

// ❌ Bad
<div style={{ color: '#E38B29', background: '#1a1a1a' }}>
```

### 3. Typography

Use monospace for data/numbers:

```tsx
<span className="font-mono-data">1,234.56</span>
```

Use technical style for labels:

```tsx
<span className="text-technical">Total P&L</span>
```

### 4. Animations

Apply animations to panels/cards, not to dense data:

```tsx
// ✅ Good - animate card entrance
<AnimatedPanel>
  <DenseCard>
    <DataTable /> {/* Table inside is static */}
  </DenseCard>
</AnimatedPanel>

// ❌ Bad - don't animate table rows
<DataTable>
  {rows.map(row => (
    <AnimatedPanel key={row.id}> {/* Too much motion */}
      <DataTableRow />
    </AnimatedPanel>
  ))}
</DataTable>
```

### 5. Focus States

All interactive elements have visible focus rings (orange). Never disable focus styles.

```tsx
// Focus ring is automatic via global CSS
// Custom focus styles should use ring-orange-400
<button className="focus:ring-2 focus:ring-orange-400">
```

## Migration Guide

### From Old Components to New

**Old Card:**
```tsx
<Card>
  <CardHeader>
    <CardTitle>Title</CardTitle>
  </CardHeader>
  <CardContent>Content</CardContent>
</Card>
```

**New DenseCard:**
```tsx
<DenseCard density="dense" hover>
  <DenseCardHeader title="Title" />
  <DenseCardContent>Content</DenseCardContent>
</DenseCard>
```

**Old KPI:**
```tsx
<Card>
  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
    <CardTitle className="text-sm font-medium">Total P&L</CardTitle>
    <TrendingUp className="h-4 w-4 text-green-600" />
  </CardHeader>
  <CardContent>
    <div className="text-2xl font-bold text-green-600">$123,456</div>
    <p className="text-xs text-muted-foreground">+12.5%</p>
  </CardContent>
</Card>
```

**New KPICard:**
```tsx
<KPICard
  label="Total P&L"
  value="$123,456"
  delta={{ value: "+12.5%", status: "positive" }}
  icon={<TrendingUp className="h-4 w-4" />}
  status="positive"
  density="dense"
/>
```

## Commands

```bash
# Development
npm run dev

# Build
npm run build

# Lint
npm run lint

# Type check
npx tsc --noEmit

# Test
npm run test
```

## File Structure

```
src/dashboard/src/
├── components/
│   ├── common/           # New component library
│   │   ├── PageHeader.tsx
│   │   ├── KPICard.tsx
│   │   ├── DenseCard.tsx
│   │   ├── StatusBadge.tsx
│   │   ├── DataTable.tsx
│   │   ├── FilterBar.tsx
│   │   ├── EmptyState.tsx
│   │   ├── AnimatedPanel.tsx
│   │   └── index.ts      # Barrel export
│   └── ui/               # shadcn/ui primitives
│       ├── button.tsx
│       ├── card.tsx
│       └── ...
├── styles/
│   └── motion.ts         # Animation tokens
└── index.css             # Theme tokens
```

## Accessibility

- ✅ All interactive elements are keyboard accessible
- ✅ Focus states are visible (orange ring)
- ✅ Color is not the only means of conveying information
- ✅ Animations respect `prefers-reduced-motion`
- ✅ Semantic HTML used throughout
- ✅ ARIA labels where appropriate

## Performance

- ✅ GSAP animations use `useGSAP` hook with proper cleanup
- ✅ Components are memoized where appropriate
- ✅ No heavy filters or repaint loops
- ✅ Lazy loading for large lists (implement virtualization if needed)

## Support

For questions or issues with the component library, refer to:
- This documentation
- Component source code with inline comments
- shadcn/ui documentation: https://ui.shadcn.com
- GSAP documentation: https://greensock.com/docs/
