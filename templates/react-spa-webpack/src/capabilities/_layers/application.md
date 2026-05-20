# Application layer — rules

This file is the canonical source of rules for the `application/` layer
of every capability. Each capability's `application/CLAUDE.md` imports
this file via the `@` syntax — do not duplicate content here.

Layer import boundaries and capability flow live in the template's root
`CLAUDE.md` — do not duplicate them here either.

## Purpose of this layer

Pure business logic and React-side orchestration of state transitions.

| Lives here | Does not live here |
|---|---|
| State shape (`*StateModel`) | DOM access |
| Action types and discriminated unions | `fetch`, HTTP, `localStorage` |
| Reducers (pure transitions) | Worker / timer / audio APIs |
| Use-case hooks (intent → dispatch) | Concrete repository implementations |
| Factories (entity construction rules) | Route definitions, JSX |

Side effects belong in `infrastructure/` or in the side-effect boundary
of a use-case hook — never inside a reducer.

## State primitive — the decision

The scaffold ships three context variants (`context.tsx`,
`context.rtk.tsx`, `context.zustand.tsx`). Only one survives the
scaffold step. Inside the **vanilla React** variant (`context.tsx` +
`use-cases.ts`), you still choose between `useState` and `useReducer`
at the use-case level. That choice is the most common architectural
mistake in this layer — pick deliberately.

| State shape | Primitive | Why |
|---|---|---|
| 1–2 independent values (open/closed flag, input text) | `useState` | Lighter, clearer |
| Async slice (`data`, `loading`, `error`) | 3 × `useState` | Independent transitions — see `use-cases.ts` |
| Cohesive state where one user gesture changes 3+ fields | `useReducer` | Centralizes transitions, keeps them atomic |
| Cross-component shared state, complex async / caching | Redux Toolkit | See `use-cases.rtk.ts` |
| Cross-component shared state, simple shape | Zustand | See `use-cases.zustand.ts` |

**Rule of thumb:** when a single user gesture changes multiple state
fields, reach for `useReducer`. The reducer becomes the only place that
defines what that gesture means at the state level.

### Why `useReducer` over multiple `useState` calls

When state fields move together, scattered `useState` setters drift.
The reducer makes the transition atomic and named.

```ts
// Bug-prone — caller owns five transitions, easy to forget one,
// and adding a new field means editing every handler that "starts" something.
function handleStart(task) {
  setActiveTask(task);
  setCurrentCycle(getNextCycle(currentCycle));
  setSecondsRemaining(task.duration * 60);
  setFormattedSeconds(formatSecondsToMinutes(task.duration * 60));
  setTasks([...tasks, task]);
}

// Centralized — the reducer owns the transition atomically.
// Adding a new field updates one case in one file.
function handleStart(task) {
  dispatch({ type: ActionTypes.START_TASK, payload: task });
}
```

The reducer's `case START_TASK` becomes the **single source of truth**
for "what starting a task means". Components dispatch *intent*, not
shape changes.

## Reducer rules (when using `useReducer`)

A reducer is a pure function `(state, action) => newState`. React calls
it during reconciliation and **may invoke it twice in StrictMode** to
catch bugs. Anything non-pure here turns into a subtle production
defect that does not reproduce in tests.

| Allowed in a reducer | Not allowed in a reducer |
|---|---|
| Reading from `state` and `action` | `Date.now()`, `Math.random()` |
| Calling pure helpers (e.g. from `task-utils.ts`) | `localStorage`, `fetch`, any I/O |
| Spreading and returning a new state object | Dispatching further actions |
| Throwing on impossible action types | `setTimeout`, `requestAnimationFrame` |

**Timestamps** that look like part of a transition (e.g. when a task
completed) belong in the **action payload**, computed by the use-case
hook before dispatching:

```ts
// Use-case hook — side-effect boundary, computes the timestamp
const completedAt = Date.now();
dispatch({
  type: ActionTypes.COMPLETE_TASK,
  payload: { completedAt },
});

// Reducer — pure, reads timestamp from payload
case ActionTypes.COMPLETE_TASK:
  return {
    ...state,
    tasks: state.tasks.map(task =>
      task.id === state.activeTask?.id
        ? { ...task, completedAt: action.payload.completedAt }
        : task,
    ),
  };
```

