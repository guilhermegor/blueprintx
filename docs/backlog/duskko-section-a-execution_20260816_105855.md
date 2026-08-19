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

**Segundo extra — `bin/ci/check_test_copy_lists.py`.** A copy-list de testes é mantida à mão
em cada um dos 5 scaffolds, e um teste esquecido lá é escrito, commitado e **nunca roda em
projeto nenhum**. 🔴 Antes do gate, o único sinal disponível era a **contagem** de testes — e ninguém a
compara com o esperado: uma rodada que soma 18 testes e continua mostrando 234 fica tão verde
quanto a que mostra 252. Mas a contagem é fraca mesmo quando lida, porque um total idêntico
esconde um teste que sumiu e outro que entrou. Por isso o gate não conta: ele compara
**conjuntos** — o conjunto de testes compartilhados alcançáveis por cada scaffold contra o
conjunto que existe em `templates/python-common/tests/unit/`, e nomeia cada ausente. Na primeira execução o
gate achou `test_startup_fragility_order.py` — o guarda do próprio fix da **#160** — ausente
das 5 tiers. Também documenta um buraco honesto: o `lib-minimal` vendoriza os utils sob
`_internal/` e por isso **não recebe os testes deles** (precisaria do mesmo
`rewrite_internal_imports` nos testes).

### Correções da review do CodeRabbit na PR #180

- [x] **`persist-credentials: false`** em `actions/checkout` — apontado em **1** job; aplicado
      nos **12** do arquivo, todos read-only. Corrigir só o apontado deixaria exatamente o
      *precedente* que a #141 existe para combater.
- [x] **`check_codespell_sync.sh` comparava minusculizado** — bug real e meu. O codespell
      separa a ignore-list em duas (`process_ignore_words`): entrada já minúscula filtra o
      dicionário; entrada com maiúscula vai para outro conjunto e só casa aquela capitalização.
      Logo `classe` e `Classe` **não** são intercambiáveis, e dobrar o caso antes de comparar
      declararia "in sync" dois configs que se comportam diferente — o gate cego para a deriva
      que existe para pegar. Agora compara verbatim **e** rejeita entrada com maiúscula.
- [x] **`pr_author_login` falhava aberto** quando `GITHUB_EVENT_PATH` estava setado mas o
      arquivo ausente: caía no `GITHUB_ACTOR`. Dentro de um workflow o payload é a única
      autoridade; qualquer falha em usá-lo agora retorna `""`. Teste nomeado adicionado.
- [x] **MD018** no ledger — linha começando com `#117`. Reescrito como lista, o que resolve
      estruturalmente em vez de depender de onde a linha quebra; varredura confirmou 0 em todo
      `docs/backlog/`.

## PR B — idioma (grupo 2) — ✅ ENTREGUE

Branch `feat/docs-language-gate-141`, empilhada sobre a PR A. Verificado nas **5 tiers**.

- [x] **#141** — `bin/check_comment_language.py` **portado** de `recon_al_cvm` (494 linhas, já
      calibrado em campo) em vez de reescrito. A escada: reusar o que existe e funciona.
      - [x] a calibração veio junta e foi **provada por mutação**: remover a redação de sigla,
            a de token pontuado, a preservação de comprimento ou o escopo-por-linha do escape
            faz **exatamente 1** teste falhar. Nenhuma das 4 regras é decorativa.
      - [x] 18 testes nomeados por classe de falso positivo em
            `tests/unit/test_comment_language_gate.py`
      - [x] controle positivo + negativo: pega português real (2 achados, linha certa) e passa
            nos 6 falsos positivos medidos (rótulos acentuados, `COM` da Microsoft, `emails.yaml`,
            `bradesco.com.br`, URL com `/para/que/nao`, citação atravessando 2 linhas)
      - [x] **os templates já passam**: 129 arquivos varridos nas 6 pastas, 0 achados — o gate
            entra verde, não com uma dívida a pagar
      - [x] duas melhorias sobre o original, ambas lições desta sessão: **falha quando a
            descoberta casa zero arquivos** (senão passa vaziamente para sempre) e **imprime a
            contagem no sucesso** (gate silencioso é indistinguível de gate ausente — medido:
            118 arquivos no mvc, 142 no ddd-native, 78 no lib-minimal)
      - [x] ligado nas 4 superfícies: hook, `make lint`, `tasks.sh lint`, step de CI
      - [x] adicionado às 5 copy-lists — e o gate `check_test_copy_lists.py` da PR A **provou**
            (26 → 27 testes compartilhados, todos alcançáveis)

