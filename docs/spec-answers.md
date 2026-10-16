# **Named-key spec answers (`--spec`)**

`blueprintx new` normally answers its prompts one of two ways: interactively, or by
piping a fixed sequence of stdin lines (`printf 'n\n%.0s' {1..12} | blueprintx new ...`).
The second form answers by **position** — line 3 is whatever the third prompt happens to
be. Add a prompt anywhere in a scaffold script and every stored answer after it silently
answers the wrong question; nothing fails loudly (blueprintx#481).

`--spec <file>` answers the same prompts by **name** instead. A name does not move when a
prompt is inserted or reordered.

```bash
blueprintx new --spec my-project.spec              # scaffold from the spec
blueprintx new --spec my-project.spec --dry-run     # print every resolved answer, write nothing
```

Both the interactive flow and the raw piped-stdin flow keep working exactly as before —
`--spec` is a third, additive path, not a replacement.

## Spec file format

A spec file is a `KEY=value` list, one pair per line — the same shape as a skeleton's own
`skeleton.meta` (`#` comments and blank lines ignored, parsed with `grep`/`cut`, no new
parser dependency). A key absent from the file takes its documented default; an absent
file is a valid (all-default) spec.

```
# my-project.spec
project_name=my-lib
project_description=A demo library
language=python
skeleton=lib-minimal
license=MIT
github_username=my-github-user

logs=n
otel=n
docker_compose=n
publish_pypi=y
publish_test_pypi=y
consume_private=n
review_bot_roster=y
git_remote=n
```

## Top-level keys

Answer `bin/blueprintx.sh`'s own prompts (before any scaffold script runs):

| Key | Required | Default | Meaning |
|---|---|---|---|
| `project_name` | yes | — | Project/folder name. Same validation as the interactive prompt. |
| `project_description` | no | empty | One-line description. |
| `project_root` | no | `$PWD` | Parent directory the project is created under. |
| `language` | yes | — | Must match a discovered `templates/*/skeleton.meta` `language=`. |
| `skeleton` | yes | — | Must name a directory under `templates/` with a `skeleton.meta`. |
| `license` | no | `MIT` | One of the choices `prompt_license` offers. |
| `docs_locale` | no | `en` | `en` or `pt-BR`, the choices `prompt_docs_locale` offers. Any other value stops the run before anything is created, naming the key. |
| `github_username` | no | `$GITHUB_USERNAME` env, else `gh` CLI, else prompt | Passed through as `GITHUB_USERNAME` to the scaffold script. |

## Value rules and flags

- **Values are trimmed.** Leading and trailing whitespace, including the `\r` a spec saved with
  CRLF line endings leaves on every line, is stripped from every value, so `otel=yes` reads the
  same on Windows. Whitespace inside a value is kept. A value that is blank after trimming
  means the key's default, for every key. Keys are not trimmed: write `otel=yes`, never
  ` otel=yes` or `otel = yes`, or the line is ignored and the default applies.
- **y/n keys** take `y`/`yes`/`true` or `n`/`no`/`false`, in any case; an empty value means the
  key's default. Any other value (for example `maybe`, or a mistyped `yes`) **stops the run before anything is
  created**, naming the key. It is never read as `n`.
- **`--dev`** scaffolds into a fresh temp directory instead of `project_root`/`$PWD`, and
  **`--clean`** (with `--dev`) deletes it on exit — the same as the interactive flow, and the
  closing notice says the printed project path will not exist afterwards. With `--dev`,
  `project_root` is ignored.
- **`--dry-run`** prints the resolved answers and the structure, and creates nothing.

## Per-skeleton keys

The translation from a named key to the scaffold script's actual `read` call order lives
in **one place**: `spec_stdin_for_skeleton()` in `bin/lib/spec.sh`. The scaffold scripts
themselves (`bin/scaffold/python_*.sh`) still read positional stdin at each prompt — they
are not edited by this mechanism — so when one of them gains a new prompt, updating that
one function is what keeps every spec-driven caller correct, instead of every stored
answer string everywhere.

Named-key support ships per skeleton. Today: the six Python tiers, `ts-lib`, `etcher-chromeos` and `ventoy-usb`. Call
`spec_skeleton_supported <skeleton>` to check before relying on `spec_stdin_for_skeleton`.

### DDD and API tiers (`ddd-service-native-db`, `ddd-service-orm-db`, `api-service-native-db`)

`api-service-native-db` asks the same prompts in the same order as the DDD tiers, so it shares
their key map (blueprintx#668). `tests/test_spec_answers.sh` compares the two scaffold scripts'
prompt sequences, so a prompt added to one of them fails there instead of silently misaligning
the stored answers.

| Key | Default | Notes |
|---|---|---|
| `docker_compose` | `n` | `y` also reads `docker_db_backend` (`postgresql`\|`mariadb`\|`mysql`). |
| `storage` | `n` | Schema-less file storage (JSON/CSV/joblib). DDD and API tiers; MVC has no such prompt. |
| `data_dir` | `n` | `y` also reads `data_dir_base` (default `logs`) and `data_dir_dated`. |
| `webhook` | `n` | `y` also reads `webhook_platform` (`teams`\|`slack`\|`custom`). |
| `otel` | `n` | OpenTelemetry OTLP log export. |
| `email` | `n` | `y` also reads `email_backend` (`outlook`\|`smtp`). |
| `env_wise_config` | `n` | Split `inputs.yaml`/`outputs.yaml` into `_dev`/`_prd` pairs. |
| `review_bot_roster` | `n` | `y` ships `.review-bots.yaml` (a PR review bot is expected). |
| `git_remote` | `n` | `y` only adds `origin` here, answering the one remote prompt; creating the repo is mapped for `ts-lib` only (see below), so leave `n` for unattended/CI runs. |

### MVC tiers (`mvc-service-native-db`, `mvc-service-orm-db`)

Same as the DDD tiers, **minus `storage`** (MVC has no schema-less storage prompt), **plus**:

| Key | Default | Notes |
|---|---|---|
| `pipeline_intent` | `n` | `y` selects the multi-intent (`PIPELINE_INTENT` dispatch) pipeline shape. The scaffold script also accepts this directly as the `MULTI_PIPELINE_OPTIN=true` environment variable — set that instead of going through stdin if calling the scaffold script yourself. |

### `lib-minimal`

| Key | Default | Notes |
|---|---|---|
| `logs` | `n` | Ships the in-repo logging helper (`utils/logs.py`). |
| `otel` | `n` | Ships the OTLP log-export helper (`_internal/utils/otel_logging.py`). |
| `docker_compose` | `n` | Same shape as the service tiers. |
| `publish_pypi` | `y` | Ship `release-pypi.yaml`. |
| `publish_test_pypi` | `y` | Ship `release-test-pypi.yaml`. |
| `consume_private` | `n` | Append a commented private-source template to `pyproject.toml`. |
| `review_bot_roster` | `n` | Same as the service tiers. |
| `git_remote` | `n` | Same as the service tiers. |

### `ts-lib`

`bin/scaffold/ts_lib.sh` reads, in this order: `review_bot_roster`, `otel`, then the git
remote block. `tests/test_spec_answers.sh` pins that order two ways: it checks the prompts
`main()` calls, and it runs the whole scaffold against a stubbed `gh`, where a misaligned
answer shows up as the wrong visibility or the wrong protection payload.

| Key | Default | Notes |
|---|---|---|
| `review_bot_roster` | `n` | Same as the service tiers. |
| `otel` | `n` | Ships the OTLP log-export helper. |
| `git_remote` | `n` | `y` adds `origin`. Alone it creates nothing on GitHub. |
| `create_repo` | `n` | `y` creates the repo on GitHub and pushes. Needs `git_remote=y`. |
| `repo_visibility` | `private` | `public` or `private`. Read only when `create_repo=y`. |
| `kanban` | `n` | `y` also creates the linked GitHub Project. Read only when `create_repo=y`. |
| `protect_branch` | `n` | `y` protects `main`. Read only when `create_repo=y`. |
| `human_reviewers` | `n` | `y` requires one approving review. Read only when `protect_branch=y`. |

**Protection can fail after the repo exists.** On a free GitHub plan, branch protection on a
private repo is refused (HTTP 403, "Upgrade to GitHub Pro"). By then the repo is created and
pushed. The scaffold prints "Failed to protect branch 'main'; adjust settings manually in
GitHub." and carries on, so the run still finishes with an unprotected `main`. Use
`repo_visibility=public` or a paid plan if you need `protect_branch=y` to take effect.

The repo slug is never a key: it is `github_username/project_name`, exactly what the
scaffold derives. Visibility defaults to `private`, not to the interactive menu's public,
because a repo made public by omission cannot be taken back; say `public` to publish.
`kanban` exists because the scaffold asks that question right after a successful push,
before it asks about protection, so a hidden constant would shift every later answer.

**Preflight (`create_repo=y` only).** Before any directory is made, the run needs `gh auth
status` to succeed and `gh repo view <owner>/<project_name>` to fail with a not-found error (the repo must not
exist). Any other lookup failure (network, token scope) is not read as "absent". Every
failure stops the run, names the cause and creates nothing. A missing
`github_username` is taken from `gh api user`. An unknown `repo_visibility`, or
`create_repo=y` with `git_remote=n`, stops the run naming the key, like any other bad value.
`--dry-run` prints every remote answer plus `repo_slug` and calls no `gh`.

```
git_remote=y
create_repo=y
repo_visibility=public
protect_branch=y
human_reviewers=n
```

### `ventoy-usb`

`bin/scaffold/ventoy_usb.sh` reads, in this order: `include_windows`, `include_android`,
`persistence_size_mb`, then `review_bot_roster` and the git remote block (the same one `ts-lib` uses).
`tests/test_spec_answers.sh` pins that order and runs the whole scaffold from a spec.

| Key | Default | Notes |
|---|---|---|
| `include_windows` | `y` | `n` skips the Windows ISOs and the `dotfiles/windows` installers. |
| `include_android` | `y` | `n` skips the Android ISOs. |
| `persistence_size_mb` | `4096` | A multiple of 1024, at least 1024; anything else stops the run naming the key. |
| `review_bot_roster` | `n` | Same as the service tiers. |
| `git_remote` | `n` | `y` adds `origin`. Alone it creates nothing on GitHub. |
| `create_repo` | `n` | `y` creates the repo on GitHub and pushes. Needs `git_remote=y`. |
| `repo_visibility` | `private` | `public` or `private`. Read only when `create_repo=y`. Defaults to `private`, as for `ts-lib`: a repo made public by omission cannot be taken back. |
| `kanban` | `n` | `y` also creates the linked GitHub Project. |
| `protect_branch` | `n` | `y` protects `main`. |

The folder tree is the same either way: the two switches only decide what is downloaded.
### `etcher-chromeos`

`bin/scaffold/etcher_chromeos.sh` reads, in this order: `default_os`, `review_bot_roster`, then
the git remote prompt.

| Key | Default | Notes |
|---|---|---|
| `default_os` | `chromeos-flex` | `chromeos-flex` or `fydeos`; stamped into the CLI as the `--os` default. Anything else stops the run naming the key. |
| `review_bot_roster` | `n` | Same as the service tiers. |
| `git_remote` | `n` | `y` adds `origin`. Creating the repo is not mapped for this tier. |

## Publish/registry keys are answer-only — they do not implement publishing

`publish_pypi`, `publish_test_pypi`, and `consume_private` answer `lib-minimal`'s
**existing** yes/no gate for which release workflow file the scaffold ships — nothing in
this seam performs a real publish, credential check, or registry call.

Any future spec key that *does* perform real publishing or registry verification (for
`lib-minimal` or a future `ts-lib`-shaped tier) must delegate that work to the
`publishprobe` tool (greenfield#26) instead of reimplementing credentials or publishing
here — scope note from blueprintx#481.

## Follow-up: TypeScript and future tiers

`react-spa-webpack` and any future skeleton not listed above have no entry in
`spec_stdin_for_skeleton` yet. `--spec` still resolves their top-level answers (project
name, language, skeleton, license, …); their scaffold-internal prompts stay interactive
until a named-key map is added for them, the same way the six Python tiers and `ts-lib` were —
`spec_skeleton_supported` returns `false` for them today. `blueprintx new --spec` **refuses**
such a skeleton before creating anything (a half-interactive run would hang an unattended
caller); `--spec ... --dry-run` still reports the resolved top-level answers with a warning.
The refusal is deliberately unconditional, not "only when stdin is not a terminal" (considered
in #636): `--spec` exists to run without a person, and a spec whose internal answers are
silently ignored in favour of live prompts would be a different, half-honoured contract.
`--spec` names a skeleton by exact equality, so two supported names joined by a space do not
match.

## Used by CI

`bin/ci/scaffold_lint_test.sh <skeleton>` drives its scaffold through
`spec_stdin_for_skeleton` (all-default: decline every opt-in, no remote — the same
"clean offline scaffold" baseline the old positional `printf` produced). Set
`SCAFFOLD_SPEC_FILE=/path/to/file.spec` to probe the harness against a specific spec
instead of the defaults, mirroring the existing `SCAFFOLD_PROJECT_NAME` override.
