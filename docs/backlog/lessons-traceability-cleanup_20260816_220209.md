# Rastreabilidade do store de lições — limpeza da dívida do audit

**Criado:** 2026-08-16 · **Base:** `main` @ `b039a42`
**Origem:** o achado residual do `/wrap-up` da sessão anterior — *"170 lições sem referência
de issue/PR e 9 issues órfãs"*, deixado explicitamente para uma sessão própria.

---

## O que o audit realmente mede

`session_capture_audit.sh` → `emit_completeness()`:

- **Linha 1 (lições → issues):** uma lição conta como rastreada **apenas** se o texto do
  arquivo casar `blueprintx#[0-9]+`. Nada mais é reconhecido.
- **Linha 2 (issues → lições):** uma issue aberta conta como *sourced* se algum arquivo do
  store citar `blueprintx#<n>`.

## Dois defeitos no próprio audit (achados hoje)

- 🔴 **O denominador estava truncado.** A linha 2 chama `gh issue list --state open --json
  number` **sem `--limit`**. O default do `gh` é **30**. O repo tem **46** issues abertas, logo
  o audit nunca olhou para 16 delas — e o "9 órfãs" reportado é na verdade **12**. Um audit
  que reporta sobre uma amostra silenciosa da população é a falha que metade das lições deste
  store descreve, ocorrendo no medidor.
- 🔴 **Não existe marcador de "entregue".** Uma lição já scaffoldada conta como dívida para
  sempre, porque a única coisa que a quita é citar um número. Consequência medida: das 243
  lições, **73** citam um número e **170** não — mas isso não separa *pendente* de
  *entregue-sem-citação*. O formato da lição **não tem campo de status**; é a causa raiz de
  ninguém conseguir responder "isso já foi?".

## A ponte mecânica

Casar 170 lições à mão contra 101 issues seria o erro que a lição
`backlog-seeded-from-a-proxy-inherits-its-blind-spot` descreve. A ponte existe: **corpos de
issue e de PR já nomeiam o slug da lição em crases**. Um regex de slug kebab (≥3 segmentos,
para não colidir com prosa) sobre os 101 issues + 81 PRs resolve **82 das 170 sem julgamento
nenhum**.

Restam **88** que nenhuma issue e nenhuma PR jamais nomeou.

## Decisão do dono (2026-08-16)

- Resíduo de 88: **verificar e marcar status, sem abrir issues novas.** Não inflar o backlog
  de 46 → ~80 antes do `make new` do duskko.
- **Corrigir o script de audit** no dotfiles-dev (fonte versionada), não só reportar.

---

## Formato novo — campo `Status:`

Entra logo abaixo de `**Tier:**` em cada lição:

```markdown
- **Status:** delivered — blueprintx#182
- **Status:** tracked — blueprintx#128
- **Status:** queued — no issue filed
```

`delivered`/`tracked` satisfazem o regex atual do audit. `queued — no issue filed` **não** —
de propósito: é uma dívida consciente, e a segunda correção do script é ensiná-lo a
distinguir *não-declarado* de *declarado-pendente*.

---

## Execução — ✅ CONCLUÍDA

### 1. Ponte mecânica — 82 lições

- [x] estampadas: **53 `delivered`**, **29 `tracked`**, derivadas do estado do próprio ref
      (PR mergeada / issue fechada → `delivered`; issue aberta → `tracked`)
- [x] controle negativo: `assert lessons` — a ponte **recusa rodar** com o store vazio, em vez
      de reportar "tudo rastreado"
- [x] amostras cruzadas contra o backlog anterior: #125 e #130 são issues abertas do corte e
      saíram `tracked`, como deviam

### 2. Resíduo — 88 lições

- [x] **71 resolvidas pelo histórico do repo**: `git log --diff-filter=A -- <alvo>` → sufixo
      `(#N)` do commit de squash. 13 delas caem antes do merge-por-PR e citam o SHA
      (`delivered — pre-PR (799db84)`), em vez de um número inventado
- [x] **17 a julgamento**, cada uma verificada contra o repo antes do veredito
- [x] 🔴 **três correções de método no caminho, todas falso-negativo meu:**
      1. um `Scaffold into:` costuma ser escrito da perspectiva do **projeto gerado**
         (`bin/precommit.sh`), não da raiz do blueprintx — resolver só na raiz reportou
         21 lições entregues como pendentes; resolvendo nas duas bases, caiu para 9
      2. alvos são renomeados (`ci.yml` → `tests.yaml`) e re-grafados
         (`release_test_pypi.yaml` → `release-test-pypi.yaml`); sem normalizar `-`/`_`,
         4 lições de release apareciam como dívida
      3. `docs/backlog/*.md` é um **terceiro livro-razão** e já registrava `DONE` para lições
         que eu ia marcar como pendentes
