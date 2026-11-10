<!-- readme-archetype: ${README_ARCHETYPE} -->
# ${PROJECT_DISPLAY_NAME}

<p align="center"><img src="https://raw.githubusercontent.com/${GITHUB_USERNAME}/${PROJECT_NAME}/main/assets/logo_lorem_ipsum.png" width="200" alt="${PROJECT_DISPLAY_NAME} logo"></p>

[![Project Status: Active](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)
![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)
[![PyPI](https://img.shields.io/pypi/v/${PROJECT_NAME}.svg)](https://pypi.org/project/${PROJECT_NAME}/)
[![Downloads](https://img.shields.io/pepy/dt/${PROJECT_NAME})](https://pepy.tech/projects/${PROJECT_NAME})
[![Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://${GITHUB_USERNAME}.github.io/${PROJECT_NAME}/)
[![Linting](https://img.shields.io/badge/linting-ruff_%7C_codespell-blue)](https://github.com/astral-sh/ruff)
[![Mypy](https://img.shields.io/badge/type--checked-mypy-blue)](https://mypy-lang.org)
![Test Coverage](https://raw.githubusercontent.com/${GITHUB_USERNAME}/${PROJECT_NAME}/badges/coverage.svg)
![License](https://img.shields.io/badge/license-${PROJECT_LICENSE}-green.svg)
![Open Issues](https://img.shields.io/github/issues/${GITHUB_USERNAME}/${PROJECT_NAME})
![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-darkgreen.svg)

<!-- slug: overview -->
## Visão geral

${PROJECT_DESCRIPTION}

<!-- optional section: delete it when the project has no feature list -->
<!-- slug: features -->
## Funcionalidades

- As capacidades que importam para quem usa, uma por linha.

<!-- slug: documentation -->
## Documentação

O site de documentação fica em https://${GITHUB_USERNAME}.github.io/${PROJECT_NAME}/. Para servi-lo localmente, rode `bash bin/poe_exec.sh docs_serve`.

<!-- slug: getting-started -->
## Primeiros passos

O Python 3.11+ é o único pré-requisito; o `bin/venv.sh` instala o [Poetry](https://python-poetry.org/) quando ele estiver ausente.

<!-- slug: install -->
### Instalação

```bash
git clone https://github.com/${GITHUB_USERNAME}/${PROJECT_NAME}.git
cd ${PROJECT_NAME}
bash bin/venv.sh
bash bin/poe_exec.sh init
```

O `poe` vive dentro do virtualenv, então o `bin/venv.sh` o cria primeiro; em seguida o
`bin/poe_exec.sh` roda o `poe init` sem ativar nada.

<!-- slug: usage -->
### Uso

Rode o projeto pelos pontos de entrada em `src/`; troque este parágrafo pelos comandos que as
pessoas usuárias executam primeiro.

<!-- slug: project-structure -->
## Estrutura do projeto

```text
${PROJECT_NAME}/
├── .github/        workflows, CODEOWNERS, PR template
├── .specs/         feature specs and backlog trackers
├── bin/            gate scripts and helpers
├── docs/           published documentation
├── src/            application code
├── tests/
│   ├── unit/
│   └── integration/
├── pyproject.toml
└── poe_tasks.toml  task runner entry points
```

<!-- slug: development -->
## Desenvolvimento

Depois do bootstrap descrito em Instalação, qualquer tarefa pode ser executada pelo script de
bootstrap: `bash bin/poe_exec.sh <task>`; e `bash bin/poe_exec.sh` sem tarefa lista todas elas.

```bash
bash bin/poe_exec.sh unit_tests
bash bin/poe_exec.sh integration_tests
```

Quando o deploy da documentação do primeiro release tiver criado a branch `gh-pages`, rode
`bash bin/poe_exec.sh enable_pages` uma vez: até que essa branch exista, o `init` deixa o Pages intocado.

<!-- slug: public-api -->
## API pública

A superfície pública é o que o `__init__.py` do pacote lista em `__all__`; tudo o que está em
`_internal/` é privado.

<!-- slug: publishing -->
## Publicação

Os lançamentos saem dos workflows de release em `.github/workflows/`; a tag do git é a versão.

O caminho da 0.x até a 1.0.0, e o gate de lançamento que o protege, está em
[docs/releasing-1-0-0.md](docs/releasing-1-0-0.md).

<!-- slug: contributing -->
## Contribuindo

Veja o [CONTRIBUTING.md](CONTRIBUTING.md) para as regras de branch, commit e revisão.

<!-- slug: license -->
## Licença

Este projeto é licenciado sob ${PROJECT_LICENSE}; veja [LICENSE](LICENSE).

<!-- slug: authors -->
## Autores

- ${AUTHOR_NAME} — [GitHub](https://github.com/${GITHUB_USERNAME}) | [LinkedIn](${LINKEDIN_URL})

<!-- slug: useful-links -->
## Links úteis

- [Repositório no GitHub](https://github.com/${GITHUB_USERNAME}/${PROJECT_NAME})
- [Issue Tracker](https://github.com/${GITHUB_USERNAME}/${PROJECT_NAME}/issues)
- [Documentação](https://${GITHUB_USERNAME}.github.io/${PROJECT_NAME}/)

---

<sub>Gerado a partir do template ${README_TIER} via [BlueprintX](https://github.com/guilhermegor/blueprintx).</sub>
<!-- add any project disclaimer inside the sub tag above; for a library wrapping a third party, e.g. "Unofficial, community library. Not affiliated with or endorsed by ORG_NAME." -->
