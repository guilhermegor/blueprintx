# **FAQ**

Common questions about using and extending BlueprintX.

> **See also:** [Get Started](get-started.md) · [CLI Reference](cli-reference.md) ·
> [Contributing](contributing.md).

---

## What is BlueprintX?

A Make + bash scaffolding tool that generates opinionated Python and TypeScript project
skeletons (DDD service, MVC service, minimal library, React SPA) with CI, pre-commit, tests,
and docs wired in. It is not a Python application — the Python code lives in `templates/` and is
copied into scaffolded projects.

## How do I scaffold a project?

`make new`, then answer the prompts (language → skeleton → project name). See
[Get Started](get-started.md).

## How do I add a new skeleton?

Create `templates/<name>/` with a `skeleton.meta` descriptor, add a scaffold script under
`bin/scaffold/`, and the menu discovers it automatically. See [Contributing](contributing.md).

## Online vs offline scaffolds — what's the difference?

If you connect a GitHub remote, the scaffold ships GitHub-only assets (Actions workflows,
CODEOWNERS, PR template). Without one, it ships an offline git-diff workflow instead. Library
projects also switch versioning: online = tag-driven, offline = a local `make bump_version`.

## How is BlueprintX itself versioned?

The version is the git tag. Cut a release from the **Release** GitHub Action (enter the version
once); `blueprintx --version` resolves it via `git describe` from a checkout, or a stamped
literal for a packaged install. See the [Changelog](changelog.md).

## Which install methods are supported?

Homebrew, Chocolatey, Snap, apt, and `make install` from a clone — see the project README.
