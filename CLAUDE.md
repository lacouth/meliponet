# CLAUDE.md

Orientações para quem trabalha neste repositório — humano ou agente.

O MelipoNet monitora colmeias de abelhas nativas sem ferrão. Três fatias
complementares (`firmware/`, `platform/`, `curation/`) costuradas por `contracts/`,
o contrato de telemetria que o firmware C++ e a plataforma Python acordam antes de
escrever código. Contexto completo no `README.md` e em `docs/guia/`.

## Ambiente

O Python da plataforma vive num virtualenv em `platform/.venv`, criado com
`python3 -m venv .venv` e povoado com `.venv/bin/pip install -e ".[dev]"` — é esse
segundo comando que traz o `ruff` e o `pytest`. O firmware usa PlatformIO, instalado
fora do repositório (`uv tool install platformio` ou `pipx install platformio`; não
use `pip install`, por causa da PEP 668).

## Verificação

`./verificar` roda, na ordem que falha mais rápido, as mesmas quatro verificações
que o CI roda a cada push. Prefira-o a invocar as ferramentas soltas:

    ./verificar              # tudo: contrato, ruff, pytest, testes nativos do firmware
    ./verificar contrato     # só os vetores dourados
    ./verificar plataforma   # só ruff e pytest
    ./verificar firmware     # só os testes nativos, no PC
    ./verificar alvo         # compila para o ESP32-C6 (baixa o toolchain na 1a vez)

O run completo termina em `=== tudo verde`; um subconjunto nomeia o que rodou. Se
faltar ferramenta, o script sai com código 2 e diz como instalá-la — isso é
diferente de teste vermelho, que sai com 1.

O espelho do `./verificar` é `.github/workflows/ci.yml`: mudou um, mude o outro.

## Fluxo de trabalho

- Em modo de planejamento, nunca crie branch, não faça commit e não dê push. O modo
  é de leitura: explore, confirme que a base está verde e apresente o plano. A
  branch só nasce depois do plano aprovado.

## Commits

- Trabalhe em commits pequenos, incrementais e verdes um a um: rode `./verificar`
  antes de cada commit, e nunca junte mudanças sem relação entre si.
- Antes de commitar, rode `git fetch && git status`, para enxergar o que outro
  processo empurrou enquanto você trabalhava.

## Refatoração

- Nunca use `sed` ou busca-e-troca em bloco para renomear. Renomeie símbolo por
  símbolo, com edições dirigidas, e rode a suíte inteira a cada lote de renomeações.
- Cuidado com colisões com membros da biblioteca padrão (`.size()`, `.length()`,
  `.data()`).

## O contrato

- `contracts/testdata/` é gerado, não editado à mão. Para mudar um vetor dourado,
  mude a fonte e rode `python3 contracts/tools/gen_testdata.py`; o `--check` do CI
  falha em vez de regravar, porque regerar um vetor é uma decisão e precisa aparecer
  no diff do commit.
- Os vetores são o único ponto de acordo entre as duas implementações. Mexer num
  lado sem o outro quebra o CI — que é exatamente o que ele existe para fazer.

## Estilo de código

- O código é escrito **em português** e para quem chega do Arduino: tipos, funções,
  variáveis, constantes e nomes de arquivo (`montarTelemetria`, `Leitura`,
  `CelulaDeCarga`). Não escreva código novo em inglês nem proponha reverter isso.
- A exceção: **o que aparece no JSON continua escrito como no JSON**. Os membros de
  `Telemetria` (`temp_in_c`, `weight_kg`, `node_id`, `seq`, `ts`), as constantes
  `Campo::` e `Flag::`, as chaves da NVS (`"ssid"`, `"wifi_pw"`, `"cal_offset"`) e os
  nomes dos comandos do console (`wifi`, `tara`, `ler`, `sondar`) ficam letra por
  letra como o contrato os escreve. Uma segunda grafia atrapalharia na hora de
  comparar o que o nó enviou com o que o banco guardou, e trocar uma chave de NVS
  faria placas já gravadas perderem a configuração em silêncio.
- Alguns termos ficam em inglês por serem vocabulário do glossário: `Spool`, `flag`,
  `MelipoCore`, `MelipoHardware`.
- Prefira a forma que um aluno de Arduino consegue ler, mesmo quando ela é menos
  idiomática ou um pouco mais verbosa. Ficaram fora do firmware, de propósito:
  ponteiro-para-membro, `enum class` de bits com sobrecarga de `operator|`, ponteiros
  para objetos globais com `static` dentro do `setup()`, e strings sem terminador
  nulo. Não os reintroduza.

## Comentários

- Cabeçalhos de arquivo são **curtos**: cinco a oito linhas dizendo o que o arquivo
  faz e qual regra o governa.
- O "porquê" continua obrigatório, mas as histórias longas de defeito moram em
  `docs/guia/04-o-firmware.md`, e o cabeçalho aponta para lá.

## Documentação

- Os guias em português vivem em `docs/guia/`, na convenção `NN-slug.md`. Todo guia
  novo traz diagramas de arquitetura em Mermaid e termina com uma seção do que ainda
  falta.
- `docs/exercicios/` segue a mesma numeração e é referenciado por
  `docs/guia/11-trilha-de-exercicios.md`. Cada exercício tem critério de pronto que o
  bolsista confere sozinho — se um exercício promete uma saída, ela precisa
  reproduzir literalmente.
