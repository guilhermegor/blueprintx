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

Named-key support ships per skeleton. Today: the six Python tiers. Call
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
| `git_remote` | `n` | `y` is out of scope for this seam — it needs a real `gh` session; leave `n` for unattended/CI runs. |

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

## Publish/registry keys are answer-only — they do not implement publishing

`publish_pypi`, `publish_test_pypi`, and `consume_private` answer `lib-minimal`'s
**existing** yes/no gate for which release workflow file the scaffold ships — nothing in
this seam performs a real publish, credential check, or registry call.

Any future spec key that *does* perform real publishing or registry verification (for
`lib-minimal` or a future `ts-lib`-shaped tier) must delegate that work to the
`publishprobe` tool (greenfield#26) instead of reimplementing credentials or publishing
here — scope note from blueprintx#481.

## Follow-up: TypeScript and future tiers

`react-spa-webpack`, `ts-lib`, and any future non-Python skeleton have no entry in
`spec_stdin_for_skeleton` yet. `--spec` still resolves their top-level answers (project
name, language, skeleton, license, …); their scaffold-internal prompts stay interactive
until a named-key map is added for them, the same way the six Python tiers were —
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
