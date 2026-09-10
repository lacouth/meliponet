# 4. O nó sensor

Para quem vai **montar, ligar ou programar um nó**. O que programar está em
[`firmware/ROTEIRO.md`](../../firmware/ROTEIRO.md); aqui ficam as peças físicas e o
porquê de cada escolha — o que é cada componente, o que ele erra quando erra, e como
conferir que está funcionando antes de fechar a caixa.

## O nó de hoje, peça por peça

| Peça | O quê |
|---|---|
| Placa | ESP32-C6-DevKitC-1, 8 MB de flash |
| Temperatura e umidade | 2× SHT30, I²C, endereços 0x44 e 0x45 |
| Peso | célula de carga de 50 kg + módulo HX711 |
| Energia | célula 18650 + divisor resistivo 2× 100 kΩ |

É só isso. Não há rádio LoRa, microfone, painel solar nem invólucro — o que entra depois
está no fim deste documento.

## A placa: ESP32-C6-DevKitC-1

Duas coisas da placa afetam quem monta.

**Ela tem duas portas USB-C, e elas não são iguais.** A porta *UART* passa pela ponte
USB-serial da placa (GPIO16/17) e é a que se usa para gravar e monitorar. A porta *USB
nativa* do chip também grava e serve para depuração JTAG. Qualquer uma das duas alimenta
a placa; nos headers, dá para alimentar por 5V/GND ou por 3V3/GND.

**Ela tem 8 MB de flash, e você vai querer todos eles.** A tabela de partições padrão
reserva 1,3 MB para a aplicação. Cabe o nó do roteiro; não vai caber quando entrarem
bioacústica e LoRa. Se for guardar leituras num sistema de arquivos, reserve a partição
antes de precisar dela — e se comprar uma DevKitC-1 de 4 MB, saiba que o espaço é outro.

### Pinos que não estão disponíveis

Antes de escolher onde ligar qualquer coisa, saiba o que já está ocupado. Esta lista vem
do guia do usuário da ESP32-C6-DevKitC-1 e da página de GPIO do ESP-IDF para o C6:

| GPIO | Por que não usar |
|---|---|
| 8 | LED RGB embutido — e pino de strapping |
| 9, 15 | strapping: decidem modo de boot e a impressão de mensagens do ROM |
| 12, 13 | USB nativo (D− e D+) |
| 16, 17 | ponte USB-UART da placa |
| 10, 11 | não são levados aos headers em placas com flash interna |
| 24 – 30 | flash SPI |

E o que importa na outra direção: **as entradas analógicas do ADC1 são o GPIO0 ao
GPIO6**. É por isso que a medição de bateria fica no GPIO0, e não em qualquer pino livre.

## Como ligar

