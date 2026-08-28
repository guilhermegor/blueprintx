# O PR gate precisa BLOQUEAR o merge, não apenas reportar

**Criado:** 2026-08-17 · **Base:** `main` @ `aaffe2b` · **Issue:** #173
**Origem:** o dono apontou, olhando a PR #184 recém-mergeada: *"NUNCA há um bloqueio no CI para
conversas não respondidas & não marcadas como resolved... não dá pra só confiar na memória,
lição, enfim porque elas são probabilísticas e não determinísticas"*. Está certo.

---

## Medição (antes)

```text
required_status_checks       : null      ← ZERO checks obrigatórios
enforce_admins               : false     ← toda proteção é conselho para o dono
required_conversation_resolution : true  ← existe, e era decorativa
```

A PR #184 mergeou com **32 de 47 checks passed**. Nenhuma regra objetou, porque não havia
nenhuma: os 47 checks rodam e não bloqueiam nada. E `required_conversation_resolution: true`
não protegeu coisa alguma, porque `enforce_admins: false` deixa o admin — a única pessoa que
merga neste repo — passar por cima em silêncio.

Os threads da #184 estavam de fato respondidos e resolvidos no instante do merge (verificado
via GraphQL). Isso é o ponto, não a defesa: **foi sorte, não garantia.**

## As três camadas e por que nenhuma bloqueia

| Camada | Cobre | Por que não bastava |
|---|---|---|
| job `Review threads answered` | resposta faltando | roda, dá vermelho, e **não era obrigatório** |
| `required_conversation_resolution` | resolução faltando | ligado, mas **bypassado por `enforce_admins: false`** |
| hook local `pr_merge_threads_guard.sh` | ambos, no `gh pr merge` | é local: some em outra máquina, em CI, na UI do GitHub |

Três camadas probabilísticas não somam uma determinística.

## O que travava tornar o check obrigatório

A objeção registrada no cabeçalho de `review_threads.yml` era real, mas **parcial**: resolver
um thread não dispara workflow nenhum (`pull_request_review_thread` é webhook, não trigger),
logo um check que exigisse RESOLUÇÃO ficaria vermelho-obsoleto para sempre.

Só que o job **não exige resolução** — roda com `REVIEW_THREADS_REQUIRE_RESOLVED=0` e afirma
apenas que houve RESPOSTA. E resposta **dispara** `pull_request_review_comment`. Além disso o
job roda `on: pull_request`, então reporta em toda PR desde a abertura — a propriedade que um
required check precisa ter para não travar tudo.

Ou seja: era seguro exigir o tempo todo. A divisão limpa é

- **resposta** → o job, obrigatório, se atualiza sozinho;
- **resolução** → `required_conversation_resolution` nativo, avaliado no botão de merge, não
  tem como ficar obsoleto.

Cada metade fica com quem consegue reavaliá-la.

> 🔴 **SUPERSEDIDO em 2026-08-24 (#196, PR #264). NÃO siga a divisão acima.**
>
> O job **agora exige as duas metades** — `REVIEW_THREADS_REQUIRE_RESOLVED: "1"`, tanto no
> workflow deste repo quanto no template. O raciocínio acima continua correto sobre o *trigger*
> e errado sobre a *delegação*: o `required_conversation_resolution` **descarta um thread
> `isOutdated`**. Medido na #193 — botão de merge habilitado sobre um thread
> `resolved=False outdated=True`, 29 de 29 checks verdes e a configuração confirmada `enabled`.
> Um thread fica outdated quando o **commit do próprio autor** reescreve as linhas comentadas,
> ou seja, é exatamente o estado que o autor consegue fabricar.
>
> Então a metade que ninguém conseguia reavaliar era também a metade que ninguém estava
> checando. O custo aceito: depois de resolver, o check fica **VERMELHO** até alguém re-rodar o
> run — e é por isso que a **#263** deixou de ser cosmética (o re-run é a única forma de uma PR
> pronta ficar verde). Ver `issue-waves_20260823_145527.md`, seção Wave B.

🔴 **SUPERSEDIDO EM 2026-08-24 — a #263 foi ENTREGUE (PR #266, v0.16.6).** A frase "o re-run é a
única forma de uma PR pronta ficar verde" **superestima o custo hoje** e não deve ser lida como
regra vigente. O que mudou e o que não mudou:

- **Mudou — desde que o token tenha `actions: write`:** as falhas VELHAS acumuladas no rollup não
  exigem mais re-run manual. Um run que passa re-roda sozinho as falhas obsoletas do mesmo head
  (`templates/python-common/bin/rerun_stale_gate_runs.sh`, passo `Clear stale failed runs`).
  Medido ao vivo na própria PR #266: `Re-ran 4 stale failed run(s)`, e a PR chegou a `CLEAN` com
  **zero** re-runs manuais — a primeira da onda que não precisou de nenhum.

  ⚠️ **A permissão não é detalhe de implementação, é a condição da frase acima** — e neste repo ela
  é comprovadamente load-bearing: medido em 2026-08-24,
  `GET /actions/permissions/workflow` responde `default_workflow_permissions: "read"`. Ou seja, é o
  bloco `permissions: actions: write` **declarado no workflow** que habilita a limpeza; quem
  remover a linha achando que é redundante volta ao comportamento antigo **em silêncio** (o janitor
  avisa e sai 0 de propósito).
  O caso que nenhuma declaração cobre é **PR vinda de fork**, onde o `GITHUB_TOKEN` é read-only por
  definição. Ali os re-runs manuais continuam sendo N, não um. Então "um clique em vez de N" vale
  para PR do próprio repo — o caso deste projeto de um mantenedor — e **não** universalmente.
