# **Contribuindo**

Tudo o que você precisa para desenvolver, testar e lançar esta biblioteca.

> **Veja também:** [Uso](usage.md) · [Referência da API](api/index.md) · o `CONTRIBUTING.md` na
> raiz do repositório guarda a política oficial de branches/PRs e de mensagens de commit.

---

## Preparando o ambiente de desenvolvimento

O `poe` é uma dependência de desenvolvimento, então só existe depois que o virtualenv existe. Faça o
bootstrap primeiro pelo ponto de entrada em shell. Nesse primeiro bootstrap use um shell comum (não
dentro de `poetry run`, do `poe` ou de um venv ativado); depois deixe o `poe_exec.sh` encontrar o
`poe` do venv para o resto:

```bash
bash bin/venv.sh           # create the Poetry venv + install deps, poethepoet included
bash bin/poe_exec.sh init  # .env (when the tier ships one), venv, git hooks, GitHub helpers
```

O `init` compõe `ensure_env` (cria o `.env`; aqui é apenas uma linha informativa, já que uma
biblioteca não traz `.env.example`), `venv` (cria o virtualenv do Poetry e instala **todas** as
dependências, incluindo dev + docs) e `precommit` (instala os hooks do git). O Poetry é instalado
automaticamente se estiver ausente. Rodar `venv` de novo de dentro do virtualenv do projeto é
seguro: ele faz o bootstrap a partir de um interpretador base e se recusa a apagar o `.venv` que
está em uso.

## Testes e lint

```bash
poe unit_tests          # poetry run pytest tests/unit/
poe integration_tests   # poetry run pytest tests/integration/
poe lint                # ruff + mypy + codespell + pydocstyle + shell/sql/yaml gates
```

O CI roda os mesmos gates em todo pull request; mantenha-os verdes localmente antes de enviar.

## Verificando o pacote construído

Antes de abrir um PR de release, confirme que o wheel realmente é construído e importado — isso
pega erros de empacotamento (um `__init__` ausente, um subpacote `_internal/` não incluído) que os
testes sobre a árvore de código-fonte nunca revelam:

```bash
poe install_dist_locally    # python -m build → install → smoke-import → report the built wheel
```

## Publicando a documentação (versionada, via mike)

