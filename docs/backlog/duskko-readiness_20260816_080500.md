# Duskko readiness — Tier A bundle

**Criado:** 2026-08-16 08:05
**Branch:** `fix/158-duskko-readiness-bundle`
**Prazo duro:** 14h de 2026-08-16 (início do projeto duskko com o Werner)

## Por que este bundle existe

O duskko será scaffoldado a partir de **`mvc-service-native-db`** e faz coleta (API da Tesouraria,
substituindo as queries de `contexto_duskko/config/consultas_sql/`), tratamento e persistência em
SQLite. Pela lição `template-fix-does-not-reach-already-scaffolded-projects` (#109), **correção
que entra antes do `make new` propaga de graça; depois dele, exige backfill manual**. Logo, o
critério de seleção não é "quantas issues fecho", é "quais tocam a superfície que o duskko usa no
dia 1".

Ambientes-alvo confirmados: **Windows + proxy TLS da XP** *e* **Linux/WSL com saída para PyPI** —
os dois contam, então os itens de ambiente corporativo permanecem no escopo.

**Fora de escopo por decisão:** o `make new` do duskko não é feito aqui. O usuário decide quando
parar o desenvolvimento na BlueprintX e scaffoldar.

## Escopo (ordenado por bloqueio × custo)

- [x] **#158** `default_stages` no `.pre-commit-config.yaml` — todo gate rodava 2x (commit + push)
- [x] **#143** `tabular_reader`: `any()` em série vazia + `astype(str)` não NA-safe
      — controle negativo: 2 failed no código antigo → 9 passed no corrigido. Achado extra: em
      **pandas 3** o `.astype(str)` não produz `"nan"` (comportamento do pandas 2), ele deixa o
      `float nan` chegar ao validador e o beartype levanta `TypeError`. O defeito é um crash, não
      uma validação errada silenciosa. `safe_str` corrige os dois regimes.
- [x] **#165** índice PyPI parcialmente bloqueado (403) aborta o `init` inteiro — **evidência de
      campo do box do Werner (2026-08-16)**; poda por `DB_BACKEND` + instalação incremental.
      O teste de poda pegou um bug meu antes do commit: `_read_env_var` resolve `.env` relativo ao
      **CWD**, então todos os backends liam `sqlite`. Ancorado em `$PROJECT_ROOT/.env` — mesma
      classe da lição `resolve-config-paths-to-absolute` (#122).
- [x] **#147** robustez do reader de ingestão — **2 de 3 licoes entregues**: nomes de campo
      normalizados no read boundary (`.strip()`) e `decode_positional_payload` com tratamento
      assimetrico da largura. A terceira (envelope de fixture) e convencao de teste e pertence ao
      #152/#124, nao ao seam.
- [x] **#166** o ramo JSON do `read_table` quebrava a garantia de "ler como texto" —
      `pd.read_json` coage ate valores publicados entre aspas (`"1000.50"` -> `1000.5`,
      `"007"` -> `7`). Fronteira de parse, atinge direto API JSON com dinheiro.
- [x] **#115** emoji nos `bin/check_*.py` quebra os gates em Windows cp1252 — 8 arquivos, 41
      caracteres nao-cp1252. Corrigido no seam de I/O (reconfigure UTF-8), nao removendo os
      glifos. Controle negativo: 2 failed sem a correcao, 9 passed com ela.
- [x] **#114** `get_corporate_ca.sh` estreita o trust store TLS em vez de uni-lo — agora le a
      trust store do SO (`ssl.enum_certificates`, sem rede e sem desabilitar verificacao) e
      `wire_corporate_ca` monta `bin/ca_bundle.pem` como UNIAO (certifi + bundle do host + CA
      corporativa). Removidos o append in-place no certifi e o `PIP_TRUSTED_HOST`.
- [x] **#160** `startup.py` construia o LOGGER depois de resolucao falivel — gradiente de
      fragilidade explicito, falha capturada e reportada em log + stderr com exit 2, guarda de
      ordem via `ast`. Controle negativo: 2 failed na forma antiga.
- [ ] **#127** wheelhouse offline para o fallback pip (índice bloqueado sai 0 com venv vazia)
      — **prioridade caiu**: a #165 resolveu a falha aguda do Nexus (403 por pacote). O
      wheelhouse cobre o indice bloqueado por inteiro, que nao e o que o box do Werner mostra.

## Aberto durante a sessao (fora do Tier A, registrado para depois)

- **#167** gate de complexidade ciclomatica no python-common (1 testes / 2 modulos) — com medicao
- **#168** o mesmo gate explorado para os layouts ts-*

## Fora do Tier A (não tocam o duskko no dia 1)

ts-lib (#132–#136), gates de docs (#159, #130, #141), PR-gate (#145), GitGuardian (#153/#155/#129),
e as 7 issues abertas nesta sessão (#158–#164, exceto a própria #158).

## Registro de auditoria desta sessão

Varredura de lições em `~/dev`, `~/github` e `~/.claude` cruzada com as issues abertas. As ondas
1+2 (#113–#130, #143–#156) já haviam drenado o corpus até 2026-08-09 e carimbado as lições com
`blueprintx#N`; sobraram 14 lições capturadas depois, que viraram **#158–#164**. O diff
bidirecional espelho↔store deu 3 anomalias, todas conhecidas e benignas.

Dobras decididas (sem issue nova, mesma superfície entregue):
- skip de build output no `.codespellrc` → estende **#126**
- destinatários vazios no envio → critério de aceite da **#121**