> **Pragmatic exception:** for small or learning-stage apps, inlining
> `Date.now()` in the reducer is a deliberate trade-off — ergonomic but
> not strictly pure. Recognize the compromise; don't pretend it is not
> there. The first time you write a reducer test that flakes because of
> wall-clock time, refactor to payload-passed timestamps.

## Reducer body — what the code looks like

Three cases below illustrate every micro-pattern that appears in a
typical reducer in this codebase. The remaining cases combine these
three shapes — read these and you can write the others.

```ts
// application/reducer.ts
export function taskReducer(
  state: TaskStateModel,
  action: TaskActionModel,
): TaskStateModel {
  switch (action.type) {
    // Case with const bindings → wrap in `{ ... }` to scope them.
    // Multi-field atomic transition — the headline reason for useReducer.
    case TaskActionTypes.START_TASK: {
      const newTask = action.payload;
      const nextCycle = getNextCycle(state.currentCycle);
      const secondsRemaining = newTask.duration * 60;
      return {
        ...state,
        activeTask: newTask,
        currentCycle: nextCycle,
        secondsRemaining,
        formattedSecondsRemaining: formatSecondsToMinutes(secondsRemaining),
        tasks: [...state.tasks, newTask],
      };
    }

    // Update one item in an array immutably: map + conditional spread.
    // Never `tasks.find(...).completeDate = ...` — that mutates state.
    case TaskActionTypes.COMPLETE_TASK: {
      return {
        ...state,
        activeTask: null,
        tasks: state.tasks.map((task) =>
          state.activeTask?.id === task.id
            ? { ...task, completeDate: Date.now() }
            : task,
        ),
      };
    }

    // No const bindings → no braces. Single return expression.
    case TaskActionTypes.COUNT_DOWN:
      return {
        ...state,
        secondsRemaining: action.payload.secondsRemaining,
        formattedSecondsRemaining: formatSecondsToMinutes(
          action.payload.secondsRemaining,
        ),
      };

    // ...remaining cases follow the same three shapes.
  }

  // Unreachable when the discriminated union is exhaustive — kept as a
  // safety net. If a new action type is added without a matching case,
  // the app still type-checks and falls through to "no change", instead
  // of silently breaking. Loud-fail alternative: `assertNever(action)`.
  return state;
}
```

Three things to internalize from this shape:

1. **Brace discipline.** A `case` that declares `const` *must* use
   `{ ... }` to scope the binding — without it, names leak into sibling
   cases and TypeScript complains. Cases with no locals stay
   brace-free for visual lightness.
2. **Immutable array update idiom.** `tasks.map(t => cond ? { ...t, x } : t)`
   is the canonical "update one item by id" pattern. The shorter
   `tasks.find(t => ...).x = ...` mutates state in place and breaks
   React's reference-equality checks for downstream `useMemo` /
   `React.memo` consumers.
3. **Blank lines between cases.** A reducer with 5+ cases scans much
   faster with one blank line between each case block. Cheap discipline,
   compounding readability win.

## Action design

Use **discriminated unions** for action types. TypeScript narrows
`action.payload` based on `action.type`, so each `case` knows the
payload shape without runtime guards.

```ts
// domain/enums.ts
export enum TaskActionTypes {
  START_TASK = 'START_TASK',
  COUNT_DOWN = 'COUNT_DOWN',
  INTERRUPT_TASK = 'INTERRUPT_TASK',
  COMPLETE_TASK = 'COMPLETE_TASK',
}

// application/actions.ts
export type TaskActionsWithPayload =
  | { type: TaskActionTypes.START_TASK; payload: TaskModel }
  | { type: TaskActionTypes.COUNT_DOWN; payload: { secondsRemaining: number } };

export type TaskActionsWithoutPayload =
  | { type: TaskActionTypes.INTERRUPT_TASK }
  | { type: TaskActionTypes.COMPLETE_TASK };

export type TaskActionModel = TaskActionsWithPayload | TaskActionsWithoutPayload;
```

Action **type enums** live in `domain/enums.ts` — they are part of the
capability's vocabulary, not application-layer implementation detail.
Action **shape unions** live in `application/actions.ts`.

## Use-case hooks pattern

One hook **per user intent**, not one mega-hook per entity. Each hook
orchestrates factory → side-effect boundary → dispatch, and returns
only the callback.

