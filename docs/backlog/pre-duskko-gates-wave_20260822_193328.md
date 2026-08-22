# Leva pré-duskko — gate de complexidade (#167) + as três triviais (#207, #206, #110)

**Criado:** 2026-08-22 19:33 · **Branch:** `feat/complexity-gate-bin-lint-167`
**Base:** `v0.15.10` · **Decisões do dono tomadas nesta sessão** (ver "Decisões" abaixo)

⚠️ Este ledger também responde à pergunta de triagem do dono sobre 15 issues —
seção **"Triagem: o que é pré-duskko e o que é backfill"**, no fim.

---

## Decisões do dono (2026-08-22, com medição na mão)

**#167 — política de limiar: `tests=1`, `src=2`, `bin=8`.** Custo medido: **79 funções**
a refatorar (38 em `tests/`, 39 em `src/`, 2 em `bin/`).

Medição refeita hoje em `templates/python-common` (`ruff C901`, a mesma implementação que
vai medir em produção — a armadilha que a #167 documenta):

| limiar | `tests/` (378 fn) | `src/` (105 fn) | `bin/` (116 fn) |
|---|---|---|---|
| 1 | 38 (10%) | 67 | 99 |
| 2 | 11 (3%) | **39 (37%)** | 86 (74%) |
| 6 | — | 7 | 10 |
| **8** | — | 2 | **2** |
| 12 | — | 0 | 0 |

Confere com a tabela de 2026-08-16 da issue (8%/38%/71% → 10%/37%/74%): a árvore andou
pouco, e o número combinado continua sendo o número aplicado.

**Escopo da leva:** #167 + #110 + #206 + #207 juntas. Todas mexem em `templates/`, logo
todas ficam mais caras depois do `make new` — scaffolding é cópia one-shot (#109).

---

## Ordem de execução

`#207 → #206 → #110 → #167`. O #207 vem primeiro porque é ele que passa a **lintar o
`bin/`** onde o #167 vai escrever `check_complexity.sh`; na ordem inversa o gate novo
nasceria fora do lint.

---

## Slice 1 — #207: `bin/` está fora do ruff ✅ ENTREGUE

- [x] O motivo escrito no `exclude` está **meio errado**, e a medição mostra onde

      ```toml
      # check tooling: ruff-format would tabify space-indented helpers and trip E101
      "bin",
      ```

      O `bin/` **já está dividido** hoje — não é um bloco homogêneo de helpers
      espaço-indentados:

      | indentação | arquivos |
      |---|---|
      | tabs (estilo da casa) | `check_all_exports.py`, `check_comment_language.py`, `check_function_length.py` |
      | espaços | outros 10 |
      | **mistura os dois** | `check_review_threads.py` (337 tabs + 21 espaços) |

      Os 27 `E101` **não** são hipotéticos e **não** viriam do `ruff-format`: eles já
      existem hoje, todos no único arquivo que mistura. E os arquivos mais novos
      (`check_function_length.py`, do #189) já nasceram com tab — o estilo da casa já
      venceu dentro do `bin/`, o `exclude` só escondeu o placar.

- [x] 73 achados atrás do exclude, por regra — **todos resolvidos, `bin/` está em 0**:

      | regra | n | natureza |
      |---|---|---|
      | `E101` mixed-spaces-and-tabs | 27 | some com `ruff format` |
      | `E501` line-too-long | 16 | mecânico |
      | `ERA001` commented-out-code | 15 | ⚠️ colide com a **#169** (decisão de ERA001) |
      | `ANN202`/`ANN001` | 5 | anotação faltando |
      | `S105` hardcoded-password-string | 3 | avaliar um a um |
      | `S607` start-process-with-partial-path | 2 | avaliar |
      | `UP038` non-pep604-isinstance | 2 | mecânico |
      | `S506` **unsafe-yaml-load** | 1 | **defeito real** |
      | `D400` missing-trailing-period | 1 | mecânico |
      | `TID251` banned-api | 1 | avaliar |

- [x] ⚠️ Formatar `check_review_threads.py` aqui **diverge da cópia do repo** — é
      exatamente a dívida da **#217** (duas cópias de 524 linhas). Decidir se a #217 entra
      nesta leva ou se o arquivo fica de fora do format até lá.

### Como cada classe foi resolvida

| regra | n | resolução |
|---|---|---|
| `E101` | 27 → 4 | `ruff format bin` tabifica o **código**, mas não toca conteúdo de string: o docstring NumPy espaço-indentado virou `TAB + 4 espaços` e o E101 subiu para **222**. `src/` sempre usou **tab dentro do docstring** (é por isso que o `D206` está no `ignore`); um script AST converteu só o corpo dos docstrings do `bin/`, 222 → 4. Os 4 finais são recuo pendente de bullet markdown (`TAB + 2 espaços`) — deliberado, e `# noqa` não existe dentro de docstring → `per-file-ignores` do `bin/`. |
| `ERA001` | 15 | **15/15 falsos positivos**, todos linha de continuação de comentário em prosa. → `per-file-ignores` do `bin/`, com o porquê escrito. Segunda medição independente do #169 (0 verdadeiros em 24). |
| `E501` | 16 → 0 | 9 sumiram no format; 7 reescritas à mão (todas 100–101 chars). |
| `S105` | 3 | Falso positivo pelo **nome**: `_ALLOW_TOKEN`/`_READ_TOKEN`/`_STAMP_TOKEN` são sentinelas de texto-fonte, não credenciais. **Renomeados para `_*_MARKER`** — fix de raiz, não `noqa`: o nome enganava o leitor e o bandit igual (mesma lição do `CODERABBIT_TRIGGER_PAT`). |
| `S506` | 1 | Falso positivo: `_MkDocsSafeLoader` **herda de `yaml.SafeLoader`** (`check_docs_sections.py:52`) e resolve tag desconhecida para `None`. ⚠️ O checkpoint chamava isto de "unsafe YAML load" — **não é**; o comentário acima da chamada já explicava. `noqa` apontando para ele. |
| `ANN202`/`ANN001` | 5 | Anotados de verdade (`types.ModuleType \| None`, `dict \| None`, `-> object` batendo com o docstring). |
| `S607` | 2 | `git` por PATH é resolução **por design** (o `git` que o shell e o CI do dev usam). `noqa` com motivo. |
| `UP038` | 2 | `isinstance(x, (A, B))` → `A \| B`. |
| `D400` | 1 | Primeira linha do docstring era pergunta; virou afirmação. |
| `TID251` | 1 | Import de `FileContract` **só para anotação**, o caso que o próprio `ruff.toml` documenta → `# noqa: E402, TID251`. |

**Verificação:** `ruff check bin` → `All checks passed!`; `ruff format --check bin` → 16 arquivos já formatados; 87 testes dos gates passam.

⚠️ **Fora de escopo, medido e registrado:** o `bin/` continua **sem mypy**. O `mypy.ini` roda com `cd src`, então `bin/` nunca entra na descoberta. A metade "lint" do #207 está entregue; a metade "type-check" não, e não é 1 linha (`bin/` não é pacote). Vale issue própria.

⚠️ Os 68 achados restantes em `optional/` são **pré-existentes** (idênticos antes e depois — conferido com stash) e fora de escopo: `optional/` é staging de template, não existe em projeto gerado.

## Slice 2 — #206: `check-urls` nunca lê docstring de uma linha

- [ ] Corrigir o parser e **esperar 404s reais aparecerem** — é o efeito declarado na issue.

## Slice 3 — #110: `wwdates >=1.0.0`

- [ ] Bump nas tiers de serviço.

## Slice 4 — #167: gate de complexidade

- [ ] `bin/check_complexity.sh` — **não reimplementar mccabe**; duas invocações do ruff
      (`per-file-ignores` só desliga regra, não muda `max-complexity` por caminho).
- [ ] Escape hatch por linha com motivo, espelhando o `# dtype-ok: <reason>` do `check_dtypes`.
- [ ] Wire em `.pre-commit-config.yaml` + CI, uma casa por check.
- [ ] Teste should-fail (convenção da #111).
- [ ] Refatorar as 79 funções.
- [ ] Docs + README.

---

## Triagem: o que é pré-duskko e o que é backfill

O duskko é um **`mvc-service-native-db`**. O critério de corte é um só: **o item entra na
cópia one-shot do `make new`?** Se sim, é mais barato antes. Se toca só o repo da
BlueprintX, o duskko não herda e a hora não importa.

### Pré-duskko de verdade (mexem em `templates/`, o duskko herda)

| # | Por que antes |
|---|---|
| **#207** | `ruff.toml` é copiado. Nasce com o `bin/` cego no duskko. **Nesta leva.** |
| **#206** | Gate quebrado que reporta verde. Copiado quebrado. **Nesta leva.** |
| **#110** | `pyproject.toml` da tier de serviço. 1 linha. **Nesta leva.** |
| **#167** | `ruff.toml` + pre-commit + CI, todos copiados. **Nesta leva.** |
| **#116** | `utils/retry.py` → pacote `retry/`. Mudança de **caminho de import**: depois do scaffold vira backfill em código já escrito. Duskko é ingestão de API — retry é o seam de toda leitura de rede. **Maior prioridade fora desta leva.** |
| **#124** | `tests/CLAUDE.md` nas 4 tiers sem ele. É o que o Werner lê no dia 1 para saber testar aqui. Backfill é barato (copiar arquivo), mas o custo de não ter é **precedente**. |
| **#155** | GitGuardian nos workflows das tiers. Secret scanning ausente no dia 1 é o pior momento para estar ausente. |
| **#159** | Gate novo em `python-common`. Copiado. |
| **#163** | Regras de fronteira em `CLAUDE.md` das tiers — prosa que o dev novo segue. Backfill barato, mas mesmo argumento de precedente da #124. |
| **#140** | Direção entre camadas no gate de import. `model/` pode importar `controller/` e passa. Config do gate é copiada. |
| **#118** | `utils/ms_office` + `excel_sheet_names`. Só se o duskko entregar Excel — port pronto (208 linhas + 18 testes em `recon_al_cvm`). |
| **#121** | Orquestração de e-mail. Só se o duskko reportar por e-mail. |
| **#117** | Seam `read_xml`. **Pronta, mas o duskko é JSON** — valor real ≈ 0 para ele. |
| **#111** | Metade já saiu no #170. A outra metade (teste should-fail em cada `check_*.py`) é convenção de `bin/` copiado — e o #167 já entrega um exemplo dela. |

### Não é pré-duskko (o duskko não herda)

| # | Por quê |
|---|---|
| **#139** | Layer map faltando em **`ddd-*` ×2 e `lib-minimal`**. O duskko é **`mvc-service-native-db`**, que **já tem** o layer map. Zero impacto nele. Pode ser depois à vontade. |
| **#169** | Auditoria dos pontos cegos do quality gate — trabalho de análise no repo da BlueprintX. Vira template só depois de decidido. ⚠️ Mas a parte de **ERA001** colide com os 15 achados do #207 acima; essa fatia se resolve sozinha nesta leva. |

### Recomendação de corte

Se a ideia é scaffoldar logo: esta leva (**#207, #206, #110, #167**) **+ #116** e pronto.
`#124`/`#163` são cópia de arquivo, baratas de backfillar. `#139` e `#117` não tocam o
duskko. O resto (`#155`, `#159`, `#140`, `#118`, `#121`) é backfill legítimo enquanto o
projeto ainda é pequeno.

**Nada aqui bloqueia o `make new`** — segue valendo a conclusão do ledger
`duskko-blockers_20260816_110000.md`.
