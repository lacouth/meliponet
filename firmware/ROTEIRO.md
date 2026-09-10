# Roteiro do nó sensor

Esta pasta está vazia de propósito. **O firmware do nó é seu.**

Você vai escrever, do zero, o programa que roda no ESP32-C6 dentro da colmeia: lê os
sensores, monta uma mensagem e entrega essa mensagem à plataforma. O resto do sistema já
existe e funciona — a plataforma recebe, guarda e desenha o gráfico. Ela é o seu
corretor: enquanto o nó não estiver certo, o ponto não aparece na tela.

Use a ferramenta que preferir: Arduino IDE, PlatformIO, ESP-IDF. O roteiro não escolhe
por você, porque o que está sendo cobrado é o comportamento do nó, não o formato do
projeto.

## O que o nó faz

```mermaid
flowchart LR
    S[sensores<br/>SHT30 e HX711] --> M[monta a mensagem<br/>JSON]
    M --> E[envia<br/>HTTP POST]
    E --> P[plataforma<br/>valida e guarda]
    P --> G[gráfico<br/>no painel]
    E -. sem rede .-> B[guarda para<br/>enviar depois]
    B --> E
```

Quatro frases: lê os sensores, monta um JSON, manda para a plataforma, repete a cada
cinco minutos. Tudo o mais no roteiro é detalhe de uma dessas quatro.

## As peças e como ligar

| Peça | O quê |
|---|---|
| Placa | ESP32-C6-DevKitC-1, 8 MB de flash |
| Temperatura e umidade | 2× SHT30, I²C, endereços 0x44 (interno) e 0x45 (externo) |
| Peso | célula de carga de 50 kg + módulo HX711 |
| Energia | célula 18650 + divisor resistivo de 2× 100 kΩ |

A ligação sugerida — você pode mudar, desde que anote no seu código:

| Sinal | GPIO | Vai para |
|---|---|---|
| SDA (I²C) | 6 | SDA dos **dois** SHT30 |
| SCL (I²C) | 7 | SCL dos **dois** SHT30 |
| DT (DOUT) | 4 | saída de dados do HX711 |
| SCK | 5 | clock do HX711 |
| ADC | 0 | ponto médio do divisor da bateria |

```
                       ESP32-C6-DevKitC-1
                      +---------------------+
   SHT30 interno      |                     |
   ADDR -> GND        |                     |
   SDA  --------------+ GPIO6          3V3  +----- VDD dos dois SHT30
   SCL  --------------+ GPIO7               |      e VCC do HX711
                      |                GND  +----- GND comum a tudo
   SHT30 externo      |                     |
   ADDR -> VDD        |                     |
   (mesmos SDA/SCL)   |                     |
                      |                     |
   HX711  DT ---------+ GPIO4               |
   HX711  SCK --------+ GPIO5               |
                      |                     |
   divisor da         |                     |
   bateria -----------+ GPIO0               |
                      +---------------------+

   bateria 18650 --+-- 100k --+-- 100k --+-- GND
                              |
                              +--> GPIO0   (a tensao lida e METADE da real)
```

Antes de escolher outro pino, veja quais **não** estão livres na DevKitC-1: GPIO8 (LED e
strapping), GPIO9 e 15 (strapping), GPIO12 e 13 (USB nativo), GPIO16 e 17 (ponte
USB-UART), GPIO10 e 11 (nem sempre nos headers), GPIO24 a 30 (flash). E as entradas
analógicas ficam do GPIO0 ao GPIO6 — é por isso que a bateria está no GPIO0.

Os cuidados que custam caro estão em [O nó sensor](../docs/guia/04-o-no-sensor.md). Leia
antes de energizar: alimentar o HX711 em 5 V queima o GPIO, e trocar os dois SHT30 de
lugar não dá erro nenhum — dá uma série inteira com o rótulo errado.

## A mensagem

O que a plataforma aceita está escrito em [`../contracts/`](../contracts/README.md), e há
exemplos prontos em `../contracts/exemplos/`. Uma mensagem completa:

