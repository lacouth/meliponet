# 10. O hardware

Para quem vai **montar, ligar ou substituir um nó**. Os outros documentos falam do
sistema e do código; este fala das peças físicas: o que é cada uma, em que pino ela
entra, e como conferir que está funcionando antes de fechar a caixa.

O uso por software está detalhado em [O firmware](04-o-firmware.md) e o roteiro de campo
em [Do nó ao gráfico](08-do-no-ao-grafico.md). Aqui fica o essencial de cada componente e,
principalmente, **a ligação** — que até hoje não estava escrita em lugar nenhum: os pinos
viviam em cinco linhas de `firmware/src/main.cpp`, e quem não abrisse o código não sabia
que existiam.

## O nó de hoje, peça por peça

| Peça | O quê | Onde no código |
|---|---|---|
| Placa | ESP32-C6-DevKitC-1, 8 MB de flash | `firmware/platformio.ini:32,40` |
| Temperatura e umidade | 2× SHT30, I²C, endereços 0x44 e 0x45 | `lib/MelipoHardware/SensoresSht.h:17` |
| Peso | célula de carga de 50 kg + módulo HX711 | `lib/MelipoHardware/CelulaDeCarga.h:1` |
| Energia | célula 18650 + divisor resistivo 2× 100 kΩ | `src/main.cpp:41`, `lib/MelipoCore/Amostra.h:25` |

