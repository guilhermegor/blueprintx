# **Registro de Incidentes**

O que quebrou neste projeto e o que mudou para que não quebre mais daquele jeito. Esta página
mantém o conhecimento de depuração dentro do código, e não no histórico do git nem na memória
de uma única pessoa: o conhecimento que a equipe já pagou uma vez não deveria ser pago de novo.

> **Veja também:** [Uso](usage.md) · [Contribuindo](contributing.md) · [Histórico de mudanças](changelog.md).

## Não é um ADR, nem um repositório de lições

Um **ADR** registra uma decisão tomada *antes* de algo dar errado. Um registro de incidente
documenta uma decisão tomada *porque* algo já deu errado: gatilho diferente, público diferente.
Se este projeto adotar ADRs no futuro, mantenha os dois separados em vez de misturá-los num
mesmo balaio.

Também não é uma cópia do repositório de "lições aprendidas" de uma ferramenta de scaffolding.
Esse tipo de repositório responde "o que todo projeto gerado no futuro deve herdar"; esta
página responde "o que feriu *este* código e o que fizemos a respeito". Público diferente,
tempo de vida diferente.

## Publicado de propósito: oculte antes de escrever

Esta página vai para o site de documentação publicado, assim como [Uso](usage.md). Um incidente
pode carregar detalhes de produção (um nome de servidor, uma consulta, um sintoma visível ao
cliente) que não devem chegar a um site público. Oculte ou generalize esses detalhes antes de
confirmar a entrada, como um postmortem externo omite os detalhes internos. Se o site deste
projeto for de fato público e as entradas não puderem ficar ocultadas, exclua `incidents.md`
via `exclude_docs` no `mkdocs.yml` em vez de deixá-lo pela metade.

## Formato

Cinco campos, nesta ordem. Mantenha cada um em poucas frases: a entrada deixa de ser escrita no
dia em que preenchê-la leva uma hora.

- **Sintoma**: o que foi observado, não o que estava errado.
- **Como foi encontrado**: a ferramenta, o comando ou o acidente que o revelou; "fomos
  cuidadosos" não entra aqui.
- **Causa raiz**: medida, não presumida.
- **A mudança**: o que agora torna essa classe de falha impossível, ou barulhenta em vez de
  silenciosa.
- **Como saberíamos que voltou**: o gate, o teste ou a asserção que a pegaria voltando.

---

## MODELO: substitua pelo primeiro incidente real deste projeto

Apague esta seção quando tiver uma entrada sua. Ela fica apenas para que o leitor veja como
é uma entrada preenchida: uma página vazia ensina o leitor que não há nada para ler aqui.

### 2026-08-16: reconfigurar o logger vazava um descritor de arquivo a cada vez

**Sintoma.** Objetos `logging.FileHandler` se acumulavam durante a vida do processo sempre que
o logger era reconfigurado (por exemplo, ao girar para um novo arquivo de log datado).
Inofensivo num script de vida curta; num serviço de longa duração, os descritores vazados se
acumulam.

**Como foi encontrado.** Não pela suíte de testes: o `ResourceWarning` não é exibido por padrão
no Python. Só apareceu quando a suíte rodou com `-W always`, ao medir outra coisa. O defeito era
invisível por construção, não por descuido de alguém.

**Causa raiz.** O caminho de reconfiguração chamava `logger.handlers.clear()` para desanexar o
handler antigo antes de anexar um novo. Limpar a lista descarta a *referência* em Python; não
fecha o descritor de arquivo do sistema, que continua aberto até o coletor de lixo rodar.

**A mudança.** Fechar explicitamente cada handler existente antes de desanexá-lo, de modo que o
descritor seja liberado na hora e não na coleta. Um único ponto de chamada: `handlers.clear()`
aparecia exatamente uma vez em todo o código, então nenhum chamador irmão ficou sem correção.

**Como saberíamos que voltou.** Um teste reconfigura o logger duas vezes e afirma que o
`.stream` do primeiro handler é `None` após a segunda chamada: `close()` define esse atributo
no instante em que o descritor é liberado, então a asserção não depende do momento da coleta de
lixo. ⚠️ Medido separadamente: promover o `ResourceWarning` puro a `error:` no `pytest.ini`
**não** pega isso sozinho, pois ele é levantado a partir de `__del__`, um contexto *unraisable*
que o pytest rebaixa para `PytestUnraisableExceptionWarning`; as duas classes de aviso precisam
ser promovidas juntas, ou a suíte continua passando sobre um vazamento real.