A ligação sugerida está no [roteiro](../../firmware/ROTEIRO.md#as-peças-e-como-ligar),
com o desenho dos headers. Aqui ficam os cuidados — cada um deles já custou uma tarde a
alguém.

**Alimente o HX711 em 3,3 V, nunca em 5 V.** O módulo aceita de 2,7 V a 5 V, e o nível
lógico da saída `DT` acompanha a alimentação. Em 5 V, ele entrega 5 V no GPIO, que não é
tolerante a 5 V. O dano é imediato e silencioso: a placa continua parecendo boa, e o
sintoma aparece como leitura errática num pino ou noutro, dias depois.

**GPIO4 e GPIO5 são pinos de strapping** (MTMS e MTDI). O HX711 mantém o `DT` em nível
alto enquanto não tem dado pronto, e esse nível é amostrado no reset. Com a configuração
de fábrica do C6 isso é inofensivo, mas guarde a informação: se a placa passar a se
comportar de forma estranha no boot **com o HX711 ligado e normal sem ele**, esta é a
primeira hipótese — e mudar os dois pinos custa uma linha.

**`Wire.begin()` sem argumentos não vai para o GPIO6/7.** O variant do C6 define
`SDA = 23` e `SCL = 22`. Passe os pinos explicitamente; quem esquecer vai depurar um
barramento mudo com a fiação perfeitamente correta.

**O que distingue o SHT30 interno do externo é só o pino `ADDR`**: em GND o sensor
responde em 0x44 (interno), em VDD responde em 0x45 (externo). Os dois dividem o mesmo
barramento, sem multiplexador — foi por isso que este sensor foi escolhido. Trocar os
dois de lugar **não dá erro nenhum**: dá uma série inteira com a temperatura de fora
rotulada como interna, e o diferencial térmico com o sinal invertido. Confira aquecendo
um deles com a mão antes de fechar a caixa. Sobre pull-ups: a maioria dos módulos já traz
os seus, e dois módulos em paralelo deixam a resistência equivalente pela metade —
aceitável nas distâncias da bancada.

**O I²C não foi feito para cabo longo.** O sensor externo fica fora da caixa, e cada
centímetro a mais aumenta a capacitância do barramento. O modo de falha é traiçoeiro: o
sensor responde na bancada, some em campo, e aparece como `sht_out_fault` intermitente.
Mantenha o cabo curto e trançado; se o invólucro exigir mais do que uns poucos
decímetros, isso vira uma decisão de hardware, não um detalhe de montagem.

## Primeira energização, na ordem segura

1. Antes de plugar qualquer sensor, ligue só a placa e **meça 3V3 e GND com o
   multímetro**. Um header trocado se descobre aqui, custando um minuto.
2. Ligue **um componente por vez**, com a placa desenergizada, conferindo entre um e
   outro.
3. Confira o HX711 pela **contagem bruta** antes de pensar em calibrar: aperte a
   plataforma com a mão e veja o número se mover. Se ele não se move, o problema é de
   ligação, e nenhuma calibração conserta.
4. Descubra qual SHT30 é o interno aquecendo um deles com a mão.
5. Só então configure WiFi e o endereço do servidor.

A razão de ligar um por vez: os dois SHT30 dividem o barramento, e um módulo em curto
derruba o I²C inteiro. Com tudo ligado de uma vez, os dois somem juntos e nada indica
qual dos dois é o culpado.

## Duas medidas que precisam de conferência externa

**A bateria.** Meça a tensão real da célula com um multímetro e compare com o que o seu
código informa, em pelo menos dois pontos da faixa, antes de acreditar no número. O ADC
do ESP32 não é calibrado de fábrica para isso, e o divisor tem tolerância. O limiar de
`low_batt` combinado no projeto é 3,50 V, escolhido para o 18650.

**O peso.** Depois de tarar com a colmeia vazia e calibrar com massa conhecida, confira
com uma massa **diferente** da que você usou para calibrar. Calibrar e conferir com o
mesmo peso não prova nada: a conta fecha por construção.

## O outro lado: onde a plataforma roda

O servidor também é hardware. Hoje ele é "a VM do IFPB" (`deploy/docker-compose.yml`) — a
mesma pilha sobe no notebook de quem trabalha no projeto, mudando só os valores de
`deploy/.env`. Está definido: TimescaleDB, Mosquitto na 1883 com credencial por nó, Caddy
emitindo o certificado, e o Flask sob gunicorn. **Não** está definido: núcleos, memória,
disco para a série temporal e política de retenção — está escrito aqui para você não
procurar uma especificação que não existe.

E o esclarecimento que evita a confusão mais provável: o **Raspberry Pi aparece apenas
como gateway de campo numa fase futura, nunca como servidor**.

## O que ainda vai entrar

| Item | Já decidido | Ainda em aberto |
|---|---|---|
| Rádio LoRa | 433 MHz, quadro binário de ~40 B, endereçado pelo `node_id` | **o módulo não foi escolhido** |
| Gateway | Raspberry Pi, publicando no mesmo tópico e formato | a pasta `gateway/` ainda não existe |
| Bioacústica | microfone MEMS INMP441 por I2S | os campos ainda não existem no contrato |
| Energia | autonomia ≥ 15 dias, por deep sleep | painel, bateria e controlador de carga |
| Invólucro | impressão em PETG | geometria, vedação e fixação na caixa |

O invariante que faz essa mudança ser menor do que parece: **do servidor para dentro,
nada muda**. O gateway publica a mesma mensagem, e o ingestor não sabe a diferença.

Um documento de hardware que descreve o nó que gostaríamos de ter é pior do que nenhum.
A coluna da direita é o estado real do projeto — e cada linha dela é uma decisão que
ainda cabe a alguém tomar.

→ Próximo: [Como trabalhamos](05-como-trabalhamos.md)
