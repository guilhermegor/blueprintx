# Scaffold prompts and non-terminal stdin

blueprintx#539. Every interactive y/n question the scaffolds ask goes through
`prompt_yes_no` in `bin/lib/common.sh`. Nothing in a scaffold or its libs reads stdin for a prompt
without passing the `prompt_can_read` guard.

## Why the guard exists

`read` consumes a non-terminal stdin without complaint. A non-interactive run (CI, `--dev`, a stray
line left on a pipe) would therefore answer a question nobody asked. For an opt-in such as OTEL that
means dependencies installed and files rewritten with nobody agreeing to it.

With no terminal on stdin, the variable is set to the prompt's default without ever calling `read`,
so a leftover `y` on the pipe can never flip an unattended run.

## The helpers

| Helper | Behavior |
|---|---|
| `prompt_can_read` | True when stdin may answer a prompt: a terminal, or a harness that feeds answers on purpose by exporting `BLUEPRINTX_STDIN_ANSWERS=1` (the `bin/lib/spec.sh` pipes). A stray piped line without that opt-in is never an answer. |
| `prompt_warn_default <prompt> [label]` | One stderr line saying a prompt fell back to its default because stdin is not a terminal. Stdout and exit status are untouched. |
| `prompt_read <var> <prompt> [label]` | `read -r -p` that leaves the variable empty, so the caller's own default applies, when `prompt_can_read` is false or stdin is at EOF. Without a readable stdin it also warns on stderr. |
| `prompt_yes_no <var> "$(prompt_main "Question? [y/N]: ")" [y\|n]` | Sets the variable to the literal `true` or `false`, the convention every `INCLUDE_*` / `USE_*` flag already uses. The prompt argument is fully rendered by the caller, so the helper stays agnostic to styling. |

## Choosing the default

The default is chosen per prompt, not globally. Hardcoding one default would trade one silent wrong
answer for another.

An opt-in defaults to `n`: installing dependencies or sending telemetry must never happen silently.
The one exception is a prompt whose safe unattended answer is yes, such as waiting for the first
deploy to finish after a confirmed Pages setup: it is a passive poll, not a mutation, so it passes
`y`.

| Prompt | Default | Reason |
|---|---|---|
| Branch protection | `n` | A GitHub API mutation (`enforce_admins`, required checks); an unattended run must not lock down a repo nobody confirmed. |
| Required reviews | `n` | Matches the pre-existing fallback: a solo maintainer with no required reviews. |
| Database Compose stack | `n` | Ships a whole database stack nobody asked for. |
| Schema-less storage | `n` | Adds a storage backend and chassis code. |
| Output layout | `n` | Changing the on-disk output layout must never happen silently; the fallback stays flat and not date-organised. |
| Webhook notifications | `n` | Adds outbound network calls to a platform nobody named. |
| E-mail sending | `n` | Same reasoning as webhooks. |
| OTEL | `n` | Installs telemetry dependencies and sends data to a collector; originally fixed inline in #519, now folded into the shared helper. |
| Multi-pipeline | `n` | Opt-in, default No; generates a whole dispatch trio nobody asked for. `MULTI_PIPELINE_OPTIN=true` is the sanctioned non-interactive override. |
| Config directory layout | `n` | Environment-wise config silently changes the on-disk shape of the generated project; an unattended run gets the single-file layout that pressing Enter gives. |
| Module Federation | `n` | Reshapes `webpack.config.js`; an unattended run must not pick a different build topology. |
| Dockerfile and nginx | `n` | Adds files nobody asked for. |
| Delivery script | `n` | Ships an extra script plus `package.json` entries. |
| Enable GitHub Pages | `n` | A GitHub API mutation; an unattended run must not publish a site nobody confirmed. |
| Wait for the first deploy | `y` | Passive poll after a confirmed Pages setup. |

The GitHub username, the React variant and the deploy target are not y/n prompts. With no terminal
the read is skipped, so a stray pipe line cannot answer as a username or pick a variant or target
nobody chose; they fall straight to `DEFAULT_GITHUB_USERNAME` and to the `1` default.

## The regression test

`tests/test_prompt_tty_guard.sh` has three legs.

- The helpers behave: a piped `y` is not an answer unless the harness opted in.
- The warning leg: piped without the opt-in, the fallback is announced on stderr only; with the
  opt-in nothing is printed there. A terminal cannot be simulated in the test, so that leg is
  covered by the opted-in assertion, which takes the same read path.
- The static leg: any bare `read` prompt in a scaffold or its libs must sit directly under a
  `prompt_can_read` guard. `while ... read` loops over files are not prompts.