```ts
// application/use-cases.ts
export function useStartTask(
  state: TaskStateModel,
  dispatch: React.Dispatch<TaskActionModel>,
) {
  return useCallback(
    (dto: CreateTaskDto) => {
      const nextCycle = getNextCycle(state.currentCycle);
      const type = getNextCycleType(nextCycle);
      const task = createTask(dto, type, state.config[type]);
      dispatch({ type: TaskActionTypes.START_TASK, payload: task });
    },
    [state.currentCycle, state.config, dispatch],
  );
}
```

Each hook should:
- Accept only the slice of state it needs (or the repo for async cases).
- Compute derived values, build the action payload.
- Dispatch **once** per call.
- Return the callback — the UI never sees raw action shapes.

For async use cases (RTK/Zustand or repo-backed), the hook also exposes
`loading` and `error` flags, as in the scaffold's vanilla
`useCreateNote` / `useListNotes`.

## When to extract a `factories.ts` function

Extract when entity construction has **rules** that should live in one
place:

| Construction shape | Where |
|---|---|
| ID generation (`crypto.randomUUID()`) | `factories.ts` |
| Default field values (`completeDate: null`) | `factories.ts` |
| Derived values from DTO + context (cycle type, duration) | `factories.ts` |
| One-line object spread with no decisions | Inline in the use case |

For DTO ↔ entity mapping rules, see the parent CLAUDE.md.

## Do / Don't

| Do | Don't |
|---|---|
| Make reducers pure — read inputs, return new state | Call `Date.now()` or `dispatch` inside a reducer |
| Put timestamps in action payloads | Mutate state in place |
| One use-case hook per user intent | Cram CRUD verbs into one giant hook |
| Use discriminated unions for action types | Use `payload: any` or `Record<string, unknown>` |
| Reach for `useReducer` when multi-field transitions cluster | Reach for `useReducer` for one boolean toggle |
| Extract to `factories.ts` when construction has rules | Wrap every `{ ...obj }` in a factory function |
| Keep action type enums in `domain/` | Define action types in `application/` |
| Test reducers and factories with pure assertions | Mount React just to test a pure transition |

## Where the composition root is NOT

A capability's **composition root** (`context.tsx` or
`<Name>ContextProvider.tsx` at the capability root) consumes everything
this layer exports — the reducer, the initial state, the use-case hooks
— and it lives **outside** `application/`. Future readers may be
tempted to file the provider here. Don't. The composition root sits one
level above all four layers because it imports `infrastructure/` too —
and `application/` is forbidden from doing that.

What `application/` exports (consumed by the composition root):

- `reducer.ts` → the pure transition function passed to `useReducer`
- `state.ts`, `actions.ts`, `initial-state.ts` → the shapes the reducer reads
- `use-cases.ts` → hooks that wrap dispatch with intent-named callbacks
- `factories.ts`, `task-utils.ts` → pure helpers consumers can call

The composition root imports these AND the infrastructure adapters,
then wires them inside a React Provider. The wiring isn't business
logic; if you find a *rule* sneaking into the composition root, move
it back here. See the template's root `CLAUDE.md` for where the
composition root file sits in the directory layout.

## Composition root — side-effect wiring

The composition root is the **browser-side-effect seam**. It is the
only file in the capability where these may legitimately appear at
the top of the import list:

| Side-effect family   | Examples                                          |
| -------------------- | ------------------------------------------------- |
| Persistence          | `localStorage`, `sessionStorage`, `IndexedDB`     |
| Document / window    | `document.title`, `document.documentElement`      |
| Web Workers / timers | `Worker`, `setInterval`, `requestAnimationFrame`  |
| Audio / media        | `AudioContext`, `HTMLMediaElement`                |
| Networking lifecycle | `EventSource`, `WebSocket` (subscribe long-lived) |

UI components do not own these — they own DOM events on their own
elements and refs into their own subtree. Infrastructure adapters own
them when they need a class with lifecycle (see `infrastructure.md`).
Anything that doesn't fit either of those slots and still has to run
in the browser belongs in the composition root.

### Subscriptions belong inside `useEffect` — never at the top of the render body

When the composition root wires a vendor adapter's callback
(`worker.onmessage`, `eventSource.addEventListener`, `audio.onended`,
`localStorage` cross-tab `storage` events), the subscription **must**
sit inside a `useEffect`, with the resource in the dependency array.
Calling the subscription at the top of the component body re-installs
the handler on every render and — if the callback closes over a
`useRef` — earns a `react-hooks/refs` violation from the linter.

