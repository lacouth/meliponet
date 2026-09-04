# 11. Folga no buffer do MQTT

**Área:** firmware · **Tempo:** ~1 h · **Contribuição** — corrige [D-03](../defeitos-conhecidos.md#d-03)

> **Combine antes de começar.** Vira um PR; só uma pessoa deve fazê-lo.

## Por que este exercício existe

Duas constantes valem 512 e estão em arquivos diferentes. Uma é o tamanho máximo do JSON
que o codec produz; a outra é o tamanho do buffer do `PubSubClient`. Elas **parecem**
iguais, mas medem coisas diferentes: o buffer do MQTT precisa acomodar o cabeçalho do
protocolo e o tópico **além** do payload.

O que torna isso instrutivo não é a conta — é o modo de falha. Uma mensagem grande demais é
recusada, vai para o spool, é drenada, é recusada de novo, e **trava a cabeça da fila para
sempre**. Todas as mensagens atrás dela ficam presas. O nó fica mudo com o spool cheio,
enquanto o `estado` mostra WiFi e broker conectados.

E há uma segunda lição, mais valiosa: a correção que o registro sugere **não é suficiente**.

## Antes de começar

- Bloco B feito.
- Leia [D-03](../defeitos-conhecidos.md#d-03) inteiro.
- Abra `firmware/lib/MelipoHardware/PublicadorMqtt.cpp` e `firmware/lib/MelipoCore/Telemetria.h`.

```bash
git switch main && git pull
git switch -c firmware/folga-no-buffer-do-mqtt
```

## Passo 1 — faça a conta você mesmo

O registro afirma que o tópico tem 30 bytes e que o teto real do payload fica "perto de
475". **Confira.** O tópico é montado em `PublicadorMqtt::configurar`:

```cpp
snprintf(topico_de_telemetria_, sizeof(topico_de_telemetria_),
         "meliponet/v1/%s/telemetry", node_id);
```

com `node_id` de 8 caracteres, pelo contrato.

> **Pergunta 1.** Quantos bytes tem `meliponet/v1/A4C1380F/telemetry`?
>
> **Pergunta 2.** Um `PUBLISH` de MQTT com QoS 0 carrega, antes do payload: 1 byte de
> controle, até 4 bytes de comprimento restante, 2 bytes com o tamanho do tópico, e o
> tópico. Qual é o teto real do payload com um buffer de 512?

<details>
<summary>Respostas</summary>

**1.** 31 bytes. Conte: `meliponet` (9) + `/` + `v1` (2) + `/` + `A4C1380F` (8) + `/` +
`telemetry` (9) = 31.

**O registro diz 30.** Está errado por um — e você acabou de encontrar isso conferindo em
vez de acreditar. Corrigir o número faz parte deste PR: um registro de defeitos com contas
erradas gasta o tempo da próxima pessoa exatamente onde deveria economizá-lo.

**2.** `512 − (1 + 4 + 2) − 31 = 474`. O registro diz "perto de 475", o que é honesto como
ordem de grandeza — mas a constante que você vai escrever precisa da conta exata, não do
"perto de".

Confira você mesmo:

```bash
python3 -c "t='meliponet/v1/A4C1380F/telemetry'; print(len(t), 512-7-len(t))"
```
</details>

## Passo 2 — a correção, e por que ela precisa de um `static_assert`

Dimensione `kTamanhoDoBuffer` a partir de `kTamanhoMaximoDoJson` **mais** a folga que você
calculou, em vez de repetir o número 512 à mão.

E acrescente um `static_assert` que quebre o build se as duas constantes voltarem a se
aproximar.

> **Por que um `static_assert`, e não um comentário?**

<details>
<summary>Resposta</summary>

Porque um comentário não é executado por ninguém.

Este defeito nasceu de duas constantes que "por acaso" valiam o mesmo. Se alguém aumentar
`kTamanhoMaximoDoJson` na Fase 5 para caber `sound_bands` — que é exatamente o que
[D-03](../defeitos-conhecidos.md#d-03) prevê —, um comentário não impede nada. Um
`static_assert` **não deixa compilar**.

É a mesma ideia do `gen_testdata --check`: transformar uma suposição num verificador. E é
mais barato que um teste, porque roda a custo zero, em tempo de compilação, em todo build.

Repare também no efeito colateral bom: quem quebrar o build vai ler a mensagem do
`static_assert`. Escreva-a como uma frase útil, não como `"erro"`.
</details>

## Passo 3 — a parte que o registro só menciona no fim

Releia a última frase de [D-03](../defeitos-conhecidos.md#d-03):

> E, independentemente disso, `drenarSpool` deveria descartar (com contador) uma mensagem
> recusada mais de N vezes, em vez de tentar a mesma para sempre.

> **Pergunta 3.** Com o buffer redimensionado, o problema da fila travada está resolvido?

<details>
<summary>Resposta</summary>

**Não.** Você resolveu *uma* causa de mensagem recusada. A fila continua sem defesa contra
qualquer outra — um erro transitório do broker, uma entrada corrompida no LittleFS, uma
mensagem de um firmware futuro maior do que este nó previa.

`drenarSpool`, em `firmware/src/main.cpp`, faz `espiar` → `publicar` → `remover`, e só
remove após confirmação. Isso está certo — é o que impede perder a mensagem quando a
publicação falha. Mas significa que uma mensagem **permanentemente** irrecuperável trava
tudo atrás dela, para sempre.

Aumentar o buffer é a correção do sintoma conhecido. A defesa contra a classe inteira é o
limite de tentativas.

**Escolha uma das duas e diga qual no PR:**

- **Só o buffer.** Menor, e resolve o que está documentado. Aí o D-03 **não sai** do
  registro: ele é reescrito, mantendo a parte da fila travada como pendente.
- **Buffer + limite de tentativas.** Aí a lógica de "quantas vezes esta mensagem já foi
  recusada?" é pura, cabe em `MelipoCore`, e **pode ter teste nativo** — que é o que
  transforma um conserto de bancada num conserto verificado.

A segunda é mais trabalho e vale mais. As duas são respostas legítimas; o que não é
legítimo é fechar o D-03 tendo resolvido metade.
</details>

## Passo 4 — verifique

O ambiente `native` **não compila** `MelipoHardware`. Então o seu `static_assert` em
`PublicadorMqtt.cpp` só é avaliado no build do alvo:

```bash
./verificar firmware     # continua verde, mas nao viu o seu static_assert
./verificar alvo         # este e o que importa aqui
```

O `alvo` baixa o toolchain na primeira vez — deixe rodando enquanto escreve a mensagem do
commit.

> **Um teste rápido de que o `static_assert` funciona:** baixe `kTamanhoDoBuffer` de
> propósito para um valor pequeno e confirme que o build quebra com a **sua** mensagem.
> Depois desfaça. É o mesmo princípio de ver o teste falhar antes.

## Passo 5 — o registro e o commit

- Se você fez só o buffer: **reescreva** D-03, deixando claro o que sobrou.
- Se fez os dois: remova D-03 dos abertos e acrescente em Resolvidos.
- Nos dois casos: corrija o "30 bytes" para 31.

No commit, conte o sintoma — *"o nó fica mudo com o spool cheio, e o `estado` mostra tudo
conectado"* — e a conta que justifica a constante nova.

## Critério de pronto

- [ ] Você fez a conta do tópico à mão e achou a divergência com o registro
- [ ] O buffer é **derivado** de `kTamanhoMaximoDoJson`, não um número novo escrito à mão
- [ ] O `static_assert` existe, e você o viu quebrar o build de propósito
- [ ] `./verificar` e `./verificar alvo` verdes
- [ ] O registro reflete o que ficou de fato resolvido

## Pistas

<details>
<summary>Onde exatamente ponho o `static_assert`?</summary>

Em `PublicadorMqtt.cpp`, ao lado de `kTamanhoDoBuffer` — é lá que a relação entre as duas
constantes existe. Para enxergar `kTamanhoMaximoDoJson`, o arquivo precisa incluir
`Telemetria.h`. Um cabeçalho traz os próprios tipos: inclua-o explicitamente em vez de
contar com quem inclui quem.
</details>

<details>
<summary>`setBufferSize` recebe `uint16_t`; meu cálculo estourou?</summary>

Não com estes números, mas vale conferir o tipo da sua constante — e é justamente o tipo de
coisa que um `static_assert` também pode guardar.
</details>

<details>
<summary>Não tenho placa. Consigo fazer este exercício?</summary>

Consegue. `./verificar alvo` **compila** para o ESP32-C6 sem placa nenhuma conectada —
gravar é que precisaria dela. E é o compilador, não o hardware, que avalia o
`static_assert`.
</details>

## O que levar daqui

**Duas constantes com o mesmo valor por coincidência são um defeito esperando a hora.**
Derive uma da outra, e trave a relação com um `static_assert`.

**Confira as contas da documentação.** O registro dizia 30; são 31. Documentação é código
que ninguém executa — só é verificada quando alguém a lê com desconfiança.

**Resolver o sintoma documentado não é resolver a classe.** Dizer no PR o que ficou de fora
vale mais do que fechar um registro pela metade.

→ Próximo: [O comando `intervalo`](12-comando-intervalo.md)