Contagem por tier após a B: mvc-native **256**, mvc-orm **256**, ddd-native **251**,
ddd-orm **251**, lib-minimal **89** — todas +18, e 30 de integração em cada.

## PR C — núcleo de ingestão (grupo 3)

- [ ] **#128** — disciplina de contrato de ingestão (8 lições) + gates de colisão de nome e de
      população de `__all__`
- [ ] **#120** — seam `raw_workspace` (retenção de artefato bronze) — nunca foi entregue
- [ ] **#150** — cachear download de vendor diário-estável dentro do seam

## PR D — queries / SQLite (grupo 4) — ✅ ENTREGUE

**PR #191 mergeada** (`fa5ea9f`), issue #119 fechada. Branch `feat/queries-engine-layout-119`,
cortada de `main` @ `fdba82a` (pós-release v0.15.4).

- [x] **#119** — layout `queries/<engine>/` + resolver `load_query` + guard de runtime para config
      git-ignorada (`src/config/queries/` existia e estava **vazio** nos dois tiers native-db)
      - [x] **derivar, não checar**: `config/queries/<engine>/<table>__<purpose>.sql`. O engine é
            um **diretório**, nunca um prefixo de nome de arquivo — um prefixo declara o engine
            uma segunda vez e passa a poder discordar da primeira. Não existe caminho de código
            que entregue T-SQL a uma conexão SQLite, então nada precisa perceber.
      - [x] `load_query(str_filename, str_backend, path_queries_root)` **puro** em
            `templates/python-common/src/utils/queries.py` — separa a regra da fronteira de I/O
            (mesmo padrão de `is_bot_author`/`pr_author_login` da #123). O caller fino por tier
            (`src/config/query_loader.py`) injeta o engine e a raiz.
      - [x] **`active_backend()` é o leitor ÚNICO de `DB_BACKEND`** — mvc-native em
            `config/connection_db.py` (com `_DICT_BUILDERS` içado a módulo), ddd-native em
            `chassis/db_schema/application/database_factory.py`. No DDD o dict **não** foi içado:
            os builders são closures sobre `str_backend`, então içar não é drop-in — assimetria
            deliberada, não descuido.
      - [x] o loader **recusa** um nome com componente de diretório (`mssql/x.sql`): passar o
            engine no nome contornaria exatamente a checagem que ele existe para fazer
      - [x] a mensagem de erro **distingue** backend errado de nome errado — nomeia os engines
            cujo diretório *carrega* o arquivo (`EXISTS for: mssql, oracle`) ou diz
            `exists for no engine` + os diretórios presentes. Sem isso, typo e má configuração
            se leem idênticos.
      - [x] **6 testes** em `tests/unit/test_queries.py`, nomeados por classe de falha, com
            **prova de mutação**: trocando `/ str_backend` por um glob, exatamente o teste de
            roteamento (`..._when_two_engines_carry_the_same_name`) falha; restaurado, passa.
      - [x] exemplo `.sql` em cada engine com o header `database / table(s) / purpose`, e os
            dois são **deliberadamente diferentes** (`TOP (n)` + `[bracket]` no tsql) para que o
            roteamento seja observável, não decorativo
      - [x] 🟢 **bônus da lição, medido:** sqlfluff resolve config **por diretório**, então cada
            `queries/<engine>/.sqlfluff` declara seu dialeto e **uma única passada** cobre os
            dois. Deletado o conselho (rejeitado) de "rodar uma passada por `--dialect`" de
            `.sqlfluff`, `.sqlfluffignore` e `bin/lint_sql.sh`. Controle negativo provado:
            removendo `mssql/.sqlfluff`, o T-SQL vira `Found unparsable section` sob
            `dialect=sqlite` — a falha de produção reproduzida no linter; restaurado, exit 0.
      - [x] `.env.example` **seccionado por escopo** nas 4 tiers com `DB_BACKEND` (não só nas
            native): a lista plana é a união de seis backends, então cinco sextos dela é inerte
            e lê como configuração viva. Cada bloco agora nomeia os `DB_BACKEND` que o leem.
      - [x] AC do `tasks.sh init`: **já satisfeito** — `bin/ensure_env.sh` nunca sobrescreve um
            `.env` existente. Isso está correto (não pode pisar em credenciais) e é justamente o
            que torna a deriva permanente, então o guard de runtime é o backstop. Documentado
            com ⚠️ em `src/config/CLAUDE.md`, não deixado como conhecimento tácito.
      - [x] docs: seção "derive, don't check" + a tabela de roteamento do guard em
            `templates/python-common/src/config/CLAUDE.md`, mais as duas páginas
            `docs/py-*-service-native-db.md` e o "Adding a new DB backend" das duas CLAUDE.md
            de tier (a instrução antiga apontava para um dict que não existe mais)

**Verificação:** 8 gates da raiz verdes (copy-lists **32** testes compartilhados alcançáveis nas
5 tiers, spell, shell, actionlint, meta, version-sync, codespell-sync, docs build) + os 5 tiers
por `bin/ci/scaffold_lint_test.sh`.

### 🔴 Achado no caminho: `exclude` do mypy não cobre módulo importado (#190)

Adicionar `config/query_loader.py` deixou o **ddd-native vermelho com 20 erros de mypy** em
`chassis/db_schema/infrastructure/*_handler.py` — arquivos que a PR não toca.

`mypy.ini` traz `exclude = ^chassis/…`, mas **`exclude` só pula DESCOBERTA de arquivo, não
módulo alcançado por `import`**. O exclude valia só enquanto nada fora de `chassis/` o
importasse — propriedade da fiação da aplicação, não da config. `query_loader` importa
`database_factory` (para ler o backend ativo), que importa os seis handlers: **31 → 33
arquivos checados**, e 20 erros antigos apareceram pela primeira vez.

Correção: `[mypy-chassis.*] ignore_errors = True` — `ignore_errors` é o setting que segue o
módulo, tornando verdadeira a intenção que o comentário do `exclude` já declarava. Depois:
`Success: no issues found in 33 source files` (os 2 arquivos extras continuam sendo checados;
só os erros do chassis é que estão silenciados). A dívida real fica na **#190**.

⚠️ **Duas hipóteses erradas antes da medição certa** — registradas porque o custo foi real:

1. *"É `mypy = ">=1.8.0"` sem teto deixando entrar o major 2.x."* Plausível e falsa. Teto
   `<3.0` **não exclui nada** (2.3.1 satisfaz `<3.0`); teto `<2.0` resolveu **1.20.2** e
   falhou igual, com os mesmos 20 erros mais um. A versão nunca foi a variável. O teto foi
   revertido nas 5 tiers.
2. *"É pré-existente, não é minha mudança."* Também falsa. O controle que devia ter vindo
   **primeiro** — o mesmo tier em `origin/main` limpo — passa: `Success: no issues found in
   31 source files`, com o **mesmo mypy 2.3.1** que eu havia acusado.

Lição procedural: **"nenhum arquivo meu aparece na lista de erros" não é evidência de que a
minha mudança não causou os erros.** Uma aresta de import muda *o que o checker olha*, então
um arquivo que ninguém editou passa a falhar por causa de uma edição em outro lugar. Rodar o
controle em árvore limpa vem antes de teorizar sobre a dependência.

### Review do CodeRabbit na PR #191 — 6 aceitos, 1 recusado

🔴 **O achado sério era meu e era explorável.** `load_query` validava o *filename* como
segmento único e aceitava **qualquer coisa** no *backend* — e o `/` do `pathlib` **substitui**
o lado esquerdo quando o direito é absoluto. Reproduzido antes de corrigir: sem o guard,
`DB_BACKEND=..` retornou `'ESCAPED-SECRET'` de um arquivo semeado fora da raiz. Validar um
operando e não o outro era o defeito; agora ambos passam pela mesma regra, e `active_backend()`
valida contra `SET_BACKENDS` nos dois tiers native. Isso desfez a assimetria que a PR chamava
de deliberada: os builders do DDD agora recebem o backend como argumento, então o dict vive a
nível de módulo e os nomes das engines têm **uma** fonte. A justificativa antiga era verdadeira
para o código como estava — mas o código não precisava estar assim.

Outros aceitos: `DB_PORT` passa a shipar **comentado** nas 4 tiers (o default por backend já
existia em `_compose_dsn`; o seed é que o anulava para cinco das seis engines); `LIMIT 1000` no
sqlite para casar o `TOP (1000)` do mssql (um filename é um contrato — o result set não pode
depender do backend); cabeçalho do `.sql` corrigido (medido: SQLite **aceita** colchetes e
rejeita `TOP`, o oposto do que eu havia escrito no arquivo que ensina a convenção); alegação
sobre `.env` estreitada nos 4 lugares onde a frase estava copiada; aspas no `DB_ODBC_DRIVER`;
comentário obsoleto do Poetry em `lint_sql.sh` (obsolescência introduzida pela minha edição).

**Recusado:** ordenação alfabética do `.env.example`. O `UnorderedKey` do dotenv-linter
interleava os blocos de escopo que a #119 existe para criar, e dotenv-linter não é gate deste
repo. Recusa argumentada no thread, com a porta aberta para revisitar se ele virar gate.

⚠️ **Três rodadas perdidas em série** no mesmo arquivo (`S108` → `ERA001` → `ruff format`),
todas invisíveis fora do harness. O `make lint` do projeto gerado **curto-circuita**, então
cada rodada revela só o primeiro erro — declarar "tratei os threads" antes de rodar o gate
custou ~12 min de descoberta em série.

### 🔴 Travamento de CI recorrente (#192)

O job `Scaffold + lint + test` travou no passo `Install scaffold tooling (envsubst)` **duas
vezes em dois dias** (#188: 6h0m15s até o limite do GitHub; #191: cancelado à mão). Não é falta
de `-y` (verificado — já tem): é `apt-get update` numa rede que não responde, sem nada que o
delimite. Dois defeitos: o passo instala um pacote que o runner **já tem** (o comentário dele
mesmo diz isso — a instalação existe só para `act`), e `grep -c timeout-minutes` no workflow
retorna **0** em 13 jobs, então vale o default de 6h. Aberta como **#192**, fora desta PR.

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

## Estado (fim da sessão 2026-08-16)

- **PR #180 mergeada** (`3a6a7f9`) — grupo 1. **PR #182 mergeada** (`b039a42`) — grupo 2.
- Issues fechadas: **#126, #146, #156, #123, #141, #174**; cards em Done.
- **#173** comentada: buraco 1 de 3 fechado (`required_conversation_resolution: true`).
- ⚠️ **Release pendente: v0.15.4.** Nada foi cortado desde a v0.15.3.
- **Grupos 3–5 não iniciados**: #128/#120/#150 (ingestão), #119 (queries/SQLite),
  #125/#122 (box Windows).

### O que a sessão descobriu além do escopo

O gate de threads de review **passava vaziamente desde sempre** — comparava a grafia REST do
roster (`coderabbitai[bot]`) com a que o GraphQL devolve (`coderabbitai`). Foi assim que a #180
mergeou com 2 threads abertos. Substituído por quatro camadas, sendo a decisiva um **hook de
`Stop`** que recusa encerrar o turno com thread pendente (dotfiles-dev PR #127) — porque bloquear
o merge impede um desfecho ruim, mas **não conduz o trabalho**.

---

## Fora deste corte

Seções B e C da triagem, mais os itens da seção A que ficaram de fora dos grupos 1–5:

- ingestão e dados: `#116`, `#144`, `#148`, `#117`, `#127`
- CI e docs do projeto gerado: `#111`, `#145`, `#130`, `#113`, `#110`, `#124`, `#152`
- entregável e e-mail: `#118`, `#121`, `#151`, `#161`, `#162`

Backfill é barato enquanto o duskko ainda não existe; depois dele passa a ser `#109`.

## Depois

`make new` → python → `mvc-service-native-db` → nome `duskko`.
