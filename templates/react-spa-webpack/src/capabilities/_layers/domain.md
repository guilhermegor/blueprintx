# Domain layer — rules

This file is the canonical source of rules for the `domain/` layer of
every capability. Each capability's `domain/CLAUDE.md` imports this
file via the `@` syntax — do not duplicate content here.

Layer import boundaries and capability flow live in the template's root
`CLAUDE.md` — do not duplicate them here either.

## Purpose of this layer

Pure types and contracts that describe the **vocabulary of the
capability**. Nothing in this layer runs at runtime in a meaningful
sense — it's the shape language used by the other three layers.

| Lives here | Does not live here |
|---|---|
| `entities.ts` — entity types (`TaskModel`, `Note`) | `useState`, `useReducer`, any hook |
| `enums.ts` — enums and union types (`CycleType`, `TaskActionTypes`) | `fetch`, `localStorage`, Worker |
| `ports.ts` — interfaces that infrastructure implements | Reducers, factories, use cases |
| `dto.ts` — input/output shapes at capability boundaries | JSX, CSS, route definitions |
| Branded types, value objects, exhaustive unions | Side effects of any kind |

The litmus test: **a domain file should have zero imports** (or only
type-only imports from other domain files). If a file in this layer
imports anything from `application/`, `infrastructure/`, `ui/`, or a
third-party library at runtime, it does not belong here.

## Imports — the hard rule

Domain files can import:

| From | To | Why |
|---|---|---|
| `domain/*` | Other `domain/*` files (type-only) | Compose entity types from enums, etc. |
| `domain/*` | **Nothing else** | Domain is the bottom of the dependency graph |

`type` imports between domain files are fine and encouraged:

```ts
// domain/entities.ts
import type { CycleType } from './enums';

export type TaskModel = {
  id: string;
  type: CycleType;
  duration: number;
  // ...
};
```

**Why so strict here:** the domain layer is the contract every other
layer depends on. If domain imports application code, you have a cycle.
If domain imports infrastructure, swapping the adapter requires touching
domain — and the architecture's promise breaks.

## File responsibilities

| File | Contains | Does not contain |
|---|---|---|
| `entities.ts` | Entity types (the nouns of the capability) | State shapes (`*StateModel` — those are application) |
| `enums.ts` | Enums (`CycleType`), action type enums (`TaskActionTypes`) | Action shape unions (those are application) |
| `ports.ts` | Interfaces that infrastructure adapters implement | Concrete classes, implementations |
| `dto.ts` | Input DTOs (`CreateTaskDto`), output DTOs at capability boundaries | Internal data shapes (those are entities) |

**Why split into multiple files instead of one `domain.ts`:** each file
has a single responsibility, and the names communicate intent at the
import site. `import { TaskModel } from '../domain/entities'` is
self-documenting; `import { TaskModel } from '../domain'` is not.

## Port design

A port is a TypeScript `interface` (not `class`, not `type alias`).
Interfaces can be implemented with `class Foo implements IPort`, which
gives compile-time substitutability — the headline rule in
`infrastructure.md`.

```ts
// domain/ports.ts
export type TimerWorkerInput = {
  activeTask: { startDate: number } | null;
  secondsRemaining: number;
};

export interface ITimerWorker {
  postMessage(input: TimerWorkerInput): void;
  onmessage(cb: (secondsRemaining: number) => void): void;
  terminate(): void;
}
```

Three rules for ports:

1. **Speak domain language.** No `MessageEvent`, no `AxiosError`, no
   `Response`. If a native type appears in a port signature, the
   adapter has leaked its implementation into the contract. See the
   "Framework type hiding" section in `infrastructure.md`.
2. **One port per external concern.** A `NoteRepository` is one port; a
   `Logger` is another; a `Clock` is another. Don't merge them into a
   `BackendServices` god-interface.
3. **Not every adapter needs a port.** See the
   "When NOT to define a port" section in `infrastructure.md`.
   Presentational-only adapters (toast facades, animation wrappers) are
   port-less and live in `infrastructure/` directly.

## DTO design

DTOs describe data **crossing the capability boundary**:

| DTO direction | Purpose | Example |
|---|---|---|
| Inbound | Input from UI form, command from outside the capability | `CreateTaskDto`, `UpdateSettingsDto` |
| Outbound | Data returned to UI, projection for external consumer | `TaskSummaryDto` (subset of `TaskModel` safe for listing) |

DTOs are **narrower than entities** — they only include what crosses
the boundary. A `CreateTaskDto` has `name` (from the form input); the
entity adds `id`, `startDate`, `completeDate`, etc. via the factory.

```ts
// domain/dto.ts
export type CreateTaskDto = { name: string };
export type UpdateSettingsDto = {
  workTime: number;
  shortBreakTime: number;
  longBreakTime: number;
};
```

**Don't use DTOs to hide a field for security/permissions** — that's a
projection concern, not a DTO concern. Use a separate `*View` type for
that case.

## Do / Don't

| Do | Don't |
|---|---|
| Use `type` for entities and DTOs | Use `class` for entities (entities are values, not behavior holders) |
| Use `interface` for ports (so adapters can `implements`) | Use `type` for ports (loses `implements` ergonomics) |
| Split into `entities.ts`, `enums.ts`, `ports.ts`, `dto.ts` | One mega `domain.ts` file |
| Keep imports type-only and within `domain/` | Import from `application/` or `infrastructure/` |
| Branded / nominal types for IDs (`type TaskId = string & { __brand: 'TaskId' }`) | Pass raw `string` everywhere and hope IDs don't get swapped |
| Enums for closed sets (`CycleType`, action types) | Magic strings sprinkled across the codebase |

## Testing notes specific to this layer

Domain types are **types, not values** — there's nothing to test at
runtime. TypeScript's structural type checker is the test.

The one runtime artifact in this layer is **enums**, and you usually
don't unit-test enum values — they're used as discriminators.

If you find yourself wanting a `domain.test.ts`, you've probably put
runtime logic in the wrong layer. Move it to `application/` (pure
helpers) or `infrastructure/` (effectful adapters).
