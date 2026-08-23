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

## Slice 2 — #206: `check-urls` nunca lê docstring de uma linha ✅ ENTREGUE

- [x] Corrigido: o `continue` na linha de delimitador pulava o scan. Agora `check_urls_in_line`
      roda **antes** do flip de estado, nas duas ramificações (`"""` e `'''`).
- [x] **O bug era maior que a issue** — e a medição também corrigiu uma suposição minha.
      Levantei "três formas cegas"; o controle negativo mostrou **duas**:

      | forma | cega antes? |
      |---|---|
      | `"""docstring de uma linha com URL"""` | ✅ sim (a que a issue reportou) |
      | linha de **abertura** de docstring multi-linha (`"""Resumo … URL`) | ✅ sim, **não estava na issue** |
      | linha de **fechamento** com texto (`… URL"""`) | ❌ não |

      O fechamento passava por um motivo que vale registrar: o guard ancora em
      `^[[:space:]]*"""`, então uma `"""` no fim de uma linha com texto **não é reconhecida
      como delimitador** — o URL era escaneado como corpo (resposta certa, mecanismo errado) e
      o estado nunca volta para `false`, de modo que tudo depois é lido como se ainda estivesse
      dentro do docstring. Isso **super-escaneia** (falso positivo), o oposto do defeito do
      #206, e a convenção NumPy fecha em linha própria — deixado como está, documentado no
      script em vez de emendado num fix para a falha inversa.

- [x] **6 testes de controle negativo**, offline: semeiam o cache do próprio hook (chaveado por
      md5 do URL) em vez de bater na rede. Mais afiado que um fetch real — **só uma linha que
      o scanner de fato leu consegue consultar o cache**. 4 formas de docstring + controle
      positivo (mesmo fixture com 200 → passa) + controle de escopo (URL fora de docstring →
      ignorado). Verificado que reprovam no script sem o fix: 2 falham, exatamente as 2 cegas.
- [x] **Os 404s reais apareceram**, como a issue previu — 2, ambos corrigidos:
      - `src/utils/sidecar_metadata.py:61` — `https://dados.cvm.gov.br/dados/FI/DOC/CAD` → **404**.
        Reescrito como host + path (o hook pula URL host-only), seguindo a convenção que o
        próprio `bin/CLAUDE.md` já enunciava.
      - `optional/webhook/infrastructure/slack_notifier.py:7` —
        `https://api.slack.com/messaging/webhooks` → **302**. Atualizado para o home 200 atual
        (`https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/`).
- [x] **Verificação:** `src`, `bin`, `tests`, `optional` → todos exit 0. shellcheck + `bash -n`
      limpos; 40 testes de integração passam.

## Slice 3 — #110: `wwdates >=1.0.0` ✅ ENTREGUE

- [x] Bump nas 4 tiers de serviço (`ddd-*`, `mvc-*`), estilo `>=` conforme a decisão da issue.
- [x] ⚠️ **A issue está desatualizada num ponto factual** e vale corrigir nela: ela afirma que
      "`0.1.0` e `1.0.0` são as únicas releases". O PyPI hoje tem **`0.1.0`, `1.0.0`, `1.0.1`,
      `2.0.0`**. Com piso aberto, `>=1.0.0` resolve para a **2.0.0** — outro major, que é
      justamente o mecanismo que a issue temia (um major mudar o significado de `DatesBRAnbima`
      sob o mesmo nome).
- [x] **Verificado nos wheels reais, não no README**, baixando 1.0.0 e 2.0.0 do PyPI:
      - as duas exportam `DatesBRAnbima` de `wwdates/br/anbima.py`;
      - nenhuma importa cliente HTTP (`requests`/`urllib`/`httpx`) → offline de verdade;
      - `__init__` só tem argumentos opcionais → `DatesBRAnbima()` continua válido;
      - os 6 métodos que o wrapper chama existem nas duas.

      O major da 2.0.0 é a **adição** dos calendários dos EUA, não uma mudança neste. O bump é
      seguro e o wrapper tem **diff zero de código**, como a issue previu.
- [x] Corrigidas as **3 afirmações obsoletas** em `src/utils/dates.py` que descreviam a
      semântica com rede da 0.1.0 (docstring do módulo, comentário do singleton, docstring de
      `holidays()`) — "buscado preguiçosamente", "network on first use, cached thereafter".
      Um doc rastreado vale mais que memória na próxima sessão.

## Slice 4 — #167: gate de complexidade 🔄 EM ANDAMENTO

- [x] `bin/check_complexity.sh` — duas invocações do ruff, mccabe não reimplementado.
- [x] Escape hatch `# complexity-ok: <reason>`, com motivo **obrigatório** (marcador pelado
      é rejeitado — o hatch existe pela frase, não pelo marcador).
