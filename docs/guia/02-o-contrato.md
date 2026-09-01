# 2. O contrato

## O problema que ele resolve

Duas pessoas escrevem código que precisa se entender:

- você, em **C++**, faz o ESP32 montar a mensagem de telemetria;
- outra pessoa, em **Python**, faz a plataforma ler essa mensagem.

Vocês não compartilham uma linha de código. Linguagens diferentes, compiladores
diferentes, bolsas diferentes, cronogramas diferentes. E precisam concordar **byte a
byte** sobre o formato da mensagem.

O jeito ingênuo é combinar por WhatsApp e cada um escrever o seu teste. Não funciona, e
o motivo é sutil: se você escreve um teste em C++ afirmando que o peso sai como `12.5`,
e sua colega escreve um teste em Python afirmando que ela lê `12.500`, **os dois testes
passam** e o sistema está quebrado. Cada um testou contra a própria crença.

Um contrato de verdade precisa ser um **terceiro artefato, externo aos dois**.

## O que é um contrato aqui

A pasta `contracts/` é a fonte da verdade. Contém:

| Arquivo | O que é |
|---|---|
| `telemetry.v1.schema.json` | a especificação formal da mensagem |
| `canonical.py` | as regras de formatação exata |
| `tools/gen_testdata.py` | o gerador dos casos de teste |
| `testdata/telemetry_*.json` | mensagens válidas de referência |
| `testdata/invalid/*` | mensagens que devem ser recusadas, com o motivo |
| `testdata/vectors.h` | os mesmos casos, em C++ |

## A mensagem

```json
{"schema":"meliponet.telemetry.v1","node_id":"A4C1380F","seq":10432,
 "ts":"2027-03-14T12:05:00Z","temp_in_c":30.12,"temp_out_c":34.80,
 "rh_in_pct":68.40,"rh_out_pct":41.20,"weight_kg":12.483,"vbat_v":3.92,"rssi":-58}
```

Três campos merecem atenção:

**`seq`** é um contador que só cresce, guardado na memória não-volátil do nó (NVS). Ele
sobrevive a reset. É o que permite à plataforma saber **quantas mensagens se perderam**:
se chegaram as `seq` 100, 101 e 104, sabemos que duas sumiram. Sem `seq`, a perda seria
estimada pelo intervalo entre horários — um chute.

**`ts`** é o instante da medição, sempre em UTC, sempre com o `Z` no fim. Não é o
instante da chegada. Uma mensagem que ficou horas no spool chega hoje com o carimbo de
ontem — e é assim que tem que ser.

**Campos ausentes são omitidos, nunca enviados como zero.** Se o SHT30 externo falhou,
`temp_out_c` simplesmente não aparece, e uma flag explica. Zero significaria "a colmeia
estava a 0 °C", que é uma afirmação falsa sobre o mundo. Ausente significa "não
sabemos", que é verdade. Essa distinção é o insumo dos indicadores de qualidade do
Edital 17.

## A regra que mais te afeta: inteiros escalados

**No firmware, nenhuma métrica é `float`.** Temperatura trafega em centésimos de grau,
peso em gramas, umidade em centésimos de ponto percentual.

```c
int32_t temp_in_c = 3012;   // 30,12 °C
int32_t weight_kg = 12483;  // 12,483 kg
```

Isso parece capricho até você tentar a alternativa. Se cada lado formatasse um `float`
com `printf("%.2f")`, a saída **não seria reproduzível**:

- a `printf` da newlib do ESP32 não arredonda igual à glibc do PC;
- o ESP32 calcula em `float` de 32 bits, o Python em `double` de 64;
- casos de empate como 30,125 caem para lados diferentes conforme a implementação.

Você teria um sistema que funciona 99,9% das vezes e falha em leituras específicas, de
forma que ninguém consegue reproduzir. É o pior tipo de bug.

Com inteiros escalados, **o arredondamento acontece uma vez só**, na camada de sensores,
e vira parte da medição em vez de um detalhe do encoder. A serialização depois é pura
aritmética inteira — determinística por construção.

