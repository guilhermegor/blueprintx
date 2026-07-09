# CLAUDE.md — `_internal/ports/`

Private behavioural interfaces for this library — the **ports** of hexagonal
*ports-and-adapters*. Everything here is an **abstract contract**, not an implementation, and
lives under the `_internal/` package, so it ships inside the wheel but is **not part of the
public API**. Consumers import the concrete adapters, never `_internal.ports`.

## Port vs adapter

A **port** is the abstract operation a family of concrete classes (the **adapters**) all
implement, so callers treat any adapter polymorphically and every new variant conforms to the
same shape. When two macro-sections share one operation (e.g. an `export`, a `read`), name that
operation as a port here; the concrete classes are the adapters.

- **One port per file** (`example_port.py`, `submission_writer.py`, …): a module docstring plus
  a single ABC. New shared operation → new file.
- **`metaclass=ABCTypeCheckerMeta`** on the port gives both abstract-method enforcement (a
  partial adapter fails at instantiation) and runtime type checking of every call.
- **Adapters inherit the port and its metaclass** — never redeclare `metaclass` on a subclass;
  Python inherits it (the `check_typing` hook already skips a class with bases for that reason).
- **Generic over its value** (`Generic[T]`): an adapter narrows the type through the type
  parameter (`class CsvHandler(ExamplePort[pd.DataFrame])`) rather than by re-annotating the
  override, keeping the concrete signature Liskov-compatible.
- `ports/__init__.py` re-exports every port so callers use one import:
  `from <pkg>._internal.ports import ExamplePort`.
- Ports stay **private** — never add one to the library's public `__all__`.

`ExamplePort` is a reference — copy `example_port.py` per real shared operation and delete the
example once your own ports exist. Drop this whole sub-package if the library has no
macro-sections sharing a behavioural contract.
