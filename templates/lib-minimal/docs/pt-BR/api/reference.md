# **Referência da API**

Interface pública desta biblioteca.

> **Veja também:** [Uso](../usage.md)

---

## Módulo: `main`

Módulo de ponto de entrada. Estenda-o com as funções públicas da sua biblioteca.

### `main() -> None`

Executa o ponto de entrada da biblioteca. Troque o corpo pela lógica de nível superior do seu projeto.

```python
from <package_name>.main import main

main()
```

---

## Adicionando novos módulos

Coloque os novos módulos em `src/<package_name>/`. Exporte os símbolos públicos em `src/<package_name>/__init__.py` para que quem usa a biblioteca possa fazer:

```python
from <package_name> import my_function
```

Siga a convenção de uma classe por arquivo: funções utilitárias sem estado compartilhado ficam no nível do módulo, e não dentro de uma classe.

---

## Convenções

| Convenção | Regra |
|-----------|-------|
| Type hints | Obrigatórias em todas as funções públicas, inclusive o retorno `-> None` |
| Docstrings | Estilo NumPy; explique o *porquê*, não o *quê* |
| Nomes de variáveis | Com prefixo de tipo (`str_`, `list_`, `cls_`, `dict_`, …) |
| Testes | `unittest`; uma asserção por teste; nome no formato `test_<unit>_<scenario>_<expected>` |