- **NÃO mudou:** resolver um thread continua não disparando trigger nenhum. Se nada mais rodar
  depois do resolve, ainda é preciso **um** re-run manual. O teto do #216/#180 continua real; o
  que caiu foi o custo ESCALAR (1 → 5 → 7 conforme o número de threads respondidos), não o teto.

Ou seja: o re-run manual deixou de ser a única saída e passou a ser, no pior caso, **um** clique
em vez de N.

---

## Execução

### Neste repo (aplicado ao vivo)

- [x] `enforce_admins: true` — sem isso todo o resto é conselho
- [x] `required_status_checks.contexts = ["Review threads answered"]`
- [x] `required_conversation_resolution` confirmado `true`
- [x] resto da proteção preservado no PUT (linear history, no force-push, no deletions)

### No template (para o duskko nascer com isso)

- [x] `REQUIRED_CHECKS` deixa de ser vazio: recebe `"Review threads answered"`
- [x] o comentário explica por que **este** nome não é chute (é o `name:` do job que o próprio
      template ships) e por que exigir resolução ali travaria
- [x] a etapa passa a **imprimir o conjunto que bloqueia**; vazio virou `warning`, não `info`
- [x] ruleset já tinha `required_review_thread_resolution: true` e não manda `bypass_actors`
      (default = sem bypass), então essa metade já estava correta lá

### Pendente

- [x] decidir com o dono se o conjunto obrigatório cresce além do check de threads
      (candidatos: `Scaffold + lint + test — *`, `Spell check`, `ShellCheck`, `MkDocs build`)
      — **decidido e aplicado.** Medido na API em 2026-08-22: `main` exige **15** contexts,
      todos os candidatos incluídos, mais `actionlint — workflows (repo + templates)`,
      `Version sync — pyproject vs CLI`, `Validate skeleton.meta integrity`,
      `Shared test copy lists — scaffolds vs python-common` e os dois jobs multi-intent.
      ⚠️ `strict` segue `false` (não exige branch atualizada antes do merge) e
      `required_approving_review_count` é **0** — o bloqueio vem dos checks, não de aprovação
      humana. `required_conversation_resolution` está `true`.
- [x] provar o bloqueio numa PR real antes de fechar a #173 — **PROVADO 2026-08-22, com
  controle negativo**, depois de duas conclusoes precipitadas minhas no mesmo dia.

### A prova do bloqueio (#173) — com os dois lados

| commit | gate `Review threads answered` | `github-advanced-security` | `mergeStateStatus` |
|---|---|---|---|
| `9e7d1fe` | **fail** (nenhuma review) | fail | **BLOCKED** |
| `7efc1e4` | success | **fail** | **CLEAN** |

A segunda linha e o controle negativo que faltava: com o GHAS vermelho e o gate verde a PR
fica **CLEAN**, logo o GHAS **nao bloqueia**. Na primeira linha a unica diferenca e o gate.
**Foi ele que segurou o botao.**

⚠️ **Duas conclusoes precipitadas, ambas a partir de UMA leitura de um campo assincrono:**

1. Primeiro tickei esta caixa lendo `BLOCKED` ao lado do gate vermelho — sem enumerar o que
   mais poderia estar bloqueando.
2. Depois destiquei, ao ver `a1ba4a6` (15/15 verdes, GHAS vermelho) responder `BLOCKED`, e
   culpei o GHAS. Errado tambem: `7efc1e4` tem a **mesma** configuracao e responde `CLEAN`.
   A unica explicacao consistente e que a leitura na `a1ba4a6` estava **atrasada** — a hipotese
   de propagacao que eu tinha declarado refutada cedo demais, duas vezes.

**A regra que sobra, e que custou tres rodadas:** `mergeStateStatus` e **computado de forma
assincrona**. Uma leitura isolada nao sustenta conclusao nenhuma — nem positiva nem negativa.
Reler depois de todos os checks completarem, e so concluir quando duas leituras separadas
concordarem. E `BLOCKED` segue dizendo *que*, nunca *por que*: a conclusao causal exige o
controle negativo, nao so a observacao.

Dois efeitos colaterais registrados na observacao original e ainda validos:

1. Toda PR nasce vermelha e fica assim ate a review chegar. E o comportamento correto, mas
   `Review threads answered` **nunca** e verde no instante em que a PR abre — quem olhar cedo
   demais le como defeito.
2. A mensagem listou `github-actions` entre os revisores esperados — o defeito da **#218**,
   visto em producao e nao so lido no codigo.

