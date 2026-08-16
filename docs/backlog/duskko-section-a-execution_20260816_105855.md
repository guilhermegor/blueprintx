# Duskko — execução do corte completo da seção A

**Criado:** 2026-08-16 · **Base:** `main` @ `198d09d` (PR #177 + #178 mergeadas, sem release)
**Origem:** a "Recomendação" de `duskko-blockers_20260816_110000.md`, escolha do dono: **grupos 1–5**

Este arquivo é o registro de execução. O arquivo de triagem continua sendo a fonte do *porquê*
de cada issue estar na fila; aqui fica o *estado* de cada uma.

⚠️ **Scaffolding é cópia one-shot.** Tudo que entrar depois do `make new` do duskko vira backfill
manual (#109). É por isso que estas 11 issues vêm antes do scaffold.

---

## Sequência de PRs

Issues relacionadas viajam na mesma branch/PR — separar por issue geraria 11 PRs que tocam os
mesmos arquivos de `templates/python-common/`.

| PR | Grupo | Issues | Tema |
|----|-------|--------|------|
| A | 1 | #126, #146, #156, #123 | atrito de CI/commit que já mordeu neste repo hoje |
| B | 2 | #141 | gate de idioma da documentação (projeto bilíngue, 2 devs) |
| C | 3 | #128, #120, #150 | núcleo de ingestão — o produto do duskko |
| D | 4 | #119 | `queries/<engine>/` + `load_query` — o que o duskko substitui por API |
| E | 5 | #125, #122 | box Windows corporativo do Werner |

---

## PR A — atrito de CI/commit (grupo 1) — ✅ ENTREGUE

Branch `feat/ci-friction-gates-126`. Verificado: **5/5 tiers Python** via
`bin/ci/scaffold_lint_test.sh`, unit + integração.

- [x] **#126** — a premissa da issue estava **desatualizada**; a causa raiz medida era outra
      - [x] medido: no **template** o `codespell` **já não** está inscrito no stage `commit-msg`
            — o `default_stages` da #158 fechou isso. `pre-commit run codespell
            --hook-stage commit-msg` responde *"No hook with id `codespell` in stage
            `commit-msg`"*.
      - [x] a causa raiz real: o `default_stages` **nunca foi aplicado ao config deste repo**,
            então os 5 hooks locais `always_run` (incl. **dois `mkdocs build --strict`**) rodavam
            duas vezes por commit. Corrigido.
      - [x] vocabulário: medido, não chutado. Os dois `.codespellrc` divergiram nos **dois
            sentidos** (30 palavras faltando no template, 25 na raiz) e o lado **desatualizado
            era o template** — ou seja, só os projetos gerados pagavam. União aplicada.
      - [x] **gate novo `bin/ci/check_codespell_sync.sh`** — a palavra não é a causa raiz, a
            divergência é. Controle negativo provado nos dois sentidos.
      - [x] pré-voo: `make check_commit_msg FILE=<p>` / `FILE=<p> ./tasks.sh check_commit_msg`.
            Usa `pre-commit run --hook-stage commit-msg`, isto é, **os próprios hooks do
            projeto** — não pode divergir do que o commit vai exigir.
      - [x] a armadilha do `*.txt` **deixou de existir**: usando o pre-commit em vez de chamar
            `codespell <file>` à mão, não há `skip` list no caminho.
      - [x] 🔴 **bônus achado no caminho:** `tasks.sh` chamava `print_status` sem nunca fazer
            source de `lib/common.sh`. Medido: `./tasks.sh init` saía **127** em
            `enable_repo_rules` — logo `enable_repo_rules` e `enable_security` **nunca rodaram
            em nenhum projeto scaffoldado**. Invisível para quem usa `make`, e `tasks.sh` é
            justamente a interface do box **sem make** (Windows do Werner). Corrigido + teste.
- [x] **#146** — guard de pre-push: índice não-vazio significa commit rejeitado
      - [x] `bin/check_clean_index.sh` + hook `local` no stage `pre-push`
      - [x] `--hook-type pre-push` já era instalado pelo `bin/precommit.sh` — confirmado
      - [x] should-fail + **prova de mutação**: desligando o guard, exatamente o teste de
            controle negativo falha; restaurado, passa
      - [x] guarda o **índice**, não a árvore suja (edição não-staged ao dar push é rotina)
- [x] **#156** — gate de `actionlint` (o `yamllint` não valida workflow)
      - [x] premissa **verificada no mesmo arquivo**: `yamllint` exit **0**, `actionlint`
            exit **1** em `pull_request_review_thread`
      - [x] `bin/lint_actions.sh` (resolve, não instala) + hook + CI + `Makefile`/`tasks.sh`
      - [x] falha quando a descoberta casa **zero** arquivos — provado
      - [x] `find` agrupado — provado com um **diretório** chamado `decoy.yaml`
      - [x] CI instala com versão pinada **e SHA-256 verificado**; `LINT_ACTIONS_REQUIRED=1`
            transforma o skip gracioso em falha (skip na CI é placebo)
      - [x] `SHELLCHECK_OPTS` na severidade da casa
      - [x] **gate irmão na raiz** `bin/ci/check_actions.sh`, que linta os workflows do repo
            **e os de dentro de `templates/`** — é o que teria pego os defeitos abaixo
      - [x] 🔴 **8 defeitos reais achados na primeira execução**, todos em workflows que já
            ships: `actions/cache@v3` (versão que o GitHub **não roda mais**) em 3 tiers,
            `softprops/action-gh-release@v1`, `SC2046` em 2 workflows de release, e um output
            `workflow_call` cuja expressão só podia resolver para string vazia (zero
            consumidores → removido). 7 corrigidos; o 8º é falso-positivo de localização.
- [x] **#123** — gate de work-ledger bloqueia permanentemente todo PR de bot
      - [x] isenção pelo sufixo `[bot]`, na **fronteira de I/O** (`pr_author_login`), regra
            pura separada (`is_bot_author`)
      - [x] lê `pull_request.user.login` do `GITHUB_EVENT_PATH`, **nunca** `GITHUB_ACTOR`
      - [x] actor só quando não há payload de PR; payload ilegível → **fecha**
      - [x] 9 testes, ambos os sentidos nomeados, incl. o caso do humano-como-actor

**Extra fora das 4 issues, mas necessário para elas não serem decorativas:**
`bin/ci/scaffold_lint_test.sh` rodava só `make lint` + `make unit_tests` — nunca os testes de
**integração**, que são o único lugar onde um `bin/*.sh` é de fato **executado**. Os 30 testes
de integração de cada tier viajavam sem nunca rodar. Agora rodam.

## PR B — idioma (grupo 2)

- [ ] **#141** — `bin/check_comment_language.py` (existe em `recon_al_cvm`, ausente dos templates)
      - [ ] **a calibração É a entrega** — 1º rascunho deu 19 achados, 18 falsos
      - [ ] casar **palavras funcionais** do idioma, nunca acento
      - [ ] redigir antes de casar, nesta ordem: spans de crase dupla → crase simples → aspas →
            URLs → tokens pontuados → siglas em CAIXA ALTA (inclusive acentuadas) → termos de arte
      - [ ] 🔴 ler comentários como **blocos**, não linhas (citação atravessa linhas)
      - [ ] redação **preserva comprimento** (N espaços) para o achado nomear a linha certa
      - [ ] `.py` exato via `tokenize` + `ast.get_docstring`; `#`/`--` só linha-cheia nos demais
      - [ ] escape hatch por **linha** (`lang:pt-ok`), nunca por bloco

## PR C — núcleo de ingestão (grupo 3)

- [ ] **#128** — disciplina de contrato de ingestão (8 lições) + gates de colisão de nome e de
      população de `__all__`
- [ ] **#120** — seam `raw_workspace` (retenção de artefato bronze) — nunca foi entregue
- [ ] **#150** — cachear download de vendor diário-estável dentro do seam

## PR D — queries / SQLite (grupo 4)

- [ ] **#119** — layout `queries/<engine>/` + resolver `load_query` + guard de runtime para config
      git-ignorada (`src/config/queries/` existe e está **vazio** nos templates)

## PR E — box Windows do Werner (grupo 5)

- [ ] **#125** — pinar `poetry-plugin-export` no instalador de bootstrap, não só como dev-dep
- [ ] **#122** — `to_absolute` público em toda passagem para processo externo

---

## Verificação (toda PR)

- `bash bin/ci/scaffold_lint_test.sh <tier>` em **cada tier afetada** — não só na raiz.
  Verificar na versão que o **projeto gerado** pina, nunca na raiz do template
  (lição `verify-with-the-version-the-project-pins`).
- Todo gate novo precisa de **controle negativo** (provar que consegue falhar), e de entrar na
  **copy-list mantida à mão** do scaffold — o tell é a CONTAGEM de testes, nunca a cor
  (lição `a-new-test-must-be-added-to-the-hand-maintained-copy-list`).
- Um gate vive em **4 superfícies**: hook de pre-commit, step de CI, `Makefile`, `tasks.sh`
  (lição `wire-a-gate-into-the-recipe-developers-actually-run`).
- Cards do kanban: o hook só move o card da issue que originou a branch. Bundlar N issues deixa
  N-1 cards parados — **mover à mão**.

## Fora deste corte

Seções B e C da triagem, mais os itens de A que ficaram de fora dos grupos 1–5 (#116, #144, #148,
#117, #127, #124, #152, #111, #145, #130, #113, #110, #118, #121, #151, #161, #162). Backfill é
barato enquanto o duskko ainda não existe — e depois dele passa a ser #109.

## Depois

`make new` → python → `mvc-service-native-db` → nome `duskko`.
