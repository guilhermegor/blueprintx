# Infrastructure layer — rules

This file is the canonical source of rules for the `infrastructure/`
layer of every capability. Each capability's `infrastructure/CLAUDE.md`
imports this file via the `@` syntax — do not duplicate content here.

Layer import boundaries and capability flow live in the template's root
`CLAUDE.md` — do not duplicate them here either.

## Purpose of this layer

Adapters that talk to the **outside world**: HTTP APIs, browser APIs
(workers, storage, audio), third-party SDKs, file systems, sockets.
This is the only layer where side effects, framework types, and
external dependencies are welcome.

| Lives here | Does not live here |
|---|---|
| `fetch` calls, HTTP clients | Business rules ("a task ends when…") |
| Web Worker scripts and managers | State shapes (`*StateModel`) |
| `localStorage` / `IndexedDB` adapters | React hooks, JSX |
| Third-party SDK wrappers (toast lib, analytics) | Route definitions |
| Singleton lifecycle for stateful resources | Action types, reducers |

If a file in this layer has no `fetch`, no `new SomeNativeClass(...)`,
no `localStorage`, no `import 'third-party-lib'` — it probably belongs
in `application/`.

## Imports — the hard rule

Infrastructure files **must not** import from `application/`, `ui/`,
or `context.tsx`. Allowed:

| From | To | Why |
|---|---|---|
| `infrastructure/*` | `../domain/ports` | The port defines the contract this adapter fulfills |
| `infrastructure/*` | `../domain/entities`, `../domain/dto`, `../domain/enums` | Adapters translate external data → domain types |
| `infrastructure/*` | external libraries (`fetch`, `react-toastify`, SDKs) | Adapters wrap external dependencies |
| `infrastructure/*` | other `infrastructure/*` | Shared helpers within the layer |

**Why so strict here:** the moment infrastructure imports from
`application/`, you've inverted the dependency direction the
architecture was designed around. Domain and application become
unswappable from infrastructure, and tests can no longer stub the
infrastructure without dragging application state into the fixture.

## The port-implementation pattern (the headline rule)