O `github-advanced-security` segue reprovando em toda PR (**#221**) — e ruido vermelho
permanente, sem titulo nem sumario, mas **nao** bloqueia merge.

---

## `github-advanced-security` (#221) — decisão final: documentar, não silenciar

> ⚠️ **Leia isto antes de reabrir uma investigação sobre este check.** Se você chegou aqui porque
> viu `github-advanced-security` vermelho numa PR nova, a resposta já está medida abaixo — não é
> preciso isolar de novo.

**Recon 2026-08-28** (PR #298, commit `3567e0c`), seis dias depois da medição original
(#173/#219, 2026-08-22): **o mesmo defeito, sem mudança.**

```text
Creating copilot-sdk session with model: claude-opus-4.6 and clientName: github/code-scanning
Error creating PR review request: SessionModelError: Execution failed:
  CAPIError: 400 The requested model is not supported.
  (Request ID: F018:23A888:53CD34A:5D159FB:6A90E161)
autofind.js version: 0.1.117
```

com, no ambiente do mesmo job: `COPILOT_AGENT_MODEL: sweagent-capi:claude-opus-4.6`,
`COPILOT_API_URL: https://api.individual.githubcopilot.com`. `autofind.js` subiu de `0.1.116`
para `0.1.117` no intervalo — o GitHub segue fazendo deploy do agente — e o 400 sobrevive ao
deploy. Confirma que não é uma falha transitória: o 400 persiste após um deploy do agente.

⚠️ **A causa continua não confirmada.** O log prova apenas que `The requested model is not
supported` sobrevive à atualização do `autofind.js`. Entitlement é *hipótese* — o `COPILOT_API_URL`
aponta para `api.individual.githubcopilot.com`, o que a sugere, mas a documentação do GitHub diz
que o Copilot Autofix está disponível em repositórios **públicos** sem assinatura do Copilot. Ou a
hipótese está errada, ou falta evidência que ligue o erro ao entitlement. Não registrar como fato.

O workflow continua **dinâmico** (`event=dynamic`, `path=dynamic/agents/github-advanced-security`,
gerado pelo GitHub, não presente em `.github/workflows/`) — não há YAML aqui para editar, então a
opção "consertar a configuração" está descartada de novo, com a mesma evidência.

**A opção "desligar" foi checada e não sai da CLI:**

```text
GET /repos/guilhermegor/blueprintx                            → sem campo advanced_security
                                                                  (repo público: GHAS é grátis e
                                                                  automático, não há toggle aqui)
GET /repos/guilhermegor/blueprintx  .security_and_analysis     → dependabot, secret_scanning,
                                                                  secret_scanning_push_protection
                                                                  — nenhum campo de Autofix
GET /repos/guilhermegor/blueprintx/code-scanning/default-setup → config do CodeQL em si, sem
                                                                  campo de Autofix
```

Não foi encontrado endpoint REST/GraphQL público documentado para o toggle "Copilot Autofix" —
as consultas acima mostram apenas que os responses não trazem o campo. A documentação do GitHub
descreve o controle pela UI nos níveis enterprise, organization e repository, sem documentar uma
operação REST/GraphQL equivalente. Pelo que se apurou, ele vive só em
**Settings → Code security → Copilot Autofix**, no dashboard, exatamente como o corpo original
da #221 já apontava (`precisa do painel — nada disso sai da CLI`). Nenhum agente com acesso só a
`gh`/API conseguiu apertar esse botão nas tentativas feitas aqui. Quem pode: um **administrador
com a permissão correspondente** — de repositório, de organização ou de empresa —, não apenas o
dono.

⚠️ **Efeitos colaterais de desligar, a considerar antes:** o GitHub **fecha automaticamente as
sugestões abertas** do Autofix. Reativar **não as restaura** — novas sugestões só aparecem em PRs
novas ou após nova análise. Como aqui o recurso nunca produziu sugestão nenhuma (todo run falha
com 400), o custo é zero neste repo; mas a regra vale se for aplicada noutro.

### Decisão: opção 3 — documentar por que fica vermelho

Não é "consertar configuração" (impossível — 400 é do lado do GitHub, sem YAML aqui) nem
"desligar via CLI" (impossível — toggle só existe no dashboard). O que fica ao alcance de um PR
neste repo é registrar o achado de forma que o próximo vermelho não custe outra rodada de
isolamento:

- Este arquivo é o registro. Quem vir `github-advanced-security` vermelho numa PR encontra aqui:
  não bloqueia merge (prova em #173 acima), causa-raiz é do lado do GitHub, sem ação disponível
  por CLI.
- O lever "desligar" **continua recomendado** para quando o dono passar pelo dashboard — reversível,
  descrito na #221 original — mas não é algo que este PR possa executar.
- Isso não é a mesma coisa que "consertado": a cor do check na UI do GitHub não muda com este PR
  — continua vermelho, sem título, sem sumário. O que muda é que deixa de custar uma investigação
  nova a cada vez.

**Consequência para o fechamento da #221:** `Refs #221`, não `Closes #221` — o critério da tarefa
é a cor do check carregar informação de novo, e a cor em si (o que a UI do GitHub mostra) não
mudou. O que mudou é que a informação agora está a um `grep` de distância em vez de uma
investigação nova.
