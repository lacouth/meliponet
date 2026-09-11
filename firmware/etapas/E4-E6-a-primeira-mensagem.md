# E4 a E6 — os sensores, a mensagem e o primeiro ponto

**Tempo:** ~9 h no total · voltar ao [índice](../ROTEIRO.md)

Aqui o nó deixa de ser uma placa que fala e passa a ser um instrumento. E6 é o marco que
muda o jeito de trabalhar: a partir dele, quem te diz se está certo é a tela da
plataforma, não mais o monitor serial.

---

## E4 — os sensores respondem

**Tempo:** ~4 h

Leia os dois SHT30 e imprima temperatura em °C e umidade em %.

> **O conceito: I²C é um barramento, e cada peça nele tem um endereço.**
> Os dois SHT30 compartilham os mesmos dois fios (SDA e SCL). Como o nó conversa com um
> sem que o outro responda junto? Cada dispositivo no barramento tem um **endereço**, um
> número de sete bits, e toda conversa começa pelo endereço de quem ela é. O SHT30 permite
> escolher entre dois: com o pino ADDR no GND ele atende em `0x44`, com ADDR no VDD ele
> atende em `0x45`. É por isso que dois sensores idênticos convivem no mesmo par de fios —
> e é por isso que ligar os dois com ADDR no mesmo lugar faz os dois responderem juntos e
> nenhuma leitura fazer sentido. Verbete no
> [glossário](../../docs/guia/06-glossario.md).

### E4.1 — quem está no barramento

Antes de ler qualquer coisa, faça o nó **varrer** o barramento e imprimir os endereços que
responderam.

**Pronto quando:** a varredura imprime **dois** endereços: `0x44` e `0x45`. Se imprimir um
só, ou nenhum, pare aqui — nenhum código de leitura vai funcionar, e o problema é de
ligação ou de ADDR.

Vale desligar um dos sensores e varrer de novo: o endereço que sumiu é o dele. Você acabou
de descobrir qual é qual sem abrir o datasheet.

### E4.2 — um sensor, dois números

Leia **só** o `0x44` e imprima temperatura e umidade.

**Pronto quando:** a temperatura é plausível para a sala (algo entre 20 e 32 °C) e a
umidade está entre 40 e 90 %. Um valor plausível não prova que está certo, mas um valor
absurdo prova que está errado — e é o que você consegue verificar agora.

### E4.3 — os dois, e quem é o interno

Leia os dois e imprima os quatro números, rotulados.

**Pronto quando:** aquecendo **um** sensor com a mão, só o valor dele sobe. É assim que
você descobre qual dos dois está no `0x44`.

> **Este passo é mais importante do que parece.** Trocar os dois SHT30 de lugar não gera
> erro nenhum: a mensagem é aceita, o gráfico é desenhado, e a série inteira sai com o
> diferencial térmico da colmeia invertido. Ninguém percebe até alguém tentar interpretar
> os dados. Este é o único momento em que o erro é barato de achar — [O nó
> sensor](../../docs/guia/04-o-no-sensor.md) explica por quê.

### E4.4 — sensor ausente não é zero

Desligue um dos sensores com o programa rodando.

**Pronto quando:** o programa diz **"ausente"** para aquele sensor, continua lendo o
outro, e **não** imprime zero. Zero é uma temperatura possível: se o campo ausente virar
`0.0`, quem ler a série daqui a um ano vai ver uma colmeia a 0 °C, não um sensor quebrado.

Guarde esse estado: em E5 ele vira a decisão de **omitir** o campo e acender a flag
(`sht_in_fault` ou `sht_out_fault`).

### Pistas — E4

<details>
<summary>A varredura não encontra nada</summary>

Antes de suspeitar do sensor: o barramento precisa ser iniciado **dizendo quais pinos
usar**. No ESP32-C6 os pinos padrão não são os GPIO6/7 que este projeto usa, e iniciar sem
dizer nada deixa o barramento mudo com a fiação perfeitamente correta. É o erro mais comum
desta etapa inteira.

Depois disso, confira alimentação e GND comum — os dois SHT30 e a placa precisam
compartilhar o GND.
</details>

<details>
<summary>A varredura encontra só um endereço</summary>

O ADDR do segundo sensor não está no nível que você acha que está. `0x44` é ADDR no GND;
`0x45` é ADDR no VDD. ADDR solto, sem ligar em nada, não é nenhum dos dois.
</details>

<details>
<summary>Os dois sensores dão exatamente o mesmo valor, sempre</summary>

