# UI layer — rules

This file is the canonical source of rules for the `ui/` layer of every
capability. Each capability's `ui/CLAUDE.md` imports this file via the
`@` syntax — do not duplicate content here.

Layer import boundaries and capability flow live in the template's root
`CLAUDE.md` — do not duplicate them here either.

## Purpose of this layer

React components, page-level routes, and the JSX that consumes the
rest of the capability. The UI's job is to:

1. Read state via `useTaskContext()` (or the capability's context hook)
2. Call use-case hooks for user intents
3. Render JSX
4. Forward user events back into use-case hooks

That's it. No business rules, no fetch calls, no localStorage —
those belong in `application/` and `infrastructure/`.

| Lives here | Does not live here |
|---|---|
| Components (`MainForm.tsx`, `CountDown.tsx`) | Reducers, action types |
| Pages (`HomePage.tsx`, `HistoryPage.tsx`) | Worker / fetch / localStorage adapters |
| CSS Modules (`*.module.css`) | State shapes, factories |
| Local view-only `useState` (form input, modal open) | Cross-component shared state (use context) |
| Calls to use-case hooks from `application/` | Direct calls to `infrastructure/` from a component |

## Imports — the hard rule

UI files **can** import from:

| From | To | Why |
|---|---|---|
| `ui/*` | `../domain/entities`, `../domain/enums`, `../domain/dto` | Render and accept typed data |
| `ui/*` | `../application/use-cases`, `../application/task-utils` | Trigger intents, format data |
| `ui/*` | The capability composition root (e.g. `../context.tsx`, `../TaskContextProvider.tsx`) | Read state, dispatch |
| `ui/*` | `@/shared/components/*`, `@/shared/templates/*` | Reuse generic UI primitives |
| `ui/*` | Other `ui/*` files in the same capability | Capability-internal composition |
| `ui/*` | Third-party UI libs (`lucide-react`, etc.) | Icon and primitive imports |

UI files **must not** import from:

- `../infrastructure/*` — components don't call adapters directly. Use
  a use-case hook from `application/`, which orchestrates the adapter
  on the component's behalf. This keeps the adapter swappable.
- `../application/state.ts` / `../application/actions.ts` /
  `../application/reducer.ts` — these are internals of the application
  layer. The UI consumes `state` via context and triggers transitions
  via use-case hooks, never by importing action types directly.
- The barrel `index.ts` of another capability's UI — cross-capability
  composition happens at the route or shared template level.

**The one exception:** `domain/enums.ts` action type values may appear
in a component when dispatching directly (e.g.
`dispatch({ type: TaskActionTypes.RESET_STATE })`). This is a pragmatic
compromise in small apps. In larger codebases, wrap every dispatch in
a use-case hook so the UI never names an action type.

## Component patterns

### Two flavors of component

| Flavor | Where it lives | What it does |
|---|---|---|
| **Capability component** | `ui/components/<Name>.tsx` | Knows about this capability's state shape; uses `useTaskContext()` |
| **Page** | `ui/pages/<Name>.tsx` | Wraps capability components in a layout template, sets `document.title` |

Generic components (Button, Input, Dialog, Container) live in
`@/shared/components/` — they accept props and have no awareness of
any capability's state.

### Local view-state vs context state

| Concern | Primitive |
|---|---|
| Form input value before submit, focus state, modal open/closed | Local `useState` in the component |
| Anything other components also need to read | Context (`useTaskContext`) → set via use-case hook |
| Anything that should survive a page navigation | Context (or `application/` slice) |

If two sibling components both need the same `useState`, lift it to
context and add a use-case hook for the transition. Don't pass setters
through props more than one level deep.

### Refs over `useState` for "uncontrolled" inputs

For form inputs the user fills and submits **once**, prefer
`useRef<HTMLInputElement>` over `useState`. The component avoids
re-rendering on every keystroke, and the value is read at submit time
with `ref.current?.value`.

```tsx
const taskNameInput = useRef<HTMLInputElement>(null);

function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
  e.preventDefault();
  const taskName = taskNameInput.current?.value.trim() ?? '';
  if (!taskName) return showMessage.warn('Digite o nome da tarefa');
  // ...
}

return <DefaultInput ref={taskNameInput} disabled={!!activeTask} />;
```

Use `useState` when **other components need to react** to the value
mid-typing (live preview, validation indicator). Otherwise refs are
the right primitive for one-shot reads.

### Event handler shape

Handlers should be **thin orchestration**: read the input, validate at
the surface level, call the use-case hook or `dispatch`. No business
rules inline.

```tsx
// ✅ Thin handler — delegates to use case
function handleCreateTask(e: React.FormEvent<HTMLFormElement>) {
  e.preventDefault();
  showMessage.dismiss();
  const name = taskNameInput.current?.value.trim() ?? '';
  if (!name) return showMessage.warn('Digite o nome da tarefa');
  startTask({ name });
}

// ❌ Business logic inline in the handler
function handleCreateTaskBad(e: React.FormEvent<HTMLFormElement>) {
  e.preventDefault();
  const nextCycle = state.currentCycle === 8 ? 1 : state.currentCycle + 1;
  const type = nextCycle % 8 === 0 ? 'longBreakTime' : /* ... */;
  const newTask: TaskModel = { /* big inline factory */ };
  dispatch({ type: TaskActionTypes.START_TASK, payload: newTask });
}
```

The first version delegates to `startTask({ name })`; the cycle logic
and the factory live in `application/use-cases.ts` and
`application/factories.ts` respectively.

## CSS Modules conventions

| Convention | Why |
|---|---|
| One `.module.css` per component, co-located (`MainForm.module.css`) | Scoped styles, no global leakage, easy to find |
| Class names in `camelCase` (`.formRow`, `.thSort`) | Translates cleanly to `styles.formRow` in JSX |
| Use design tokens from `@/shared/styles/foundations/` (`var(--primary)`) | Theme switching is one CSS variable swap |
| Composition with template literals: `` `${styles.button} ${styles[color]}` `` | Variant styling without runtime CSS-in-JS |

Avoid inline `style={{}}` props except for runtime-computed values
(percentages from state, computed colors). Even then, prefer a CSS
custom property set on the element so the styling stays declarative.

## Responsive design — fluid-first

Don't chase per-device pixel-perfection. The browser DevTools device list
has dozens of presets and grows every year. Match the shape of the
viewport, not the name of the phone — write **one design that has no
fixed width**.

### Hierarchy (use the first that solves the problem)

1. **Fluid math** — `clamp(min, preferred, max)`, `min(a, b)`, `max(a, b)`.
   Continuous interpolation across viewports, **zero breakpoints**.
2. **Flexbox / Grid auto-fit** — `flex-wrap: wrap`, `grid-template-columns:
   repeat(auto-fit, minmax(20rem, 1fr))`. The browser handles reflow.
3. **`overflow-x: auto` on data-dense containers** — tables, code blocks,
   timelines. Don't try to fit a 64rem table into a 320px screen; let
   the user scroll horizontally inside a bounded box.
4. **Media queries** — only when the layout fundamentally **changes**
   (e.g. sidebar collapses into a hamburger). Not for "tweak a margin."

### Worked examples from this template family

```css
/* ✅ Fluid: never overflows, no breakpoint */
.button { min-width: min(24rem, 100%); }

/* ✅ Fluid edge spacing: ~14px on phones, 32px on desktop */
.content { margin: clamp(1.6rem, 5vw, 3.2rem); }

/* ✅ Fluid type, scales with viewport but bounded */
.heading { font-size: clamp(2rem, 5vw, 4rem); }

/* ✅ Data table that doesn't reflow — controlled horizontal scroll */
.tableWrapper { overflow-x: auto; }
.tableWrapper table { min-width: 64rem; }
```

### Content-based breakpoints, not device-based

When a media query is genuinely needed, **add it at the width where
*your content* visually breaks**, not at "iPhone width." Pick the value
empirically by shrinking the browser and watching when the layout
fails. Mobile-first (`min-width`) is the recommended convention.

```css
/* ✅ Mobile-first: base styles target the smallest viewport;
       media queries widen the layout as space allows. */
.layout { display: flex; flex-direction: column; }

@media (min-width: 48rem) {
  /* Tablet+: side-by-side */
  .layout { flex-direction: row; }
}
```

### Custom properties don't work in media-query conditions

**This is the responsive footgun that costs an hour the first time**:

```css
:root { --bp-md: 48rem; }

/* ❌ Silently does nothing — CSS custom properties cannot be used
       in media query conditions. The media query is parsed before
       custom properties resolve. */
@media (min-width: var(--bp-md)) { /* ... */ }

/* ✅ Use a literal value */
@media (min-width: 48rem) { /* ... */ }
```

Workarounds (`@custom-media` via PostCSS, Sass variables) exist but
aren't part of this template's stack. The honest answer: **breakpoint
values stay as literal `rem` in media queries**, and you tolerate the
repetition for the ~2-3 breakpoints a typical SPA needs.

### Test at the extremes

Open DevTools device-mode and check the narrowest viewport you support
(Galaxy Fold outer ~280px is a stress test) and the widest. Skip the
38 devices in between — they all fit between those bounds. The two
manual breakpoints to add to muscle memory:

| Viewport | Why |
| --- | --- |
| ~280px (Galaxy Fold outer) | Narrowest realistic phone; catches "min-width too large" bugs |
| ~1920px (wide desktop) | Catches "max-width too small / content awkwardly stretched" bugs |

If both extremes look reasonable, the in-between sizes will too. Test
at your own content's breakpoints separately if you have any.

### `<meta name="viewport">` is the prerequisite

Without `<meta name="viewport" content="width=device-width, initial-scale=1">`
in `public/index.html`, mobile browsers render at a fake 980px and zoom
out — none of your CSS breakpoints fire. The scaffold ships this tag
by default; don't remove it.

## Pages — the contract

A page component sits at the top of a route and is responsible for:

1. Wrapping content in the layout template (`<MainTemplate>`)
2. Setting `document.title` via `useEffect` (or `useDocumentTitle` if
   you've extracted the helper)
3. Composing capability components in the order they should render
4. **Nothing else** — no business logic, no fetch, no state shape work

Pages should be **boring**. If a page is hard to read at a glance, the
heavy lifting belongs in a child component or a use-case hook.

## Do / Don't

| Do | Don't |
|---|---|
| Read state via the capability's context hook (`useTaskContext`) | Pass `state` through 4 levels of props |
| Call use-case hooks for user intents | Dispatch action types from deep components |
| Local `useState` / `useRef` for view-only state | Promote every state slice to context |
| Import from `application/use-cases`, `domain/`, `@/shared/components` | Import from `infrastructure/*` |
| One component per file (`MainForm.tsx`) | Multiple top-level components in one file |
| CSS Modules with co-located `*.module.css` | Global stylesheets for component-specific rules |
| Pages stay boring — wrap, title, compose | Pages do data fetching, state shaping, or formatting |

## Testing notes specific to this layer

Components are tested with `@testing-library/react`. Render the
component inside a provider that supplies a stub context value:

```tsx
function renderWithStub(state: Partial<TaskStateModel>) {
  const stub = { state: { ...initialTaskState, ...state }, dispatch: jest.fn() };
  return render(
    <TaskContext.Provider value={stub}>
      <ComponentUnderTest />
    </TaskContext.Provider>,
  );
}
```

Three guidelines:

1. **Stub the context, not the use-case hook.** The component's job
   is "given this state, render this". The use-case hook is application
   concern; its test lives there.
2. **Test what the user sees, not implementation.** Query by role and
   text (`getByRole('button', { name: /iniciar/i })`), not by class
   name or component name.
3. **No `act()` ceremony for synchronous events.** `userEvent.click()`
   wraps `act` for you. Reach for `act()` manually only when timers
   or async are involved.

Visual / snapshot tests are usually a smell — they fail on every
intentional change without explaining why. Prefer assertions about
specific text or roles.