- [x] ⚠️ nenhuma marcada `delivered` porque "o arquivo existe" — todo veredito nomeia o commit
      ou a checagem que o sustenta

### 3. Direção reversa — issues órfãs

- [x] o audit dizia **9**; o número real era **12** (ver defeito do `--limit` acima)
- [x] após a estampagem caíram para **8**, e duas delas **eram** nascidas de lição, só que a
      lição não citava o número: **#120** (`ingestion-reader-persists-raw-artifact`) e
      **#175** (`gate-on-thread-content-not-on-resolver-identity`) — referências adicionadas
- [x] as **6** restantes (#110, #132, #133, #134, #136, #164) são trabalho de feature/ops que
      genuinamente não nasce de lição → registradas na seção **"Issues not born of a lesson"**
      do README do store, para pararem de ser re-triadas toda sessão

### 4. README do store

- [x] campo `Status:` documentado com a tabela dos 5 valores
- [x] os dois avisos que custaram tempo nesta sessão escritos como regra: nunca marcar
      `delivered` por existência de arquivo; resolver caminho nas duas bases

### 5. Script de audit (dotfiles-dev)

- [x] `--limit 500` explícito, mais aviso quando a página **enche** (aí a contagem é piso, não total)
- [x] `Status:` reconhecido como declaração; `queued` contado **à parte** — é o único número
      que é dívida real
- [x] 4 testes novos no `tests/session_capture_audit.bats` (Status sem número conta como
      declarado; `queued` conta à parte; `advisory` não conta como queued; o stub de `gh`
      registra o argv e prova o `--limit`)
- [x] `shellcheck` limpo; **`bats` não está instalado nesta máquina**, então a verificação foi
      executar o script contra o repo real, mais controle negativo (lição sem `Status` → é
      acusada; removida → volta a zero)
- [x] deployado para `~/.claude/hooks/` (a cópia viva ainda tinha o bug)
- [ ] ⚠️ **não commitado** — a única branch do dotfiles-dev é `feat/pr-merge-threads-guard-126`,
      da PR #127 ainda aberta, e este fix não pertence a ela

---

## Resultado

| | antes | depois |
|---|---|---|
| lições com disposição registrada | 73 / 243 (só citação) | **244 / 244** |
| dívida real (`queued`) | desconhecida | **6** |
| issues abertas órfãs | 9 reportadas (12 reais) | **0** |

O denominador sobe de 243 para 244 porque o store **ganhou uma lição durante esta sessão** —
`scaffold-copy-excludes-build-artifacts`, do achado colateral abaixo. As 243 originais foram
todas estampadas; a 244ª nasceu já com `Status:`.

Distribuição final: **156 delivered · 76 tracked · 6 queued · 4 advisory · 2 superseded** = 244.

As 6 `queued` são a dívida honesta que sobrou, cada uma com a evidência da ausência anotada:
`confirm-the-spec-document-before-writing-the-reader` (sem `config/contracts/CLAUDE.md`),
`config-reference-optional-override`, `instrument-before-the-gate-not-after-it`,
`codeql-default-setup-drops-a-pr-dispatch-deadlocking-merge`,
`recorded-browser-flow-is-data-not-code`, `scaffold-copy-excludes-build-artifacts`.

## Achado colateral — build output dentro de `templates/`

Enquanto verificava alvos, dois `__pycache__` apontaram para módulos **deletados de propósito**
(`mkdocs_hooks.py`, `yaml_reader.py`). São **205 arquivos `.pyc`** sob `templates/`, e os
scaffolds fazem `cp -r templates/<tier>/src/.` **sem nenhuma exclusão** — todo projeto gerado
nasce com bytecode de outra máquina. O git nunca rastreou esses arquivos, então `git status`
fica limpo e o defeito é invisível.

O custo caro não é o lixo: um `.pyc` órfão **sobrevive ao `.py`** e faz `grep -rl` responder que
um módulo ships quando ele não ships — foi o que quase produziu dois vereditos errados aqui.
Lição registrada (`scaffold-copy-excludes-build-artifacts`, `queued`); **não abri issue**, pela
mesma decisão que rege esta sessão.

**Completo — mantido como registro.**