Você está lendo o mesmo sensor duas vezes — endereço repetido no código, ou os dois com
ADDR no mesmo nível. Aqueça um com a mão: se os dois números subirem juntos, é isso.
</details>

<details>
<summary>Funciona na bancada, falha quando o sensor externo é ligado no cabo longo</summary>

O I²C não foi feito para cabo longo, e o sensor de fora da caixa fica a metros do nó.
[O nó sensor](../../docs/guia/04-o-no-sensor.md) trata disso. Sintoma característico: os
**dois** sensores somem juntos, porque um barramento travado leva o outro junto.
</details>

---

## E5 — a mensagem existe

**Tempo:** ~3 h

Monte o JSON e imprima no serial. Ainda sem enviar nada.

> **O conceito: o contrato é um acordo, e a plataforma é quem confere.**
> `../../contracts/telemetry.v1.schema.json` descreve, formalmente, toda mensagem
> aceitável: quais campos são obrigatórios, o formato de cada um, as faixas plausíveis, e a
> regra de que **nenhum campo fora da lista é permitido**. A plataforma valida contra ele
> antes de gravar. Por isso o roteiro pede que você monte o JSON e compare com o exemplo
> **antes** de escrever o código de envio: se a mensagem estiver errada, é melhor descobrir
> lendo, do que descobrir depois de somar o envio e o WiFi ao conjunto de coisas que podem
> ter falhado.

### E5.1 — o JSON no serial

Imprima a mensagem montada, com os campos que você já consegue produzir (`schema`,
`node_id`, `seq`, `ts`, e as temperaturas e umidades de E4).

**Pronto quando:** você comparou, campo a campo, com
`../../contracts/exemplos/02-completa.json` — mesma grafia, mesmo tipo, mesmas aspas nos
lugares certos. Os nomes dos campos são letra por letra os do contrato: `temp_in_c`, não
`tempIn` nem `temperatura_interna`.

### E5.2 — o campo ausente some

Aplique a decisão de E4.4: sensor ausente significa que o campo **não aparece** no JSON, e
a flag correspondente entra na lista `flags`.

**Pronto quando:** com um sensor desligado, a mensagem impressa tem dois campos a menos e
uma flag a mais — e continua sendo um JSON válido (sem vírgula sobrando onde o campo
saiu).

### E5.3 — a plataforma aceita

Copie o JSON impresso no serial, cole num arquivo e mande à mão:

```bash
curl -i -X POST http://127.0.0.1:5000/api/v1/telemetria \
  -H 'Content-Type: application/json' \
  --data @a-minha-mensagem.json
```

**Pronto quando:** a resposta é `201`. Ainda não é o seu nó enviando — mas é a prova de
que a mensagem que ele produz está certa, e é exatamente essa separação que faz E6 ser
fácil.

### E5.4 — provoque as recusas

Estrague a mensagem de propósito, uma coisa por vez, e **leia o motivo** que volta. Comece
pelas quatro que mais acontecem de verdade:

| Estrague assim | Motivo esperado |
|---|---|
| tire o `Z` do fim do `ts` | `400 ts sem fuso horario` |
| escreva o `node_id` em minúsculas | `400 node_id ...` |
| mande só `vbat_v`, sem temperatura, umidade nem peso | `400 mensagem sem nenhuma metrica de colmeia` |
| corte a mensagem no meio, apagando o fim | `400 JSON malformado` |

Os mesmos casos estão prontos em `../../contracts/exemplos/invalidas/`, com o motivo
escrito num arquivo `.motivo` ao lado.

**Pronto quando:** você viu os quatro motivos e reconhece cada um de cara.

> **O último é o que mais vai te morder.** `400 JSON malformado` quase nunca é erro de
> lógica: é a mensagem chegando **cortada**, porque o buffer que a montou era menor que
> ela. No serial a mensagem parece inteira, porque o serial imprime o que você mandou
> imprimir; na rede vai só o que coube. Quando esse erro aparecer em E6 ou E8, suspeite do
> tamanho do buffer antes de suspeitar do conteúdo.

### Pistas — E5

<details>
<summary><code>400 campo fora do contrato</code></summary>

Você inventou um campo, ou errou a grafia de um existente. O schema tem
`additionalProperties: false` de propósito: um `temp_int_c` escrito com erro de digitação
seria aceito em silêncio e viraria uma coluna que ninguém lê, em vez de um erro que você
conserta hoje.
</details>

