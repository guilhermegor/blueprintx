# **Registros de incidentes**

O que quebrou neste projeto e o que mudou para que não quebre mais daquela forma. Esta página
mantém o conhecimento de depuração dentro do código, e não no histórico do git nem na memória de
uma única pessoa — o conhecimento que a equipe já pagou uma vez não deveria ser pago duas vezes.

> **Veja também:** [Uso](usage.md) · [Contribuindo](contributing.md) · [Histórico de mudanças](changelog.md).

## Não é um ADR, nem um repositório de lições

Um **ADR** registra uma decisão tomada *antes* de algo dar errado. Um registro de incidente
documenta uma decisão tomada *porque* algo já deu errado — gatilho diferente, público diferente.
Se este projeto adotar ADRs no futuro, mantenha os dois separados em vez de misturá-los num
mesmo balaio.

Também não é uma cópia do repositório de "lições aprendidas" de uma ferramenta de scaffolding.
Esse tipo de repositório responde "o que todo projeto gerado no futuro deve herdar" — esta
página responde "o que afetou *este* código e o que fizemos a respeito". Público diferente,
vida útil diferente.

## Publicada de propósito — anonimize antes de escrever

Esta página vai para o site de documentação publicado, assim como [Uso](usage.md). Um incidente
pode conter detalhes de produção (um nome de host, uma consulta, um sintoma visível ao cliente)
que não devem chegar a um site público — anonimize ou generalize antes de registrar a entrada,
como um postmortem externo omite detalhes internos. Se o site deste projeto for realmente
público e as entradas não puderem ser anonimizadas, exclua `incidents.md` via `exclude_docs` no
`mkdocs.yml` em vez de deixá-la pela metade.

## Formato

Cinco campos, nesta ordem. Mantenha cada um em poucas frases — a entrada deixa de ser escrita no
dia em que preenchê-la leva uma hora.

- **Sintoma** — o que foi observado, não o que estava errado.
- **Como foi encontrado** — a ferramenta, o comando ou o acaso que revelou o problema; "fomos
  cuidadosos" não cabe aqui.
- **Causa raiz** — medida, não presumida.
- **A mudança** — o que agora torna essa classe de falha impossível, ou barulhenta em vez de
  silenciosa.
- **Como saberíamos que regrediu** — o gate, teste ou asserção que pegaria o problema voltando.

---

## MODELO — substitua pelo primeiro incidente real deste projeto

Apague esta seção quando tiver uma entrada própria. Ela fica apenas para que o leitor veja como
é uma entrada preenchida — uma página vazia ensina que não há nada para ler aqui.

### 2026-08-16 — Reconfigurar o logger vazava um descritor de arquivo a cada vez

**Sintoma.** Objetos `logging.FileHandler` se acumulavam ao longo da vida do processo sempre que
o logger era reconfigurado (por exemplo, ao trocar para um novo arquivo de log datado). Inofensivo
em um script de vida curta; em um serviço de longa duração, os descritores vazados se acumulam.

**Como foi encontrado.** Não pela suíte de testes — `ResourceWarning` não é exibido por padrão no
Python. Só apareceu quando a suíte rodou com `-W always`, ao medir outra coisa. O defeito era
invisível por construção, não por descuido de alguém.

**Causa raiz.** O caminho de reconfiguração chamava `logger.handlers.clear()` para desanexar o
handler antigo antes de anexar um novo. Limpar a lista descarta a *referência* do Python; não
fecha o descritor de arquivo do sistema operacional, que permanece aberto até o coletor de lixo
rodar.

**A mudança.** Fechar explicitamente cada handler existente antes de desanexá-lo, para que o
descritor seja liberado na hora e não na coleta de lixo. Um único ponto de chamada —
`handlers.clear()` aparecia exatamente uma vez em todo o código, então nenhum chamador irmão
ficou sem correção.

**Como saberíamos que regrediu.** Um teste reconfigura o logger duas vezes e afirma que
`.stream is None` no primeiro handler após a segunda chamada — `close()` define esse atributo no
instante em que o descritor é liberado, então a asserção não depende do momento da coleta de
lixo. ⚠️ Medido separadamente: promover `ResourceWarning` a `error:` no `pytest.ini` **não**
pega isso sozinho — ele é emitido por `__del__`, um contexto *unraisable* que o pytest rebaixa
para `PytestUnraisableExceptionWarning`, então as duas classes de aviso precisam ser promovidas
juntas, ou a suíte continua passando por cima de um vazamento real.