```json
{
  "schema": "meliponet.telemetry.v1",
  "node_id": "A4C1380F",
  "seq": 10432,
  "ts": "2027-03-14T12:10:00Z",
  "temp_in_c": 30.12,
  "temp_out_c": 34.8,
  "rh_in_pct": 68.4,
  "rh_out_pct": 41.2,
  "weight_kg": 12.483,
  "vbat_v": 3.92,
  "rssi": -58
}
```

As três regras que mais derrubam mensagem:

1. **Campo ausente é omitido.** Se o SHT30 externo não respondeu, `temp_out_c` **não
   entra** na mensagem, e você acende a flag `sht_out_fault`. Nunca mande `0` nem `null`:
   zero é uma temperatura possível, e quem ler a série daqui a um ano não terá como
   saber que aquilo era um sensor quebrado.
2. **`ts` em UTC, terminando em `Z`.** É o horário da medição pelo relógio do nó. Sem o
   `Z` a mensagem é recusada.
3. **`node_id` são os 4 últimos bytes do MAC, em hexadecimal MAIÚSCULO**, oito dígitos.
   É o que identifica o seu nó no meio dos outros.

E `seq` é um contador que você incrementa a cada leitura e que **precisa sobreviver ao
reinício** — guarde-o na NVS (`Preferences`, no Arduino). A plataforma usa o par
(`node_id`, `seq`) para reconhecer reenvio: um contador que volta ao zero faz ela
descartar leituras novas achando que já as tinha.

## Como entregar

```
POST http://<endereço-do-servidor>:5000/api/v1/telemetria
Content-Type: application/json
```

O corpo é a mensagem, e mais nada. As respostas:

| Código | Significa | O que o nó faz |
|---|---|---|
| `201` | leitura nova, gravada | segue em frente |
| `200` | você já tinha mandado essa `seq` | trate como sucesso: pode apagar a cópia local |
| `400` | a mensagem está errada; o corpo diz o motivo | **leia o motivo** e conserte a mensagem |
| `401` | o servidor exige token e o seu não confere | ver `TOKEN_INGESTAO` com quem administra |
| sem resposta | rede ou servidor fora | guarde a leitura e tente de novo |

Um `201` com `"colmeia": null` quer dizer que a leitura foi gravada mas o seu nó ainda
não está vinculado a nenhuma colmeia no cadastro — os dados estão salvos e passam a
aparecer no gráfico assim que alguém fizer o vínculo na tela de administração.

Antes de escrever uma linha de C++, mande a mensagem à mão e veja a resposta:

```bash
curl -i -X POST http://127.0.0.1:5000/api/v1/telemetria \
  -H 'Content-Type: application/json' \
  --data @contracts/exemplos/02-completa.json
```

## As etapas

Faça na ordem. Cada uma tem um **pronto quando** que você confere sozinho, e nenhuma
depende da seguinte estar pronta.

### E1 — a placa fala com você
Programa mínimo que imprime alguma coisa no monitor serial a cada segundo.
**Pronto quando:** você vê a contagem andando no monitor serial a 115200 bps.

### E2 — o nó entra na rede
Conecte no WiFi e imprima o IP e o `node_id` (os 4 últimos bytes do MAC, em hexadecimal
maiúsculo). Não escreva a senha do WiFi no meio do código que você vai versionar.
**Pronto quando:** o serial mostra um IP válido e um `node_id` de 8 dígitos.

### E3 — o nó sabe que horas são
Acerte o relógio por NTP e imprima o instante no formato do contrato
(`2027-03-14T12:05:00Z`, em UTC). Se o NTP não responder, você ainda assim manda a
mensagem — com a flag `clock_unsynced`, avisando que o horário é estimado.
**Pronto quando:** o horário impresso bate com o horário real, em UTC.

### E4 — os sensores respondem
Leia os dois SHT30 (0x44 e 0x45) e imprima temperatura em °C e umidade em %. Um sensor
que não responde precisa aparecer como **ausente**, e não como zero.
**Pronto quando:** aquecendo um sensor com a mão, só o valor dele sobe — e assim você
descobre qual é o interno. Desligando um deles, o programa diz "ausente" e continua
rodando.