<details>
<summary>A temperatura sai como <code>30.119999</code></summary>

Escolha quantas casas decimais fazem sentido e arredonde. O sensor não tem seis casas de
precisão, e a mensagem fica maior à toa — o que, num buffer apertado, é justamente o que
causa o `JSON malformado` do parágrafo acima.
</details>

<details>
<summary>Sai <code>nan</code> ou <code>inf</code> no lugar de um número</summary>

JSON não tem representação para esses valores, e a mensagem inteira é recusada. É o mesmo
caso de E4.4 por outro caminho: o valor não existe, então o campo não deve existir.
</details>

---

## E6 — o primeiro ponto no gráfico

**Tempo:** ~2 h

Agora o próprio nó envia, por HTTP.

> **O conceito: o código de resposta é o seu instrumento de depuração.**
> Cada resposta diz uma coisa diferente sobre onde o problema está — e distinguir as três
> primeiras poupa horas:
>
> | Resposta | Onde está o problema |
> |---|---|
> | `201` | em lugar nenhum; gravou |
> | `200` | lugar nenhum também: você mandou uma `seq` repetida, e isso é **sucesso** |
> | `400` | na sua mensagem, e o corpo diz exatamente onde |
> | `401` | no token, não na mensagem |
> | nenhuma resposta | na rede ou no servidor; a mensagem pode estar perfeita |
>
> A diferença entre "`400`" e "nenhuma resposta" é a diferença entre "a plataforma está
> recusando" e "a plataforma não está recebendo" — duas coisas que parecem uma só quando o
> ponto não aparece na tela. O exercício
> [02](../../docs/exercicios/02-uma-mensagem-ate-o-grafico.md) foi feito para você já
> conhecer essa distinção antes de chegar aqui.

### E6.1 — o nó alcança o servidor

Antes de enviar a mensagem, faça o nó pedir qualquer coisa ao servidor e imprimir o código
que voltou.

**Pronto quando:** veio um código, qualquer um. Se não veio nada, o problema é de rede ou
endereço — e `127.0.0.1` é o caso clássico: para a placa, `127.0.0.1` é a própria placa. O
endereço tem de ser o IP do computador onde a plataforma roda, na rede local.

### E6.2 — o POST com a mensagem

Envie o JSON de E5 e imprima o código **e o corpo** da resposta.

**Pronto quando:** a resposta é `201`. Imprimir o corpo não é opcional: é ele que diz o
motivo quando for `400`.

### E6.3 — o ponto na tela

Abra o painel da plataforma e ache a sua leitura.

**Pronto quando:** o ponto está no gráfico. Se a resposta foi `201` e o gráfico está
vazio, olhe o corpo da resposta: um `"colmeia": null` quer dizer que a leitura **está
gravada** e que falta apenas vincular o seu nó a uma colmeia na tela de cadastro. Não é
erro do firmware.

**Daqui em diante você depura olhando a tela.** É a etapa que fecha o circuito.

### Pistas — E6

<details>
<summary><code>201</code> no <code>curl</code>, nada quando o nó envia</summary>

Compare o que o nó mandou com o que você mandou à mão — imprima o corpo exato, com o
tamanho em bytes. Quase sempre a diferença é o cabeçalho `Content-Type: application/json`
que ficou faltando, ou a mensagem cortada de E5.4.
</details>

<details>
<summary>O servidor não responde ao nó, e responde ao <code>curl</code></summary>

O servidor de desenvolvimento do Flask, por padrão, só atende quem chama de dentro da
própria máquina. Para receber da placa ele precisa escutar em todas as interfaces — e o
firewall do computador precisa deixar passar a porta 5000.
</details>

<details>
<summary>Sempre <code>200</code>, e o gráfico não ganha ponto novo</summary>

A sua `seq` não está incrementando. A plataforma reconhece o par (`node_id`, `seq`) e
trata a repetição como reenvio. É assunto de E8.2 — por ora, incremente a cada envio,
mesmo que ainda não sobreviva ao reset.
</details>

---

## O que levar daqui

**Separe a mensagem do envio.** E5 prova que a mensagem está certa sem nenhum WiFi no
caminho; E6 prova que o envio funciona com uma mensagem que você já sabe correta. Juntar
as duas coisas dobra o número de hipóteses a cada falha.

**Ausente não é zero.** É a regra que atravessa o projeto inteiro, e a única cujo
descumprimento não dá erro nenhum — só produz dados falsos.

→ Próximo: [E7 — o peso](E7-o-peso.md)
