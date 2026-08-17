# PR C — núcleo de ingestão (grupo 3 da seção A do duskko)

**Criado:** 2026-08-17 · **Base:** `main` @ `aaffe2b`
**Origem:** `duskko-section-a-execution_20260816_105855.md`, grupos 1 e 2 já entregues (#180, #182)

Três issues que viajam juntas porque tocam o mesmo seam de ingestão em
`templates/python-common/src/utils/` e o mesmo `src/config/CLAUDE.md`.

⚠️ **Scaffolding é cópia one-shot** (#109): o que não entrar antes do `make new` do duskko vira
backfill manual.

---

## Escopo

| Issue | Tema |
|---|---|
| #120 | seam `raw_workspace` — retenção de artefato bronze |
| #150 | cache diário em disco de download de vendor, dentro do seam |
| #128 | disciplina de contrato de ingestão (8 lições) + 2 gates executáveis |

## Estado atual medido

- `src/utils/raw_workspace.py` → **ausente** (checagem direta)
- `src/utils/sidecar_metadata.py` já **consome** um `path_raw` — o seam que o *produz* nunca foi
  entregue, então cada reader teria de reimplementar a mesma bifurcação
- Existem: `http_downloader.py`, `retry.py`, `tabular_reader.py`, `zip_extractor.py`,
  `provenance.py`, `dtypes.py`, `frames.py`

---

## Execução

### #120 — `raw_workspace` — ✅ ENTREGUE

- [x] `src/utils/raw_workspace.py` — um único ponto para "onde os bytes crus deste read vivem"
- [x] `path_raw=None` → `TemporaryDirectory`, sem resíduo em disco depois do read
- [x] `path_raw=<dir>` → criado com `parents=True` e **mantido**, byte-a-byte
- [x] teste dos dois ramos, incl. a asserção de que o temp **sumiu** (roda FORA do bloco `with`;
      dentro dele não prova nada)
- [x] 🔴 `@contextmanager` fica **por fora** do `@type_checker`: na ordem inversa o checker
      compara o `_GeneratorContextManager` com a anotação `Iterator[Path]` e **toda** chamada
      levanta `TypeError`. Amenda registrada na lição `runtime-type-checking`.

### #150 — cache diário no seam — ✅ ENTREGUE

- [x] `src/utils/daily_cache.py` — cache em disco chaveado pela **data de referência do dado**,
      nunca relógio de parede (um run às 23:59 e outro às 00:01 pedindo o mesmo dia de
      referência precisam acertar o mesmo arquivo)
- [x] cria a pasta pai em vez de assumir que o arquivador criou
- [x] **loga qual ramo rodou** (HIT vs miss vs bypass) — cache silencioso é indistinguível de
      cache que nunca engatou, e "por que este dado está velho?" fica sem resposta no log
- [x] flag explícita `bool_use_cache` — política de cache é do **chamador**, não do cliente
- [x] **guarda contra arquivo de 0 byte**: `write_bytes` não é atômico, então um run
      interrompido deixa arquivo vazio, e servi-lo entrega um caminho válido para nada
- [x] teste executável de que o job de drift **não** usa o cache — hoje ele está correto por
      **acidente** (ninguém ligou o cache nele), e acidente reverte com um import conveniente
- [x] docstring declara a granularidade de mudança que o cache assume
- [x] 🔴 lição nova: `pythonpath = . src` carrega cada módulo **duas vezes**, então uma
      subclasse vinda de `src.utils.retry` não é a mesma classe que `utils.retry` — a checagem
      nominal recusa. Ver `two-import-paths-for-one-module-break-nominal-type-checks`.

### #128 — disciplina de contrato + 2 gates

- [ ] estender `src/config/CLAUDE.md` com as 8 lições de disciplina de reader
- [ ] gate de **colisão de nome**: um caminho de origem mapeia para exatamente um nome de coluna
      na família de readers, e vice-versa
- [ ] gate de **população de `__all__`**: caminhar a árvore de módulos e exigir que cada membro
      esteja exportado (descobrir *através* de `__all__` não enxerga o membro ausente dele)

---

## Verificação (toda PR)

- `bash bin/ci/scaffold_lint_test.sh <tier>` em **cada tier afetada** — nunca só na raiz
- Todo gate novo precisa de **controle negativo** e de entrar na copy-list mantida à mão
- Um gate vive em **4 superfícies**: hook, CI, `Makefile`, `tasks.sh`
