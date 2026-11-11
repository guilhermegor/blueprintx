# **FAQ**

Respostas para perguntas comuns sobre o uso e o desenvolvimento desta biblioteca. Acrescente
entradas específicas do projeto conforme elas surgirem nas issues.

> **Veja também:** [Uso](usage.md) · [Exemplos](examples.md) · [Contribuindo](contributing.md).

---

## Como instalo?

```bash
pip install <project_name>
```

Troque pelo nome real da distribuição e pelos extras, se houver (por exemplo,
`pip install "<project_name>[web]"`).

## Como adiciono ou atualizo uma dependência?

Use o Poetry para que o arquivo de lock continue sendo a fonte da verdade:

```bash
poetry add <package>          # dependência de runtime
poetry add --group dev <package>   # ferramenta somente de desenvolvimento
```

Todo pacote que o código importa deve ser uma dependência **direta** — nunca conte com ele
chegando de forma transitiva por outro pacote.

## Quais versões do Python são suportadas?

Veja a restrição `python = "..."` no `pyproject.toml`; o CI roda a matriz de testes contra cada uma.

## Como a versão é definida?

A versão é a **tag do git** (via poetry-dynamic-versioning); o `pyproject.toml` guarda um
valor provisório `0.0.0`. Faça o lançamento pelo workflow de release — veja
[Contribuindo](contributing.md).
