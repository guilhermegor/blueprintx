# Guia de Contribuição

Obrigado por considerar contribuir com o nosso projeto! Reserve um momento para ler estas diretrizes e garantir uma colaboração tranquila.

## Convenções de Desenvolvimento

### Padrões de Nomes de Variáveis

Usamos as seguintes convenções padronizadas de nomes de variáveis:

| Variável        | Descrição |
|-----------------|-----------|
| `int_cddr`      | Inteiro: dias corridos do prazo de resgate (do aporte à entrega) |
| `int_wddr`      | Inteiro: dias úteis do prazo de resgate (do aporte à entrega) |
| `int_cddt`      | Inteiro: dias corridos do prazo total do investimento (do aporte ao vencimento) |
| `int_wddt`      | Inteiro: dias úteis do prazo total do investimento (do aporte ao vencimento) |
| `int_cddm`      | Inteiro: dias corridos por mês (convenção: 30) |
| `int_wddm`      | Inteiro: dias úteis por mês (convenção: 22) |
| `int_cddy`      | Inteiro: dias corridos por ano (convenção: 365) |
| `int_wddy`      | Inteiro: dias úteis por ano (convenção: 252) |
| `int_cd_bef`    | Inteiro: dias corridos antes (convenção: 1) |
| `int_wd_bef`    | Inteiro: dias úteis antes (convenção: 1) |
| `int_cd_aft`    | Inteiro: dias corridos depois (convenção: 1) |
| `int_wd_aft`    | Inteiro: dias úteis depois (convenção: 1) |
| `int_cd_cap`    | Inteiro: dias corridos de capitalização |
| `int_wd_cap`    | Inteiro: dias úteis de capitalização |
| `int_nper_cd`   | Inteiro: número de períodos (dias corridos) |
| `int_nper_wd`   | Inteiro: número de períodos (dias úteis) |
| `float_pv`      | Valor presente do principal do instrumento (negativo na compra, positivo na venda) |
| `float_fv`      | Valor futuro do principal do instrumento (negativo na compra, positivo na venda) |
| `float_notional`| Valor precificado do contrato em termos absolutos |
| `float_position_value`| Valor contábil atual de mercado, para fins tributários |
| `float_acquisition_basis`| Custo contábil de aquisição, para fins tributários |
| `float_size`    | Tamanho do contrato do instrumento |
| `float_xcg`     | Valor de câmbio para a precificação do instrumento |
| `float_qty`     | Quantidade de instrumentos (positiva na compra, negativa na venda) |
| `date_ref`        | Data de referência |
| `date_xpt`        | Data de vencimento |
| `date_rdm`        | Data de resgate |
| `date_start`        | Data de início |
| `date_end`        | Data de fim |
| `date_current` | Data atual, para fins de iteração |
| `int_n_smp`     | Número de amostras |
| `int_max_retries` | Número máximo de tentativas |

## Estratégia de Branches

**A `main` é protegida: commits e pushes diretos são bloqueados** (`no-commit-to-branch` localmente,
proteção de branch no servidor do GitHub). Toda mudança entra por branch, Pull Request e merge
(online), ou por `poe new_branch` e `poe git_merge_to_main` (offline).

### Convenção de Nomes de Branch

Toda branch segue o padrão `<propósito>/<número-da-issue>-<tarefa>`
(por exemplo `feat/42-user-authentication`). O workflow `branch-has-issue` rejeita uma
branch sem o número da issue, exceto `release/`, `dependabot/` e `renovate/`.

**Propósitos disponíveis:**

| Propósito       | Formato                     | Quando usar |
|-----------------|-----------------------------|-------------|
| Feature         | `feature/<N>-<nome>` ou `feat/<N>-<nome>` | Funcionalidade nova |
| Bugfix          | `bugfix/<N>-<descrição>` ou `fix/<N>-<descrição>` | Correção de defeito |
| Hotfix          | `hotfix/<N>-<descrição>` | Correções críticas em produção |
| Release         | `release/<versão>` | Preparação de versão |
| Documentation   | `docs/<N>-<descrição>` | Atualização de documentação |
| Refactor        | `refactor/<N>-<descrição>` | Melhorias de código |
| Chore           | `chore/<N>-<descrição>` | Manutenção do projeto |

