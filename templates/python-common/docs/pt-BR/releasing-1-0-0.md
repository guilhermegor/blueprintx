# Lançando a 1.0.0

A 1.0.0 é o momento em que esta biblioteca promete a sua API pública. Até lá valem as regras da
0.x: uma mudança incompatível é um aumento de MINOR, e uma funcionalidade ou correção é um
aumento de PATCH. A partir da 1.0.0, vale o semver completo. Duas coisas precisam ser verdade
nesse momento e são fáceis de errar à mão: o backlog está concluído e a documentação descreve o
código que de fato é entregue.

## O caminho

1. A issue **Cut 1.0.0** é aberta para você quando o scaffold cria o repositório no GitHub, a
   partir do template de issue, com `state:blocked` e bloqueada por todas as outras issues
   abertas (no kanban, com status `Blocked`). Se o repositório não foi criado pelo scaffold,
   abra-a à mão a partir do template de issue, com o label `state:blocked` e o título exato
   `Cut 1.0.0`.
2. Implemente o backlog. Uma issue que não vai entrar na 1.0.0 recebe o label `post-1.0`,
   aplicado pelo dono (o scaffold cria o label; do contrário, `gh label create post-1.0`), de
   modo que ela fique adiada no registro, e não descartada.
3. Percorra o checklist da issue: a auditoria da documentação, os exemplos executáveis, a tabela
   de versões suportadas da 1.x no `SECURITY.md`, o congelamento da API pública (audite os nomes
   exportados; remover um depois da 1.0 é uma 2.0), a garantia de API da 1.x declarada nas notas
   da release 1.0.0 e no README (o `CHANGELOG.md` é regenerado, então não pode guardá-la) e todo
   pull request aberto mesclado, fechado ou explicitamente adiado para depois da 1.0 pelo dono;
   depois, o ensaio e a publicação. Projetos Python também trocam o classifier para
   `Development Status :: 5 - Production/Stable`, conferem se `requires-python` (a restrição
   `python` do Poetry) e um classifier de Python por versão da matriz do `tests.yml` concordam,
   e confirmam que o `py.typed` está no wheel construído.
4. Depois do lançamento, troque a política de versão documentada para o semver completo e, em um
   projeto que publica a documentação com mike, confirme que o alias `latest` foi para a 1.0.

## O gate de lançamento

O workflow de release roda `bin/check_release_gate.py` antes de publicar. Ele só se aplica
quando o MAJOR solicitado é pelo menos 1 e a última versão publicada é 0.x. Nesse caso, ele lista
as issues abertas e falha enquanto alguma não tiver o label `post-1.0`, nomeando cada uma.

- Pull requests não são contados, nem a própria issue **Cut 1.0.0**. Isso é uma decisão, não
  um esquecimento: falhar por PRs abertos deixaria um PR fixo do Dependabot ou uma branch de
  funcionalidade `post-1.0` bloquear todo lançamento, e o gate não tem um label para isentar um
  PR. O menor raio de impacto é manter o gate nas issues e colocar "todo PR aberto mesclado,
  fechado ou adiado para depois da 1.0" no checklist da **Cut 1.0.0**, onde o dono julga cada PR.
- As issues são lidas pela API REST do GitHub com o token do workflow, somente leitura.
- Se a API não puder ser lida, o gate falha fechado: ele bloqueia o lançamento em vez de
  adivinhar.
- Qualquer outro aumento de versão, como 0.4.0 para 0.5.0 ou 1.0.0 para 1.0.1, não é afetado.
- Uma primeira publicação conta como vinda de 0.0.0, então um projeto cuja primeira release é a
  1.0.0 também passa pelo gate.

## A verificação de módulos inalcançáveis

Uma biblioteca Python traz `bin/check_unreachable_modules.py`, e o gate de lançamento o roda
depois da verificação das issues abertas. Ele existe porque o deptry enxerga dependências não
usadas, não módulos não usados: um seam do template que o pacote nunca ligou (`http_downloader`,
`daily_cache`, `retry/` e assim por diante) continua em `src/`, e um módulo morto que importa um
pacote de terceiros mantém essa dependência "em uso".

- Um módulo é **público** quando nenhum segmento do seu caminho pontuado começa com `_`. O gate
  percorre os `import` e `from ... import` (imports relativos resolvidos) a partir dos módulos
  públicos, e um módulo alcançado também alcança seus pacotes pai. Todo módulo de `src/` que
  sobrar reprova o gate, e a saída nomeia cada um.
- Corrija um achado removendo o módulo, seus testes e toda dependência que só ele importava, e
  rodando o deptry de novo. Um módulo carregado dinamicamente (`importlib.import_module` com uma
  string, um entry point, uma string de engine) é invisível ao percurso: coloque-o em
  `.unreachable-modules.txt` na raiz do projeto, um `<módulo ou glob> | <motivo>` por linha. Uma
  entrada sem motivo, ou que não corresponda a nenhum módulo inalcançável, reprova o gate.
- Ele roda só no gate de lançamento, não no CI: um scaffold novo de biblioteca traz os seams do
  template sem ligação de propósito, então a verificação ficaria vermelha desde o primeiro commit.
- Um import sob `if TYPE_CHECKING:`, ou dentro de uma função, conta como alcançado. Os testes não
  são raízes: um módulo que só os testes importam está morto.
- Um projeto sem o script, como uma biblioteca TypeScript, pula a verificação.

Para passar, implemente cada issue citada ou aplique a ela o label `post-1.0`, remova ou
coloque na lista cada módulo apontado, e então rode o workflow de novo.
