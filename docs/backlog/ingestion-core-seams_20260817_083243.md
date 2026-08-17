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

### #120 — `raw_workspace`

- [ ] `src/utils/raw_workspace.py` — um único ponto para "onde os bytes crus deste read vivem"
- [ ] `path_raw=None` → `TemporaryDirectory`, sem resíduo em disco depois do read
- [ ] `path_raw=<dir>` → criado com `parents=True` e **mantido**, byte-a-byte
- [ ] teste dos dois ramos, incluindo a asserção de que o temp **sumiu**

### #150 — cache diário no seam

- [ ] cache em disco chaveado pela **data de referência do dado**, nunca relógio de parede
- [ ] dentro do seam, para nenhum call site conseguir passar por fora
- [ ] cria a pasta pai em vez de assumir que o arquivador criou
- [ ] **loga qual ramo rodou** (hit de cache vs rede)
- [ ] flag explícita no construtor + wrapper `_uncached()` — política de cache é do **chamador**,
      não do cliente (o job de drift precisa do oposto, `drift-job-must-disable-the-client-cache`)
- [ ] docstring declara a granularidade de mudança que o cache assume

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