Bônus: é exatamente o mesmo inteiro que o quadro binário LoRa vai carregar na Fase 5.
Os dois transportes rendem valores idênticos de graça.

## Vetores dourados

O termo vem de duas tradições. Da criptografia, *test vector*: o NIST publica blocos de
teste para o AES, e qualquer implementação nova prova compatibilidade cifrando aqueles
blocos. Da verificação de hardware, *golden model*: o modelo de referência que **define**
o que é o comportamento correto.

Um vetor dourado é um par entrada→saída conhecidamente correto, congelado num arquivo.

Veja o mesmo caso, materializado dos dois lados:

**Lado Python** (`contracts/testdata/telemetry_02_arredondamento.json`):
```json
{"schema":"meliponet.telemetry.v1","node_id":"A4C1380F","seq":10433,...,"weight_kg":12.500,...}
```

**Lado C++** (`contracts/testdata/vectors.h`):
```c
Telemetry{
    .node_id = "A4C1380F",
    .seq = 10433,
    .weight_kg = 12500,          // gramas
    ...
},
"{\"schema\":\"meliponet.telemetry.v1\",...,\"weight_kg\":12.500,...}"
```

O C++ recebe os inteiros e precisa produzir aquela string. O Python recebe a string e
precisa aceitá-la. Os dois arquivos **saem do mesmo gerador**, declarados uma vez só.

```
gen_testdata.py  (o caso, declarado uma vez)
   ├── telemetry_02_arredondamento.json ──> pytest    (plataforma)
   └── vectors.h                        ──> pio test  (firmware)
```

Esse caso específico carrega três armadilhas de propósito:

- `30.125` é um **empate exato** de arredondamento;
- `12.5` kg tem que sair `12.500`, não `12.5`;
- `-0.004` arredonda para zero e **não pode virar `-0.00`**.

## Como verificar

```bash
pio test -e native -d firmware              # o codec C++ reproduz os vetores
pytest platform/tests/test_contract.py      # o ingestor lê os mesmos vetores
python3 contracts/tools/gen_testdata.py --check   # os vetores estão atualizados
```

Enquanto os três passarem, firmware e plataforma **não podem** ter divergido.

## O modo de falha dos vetores dourados

Existe uma armadilha, e você precisa conhecê-la.

Se alguém muda o contrato e roda o gerador sem pensar, os vetores passam a descrever o
comportamento **novo**, os dois testes voltam a passar, e o bug foi abençoado. O vetor
virou cúmplice em vez de juiz.

Por isso o CI roda `gen_testdata.py --check`, que **falha se os vetores estiverem
desatualizados** em vez de regravá-los em silêncio. Regerar é uma decisão explícita, e
o diff aparece no commit.

**Um vetor alterado deve ser lido com o mesmo cuidado de uma mudança de código.** É
isso que ele é.

E o limite honesto: vetores dourados provam **compatibilidade**, não **correção**. Se
os casos estiverem todos errados da mesma forma, os dois lados concordam lindamente em
produzir lixo. Eles garantem que firmware e plataforma falam a mesma língua — não que
essa língua seja a certa.

## Como mudar o contrato

1. Converse com a outra ponta **antes**. Isso não é formalidade: mudança de contrato
   afeta código que você não escreveu.
2. Edite os casos em `contracts/tools/gen_testdata.py` e/ou o schema.
3. Rode `python3 contracts/tools/gen_testdata.py`.
4. Rode os testes dos dois lados.
5. **Campo novo entra como opcional.** Foi assim que o protótipo (sem bioacústica) e o
   nó completo da Fase 5 couberam na mesma versão do contrato.

Só mude para `v2` em alteração incompatível. E aí o ingestor precisa aceitar as duas
versões durante a transição — porque há nós lacrados dentro de colmeias que ninguém vai
reprogramar no mesmo dia.

→ Próximo: [Engenharia de software](05-engenharia-de-software.md)