- [x] Wire nas **5** superfícies: pre-commit, `Makefile` (em `lint` + alvo próprio), `tasks.sh`
      (função + `case` + sync), `bin/help.txt`, CI (`tests.yaml`).
- [x] 6 testes should-fail em `tests/integration/test_bin_scripts.py` (convenção #111):
      reprova acima do teto, passa limpo, honra hatch com motivo, **rejeita hatch sem motivo**,
      aplica teto diferente por árvore, e **recusa reportar sucesso com zero arquivos**.
- [x] **`tests/` — 39 de 39 refatorados, ZERO hatches** (decisão do dono: stub vai para
      módulo/fixture, não para escape hatch).
- [x] **`src/` — 39 de 39.** 28 refatorados de verdade, 11 com hatch justificado.
- [x] **`bin/` — 2 de 2**, ambos refatorados (nenhum hatch).
- [x] Docs: `templates/python-common/CLAUDE.md` (linha do gate) + `CLAUDE.md` da raiz
      (parágrafo de paridade, ao lado do gate de tamanho de função).
- [x] Wire também **do lado da BlueprintX** via `--root .` (pre-commit `check-complexity` +
      job `complexity`), a mesma disciplina de uma-implementação-só que a #189 estabeleceu.
      ⚠️ A árvore da própria BlueprintX não tem `src/` nem `tests/`, então aqui ele checa só
      `bin/` (2 arquivos): ele vale por viajar junto com o template que policia, não pelo
      tamanho do que encontra deste lado.

### Onde o hatch foi usado em `src/` (11), e por quê

| função | motivo |
|---|---|
| `env_config.resolve_config_path` | cada ramo é uma falha de config documentada, com mensagem própria |
| `queries.load_query` | cada ramo é uma falha de lookup com o próprio remédio |
| `logs.CreateLog._validate_path` | duas faltas de validação distintas, cada uma com sua mensagem |
| `logs.CreateLog._caller_context` | andar a pilha **é** o trabalho |
| `logs.CreateLog._emit` | dois destinos e um nível rejeitado |
| `dtypes._validate_referenced_columns` | duas faltas de validação distintas |
| `http_downloader._assert_public_host` | **guarda de SSRF** — trocar checagem auditável por uma mais curta não é troca que este gate deva ganhar |
| `http_downloader._assert_url_allowed` / `_fetch_bytes` | validação de entrada / erro de transporte |
| `tabular_reader._cnpj_column_problem` / `decode_positional_payload` / `resolve_sheet_name` | regras de rejeição que não podem ser colapsadas |
| `retry` (3 funções) | ver abaixo |
| `outlook_gateway` (5 funções) | COM do Windows com degradação **não-fatal** |

### ⚠️ Dois achados sobre o limiar que vale registrar

1. **`src=2` é inatingível para um decorator factory, sempre.** Ele é três escopos aninhados
   por construção e o mccabe **dobra o corpo aninhado no score do envolvente** — a factory é
   cobrada pelo laço de retry do wrapper sem conter ramo nenhum. Nenhum arranjo desce de 3.
   É a métrica encontrando o idioma, não um defeito do código.
2. **O hatch quebrava quando o formatter mexia no arquivo.** O ruff ancora o C901 no `def`,
   mas o `ruff format` re-quebra assinatura longa e empurra o comentário para a linha do `)`.
   Um hatch escrito certo parava de valer. Medido no `_validate_path`. O gate agora varre a
   **assinatura inteira**, com limite, e para no fim dela — com dois controles negativos
   (assinatura quebrada é honrada; marcador no **corpo** não é).

### Refactors que seguiram regra da casa (não foram contorção para um número)

- `decimals._parse` (8) e `dtypes._to_decimal` (7): cadeias de `isinstance` → `singledispatch`,
  que é literalmente o que `rules/python.md` manda. A ordem `bool` antes de `int`, que a cadeia
  codificava em comentário + posição, agora sai de graça do MRO.
- `tabular_reader._read_raw_dispatch` (6): if-chain por extensão → **dict dispatch**, a regra do
  `common.md` para ramificar em **valor**. Adicionar formato virou adicionar chave.
- `dtypes.apply_dtypes` (9): validação separada da coerção; três laços mutantes → um `.assign()`.
- `logs.initiate_logging` e `outlook_gateway._parse_env_bool`: tri-estado e dois conjuntos de
  tokens viraram **tabela**, que também passa a ser a fonte única dos valores válidos.

### 🐛 Defeitos reais encontrados de carona (não eram complexidade)

- `logs.CreateLog._validate_path`: guardas na **ordem errada** — `not path` vinha primeiro,
  então um valor falsy não-string (`0`, `[]`, `None`) era reportado como "cannot be empty",
  mandando o leitor procurar uma string vazia que nunca existiu. Tipo antes de vazio.
- `decode_positional_payload`: agora nomeia a **primeira** posição excedente populada, em vez
  daquela em que o laço por acaso levantou.

### ⚠️ ERA001 — sexta medição da sessão

Os comentários que escrevi para explicar os refactors dispararam `ERA001` repetidamente; o
gatilho isolado inclui a própria palavra `returns` no início de uma frase. `src/` e `tests/`
**mantêm** a regra (o ignore ficou escopado a `bin/`), então o custo é recorrente e real —
mais dado para a decisão da **#169**.

### ⚠️ Dois defeitos que o próprio gate teve, e os dois eram CEGUEIRA

O primeiro rascunho reportou **"Cyclomatic complexity within limits (76 Python file(s))"** com
**79 violações conhecidas na árvore**. Duas causas independentes, ambas corrigidas e ambas
documentadas no script:

1. `resolve_ruff` era chamada como `$(resolve_ruff)`. `resolve_poetry` popula o array
   `POETRY_CMD`, e **substituição de comando roda em subshell** — então o array morria ali,
   todo `run_poetry` seguinte falhava, e o `2>/dev/null || true` que eu havia posto engolia o
   erro. O gate reportava árvore limpa porque não rodou nada. Agora seta **global**.
2. O loop lia `< <(run_ruff_c901 …)`. **Process substitution também é subshell**: uma falha
   dura lá dentro só conseguiria `exit` o subshell, o loop leria vazio e a árvore reportaria
   limpa — a mesma cegueira, pela segunda vez no mesmo arquivo. Agora a saída vai para arquivo
   e é lida de forma síncrona, e um exit do ruff **> 1** re-imprime o que o ruff disse e falha.

É exatamente a lição do `export_deps.sh` ("nunca diagnostique um comando cuja saída você
descartou") batendo de novo, agora no gate escrito para pegar esse tipo de coisa.

### ⚠️ Achado que corrige a tabela de custo aprovada

A decisão do dono foi tomada sobre "38 funções com ramificação em `tests/`". Medindo função a
função, **13 das 39 (33%) não tinham ramificação alguma**: eram stubs/closures `def`
aninhados dentro do teste, e **mccabe cobra +1 da função que envolve cada `def` aninhado**
(um `lambda` custa 0; comprehension, `with`, `and`/`or`, ternário e `assert` também custam 0).
O argumento do limiar 1 — "um teste com desvio testa dois caminhos e o verde não diz qual
rodou" — não se aplicava a nenhum deles. O custo real de ramificação era **26**, não 38.

Decisão do dono ao ver o dado: **mover os stubs para módulo/fixture, zero hatches em `tests/`.**

### Padrões usados em `tests/` (todos verificados por medição)

| era | virou | por quê |
|---|---|---|
| `def fn_stub(...)` aninhado | classe callable ou função no módulo | mccabe cobra +1 do teste que envolve; o stub não ramifica |
| stub que ramifica por chamada | `Mock(side_effect=[...])` | a sequência vira **dado**; o `if` saía do corpo do teste |
| `for x in (...)` com assert | `@pytest.mark.parametrize` | o loop afirmava N casos atrás de UM verde; agora cada caso se nomeia no relatório |
| `if not cond: pytest.skip()` | `@pytest.mark.skipif` | a condição é fixa em import-time; não é caminho *através* do teste |
| skip por resultado de subprocess | helper `_skip_unless` | genuinamente runtime; short-circuit em vez de `if` |
| `try/except ImportError` | `contextlib.suppress` | tratamento idêntico, `with` custa 0 |
| loops aninhados de AST/discovery | comprehension | mesma descoberta, custo 0 |
| `for h in logger.handlers: h.flush()` | **deletado** | `StreamHandler.emit()` já dá flush — era código morto |

⚠️ Dois `list(map(lambda …))` escritos no caminho foram **revertidos**: usar `map` por efeito
colateral é o "clever" que a casa proíbe. Viraram `shutil.copytree` (que ainda por cima não
consegue esquecer a próxima extensão) e três chamadas escritas por extenso.

⚠️ **Quinto grupo de falso positivo do `ERA001` nesta sessão**, agora nos comentários que eu
mesmo escrevi para explicar os refactors: o eradicate lê `` `algo` `` seguido de `:` ou `(`
como código. Reescritos em prosa. `tests/` e `src/` **mantêm** a regra (o ignore ficou escopado
a `bin/`), então o custo é real e recorrente — dado a mais para a decisão da **#169**.

**Verificação:** 381 testes passam, `ruff check tests` limpo, `tests/` zerado no gate.

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
