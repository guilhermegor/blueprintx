# CLAUDE.md — docs/

This file guides Claude Code when working inside the `docs/` directory.
It must be updated whenever a new file is added, a file is removed, or a major structural change is made to any document.

---

## 1. File index

| Path | Type | Purpose |
|------|------|---------|
| `index.md` | Utility page | Site home — logo, tagline, scaffold quick reference, links to all sections |
| `get-started.md` | Utility page | Installation and first-run instructions, requirements, key highlights |
| `ddd-service-native-db.md` | Skeleton overview | DDD hexagonal scaffold using native DB drivers (psycopg2, sqlite3, etc.) |
| `ddd-service-orm-db.md` | Skeleton overview | DDD hexagonal scaffold using SQLAlchemy ORM |
| `lib-minimal.md` | Skeleton overview | Lean Python library starter with packaging, tests, and CI |
| `examples/ddd-usage-examples.md` | Example walkthrough | Wiring DDD layers end-to-end; FastAPI integration; swapping implementations |
| `examples/ddd-external-api.md` | Example walkthrough | Consuming external APIs (stock exchange); swapping providers via ports |
| `examples/ddd-bank-balance-alert.md` | Example walkthrough | Complete multi-port DDD example (native DB) |
| `examples-orm/ddd-orm-usage-examples.md` | Example walkthrough | Wiring DDD layers with SQLAlchemy ORM; session management |
| `examples-orm/ddd-orm-external-api.md` | Example walkthrough | Consuming external APIs in an ORM-based DDD service |
| `examples-orm/ddd-orm-bank-balance-alert.md` | Example walkthrough | Complete multi-port DDD example (ORM) |

---

## 2. Naming and nav rules

### File naming

- All filenames must be **kebab-case** with a `.md` extension.
- Skeleton overview files are named after their skeleton: `ddd-service-native-db.md`, `lib-minimal.md`.
- Example files are prefixed with the skeleton they illustrate: `ddd-external-api.md`, `ddd-orm-bank-balance-alert.md`.

### Subdirectory pattern

| Directory | Contents |
|-----------|----------|
| `examples/` | Example walkthroughs for the **native-DB** DDD skeleton |
| `examples-orm/` | Example walkthroughs for the **ORM** DDD skeleton |

Future skeletons follow the same pattern: `examples-<skeleton-name>/`.

### MkDocs nav coupling

Every new file **must** be registered in `mkdocs.yml` under `nav:` in the same commit it is created. Never leave a file unregistered — MkDocs will silently omit it from navigation.

Current nav shape for reference:

```yaml
nav:
  - Home: index.md
  - Get Started: get-started.md
  - Python:
      - DDD Service (Native DB):
          - Overview: ddd-service-native-db.md
          - Example - <title>: examples/<filename>.md
      - DDD Service (ORM DB):
          - Overview: ddd-service-orm-db.md
          - Example - <title>: examples-orm/<filename>.md
      - Lib Minimal: lib-minimal.md
```

When adding a new skeleton, add a new group under `Python:`. When adding a new example, append it under the relevant skeleton group.

---

## 3. Content structure per document type

### Type A: Skeleton overview

Files: `ddd-service-native-db.md`, `ddd-service-orm-db.md`, `lib-minimal.md`

Required sections in order:

1. **H1 title** — bold, descriptive: `# **Skeleton Name (subtitle)**`
2. **Intro blurb** — 1-2 paragraphs: what the skeleton is, its design philosophy, and the key technology it uses.
3. **Key differences table** *(optional)* — used when a skeleton is a variant of another (e.g., ORM vs native). Columns: Aspect | Native DB | This template.
4. **Expected layout** — fenced code block (`bash`) showing the full directory tree after scaffolding.
5. **Folder descriptions** — table with columns: `Folder | Purpose | Expected Content`. Cover every top-level directory in the layout.
6. **Layers** — one `###` subsection per DDD layer (Domain, Application, Infrastructure, Modules). Each subsection includes:
   - Bold "What goes here:" sentence.
   - At least one annotated Python code snippet.
7. **Rules of thumb** — table with columns: `Layer | Responsibility`. Summarises each layer in one line.
8. **Learn more** — bulleted list of links to the skeleton's example walkthroughs, each with a one-line description.
9. **Acknowledgments** *(optional)* — credit to foundational works (e.g., Eric Evans for DDD skeletons).

### Type B: Example walkthrough

Files: `examples/*.md`, `examples-orm/*.md`

Required sections in order:

1. **H1 title** — bold, descriptive: `# **Skeleton — Example Title**`
2. **Intro line** — one sentence describing what this example demonstrates, followed by a `> **See also:**` blockquote linking back to the overview and sibling examples.
3. **Scenario sections** — one `##` section per scenario or concept demonstrated. Each section contains:
   - A brief context sentence (what problem this solves or pattern it shows).
   - One or more annotated code blocks. Comments in code must explain *why*, not just what.
4. **No standalone "Key takeaways" section** — insights should be embedded naturally as comments or brief prose within each scenario section.

### Type C: Utility page

Files: `index.md`, `get-started.md`

No fixed section template — these pages serve different purposes. Preserve the intent of each:

| File | Intent | Key sections to maintain |
|------|--------|--------------------------|
| `index.md` | Landing page / hub | Logo, tagline, Python scaffolds overview, local docs instructions, scaffold quick reference |
| `get-started.md` | First-run guide | Numbered setup steps, requirements, feature highlights |

When adding a new utility page, document its intent and key sections in the table above.

---

## 4. Maintenance rules

Apply these rules every time a change is made to the `docs/` directory:

| Event | Required actions |
|-------|-----------------|
| New file added | 1. Add a row to the **file index** (Section 1). 2. Register the file in `mkdocs.yml` nav. Both changes go in the same commit. |
| File removed | 1. Remove its row from the **file index**. 2. Remove its entry from `mkdocs.yml` nav. Fix any cross-links in other docs that pointed to it. |
| File renamed | Update the file index path, the `mkdocs.yml` nav entry, and all internal cross-links. |
| New skeleton added | 1. Create its overview file following Type A structure. 2. Create its `examples-<skeleton>/` subdirectory and at least one example following Type B. 3. Add both to the nav under a new group. 4. Update Sections 1, 2, and 3 of this CLAUDE.md. |
| Major content restructure | Update the relevant content structure description in Section 3 to reflect the new pattern. |