É só isso. Não há rádio LoRa, microfone, painel solar nem invólucro — o que entra depois
está na [seção da Fase 5](#o-que-ainda-vai-entrar-fase-5), no fim deste documento.

## A placa: ESP32-C6-DevKitC-1

A placa é fixada em `platformio.ini:32` e o Arduino core vem do fork **pioarduino**, com
a versão travada, porque o `espressif32` oficial parou no core 2.x e o C6 só apareceu no
3.x (o *porquê* completo está em [O firmware](04-o-firmware.md#platformio)).

Duas coisas da placa afetam quem monta:

**Ela tem 8 MB de flash, e o projeto usa a flash inteira.** A tabela de partições padrão
reserva 1,3 MB para a aplicação e o firmware do protótipo já ocupa 87% disso — antes de
entrar bioacústica, FFT e LoRa. Por isso `board_build.partitions = default_8MB.csv`, que
também reserva a partição de arquivos onde o spool sobrevive a uma queda de energia
(`platformio.ini:36-40`). **Se você comprar uma DevKitC-1 de 4 MB, o firmware não cabe
como está.**

**Ela tem duas portas USB-C, e elas não são iguais.** A porta *UART* passa pela ponte
USB-serial da placa (GPIO16/17) e é a que se usa para `upload` e `monitor`. A porta *USB
nativa* do chip também grava e serve para depuração JTAG. Qualquer uma das duas alimenta
a placa; nos headers, dá para alimentar por 5V/GND ou por 3V3/GND.

### Pinos que não estão disponíveis

Antes de escolher onde ligar qualquer coisa nova, saiba o que já está ocupado. Esta
lista vem do guia do usuário da ESP32-C6-DevKitC-1 e da página de GPIO do ESP-IDF para
o C6:

| GPIO | Por que não usar |
|---|---|
| 8 | LED RGB embutido — e pino de strapping |
| 9, 15 | strapping: decidem modo de boot e a impressão de mensagens do ROM |
| 12, 13 | USB nativo (D− e D+) |
| 16, 17 | ponte USB-UART da placa |
| 10, 11 | não são levados aos headers em placas com flash interna |
| 24 – 30 | flash SPI |

E o que importa na outra direção: **as entradas analógicas do ADC1 são o GPIO0 ao
GPIO6**. É por isso que a medição de bateria está no GPIO0 e não em qualquer pino livre.

## Como ligar

Os pinos estão em `firmware/src/main.cpp:34-38`, sob o comentário "Ajuste conforme a
placa do lote" — ou seja, são **provisórios** e mudam num lugar só:

```cpp
constexpr int kI2cSda = 6;
constexpr int kI2cScl = 7;
constexpr int kHx711Data = 4;
constexpr int kHx711Clock = 5;
constexpr int kBatteryAdc = 0;
```

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

### Cinco cuidados que custam caro

**Alimente o HX711 em 3,3 V, nunca em 5 V.** O módulo aceita de 2,7 V a 5 V, e o nível
lógico da saída `DT` acompanha a alimentação. Em 5 V, ele entrega 5 V no GPIO4, que não é
tolerante a 5 V. O dano é imediato e silencioso: a placa continua parecendo boa, e o
sintoma aparece como leitura errática num pino ou noutro, dias depois.

**GPIO4 e GPIO5 são pinos de strapping** (MTMS e MTDI). O HX711 mantém o `DT` em nível
alto enquanto não tem dado pronto, e esse nível é amostrado no reset. Com a configuração
de fábrica do C6 isso é inofensivo, mas guarde a informação: se a placa passar a se
comportar de forma estranha no boot **com o HX711 ligado e normal sem ele**, esta é a
primeira hipótese — e mudar os dois pinos custa uma linha.

**`Wire.begin()` sem argumentos não vai para o GPIO6/7.** O variant do C6 define
`SDA = 23` e `SCL = 22`. O firmware sempre passa os pinos explicitamente
(`SensoresSht.cpp:31`); quem escrever código novo e esquecer os argumentos vai depurar um
barramento mudo com a fiação perfeitamente correta.

**O que distingue o SHT30 interno do externo é só o pino `ADDR`**: em GND o sensor
responde em 0x44 (interno), em VDD responde em 0x45 (externo). Os dois dividem o mesmo
barramento, sem multiplexador — foi por isso que este sensor foi escolhido
(`SensoresSht.h:1-5`). Trocar os dois de lugar **não dá erro nenhum**: dá uma série inteira
com a temperatura de fora rotulada como interna, e o diferencial térmico com o sinal
invertido. Confira com `ler` antes de fechar a caixa. Sobre pull-ups: a maioria dos
módulos já traz os seus, e dois módulos em paralelo deixam a resistência equivalente
pela metade — aceitável nas distâncias da bancada.

**O I²C não foi feito para cabo longo.** O sensor externo fica fora da caixa, e cada
centímetro a mais de cabo aumenta a capacitância do barramento. O modo de falha é
traiçoeiro: o sensor responde na bancada, some em campo, e aparece como `sht_out_fault`
intermitente — que, com a detecção sendo feita só no boot
([D-05](../defeitos-conhecidos.md#d-05)), vira um sensor "ausente" até alguém reiniciar o
nó. Mantenha o cabo curto e trançado; se o projeto do invólucro exigir mais do que uns
poucos decímetros, isso vira uma decisão de hardware, não um detalhe de montagem.

## Como exercitar cada peça

Tudo abaixo funciona com a placa alimentada só pelo cabo USB, sem rede e sem plataforma.
A saída completa e comentada do comando `ler` está em
[O firmware](04-o-firmware.md#testar-os-sensores-na-bancada).

**SHT30** — `ler` mostra os dois sensores; `sondar` redetecta sem reiniciar, que é o que
você vai usar toda vez que plugar ou desplugar um sensor na bancada. Um sensor que não
responde aparece como `ausente`, e **`ausente` não é zero**: na mensagem real o campo é
omitido e uma flag acende.

**HX711** — `ler` mostra a **contagem bruta** mesmo sem calibração nenhuma. É o teste
elétrico: aperte a plataforma com a mão e veja a contagem se mover. Se ela não se move,
o problema é de ligação, e nenhuma calibração conserta. Só depois disso vêm `tara` (com a
colmeia montada e vazia) e `calibrar <kg>` (com massa-padrão conhecida). Cada amostra
publicada é a média de 10 leituras (`CelulaDeCarga.h:15`).

**Bateria** — `ler` mostra a tensão já multiplicada pelo divisor. **Confira com um
multímetro antes de confiar no alerta de bateria fraca.** O firmware assume 12 bits de
resolução e 3,3 V de fundo de escala (`main.cpp:41-43`) e não faz nenhuma calibração do
ADC; o limiar de `low_batt` é 3,50 V, escolhido para o 18650 (`Amostra.h:25`). Meça a
tensão real da célula e compare com o que o `ler` informa, em pelo menos dois pontos da
faixa, antes de acreditar no número.

**Rede** — `wifi <ssid> <senha>`, `broker <host> [porta]`, `mqtt <usuario> <senha>` e
`estado`. Os três primeiros gravam na NVS e **pedem reinício** para valer. O roteiro
completo, do provisionamento ao gráfico aparecendo na tela, está em
[Do nó ao gráfico](08-do-no-ao-grafico.md).

## Primeira energização, na ordem segura

1. Antes de plugar qualquer sensor, ligue só a placa e **meça 3V3 e GND com o
   multímetro**. Um header trocado se descobre aqui, custando um minuto.
2. Ligue **um componente por vez**, com a placa desenergizada, e depois `sondar` e `ler`
   entre um e outro.
3. Confira o HX711 pela contagem bruta antes de pensar em calibrar.
4. Confira qual SHT30 é o interno pelo próprio `ler`, aquecendo um deles com a mão.
5. Só então provisione WiFi, broker e credenciais MQTT.

A razão de ligar um por vez: os dois SHT30 dividem o barramento, e um módulo em curto
derruba o I²C inteiro. Com tudo ligado de uma vez, os dois somem juntos e nada indica
qual dos dois é o culpado.

## O outro lado: onde a plataforma roda

O servidor também é hardware. Hoje ele é "a VM do IFPB"
(`deploy/docker-compose.yml:1-2`, `deploy/Caddyfile:1`) — a mesma pilha sobe no notebook
do bolsista, mudando só os valores de `deploy/.env`.

O que está definido: TimescaleDB, Mosquitto escutando na 1883 com `allow_anonymous
false` e credencial por nó, Caddy nas portas 80/443 emitindo o certificado, e o Flask sob
gunicorn com 3 workers. O ingestor é um processo separado do web, de propósito.

O que **não** está definido em lugar nenhum: núcleos, memória, disco para a série
temporal e política de retenção. Está escrito aqui para você não procurar uma
especificação que não existe — quando ela for necessária, será uma decisão a tomar.

E o esclarecimento que evita a confusão mais provável: o **Raspberry Pi aparece apenas
como gateway de campo na Fase 5, nunca como servidor**.

## O que ainda vai entrar (Fase 5)

A coluna que importa aqui é a terceira: o que está decidido e o que ainda não está.

| Item | Já decidido | Ainda em aberto |
|---|---|---|
| Rádio LoRa | 433 MHz, quadro binário de ~40 B, endereçado pelo `node_id` | **o módulo não foi escolhido** |
| Gateway | Raspberry Pi 5, publicando no mesmo tópico e formato | a pasta `gateway/` ainda não existe |
| Bioacústica | microfone MEMS INMP441 por I2S; `sound_rms` já reservado no contrato | `sound_bands` precisa de migração no banco |
| Energia | autonomia ≥ 15 dias (meta M5 do PIBITI), por deep sleep | painel, bateria e controlador de carga |
| Invólucro | impressão em PETG | geometria, vedação e fixação na caixa |
| Lote | 20 unidades | — |

O invariante que faz essa mudança ser menor do que parece: **do broker para dentro, nada
muda**. O gateway LoRa publica no mesmo tópico, com o mesmo JSON, e o ingestor não sabe
a diferença.

## O que ainda não foi decidido

Vale listar junto, porque são as perguntas que aparecem na hora de comprar:

- **O módulo LoRa.** Só a frequência está fixada. Nenhum chip ou módulo concreto aparece
  em lugar nenhum do repositório.
- **O caminho de energia.** Sabemos a célula (18650) e o limiar do alerta, mas não como
  ela alimenta a placa: 3,0 a 4,2 V não entra direto no 3V3, e é pouco para o regulador
  do pino 5V. Falta o conversor e o controlador de carga, além do painel.
- **O invólucro**, além da palavra "PETG": grau de proteção, vedação, fixação e onde
  exatamente o sensor externo fica.
- **A máquina do servidor**, como dito acima.

Um documento de hardware que descreve o nó que gostaríamos de ter é pior do que nenhum.
Estas quatro linhas são o estado real do projeto — e cada uma é uma decisão que ainda
cabe a alguém tomar.

→ Próximo: [Engenharia de software](05-engenharia-de-software.md)
