# **Examples**

Worked, end-to-end walkthroughs of the skeletons BlueprintX scaffolds. Each links into the
relevant skeleton's own example set.

> **See also:** [Get Started](get-started.md) to scaffold your first project.

---

## DDD Service (Native DB)

- [External API calls](py-examples/ddd-external-api.md) — consume a third-party API behind a port.
- [Wiring with FastAPI](py-examples/ddd-usage-examples.md) — expose the service over HTTP.
- [Bank balance alert](py-examples/ddd-bank-balance-alert.md) — a complete multi-port example.

## DDD Service (ORM DB)

- [Usage with SQLAlchemy](py-examples-orm/ddd-orm-usage-examples.md) — session management + wiring.
- [External API calls](py-examples-orm/ddd-orm-external-api.md) — swapping providers via ports.
- [Bank balance alert](py-examples-orm/ddd-orm-bank-balance-alert.md) — the multi-port example, ORM.

## Other skeletons

The MVC service, lib-minimal, and React SPA skeletons ship their own runnable reference code
(a sample entity/view/controller, a sample module, a sample capability). Scaffold one with
`make new` and read its in-repo `docs/` and `CLAUDE.md` for tier-specific examples.