### E5 — a mensagem existe
Monte o JSON e imprima no serial. Compare, campo a campo, com
`../contracts/exemplos/02-completa.json`.
**Pronto quando:** você copia o JSON impresso pelo serial, cola num arquivo e o `curl`
acima responde `201`.

### E6 — o primeiro ponto no gráfico
Agora faça o próprio nó enviar, por HTTP.
**Pronto quando:** a resposta é `201` e a leitura aparece no painel da plataforma.
É a etapa que fecha o circuito: daqui em diante você depura olhando a tela.

### E7 — o peso
Leia o HX711. Primeiro a **contagem bruta**: aperte a plataforma com a mão e veja o
número se mover — se ele não se move, o problema é de ligação, e nenhuma calibração
conserta. Só então implemente `tara` (com a colmeia montada e vazia) e a calibração com
uma massa conhecida, e guarde os dois valores na NVS para não recalibrar a cada reinício.
**Pronto quando:** uma massa conhecida de 1 kg lê 1,0 kg ± 20 g, e o valor continua certo
depois de reiniciar a placa.

### E8 — o nó vira um nó
Junte tudo num laço que mede e envia a cada 5 minutos, com `seq` incrementando e
persistido na NVS, `vbat_v` medido no divisor e a flag `low_batt` abaixo de 3,50 V.
**Pronto quando:** o gráfico do painel ganha um ponto a cada 5 minutos, por uma hora
seguida; e, depois de você desligar e religar a placa, a `seq` continua de onde parou.

### E9 — sobreviver à queda da rede (opcional)
Quando o envio falha, guarde a leitura (em memória ou no sistema de arquivos) e reenvie
quando a rede voltar, com a flag `spooled`. Cuide para não encher a memória: decida
quantas leituras cabem e o que fazer quando encher.
**Pronto quando:** você desliga o WiFi por 15 minutos, liga de volta, e as leituras do
período aparecem no gráfico com o horário em que foram **medidas**, não o da chegada.

### E10 — MQTT, o caminho de campo (opcional)
Troque o POST por uma publicação MQTT no tópico `meliponet/v1/<node_id>/telemetry`, com
QoS 1. A mensagem é a mesma, byte por byte. É assim que o nó vai funcionar instalado na
colmeia, porque o broker guarda a mensagem enquanto o servidor reinicia.
**Pronto quando:** com o ingestor MQTT rodando, o gráfico continua ganhando pontos e
você não mudou uma vírgula da mensagem.

## Quando não funcionar

| Sintoma | Primeira hipótese |
|---|---|
| `400 campo obrigatorio ausente` | faltou `schema`, `node_id`, `seq` ou `ts` |
| `400 mensagem sem nenhuma metrica de colmeia` | só mandou `vbat_v`/`rssi`; falta temperatura, umidade ou peso |
| `400 ts sem fuso horario` | faltou o `Z` no fim do horário |
| `400 node_id ...` | o hexadecimal está minúsculo ou não tem 8 dígitos |
| `400 campo fora do contrato` | inventou um campo; confira a grafia no schema |
| `400 JSON malformado` | vírgula sobrando, aspas faltando, ou o buffer cortou a mensagem no meio |
| `200` sempre, e nada muda no gráfico | a `seq` não está incrementando (ou reiniciou do zero) |
| `201`, mas o gráfico está vazio | o nó ainda não foi vinculado a uma colmeia no cadastro |
| I²C mudo com a fiação certa | `Wire.begin()` sem argumentos não usa o GPIO6/7 no C6 |
| tudo funciona na bancada e falha em campo | cabo do sensor externo longo demais |

Uma mensagem recusada nunca some: a plataforma guarda o motivo. Se você tem acesso ao
banco, a tabela `ingest_rejects` mostra o que o seu nó mandou e por que foi recusado.

## O que fica para depois

Rádio LoRa e gateway, microfone para bioacústica, painel solar e deep sleep, e o
invólucro impresso. Tudo isso reaproveita a mesma mensagem — do servidor para dentro,
nada muda quando o transporte mudar.
