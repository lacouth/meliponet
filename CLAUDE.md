# CLAUDE.md

Orientações para quem trabalha neste repositório — humano ou agente.

O MelipoNet monitora colmeias de abelhas nativas sem ferrão, e é **antes de tudo um
projeto de ensino**. A plataforma web (`platform/`) é código nosso e funciona; o firmware
do nó sensor é **exercício do aluno**, e por isso `firmware/` guarda apenas
`ROTEIRO.md` — o que precisa ser programado, com etapas verificáveis. `contracts/` é o
acordo entre os dois. Contexto completo no `README.md`, em `docs/trilha.md` e em
`docs/guia/`.

## O firmware não é nosso

- **Não escreva o firmware do nó.** Se um pedido levar a implementar leitura de sensor,
  montagem da mensagem, envio para a plataforma ou spool em C++/Arduino, o entregável
  certo é o roteiro, o critério de pronto e a documentação — não a solução.
- O código C++ que existiu aqui até a virada para projeto de ensino está preservado na tag
  `firmware-referencia-v1`. Ele é gabarito do orientador, não material do aluno.
- `.gitignore` ignora `firmware/` inteiro menos o `ROTEIRO.md`, para que o projeto pessoal
  de quem está fazendo o exercício não seja commitado por engano.

## Ambiente

O Python da plataforma vive num virtualenv em `platform/.venv`, criado com
`python3 -m venv .venv` e povoado com `.venv/bin/pip install -e ".[dev]"` — é esse segundo
comando que traz o `ruff` e o `pytest`. Não há mais nenhuma ferramenta a instalar.

## Verificação

`./verificar` roda as mesmas duas verificações que o CI roda a cada push. Prefira-o a
invocar as ferramentas soltas:

    ./verificar              # ruff e pytest
    ./verificar plataforma   # o mesmo; o nome existe para quem procura por ele

Termina em `=== tudo verde`. Se faltar ferramenta, o script sai com código 2 e diz como
instalá-la — isso é diferente de teste vermelho, que sai com 1.

O espelho do `./verificar` é `.github/workflows/ci.yml`: mudou um, mude o outro.

## Fluxo de trabalho

- Em modo de planejamento, nunca crie branch, não faça commit e não dê push. O modo é de
  leitura: explore, confirme que a base está verde e apresente o plano. A branch só nasce
  depois do plano aprovado.

## Commits

- Trabalhe em commits pequenos, incrementais e verdes um a um: rode `./verificar` antes de
  cada commit, e nunca junte mudanças sem relação entre si.
- Antes de commitar, rode `git fetch && git status`, para enxergar o que outro processo
  empurrou enquanto você trabalhava.

## Refatoração

- Nunca use `sed` ou busca-e-troca em bloco para renomear. Renomeie símbolo por símbolo,
  com edições dirigidas, e rode a suíte inteira a cada lote de renomeações.

## O contrato

- `contracts/telemetry.v1.schema.json` é o que o ingestor valida, e `contracts/exemplos/`
  é o que o roteiro do firmware manda o aluno reproduzir. Os dois mudam juntos: um exemplo
  que a plataforma recusa é um roteiro que ensina errado, e `platform/tests/test_contract.py`
  existe para que isso quebre aqui em vez de na bancada.
- Campo novo entra como **opcional**. Alteração incompatível exige uma `v2`, com o ingestor
  aceitando as duas versões durante a transição.
- Mudança que atravessa o nó e a plataforma **começa no contrato**.

## Estilo de código

- O código é escrito **em português** e para quem chega do Arduino: tipos, funções,
  variáveis, constantes e nomes de arquivo (`montarTelemetria`, `Leitura`,
  `CelulaDeCarga`). Não escreva código novo em inglês nem proponha reverter isso.
- A exceção: **o que aparece no JSON continua escrito como no JSON**. Os campos da
  mensagem (`temp_in_c`, `weight_kg`, `node_id`, `seq`, `ts`), os nomes das flags e as
  chaves da NVS (`"ssid"`, `"wifi_pw"`, `"cal_offset"`) ficam letra por letra como o
  contrato os escreve. Uma segunda grafia atrapalharia na hora de comparar o que o nó
  enviou com o que o banco guardou, e trocar uma chave de NVS faria placas já gravadas
  perderem a configuração em silêncio.
- Alguns termos ficam em inglês por serem vocabulário do glossário: `Spool`, `flag`.
- Prefira a forma que um aluno de Arduino consegue ler, mesmo quando ela é menos idiomática
  ou um pouco mais verbosa.

## Comentários

- Cabeçalhos de arquivo são **curtos**: cinco a oito linhas dizendo o que o arquivo faz e
  qual regra o governa.
- O "porquê" continua obrigatório.

## Documentação

- `docs/trilha.md` é a porta de entrada, e aponta para `docs/exercicios/NN-slug.md` (oito
  exercícios) e para `firmware/ROTEIRO.md`.
- Os guias em português vivem em `docs/guia/`, na convenção `NN-slug.md`, e hoje são seis.
  Todo guia traz diagramas de arquitetura em Mermaid e termina com uma seção do que ainda
  falta.
- Cada exercício tem critério de pronto que o aluno confere sozinho — se um exercício
  promete uma saída, ela precisa reproduzir literalmente.
- Simplicidade é requisito, não estética: diante de uma bifurcação, prefira a alternativa
  que o aluno consegue acompanhar sozinho.