```tsx
// ❌ Anti-pattern — subscription at render-time. Re-installed every
//    render; reading playBeepRef.current here is a ref-during-render bug.
const worker = TimerWorkerManager.getInstance();
worker.onmessage((countDownSeconds) => {
  if (countDownSeconds <= 0) {
    playBeepRef.current?.();
    dispatch({ type: ActionTypes.COMPLETE_TASK });
  }
});

// ✅ Correct — subscription scoped to a useEffect with the resource
//    in the deps. Installed once per worker instance; ref access lives
//    inside the callback, which only runs on actual messages.
useEffect(() => {
  worker.onmessage((countDownSeconds) => {
    if (countDownSeconds <= 0) {
      playBeepRef.current?.();
      dispatch({ type: ActionTypes.COMPLETE_TASK });
    }
  });
}, [worker]);
```

The same rule applies to write-effects (persisting to localStorage,
syncing `document.title`, posting messages to a Worker on state
changes): wrap them in a `useEffect` whose deps are the state slices
those effects read.

### Hydrating state from `localStorage` — the `useReducer` lazy initializer

When the composition root restores persisted state, do it in
`useReducer`'s **third argument** (the lazy initializer), not in a
mounting `useEffect`. The third argument runs once before the first
render, so the UI never flashes the default state on reload.

```tsx
const [state, dispatch] = useReducer(reducer, initialState, () => {
  const stored = localStorage.getItem('app_state');
  if (!stored) return initialState;
  const parsed = JSON.parse(stored) as AppStateModel;
  // Strip fields that are unsafe to resume verbatim — e.g. an in-flight
  // countdown whose wall-clock anchor would now be stale.
  return { ...parsed, activeTask: null, secondsRemaining: 0 };
});
```

Two non-obvious rules in that snippet:

1. **Cast at the boundary.** `JSON.parse(stored) as AppStateModel` is a
   boundary cast — `localStorage` returns `string`, the type system
   has no idea what's inside. The composition root is one of the few
   places where `as Foo` is acceptable; cross-reference the
   "Boundary casting rule" in `infrastructure.md` — the same rule
   applies here, with `localStorage` as the boundary.
2. **Strip in-flight fields on restore.** Any state field that
   captures a moment-in-time (a countdown's `startDate`, an open
   socket id, a pending request id) cannot be safely resumed after
   a reload. The hydrator must reset those to a known-good baseline.

### Provider + hook split — keep the warning from ever appearing

The `react-refresh/only-export-components` rule fires on **any**
file that mixes component and non-component exports. That means **all**
non-component exports (the `Context` object itself, the value-type
interface, the hook) have to live in a separate file from the
provider component. Splitting on just the hook is not enough — the
`Context` is also a non-component value and triggers the same rule.

The canonical layout is two files per capability composition root:

```
capabilities/<name>/
├── context.tsx           — exports: NoteProvider                                   (component file)
└── use-context.ts        — exports: NoteContext, NoteContextValue, useNoteContext  (non-component file)
```

Or, for capabilities that name the provider file after the entity:

```
capabilities/<name>/
├── <Name>ContextProvider.tsx   — exports: <Name>ContextProvider                                  (component file)
└── use-<name>-context.ts        — exports: <Name>Context, <Name>ContextProps, use<Name>Context  (non-component file)
```

The non-component file holds the `createContext(...)` call, the
context-value type, and the consumer hook. The provider file
imports `Context` back from the non-component file to wrap its
children in `<Context.Provider value={...}>`. UI components import
**only** the hook (`useNoteContext` / `useTaskContext`) — they
never reach for the `Context` directly.

This is a deliberate move away from the older colocated pattern
(provider + hook + context all in `context.tsx` with an
`eslint-disable-next-line react-refresh/only-export-components`
directive). Splitting removes the warning at its source, restores
full Fast Refresh fidelity for edits to either file, and makes the
dependency graph between hook and provider explicit — the provider
depends on the hook file (for the Context object), not the other
way around.

## Testing notes specific to this layer

Reducers and factories are pure — assert on input/output, no React
needed. Use-case hooks need `renderHook` from
`@testing-library/react`; mock the **port interface** from
`domain/ports.ts`, never the concrete adapter from `infrastructure/`.
See the parent CLAUDE.md for the full testing matrix.
