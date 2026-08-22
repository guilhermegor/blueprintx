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
- [x] provar o bloqueio numa PR real antes de fechar a #173 — **provado 2026-08-22 na PR
      #219**, e provado por acidente: a PR e a medicao sao a mesma coisa. Antes de o
      CodeRabbit responder, a #219 respondeu `mergeable=MERGEABLE` mas
      **`mergeStateStatus=BLOCKED`** — os dois campos discordando e o segundo sendo o que
      manda. O check `Review threads answered` estava `fail` com a mensagem nova do #208:
      *"no declared reviewer ever reported on this PR"*.
      Isto fecha a composicao que faltava: ate aqui o script saindo 1 (#204/#213) e o job
      sendo obrigatorio tinham sido medidos **separadamente**, e nenhum dos dois prova que o
      botao de merge recusa.
      ⚠️ Dois efeitos colaterais uteis da mesma observacao:
      1. Toda PR nasce vermelha e fica assim ate a review chegar. E o comportamento correto,
         mas significa que `Review threads answered` **nunca** e verde no momento em que a PR
         abre — quem olhar cedo demais vai ler como defeito.
      2. A mensagem listou `github-actions` entre os revisores esperados. E exatamente o
         defeito da **#218**, agora visto em producao e nao so lido no codigo.