O site publicado é **versionado**: quem usa uma versão antiga lê a documentação *daquela
versão*, não a do HEAD. O [mike](https://github.com/jimporter/mike) mantém a árvore de versões
na branch `gh-pages` e o MkDocs-Material exibe o seletor de versão.

Dois workflows dividem o trabalho:

| Workflow | Gatilho | O que faz |
|---|---|---|
| `Docs - Strict Build Check` (`docs.yml`) | todo push + PR | apenas `mkdocs build --strict` — pega links e nav quebrados antes de um release. **Nunca publica.** |
| `Release to PyPI` (`release-pypi.yaml`) | release manual | depois que a publicação no PyPI dá certo, publica a versão lançada com `mike deploy --update-aliases <X.Y> latest` |

Como a publicação roda **depois** do lançamento, o site só anuncia versões que de fato foram
entregues. Observações:

- **A granularidade é `X.Y`** — `1.4.2` e `1.4.7` compartilham a entrada `1.4`; o alias `latest`
  sempre acompanha o release mais novo e é a versão padrão de entrada.
- **Pré-releases nunca movem o `latest`** — uma versão com sufixo (`1.2.3rc1`) é construída e
  publicada, mas o job de publicação da documentação é pulado.

### Configuração única do Pages

O mike publica a partir da **branch `gh-pages`**, então o Pages precisa estar em *Deploy from a
branch → gh-pages*. O `GITHUB_TOKEN` do workflow não consegue alterar isso (é um token de GitHub
App sem direitos de administrador do repositório), então faça com a sua própria autenticação do
`gh`:

```bash
poe enable_pages
```

Isso já roda dentro do `poe init` (depois do bootstrap) e é **idempotente e não bloqueante** —
ele avisa e segue em frente se o `gh` estiver ausente ou sem autenticação, se nenhum remoto for
resolvido ou se você não for administrador do repositório (um fork), então nunca quebra o `init`.

**A ordem importa:** a branch `gh-pages` não existe até que o primeiro deploy de release a crie.
Até lá, o `enable_pages` deliberadamente deixa o Pages intocado (para que o site nunca aponte
para uma branch vazia) e avisa para rodá-lo de novo. Portanto: corte o primeiro release e depois
rode `poe enable_pages` uma vez. Alternativa manual: *Settings → Pages → Build and deployment →
Source: Deploy from a branch → `gh-pages` / `/`*.

## Pull requests

1. Abra primeiro uma issue, usando o template de issue do repositório. Diga o que você quer mudar
   e por quê, e liste os arquivos que serão tocados. Para trabalhos não triviais, espere a issue
   ser aceita antes de escrever código.
2. Crie a branch a partir da branch padrão como `<type>/<issue-number>-<slug>` (por exemplo,
   `feat/42-user-authentication`), seguindo a política de prefixos (`feat/…`, `fix/…`, …).
3. Coloque `Closes #<N>` no corpo do PR para que a issue feche quando o PR for mesclado.
4. Preencha o template de PR por completo.
5. Garanta que as verificações do CI (testes, lint, build da documentação) passem — elas são o
   gate de merge.

<a id="releasing"></a>

## Lançamento de versões

Os lançamentos são **guiados por tag e sem segredos** quando o projeto está conectado a um remoto
do GitHub:

- A versão é a **tag do git** (via `poetry-dynamic-versioning`); o `pyproject.toml` guarda um
  valor provisório `0.0.0`. Não o edite à mão. Dispare um release pela aba Actions
  (`Release to PyPI` / `Release to Test PyPI`, `workflow_dispatch` com a versão) ou enviando uma
  tag `vX.Y.Z`.
- A versão publicada é derivada da última tag do git no formato `vX.Y.Z`. Em uma tag exata o
  build é limpo (`0.2.0`); builds fora de uma tag recebem uma versão de desenvolvimento PEP 440.
  Os workflows de release passam `POETRY_DYNAMIC_VERSIONING_BYPASS` para construir uma versão
  específica. Construa com `python -m build` (um frontend PEP 517).
- Uma `version` editada à mão falha no hook de pre-commit `dynamic-version-stub`
  (`bin/check_dynamic_version_stub.py`): ela contradiz a tag e o índice de pacotes. O hook não faz
  nada em projetos que não habilitam o `poetry-dynamic-versioning`.
- O workflow de release roda a **suíte de testes completa** como gate obrigatório, constrói com
  `python -m build` e publica por **OIDC trusted publishing** (`pypa/gh-action-pypi-publish`) —
  nenhum segredo de token é necessário.
- O changelog é regenerado a partir das tags no momento do release/build (`poe changelog`
  localmente); o CI nunca faz commit do `CHANGELOG.md` na branch padrão protegida.

### Configuração do mantenedor — trusted publisher (uma vez, antes do primeiro release)

Registre um **trusted publisher** no [pypi.org](https://pypi.org) **e** no
[test.pypi.org](https://test.pypi.org). Cada campo precisa coincidir exatamente com o workflow,
ou o upload falha com um opaco `invalid-publisher`:

| Campo | Valor |
|-------|-------|
| Owner / repository | o seu `<owner>` / `<repo>` do GitHub |
| Nome do arquivo do workflow | `release-pypi.yaml` (PyPI) / `release-test-pypi.yaml` (Test PyPI) |
| Environment | `release-pypi` / `release-test-pypi` |
| **Project Name** no PyPI | deve ser igual ao nome da distribuição (`name` no `pyproject.toml`) |

A etapa de GitHub Release existe apenas no `release-pypi.yaml`, não no workflow do Test PyPI, então uma mudança nela nunca é ensaiada; compare os dois workflows ao editar qualquer um deles.

No primeiro upload o projeto ainda não existe — registre um **pending publisher** no nível da
conta (não nas configurações de um projeto existente). Publicar a partir de um notebook, em vez do
CI, é o único caso que ainda exige um token de API; o OIDC funciona apenas no GitHub Actions.

### Publicando a documentação — primeiro release

A primeira execução de `release-pypi.yaml` cria a branch `gh-pages` com `mike deploy`.
O `GITHUB_TOKEN` não consegue definir a origem do Pages (o endpoint exige direitos de
administrador do repositório), então o job `deploy_docs` imprime a solução no resumo do job. Rode
`poe enable_pages` uma vez, como administrador do repositório, depois disso.

### Escolhendo os destinos de publicação

O scaffold liga os workflows de release ao registro público oficial (PyPI) e a um registro de
homologação (Test PyPI). Para publicar em uma fonte **privada / não oficial** — uma fonte git
(`pip install git+https://…`), um índice PEP 503 privado ou (em ecossistemas que suportam) o GitHub
Packages — configure a fonte do lado do consumidor no `pyproject.toml` com uma proteção de
prioridade explícita contra confusão de dependências (`priority = "explicit"` do `poetry`;
`pip --index-url`, nunca `--extra-index-url`).

## Aplicando a identidade visual ao site de documentação

O scaffold traz uma imagem de marca **provisória** em `docs/assets/logo.png`, ligada como
logo/favicon do cabeçalho (`theme.logo` / `theme.favicon` no `mkdocs.yml`) e como imagem de
destaque em `docs/index.md`. Para aplicar a sua marca:

1. Troque `docs/assets/logo.png` pelo seu próprio arquivo (mantenha o nome do arquivo ou atualize
   os dois caminhos no `mkdocs.yml` e a tag `<img>` em `docs/index.md`).
2. Ajuste tamanho, posição e borda diretamente na tag `<img>` — `width="200"` (escala),
   `align="right"` (posição) e `style="border-radius: 15px;"` (arredondamento) — em
   `docs/index.md`.
3. Defina a cor do cabeçalho em `docs/stylesheets/brand.css` (`--md-primary-fg-color`, mais a
   variante `slate` para o modo escuro) para combinar com o seu logo.

## Proteção e segurança do repositório (uma vez, via script)

O `poe init` roda três helpers que exigem permissão de administrador. Eles são **idempotentes e
não bloqueantes**: sem `gh`, sem autenticação, sem remoto do GitHub ou sem direitos de
administrador, eles avisam e pulam, então o `init` ainda termina para colaboradores e para
scaffolds offline. Rode qualquer um deles isoladamente depois:

| Alvo | O que provisiona |
|------|------------------|
| `poe enable_pages` | Origem do GitHub Pages (branch gh-pages para documentação versionada, senão Actions) |
| `poe enable_repo_rules` | O ruleset de branch `pr-quality-gate` + as configurações de merge de que o gate de PR precisa |
| `poe enable_security` | Relato privado de vulnerabilidades, alertas do Dependabot, atualizações de segurança do Dependabot |

### O ruleset `pr-quality-gate`

Aplicado a `~DEFAULT_BRANCH` (essa referência sobrevive a uma troca de nome da branch) e
localizado **pelo nome**, para que uma nova execução atualize no lugar em vez de criar uma
duplicata:

| Regra | Configuração | Por quê |
|-------|--------------|---------|
| `pull_request` | `required_approving_review_count: 0` | ⚠️ **Precisa ser 0.** O GitHub proíbe aprovar o próprio PR, então qualquer valor ≥ 1 impede um mantenedor solo de mesclar o próprio trabalho. Zero ainda obriga toda mudança a passar por um PR — essa é a verdadeira proteção. |
| `pull_request` | `required_review_thread_resolution: true` | Torna os comentários de revisão **vinculantes**: uma thread não resolvida bloqueia o merge em vez de ser decorativa. |
| `code_scanning` | CodeQL, segurança `high_or_higher`, alertas `errors` | Os alertas ficam em `errors`: `errors_and_warnings`/`all` passam a bloquear merges por consultas estilísticas, duplicando ruff/mypy com ruído. |
| `copilot_code_review` | `review_on_push: true` | É um **tipo de regra próprio** — não um parâmetro de `pull_request` (isso retorna HTTP 422 e faz o recurso parecer exclusivo da interface). |
| `non_fast_forward`, `deletion` | ligadas | Sem force-push e sem exclusão de branch na branch padrão. |
| `required_status_checks` | **vazio por padrão** | ⚠️ Deliberado. Uma verificação obrigatória cujo nome nunca é reportado bloqueia **todo** PR para sempre. Preencha `REQUIRED_CHECKS` em `bin/enable_repo_rules.sh` a partir de um PR real — `gh api repos/:owner/:repo/commits/<sha>/check-runs --jq ".check_runs[].name"` — e rode de novo. |

**Deliberadamente não habilitados:** *Require code quality results* (severidade subjetiva de IA no
caminho do merge — ruff, mypy e os gates `bin/check_*.py` já garantem a qualidade de forma
determinística) e *Restrict code coverage* (preview; o piso tem fonte única em `fail_under` no
`.coveragerc`).

### Automático vs. manual — a fronteira é a configuração do repositório vs. o plano da conta

**Nada aqui exige um clique.** Toda configuração de *repositório* acima é feita por script. O que
**não** dá para automatizar é o direito de uso da sua *conta*: a regra `copilot_code_review` só
dispara se o autor tiver acesso à revisão de código do Copilot, e **a revisão de código não faz
parte do Copilot Free**. Sem um plano qualificado, a regra fica corretamente configurada e
**inerte** — nenhuma revisão aparece e nada dá erro. Esse silêncio é a armadilha, porque o JSON do
ruleset parece perfeito nos dois casos.

Toda outra regra (PR obrigatório, CI verde, CodeQL limpo) funciona independentemente de qualquer
plano do Copilot, então vale a pena aplicar o ruleset incondicionalmente. O Copilot Pro é gratuito
para estudantes, professores e mantenedores de projetos open source populares verificados.

> **Não** diagnostique isso com `gh api user/copilot_billing` → 404: esse endpoint serve ao
> gerenciamento de assentos de organizações/empresas e retorna 404 para uma conta pessoal mesmo
> com o Copilot Free ativo.

### Segurança

O `SECURITY.md` na raiz do repositório é detectado automaticamente pelo GitHub (sem chamada de
API) e muda a *Security policy* para Enabled; o `poe enable_security` liga a entrada de relatos
privados correspondente, além dos alertas e das atualizações de segurança do Dependabot. Os
aumentos de versão comuns são separados — veja `.github/dependabot.yml`, que usa
`versioning-strategy: lockfile-only` para atualizar o `poetry.lock` (mantendo o CI honesto sobre o
que os consumidores instalam) sem nunca reescrever as faixas do seu `pyproject`.

## Fluxo automatizado de PR (o gate de qualidade)

Todo PR é classificado pelo `bin/pr_gate.py` (workflow `pr-gate.yml`), que o rotula, publica um
único comentário fixo com uma tabela de status por eixo e entrega as **classes seguras** ao
auto-merge nativo do GitHub. Duas regras são todo o desenho:

**Classificado por CAMINHO, nunca pelo tamanho do diff.** A mudança perigosa é *semântica*, não
grande: a edição de um único caractere em uma constante de schema/contrato é o menor diff possível
e o mais perigoso — e todos os testes continuam passando, porque os testes afirmam o contrato que
foi escrito. Então o tamanho nunca decide a elegibilidade; os caminhos alterados decidem. (O único
lugar em que o tamanho ainda importa — um diff `XL` é vetado — é **dispensado para um diff apenas
de lockfile**, cuja contagem de linhas acompanha quantos hashes de dependência mudaram, não o
risco.)

| Classe de risco | Caminhos | Auto-merge? |
|-----------------|----------|-------------|
| `src` | `src/` | ❌ define o que significa "passar" |
| `tests` | `tests/` | ❌ define o que significa "passar" |
| `other` | qualquer caminho não reconhecido | ❌ desconhecido = inseguro (negar por padrão) |
| `ci` | `.github/`, `bin/`, `Makefile`, `tasks.sh`, `.pre-commit-config.yaml` | ✅ |
| `deps` | `pyproject.toml`, `poetry.lock`, `requirements.txt` | ✅ (a suíte de testes é o gate) |
| `docs` | `docs/`, `mkdocs.yml`, `README.md`, `CHANGELOG.md`, … | ✅ |

**O consentimento é opt-OUT.** As classes seguras entram por auto-merge **sem nenhum label**;
adicione `do-not-merge` para forçar um merge humano. O auto-merge nativo **não contorna nada** — o
GitHub segura o merge até que toda verificação obrigatória do ruleset esteja verde, então o gate só
decide a *elegibilidade*, nunca *se passou*.

Edite a tabela de risco (a constante `RISK_PATHS`) em `bin/pr_gate.py` para o layout real do seu
projeto.

### ⚠️ Depois de mudar a política do gate, reprocesse os PRs abertos

O gate roda em eventos `pull_request`, então um PR que **já estava aberto** quando você mudou a
política (as regras de classificação/consentimento em `pr_gate.py`, ou `allow_auto_merge` /
`delete_branch_on_merge`) **nunca é reavaliado** — ele mantém os labels e o estado de auto-merge
que recebeu sob as regras antigas até que algum evento novo o toque. Isso não é um bug; o gate
simplesmente nunca rodou de novo. Então, depois de mesclar uma mudança de política, rode o
reprocessamento:

```bash
gh workflow run pr-gate.yml -f backfill=true   # re-evaluates every open PR
# for a Dependabot PR, `gh pr comment <n> --body "@dependabot rebase"` also works
```

### PRs mesclados por bot e o reconciliador

Um PR mesclado pelo **auto-merge nativo** (uma ação de bot) **não** fecha a issue vinculada e
**não** apaga a sua branch, mesmo com `delete_branch_on_merge` ligado — ações executadas por bots
são deliberadamente inertes para evitar recursão de automação. O `pr-reconcile.yml` corrige as
duas coisas: ele fecha as issues `Closes #N` e apaga a branch de origem dos PRs mesclados. A sua
**execução diária agendada é a correção de fato** — eventos agendados são isentos da supressão de
"nenhuma nova execução de workflow" que também engole o caminho rápido `pull_request: [closed]`
no merge de um bot. A latência é de até um dia; esse é o custo aceito de não precisar de um
personal access token.

### PRs fechados sem merge

O `delete_branch_on_merge` nunca dispara para um PR **fechado sem merge**, então a sua branch
ficaria acumulada no `origin`. O `delete-closed-pr-branch.yml` apaga a branch de origem de um PR do
mesmo repositório fechado sem merge, e só quando todas as proteções valem; uma branch pulada é
nomeada com o motivo no resumo do job:

- o PR é deste repositório, nunca de um fork;
- a branch é de vida curta, no formato `<type>/<N>-<slug>` (o padrão que `bin/check_pr_policy.sh`
  impõe), então `develop`, `release/*`, `dependabot/*` e `renovate/*` nunca são tocadas;
- ela não é a branch padrão nem a branch base do próprio PR;
- nenhum outro PR aberto a usa como base ou como origem (um PR empilhado, ou um segundo PR da
  mesma origem, seria fechado pela exclusão); uma resposta ilegível conta como "em uso";
- o GitHub informa que ela não é protegida, e um estado de proteção ilegível conta como
  protegida;
- o nome usa apenas letras, dígitos e `._/-`, e a ponta dela ainda é a origem do PR quando lida
  imediatamente antes da exclusão.

As verificações e a exclusão são chamadas de API separadas e a API de refs não tem
compare-and-delete, então um push, ou um PR aberto a partir da branch ou contra ela, nesse
intervalo é coberto apenas pelo caminho de restauração abaixo.

Nada se perde: o resumo do job nomeia a ref apagada e o seu sha, e a página do PR oferece
**Restore branch** (ou, a partir de um clone que tenha o commit,
`git push origin <sha>:refs/heads/<branch>`). Um PR cuja branch foi apagada só pode ser reaberto
depois de **Restore branch**. Uma recusa do ruleset é reportada como "mantida" (verde); qualquer
outro erro inesperado de API faz o job falhar. O arquivo do workflow é lido da merge ref do PR,
então quem tem escrita no mesmo repositório pode executar código com `contents: write` editando-o;
isso não acrescenta privilégio, já que essa pessoa já pode fazer push.

Limites conhecidos. O GitHub não roda workflows de `pull_request` enquanto o PR tem conflito de
merge, então um PR com conflito fechado sem merge mantém a sua branch; apague-a à mão. O script é
obtido por checkout da branch padrão, enquanto o YAML do workflow vem da merge ref do PR, então um
repositório cuja branch padrão ainda não contém `bin/delete_closed_pr_branch.sh` faz esse job
falhar até que contenha.

### O gate do ledger de trabalho

O `bin/check_backlog_ledger.py` (pre-commit + CI) reprova uma branch que toca `src/` ou caminhos de
CI mas não adiciona um ledger `.specs/backlog/<kebab>_YYYYMMDD_HHMMSS.md` com um checklist `- [ ]`
— tornando a convenção de ledger de trabalho por branch estrutural, em vez de algo que você
precisa lembrar. Branches rotineiras só de docs, dependências ou testes não precisam de nenhum.

### Registrando um novo módulo

Adicione a importação em `src/<package>/__init__.py` e o nome em `__all__`, cada um em posição
ordenada e uma entrada por linha. Nunca escreva um número ao lado de um substantivo contável no
README ou na documentação. Assim, dois PRs paralelos tocam linhas diferentes e mesclam sem
conflito; o `bin/check_registry_order.py` (parte do `poe lint`) impõe a ordem e a ausência de
contagens.