**Exemplos:**
- `feat/42-user-authentication`
- `fix/57-login-validation-issue`
- `docs/63-update-api-reference`

## Padrões de Mensagem de Commit

Todo commit segue a especificação [Conventional Commits](https://www.conventionalcommits.org/): `<tipo>/<escopo>`.
As mensagens de commit são escritas em inglês, porque fazem parte do registro técnico.

**Tipos disponíveis:**

| Tipo       | Finalidade |
|------------|------------|
| `build`    | Mudanças no build ou nas dependências |
| `ci`       | Mudanças na configuração de CI |
| `docs`     | Atualizações de documentação |
| `feat`     | Funcionalidades novas |
| `fix`      | Correções de defeitos |
| `perf`     | Melhorias de desempenho |
| `refactor` | Reestruturação de código |
| `style`    | Mudanças de formatação |
| `test`     | Inclusão ou alteração de testes |
| `chore`    | Tarefas de manutenção |
| `revert`   | Reversão de mudanças |
| `bump`     | Atualização de versão |

**Exemplos:**
- `feat(auth): implement OAuth2 integration`
- `fix(calculations): correct rounding errors in tax computation`
- `docs(readme): add installation instructions`

**Verificação antes do commit:** `poe check_commit_msg <arquivo>` roda em segundos as mesmas
verificações de gitlint e commitizen que o hook `commit-msg` impõe, e pega um título longo demais
ou um tipo errado antes que o problema apareça depois de todo o gate de pre-commit (lint, testes,
cobertura) já ter rodado.

## Configuração do Ambiente de Desenvolvimento

1. **Gerenciamento de dependências**:
   - Use o Poetry (versão definida em `requirements.txt`)
   - Evite adicionar bibliotecas redundantes: confira o `pyproject.toml` antes
   - Rode `poetry install` para preparar o ambiente de desenvolvimento

2. **Hooks de pre-commit**:
   - Instale com `poe precommit`
   - Isso habilita, automaticamente:
     - Lint de código
     - Formatação
     - Varredura de vulnerabilidades de segurança
     - Detecção de arquivos grandes
     - Detecção de chaves secretas

3. **Framework de testes**:
   - Mantenha a estrutura padrão de arquivos:
     - Implementação: `src/<nome_da_feature>.py`
     - Testes: `tests/test_<nome_da_feature>.py`
   - Rode a validação completa com: `poe unit_tests -k <palavra-chave>`
        - Esse comando executa:
            - **Ruff**: lint, formatação e sinalização de recursos obsoletos do Python
            - **Codespell**: verificação ortográfica em comentários e docstrings
            - **Testes automatizados**: todos os casos de teste que seguem os padrões do projeto
   - Garanta 100% de cobertura de testes nos componentes críticos
   - Rode os testes localmente antes de enviar as mudanças

4. **Desenvolvimento guiado por testes**:
   - Escreva os testes antes da implementação sempre que possível
   - Inclua operações normais, casos de borda, condições de erro, validação de tipos e verificação dos exemplos das docstrings
   - Mantenha fixtures para os cenários complexos
   - Recomenda-se usar o UNIT_TEST_TEMPLATE.md para gerar testes unitários com IA, de modo a aplicar as boas práticas de desenvolvimento guiado por testes e seguir os padrões do projeto

5. **Ordem dos testes e falhas ligadas a uma seed**:
   - O `pytest-randomly` embaralha a ordem dos testes a cada execução e imprime a seed usada,
     com sucesso ou falha: uma dependência escondida entre testes (um teste de `get` que
     depende do estado deixado por um teste de `post`) falha, em vez de passar em silêncio
     para sempre.
   - A seed aparece no cabeçalho da sessão como `Using --randomly-seed=<N>`, em toda
     execução e não apenas na falha. Para reproduzir uma ordem, monte o comando com esse
     número: `pytest -p randomly --randomly-seed=<N>`.
   - **Um teste que falha apenas com uma seed específica é um defeito real, nunca uma
     instabilidade para rodar de novo até passar.** Rodar até ficar verde esconde exatamente
     o defeito que isso existe para pegar: informe a seed e o teste que falhou, em vez de
     tentar de novo.
   - Uma fixture com `scope="module"`/`"class"`/`"session"` compartilha a instância entre os
     testes, que é justamente a forma que uma dependência de ordem assume.
     O `check_fixture_scope.py` (um indicador, não um detector: veja a docstring do módulo)
     exige um comentário `# fixture-scope-ok: <motivo>` escrito antes de aceitar uma.

## Processo de Pull Request

1. **Abra uma issue primeiro**:
   - Confira as issues existentes na página de [Issues do GitHub](../../issues) deste repositório
   - Abra uma issue nova com o template do repositório se não houver uma para o seu trabalho
   - Diga o que você quer mudar e por quê, e liste os arquivos que serão tocados
   - Em trabalhos não triviais, espere a issue ser aceita antes de escrever código

2. **Crie a branch a partir da branch padrão**:
   - Nomeie como `<tipo>/<número-da-issue>-<slug>` (por exemplo `feat/42-user-authentication`);
     veja "Convenção de Nomes de Branch" acima

3. **Abrindo o PR**:
   - Coloque `Closes #<N>` no corpo do PR para que a issue feche quando o PR for mesclado
   - Preencha o template de PR por completo
   - Inclua:
     - Descrição detalhada
     - Mudanças feitas
     - Testes realizados
     - Atualizações de documentação
     - Qualquer dívida técnica criada

4. **Revisão de código**:
   - Espere feedback construtivo
   - Responda a todos os comentários da revisão
   - Atualize a documentação conforme necessário
   - Mantenha os commits organizados de forma lógica

5. **Aprovação do merge**:
   - Exige pelo menos uma aprovação
   - Todos os testes devem passar
   - A cobertura de código não deve diminuir
   - A documentação deve estar atualizada

### Guardas de Baseline-Ratchet: o PR do Baseline Entra Primeiro

Uma guarda de baseline-ratchet tolera o que existe hoje e dá a todo arquivo novo um orçamento
zero. O orçamento de comentários (`bin/check_comment_budget.py`, baseline `comment_budget_baseline.txt`)
é a guarda atual. O baseline é um retrato da branch padrão, então todo PR que entra antes do PR
que o cria ou o regenera adiciona arquivos para os quais o retrato não tem linha, e esse PR fica
vermelho a cada atualização de branch, sem culpa própria.

- **O PR que cria ou regenera um baseline entra primeiro.** Segure a fila de merge até ele
  chegar; numa fila serial, caso contrário, ela nunca converge, e um PR de baseline vermelho
  empurrado para o fim da fila continua vermelho.
- **As violações novas de um PR posterior são de quem o escreveu corrigir, nunca de baselinar.**
  Não regenere o baseline para absorvê-las; o ratchet só desce.
- O `--write-baseline` registra o commit medido numa linha `base <sha>` (`unknown` quando o git
  não está disponível) e o imprime. Uma execução que falha imprime `baselined at <sha>, HEAD is
  at <sha>`, de modo que um baseline velho aparece no log do CI em vez de parecer um PR quebrado.

## Boas Práticas

- **Mantenha as branches focadas**: uma funcionalidade ou correção por branch
- **Faça commits pequenos e frequentes**: são mais fáceis de revisar
- **Escreva mensagens de commit descritivas**: explique o porquê, não só o quê
- **Atualize a documentação**: ao adicionar funcionalidades novas
- **Siga os padrões existentes**: mantenha a consistência
- **Comunique-se cedo**: se estiver travado ou precisar de esclarecimento

Agradecemos suas contribuições e esperamos colaborar com você!