**Most** infrastructure classes should declare `implements <Port>`
where `<Port>` is an interface from `../domain/ports`. The port is the
contract; the adapter is one implementation. The exception —
presentational adapters with no domain stake — is covered in
[When NOT to define a port](#when-not-to-define-a-port-presentational-adapters)
below.

```ts
// domain/ports.ts — the contract
export interface NoteRepository {
  add(note: Note): Promise<Note>;
  list(): Promise<Note[]>;
}

// infrastructure/api-adapter.ts — one implementation
export class ApiNoteRepository implements NoteRepository {
  async add(note: Note): Promise<Note> { /* fetch... */ }
  async list(): Promise<Note[]> { /* fetch... */ }
}
```

**Why `implements`:** TypeScript errors immediately when the class's
public signatures drift from the port. Without it, you can quietly
add a method to the adapter that callers grow to depend on — and the
port becomes a lie. With `implements`, the class is provably
substitutable.

**Why this matters for tests:** the application layer accepts the
**port type** as a parameter (`useCreateNote(repo: NoteRepository)`),
never the concrete adapter. Tests pass a stub `{ add: jest.fn(), … }`
that satisfies the port. No `jest.mock('./api-adapter')` needed.

## When NOT to define a port (presentational adapters)

The port-implementation pattern above applies when **domain has a
semantic stake** in the external system: timer cycles are domain (so
`ITimerWorker`); note persistence is domain (so `NoteRepository`).

**Some adapters have no domain stake** — they translate one API surface
into another, where the caller is purely presentational (UI). In those
cases, no port belongs in `domain/ports.ts`. The adapter exports its
shape directly and is consumed as a frozen object of functions.

Canonical example — a toast-message facade:

```ts
// infrastructure/show-message.ts — port-less, presentation only
import { toast } from 'react-toastify';

export const showMessage = {
  success: (msg: string) => toast.success(msg),
  error: (msg: string) => toast.error(msg),
  warning: (msg: string) => toast.warning(msg),
  dismiss: () => toast.dismiss(),
};
```

**Decision rule** — would replacing the external system change any
domain behavior?

| Swap | Domain reaction | Verdict |
|---|---|---|
| `react-toastify` → `sonner` | UI looks different; no domain rule changes | **port-less** |
| Web Worker → server-side timer | Cycle timing is a domain rule; contract must hold | **port required** |
| `localStorage` → IndexedDB | Persistence is a domain rule (data survives reload) | **port required** |
| Animation library swap | Pure presentation | **port-less** |

When in doubt: if your `domain/` folder has **nothing to say** about
the external system, the adapter is port-less.

**Shape of a port-less adapter** (the same rule from the root
`CLAUDE.md`'s class-vs-function table applies):

- 0 of 3 triggers (no state, no port, no DI) → frozen object of
  functions or plain module of functions.
- Single import of the vendor library (the seam).
- No `class` — the export is the public surface directly.

## Boundary casting rule

Untyped data from external sources (`response.json()`, `event.data`,
`localStorage.getItem()`, `URLSearchParams.get()`) must be **cast or
validated at the first line that touches it** — never deeper.

```ts
// ✅ Cast at the boundary, return a typed value
async list(): Promise<Note[]> {
  const data = (await response.json()) as Note[];
  return data;
}

// ✅ Better: validate (e.g. with Zod) — cast lies, parse proves
async list(): Promise<Note[]> {
  const raw = await response.json();
  return NoteListSchema.parse(raw);
}

// ❌ Cast leaking into application code
async list(): Promise<unknown> {
  return response.json();
}
// ...then somewhere in application/:
const notes = (await repo.list()) as Note[]; // wrong layer, hidden lie
```

The boundary is the **only place** an `as Foo` cast is acceptable.
If you find yourself casting in `application/` or `ui/`, that's a
signal the adapter is leaking untyped data — fix it at the source.

## Framework type hiding

Native and library types (`MessageEvent`, `AxiosError`, `Response`,
`IDBDatabase`, `Promise<AxiosResponse<T>>`) must not appear in **port
signatures**. They may appear inside adapter implementations, but the
port stays framework-agnostic.

```ts
// ✅ Port speaks domain language
export interface ITimerWorker {
  onmessage(cb: (secondsRemaining: number) => void): void;
}

// ✅ Adapter hides the MessageEvent at the boundary
onmessage(cb: (secondsRemaining: number) => void): void {
  this.worker.onmessage = (e: MessageEvent) => cb(e.data as number);
}

// ❌ Port leaks the Worker implementation
export interface ITimerWorker {
  onmessage(cb: (e: MessageEvent) => void): void;
}
```

**Why this matters:** the moment `MessageEvent` appears in a port,
every consumer (use cases, context, components) couples to the Worker
API. Swap the worker for a `setInterval` fallback or a server-side
timer → every consumer rewrites. Hidden behind the port → the swap is
one file.

## Singletons and lifecycle

When an adapter wraps a **stateful, expensive-to-construct resource**
(a Worker, a WebSocket, a DB connection, an audio context), use the
module-scope singleton pattern:

```ts
let instance: TimerWorkerManager | null = null;

export class TimerWorkerManager implements ITimerWorker {
  private constructor() { /* ... */ }

  static getInstance(): TimerWorkerManager {
    if (!instance) instance = new TimerWorkerManager();
    return instance;
  }

  terminate(): void {
    this.worker.terminate();
    instance = null;
  }
}
```

Three rules for this pattern:

1. **`private constructor`** — forces callers through `getInstance()`.
   Without it, someone will accidentally `new TimerWorkerManager()` and
   spawn a second worker.
2. **Reset `instance = null` in `terminate()`** — so the next
   `getInstance()` builds a fresh resource. Without this, a terminated
   worker stays cached, and the next caller gets a dead handle.
3. **No singletons for stateless adapters.** An `ApiNoteRepository`
   has no internal state — just construct it where you need it. The
   singleton overhead (private constructor, instance management) is
   only worth paying when the resource itself has lifecycle.

## Do / Don't

| Do | Don't |
|---|---|
| Implement a port from `../domain/ports` when domain has a stake | Export bare functions that bypass the port |
| Port-less adapter for purely presentational concerns (toast, modals) | Invent a domain port for UI-only behavior |
| Cast untyped data at the first line that touches it | Return `unknown` and cast in upper layers |
| Use `private constructor` + `getInstance()` for stateful resources | Use singletons for stateless HTTP clients |
| Reset module-scope `instance` to `null` in `terminate()` | Cache a terminated handle and hand it out again |
| Translate native types (`MessageEvent`, `Response`) to domain types | Leak `MessageEvent` / `AxiosError` into port signatures |
| Throw with context (`new Error(\`Failed to fetch /notes: ${status}\`)`) | `throw err` with no message — the stack is not enough |
| One adapter per external system | Cram HTTP + worker + localStorage into one class |

## Testing notes specific to this layer

Adapters are tested **end-to-end against a fake of the external
system**, not via inner mocks. The right tools per resource type:

| Resource | Test approach |
|---|---|
| HTTP / REST | MSW (Mock Service Worker) intercepting real `fetch` |
| Web Worker | Spawn the worker in a test runner with `jsdom-worker` or fake the `Worker` global |
| `localStorage` / `sessionStorage` | jsdom provides these natively — assert against the real store |
| Third-party SDK | Wrap in a port, stub the port in upstream tests, integration-test the adapter alone |

**Anti-pattern: mocking the adapter to test the use case.** The use
case accepts the **port interface** as a parameter — pass a hand-rolled
stub (`{ add: vi.fn(), list: vi.fn() }`) that satisfies the port.
`jest.mock('./api-adapter')` couples your test to a path that may
not exist in the next refactor.

If the adapter holds significant logic (retries, exponential backoff,
JSON shape validation), extract that logic into a pure helper in
`infrastructure/` and unit-test it directly. The adapter's
integration test then only needs to verify the wiring.
