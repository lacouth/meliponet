# 10. Um vetor dourado novo

**Área:** contrato · **Tempo:** ~1 h · **Treino, e pode virar PR**

## Por que este exercício existe

No exercício [06](06-mutante-do-contrato.md) você quebrou o contrato e viu os vetores
virarem cúmplices. Agora você vai do outro lado: **acrescentar** um vetor, de propósito,
para cobrir um caso de borda que hoje ninguém exercita.

É a menor contribuição possível ao contrato, e ela toca os dois lados de uma vez — um
arquivo em Python vira, na mesma execução, um `.json` para o `pytest` e um `vectors.h` para
o `pio test`.

## Antes de começar

- Exercício [06](06-mutante-do-contrato.md) feito.
- Leia [O contrato](../guia/02-o-contrato.md#vetores-dourados) e `contracts/README.md`.

```bash
git switch main && git pull
git switch -c contrato/vetor-de-borda
```

## Passo 1 — ache um caso descoberto

Abra `contracts/tools/gen_testdata.py` e leia os sete casos de `VALID` e os dezenove de
`SCALING`. Os comentários dizem o que cada um cobre — empate exato, zero negativo, deriva
de tara, nó completo da Fase 5.

Sua tarefa: **encontrar um caso que nenhum deles cobre.** Algumas pistas de onde procurar:

| Onde | Pergunta |
|---|---|
| `weight_kg` | um peso que é exatamente um número inteiro de quilos sai com as três casas? |
| `weight_kg` | e meio grama — `0.0005` — para que lado vai? |
| `rh_out_pct` | o limite superior, 100,00, aparece em algum caso **válido**? |
| `rssi` | um valor positivo, ou zero, é aceito pelo schema? |
| flags | existe caso com **todas** as flags ligadas ao mesmo tempo? |
| tamanho | qual é a maior mensagem que os vetores exercitam? Ela testa o limite do buffer? |

Escolha **um**, e escreva antes de codar: qual comportamento você espera, e por que esse
caso poderia dar errado.

<details>
<summary>Se nenhum te convencer, aqui vai um pronto</summary>

`weight_kg: 5.0` — cinco quilos exatos. O caso `02_arredondamento` já tem `12.5`, que
testa "12.500 e não 12.5", mas nenhum vetor testa um valor cuja parte decimal é
**inteiramente** zero.

O que poderia dar errado: `render_scaled` faz `str(abs(5000)).rjust(4, "0")` → `"5000"`, e
depois corta em `whole = "5"`, `fraction = "000"`. Funciona — mas nada garantia que
funcionasse, e é exatamente esse tipo de caso que um `if` mal escrito no futuro quebraria
primeiro.

Um segundo pronto, mais interessante: **uma mensagem com todas as flags ligadas**. Ela
exercita a ordenação canônica em `FLAG_ORDER` no seu pior caso, e é a maior mensagem
possível — o que a liga ao [D-03](../defeitos-conhecidos.md#d-03).
</details>

## Passo 2 — declare o caso

Acrescente ao dicionário `VALID` (ou à lista `SCALING`, se for um caso de conversão).
Escreva o comentário explicando **o que o caso cobre e por quê** — os que já existem são o
modelo. Um vetor sem essa frase vira, meses depois, um número que ninguém ousa mexer.

Se for um caso de `VALID`, use uma `seq` que não colida com as existentes.

## Passo 3 — gere e **leia o diff**

```bash
python3 contracts/tools/gen_testdata.py
git diff
```

Este passo é o exercício. Leia o diff inteiro, nos dois arquivos:

- o `.json` novo em `testdata/`;
- o bloco novo em `testdata/vectors.h`.

> **Pergunta 1.** No `vectors.h`, de onde saíram os inteiros? Confira à mão que eles batem
> com o valor que você declarou.
>
> **Pergunta 2.** A linha `.presentes = Campo::... | Campo::...` foi montada como? Por que
> `node_id`, `seq` e `ts` não aparecem nela?
>
> **Pergunta 3.** Se você tivesse errado o valor esperado, algum dos verificadores
> reclamaria?

<details>
<summary>Respostas</summary>

**1.** De `canonical.quantize`, a mesma função que produz o `.json`. Os dois arquivos saem
da mesma chamada — é isso que impede os lados de divergirem. Confira com:

```bash
platform/.venv/bin/python -c "
import sys; sys.path.insert(0,'contracts')
from canonical import quantize; print(quantize('weight_kg', 5.0))"
```

**2.** Em `render_header`: `optional = [f for f in scaled if f not in REQUIRED and f != 'flags']`.
Os três obrigatórios ficam de fora porque o bitmask `presentes` descreve **apenas os campos
opcionais** — os que podem ou não ser emitidos. Um campo que o contrato sempre exige não
precisa de bit para dizer que está lá.

**3.** **Nenhum.** E esta é a resposta mais importante do exercício.

Os vetores provam **compatibilidade**, não **correção**. Se você declarar um caso errado, o
gerador produz o `.json` e o `vectors.h` errados de forma consistente, o C++ reproduz o
JSON errado com perfeição, e os três verificadores ficam verdes. O guia diz isso em uma
frase: *"se os casos estiverem todos errados da mesma forma, os dois lados concordam
lindamente em produzir lixo"*.

O que protege contra isso é uma pessoa lendo o diff. Por isso um PR que mexe em vetores
dourados exige revisão atenta — e por isso o seu comentário explicando o caso vale tanto
quanto o caso.
</details>

## Passo 4 — verifique os dois lados

```bash
./verificar
```

Os três verificadores têm de passar: o `--check` (os vetores estão atualizados), o `pytest`
(o ingestor aceita o caso novo) e o `pio test` (o codec C++ reproduz o JSON novo byte a
byte).

Se o `pio test` falhar, **você encontrou uma divergência real entre C++ e Python** — o que
é exatamente o que o vetor existe para achar. Não "conserte" o vetor para o C++ passar: aí
o vetor teria virado cúmplice. Descubra qual dos dois lados está errado.

## Passo 5 — commit

Um commit só, com o `gen_testdata.py` e os arquivos gerados juntos. Separá-los deixaria a
`main` num estado em que o `--check` falha.

## Critério de pronto

- [ ] O caso novo tem um comentário explicando o que cobre e por quê
- [ ] Você leu o diff dos **dois** arquivos gerados e conferiu os inteiros à mão
- [ ] `./verificar` verde
- [ ] Você entendeu por que um vetor errado passaria em tudo

## Pistas

<details>
<summary>O `pytest` recusa meu caso novo</summary>

O `test_contract.py` valida cada vetor contra o JSON Schema. Se o seu caso violar o
schema — um `rssi` fora da faixa, um campo que não existe, ou nenhuma métrica de colmeia —
ele é recusado com o motivo. Leia a mensagem: ela diz qual regra você bateu.

Repare que o schema exige `anyOf` com pelo menos uma métrica de colmeia. Um vetor só com
`vbat_v`, por exemplo, é inválido de propósito — já existe como caso **inválido**, o
`03_sem_metrica`.
</details>

<details>
<summary>O `vectors.h` não compila depois de eu gerar</summary>

Se você acrescentou um campo em ordem diferente da declaração da `struct Telemetria`, o
C++20 recusa os inicializadores fora de ordem — é exatamente o erro do exercício
[06](06-mutante-do-contrato.md). A ordem de `FIELD_ORDER` e a ordem dos membros em
`Telemetria.h` andam juntas.
</details>

<details>
<summary>Quero conferir o tamanho da mensagem que criei</summary>

```bash
wc -c contracts/testdata/telemetry_*.json
```

Compare com `kTamanhoMaximoDoJson` (512) e com o buffer do `PubSubClient` — é o assunto do
exercício [11](11-folga-no-buffer-do-mqtt.md).
</details>

## O que levar daqui

**Um caso declarado uma vez vira teste nos dois lados.** É o que permite ao bolsista do
firmware e ao da plataforma trabalharem sem se falar todo dia — e o que garante que, quando
divergirem, o CI conte.

**Vetor dourado prova compatibilidade, não correção.** Os dois lados podem concordar em
estar errados. A revisão humana do diff é a única defesa contra isso.

→ Próximo: [Folga no buffer do MQTT](11-folga-no-buffer-do-mqtt.md)
