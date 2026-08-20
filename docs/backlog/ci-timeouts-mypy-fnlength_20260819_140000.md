# Backlog — #192 (CI timeouts) · #190 (mypy chassis) · #189 (function-length gate)

Criado 2026-08-19. Três issues abertas depois do fechamento da seção A do duskko.

## #192 — apt-get sem bound trava jobs de scaffold

- [ ] Guardar o install do `envsubst` em `command -v` (2 ocorrências,
      `.github/workflows/scaffold_checks.yml:187,227`)
- [ ] Guardar o install do `shellcheck` do mesmo jeito (mesmo shape, mesma exposição:
      `scaffold_checks.yml:28`, `templates/python-common/.github/workflows/tests.yaml:233`)
- [ ] `timeout-minutes` em **todo** job com `runs-on:` — 22 arquivos de workflow, 0 tinham bound
      (jobs que só fazem `uses:` não aceitam o campo)
- [ ] Verificar com `act` que o install ainda roda onde `envsubst` falta
- [ ] `bin/ci/check_actions.sh` verde

## #190 — chassis handlers fora do type-check

O `exclude` do mypy só afeta descoberta; `[mypy-chassis.*] ignore_errors = True` já entrou
na #191. Falta decidir se a dívida vira código type-clean.

- [ ] Decidir: manter `ignore_errors` ou tipar os handlers
- [ ] Root da maioria (8 de 20): fallback `except ImportError: <driver> = None`
- [ ] DSN parsing + argv de `pg_dump`/`mysqldump` (`list[str]`)
- [ ] Auditar os outros `exclude` pelo mesmo buraco de import-reachability

## #189 — gate de 60 linhas (docstring fora)

- [ ] `bin/check_function_length.py` baseado em `ast` (Ruff não tem regra de linhas por função)
- [ ] Ligar nas 4 superfícies dos dois lados (pre-commit, CI, Makefile, tasks.sh)
- [ ] Falhar quando a descoberta casar zero arquivos; imprimir a contagem no sucesso
- [ ] Controle negativo + entrada nas 5 copy lists
- [ ] Decisão em aberto: shell entra junto (rota 2) ou em issue de follow-up (rota 1)

## Nota

#167 (complexidade ciclomática) **existe como issue** e está aberta — o que não existe é
implementação. A memória do checkpoint dizia "não tem nem issue"; corrigido aqui.
