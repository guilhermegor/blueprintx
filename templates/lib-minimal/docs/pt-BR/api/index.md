# **Referência da API**

A interface pública, agrupada pela divisão de nível superior do próprio código.

> **Veja também:** [Uso](../usage.md)

## Páginas

| Grupo | Conteúdo |
|-------|----------|
| [Referência](reference.md) | A superfície pública entregue desde o primeiro dia |

## Fazendo esta seção crescer

Esta seção é um **diretório, e não uma página única**, de propósito. Uma referência de API cresce
a cada unidade entregue, então um único `api.md` vira a maior página do repositório; dividi-lo
depois é trivial, mas **quebra todo link profundo já publicado** — e para sempre, quando a
documentação versionada estiver no ar, porque `/<version>/api/#anchor` existe eternamente. O
custo de começar como diretório é um arquivo a mais e um nível a mais no nav, pago uma só vez.

Ao adicionar páginas:

- **Agrupe pela divisão de nível superior do próprio código — nunca invente uma taxonomia
  paralela** (por exemplo, uma página por módulo público, espelhando a divisão do pacote). Assim,
  quem conhece o pacote consegue adivinhar a URL, e a documentação não se afasta de uma estrutura
  que ela espelha.
- **A profundidade segue a quantidade, não o gosto.** O eixo real define as seções; só o volume
  decide se uma seção precisa de um segundo nível.
- O texto compartilhado por um grupo fica uma única vez na página desse grupo, sem ser repetido
  em cada item.
- **Registre toda página nova em `nav:` no `mkdocs.yml` no mesmo commit.** O MkDocs publica uma
  página não registrada mesmo assim — ela só some da navegação, que é como uma página desaparece
  em silêncio (e o que o gate `check_docs_sections.py` existe para pegar).
