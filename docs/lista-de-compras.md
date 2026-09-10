# Lista de compras — o nó de hoje

Este documento é a ponte entre o que o [guia de hardware](guia/10-o-hardware.md) descreve e
o que precisa ser comprado para existir um nó de verdade. Ele cobre **apenas as peças do
nó de hoje**: placa, os dois sensores de temperatura e umidade, a pesagem e a alimentação.
Rádio LoRa, gateway, painel solar, microfone e invólucro são da Fase 5 e não entram aqui —
o guia de hardware explica por quê.

Duas quantidades por linha, porque elas têm urgências diferentes. O **kit de bancada** é
o que permite começar a trabalhar já, com uma unidade de cada coisa. O **lote** é o número
do projeto: 20 nós.

## Como preencher

Cada dupla preenche as linhas da sua peça. Uma linha só está pronta quando tem modelo
exato, fornecedor e preço — "um SHT30 qualquer" não é uma decisão de compra, é um
adiamento. Onde a escolha tiver pegadinha, escreva a pegadinha na coluna do porquê: quem
comprar daqui a um ano não vai lembrar, e o erro só aparece com a peça na mão.

Duas pegadinhas já conhecidas, que estão no guia de hardware e precisam sobreviver até o
carrinho de compras:

- **A DevKitC-1 precisa ser a de 8 MB de flash.** O firmware não cabe na de 4 MB como está.
- **O módulo do SHT30 precisa expor o pino `ADDR`.** É só ele que distingue o sensor
  interno (0x44) do externo (0x45), e sem ele não dá para ter dois no mesmo barramento.

## A lista

| Peça | Modelo exato | Kit de bancada | Lote (20 nós) | Fornecedor | Preço unit. | Por que este |
|---|---|---|---|---|---|---|
| Placa | ESP32-C6-DevKitC-1, **8 MB** | 1 | 20 | | | flash de 4 MB não comporta o firmware |
| Temp./umidade interno | módulo SHT30 com pino `ADDR` | 1 | 20 | | | `ADDR` em GND → 0x44 |
| Temp./umidade externo | módulo SHT30 com pino `ADDR` | 1 | 20 | | | `ADDR` em VDD → 0x45 |
| Cabo do sensor externo | par trançado, curto | 1 | 20 | | | I²C não foi feito para cabo longo |
| Peso | célula de carga 50 kg | 1 | 20 | | | faixa da colmeia povoada |
| Amplificador | módulo HX711 | 1 | 20 | | | **alimentar em 3,3 V, nunca 5 V** |
| Bateria | célula 18650 | 1 | 20 | | | |
| Suporte de bateria | | 1 | 20 | | | |
| Divisor de tensão | 2× resistor 100 kΩ | 2 | 40 | | | leitura de bateria no GPIO0 (ADC1) |
| Protoboard e jumpers | | 1 | — | | | só bancada |
| Cabo USB-C | | 1 | 20 | | | a porta UART é a que grava |

### Sobressalentes

Peças que queimam quando alguém erra a alimentação, e que param o trabalho de uma pessoa
por uma semana esperando reposição:

| Peça | Quantidade | Por quê |
|---|---|---|
| ESP32-C6-DevKitC-1 | | HX711 em 5 V danifica o GPIO4, e o dano é silencioso |
| Módulo HX711 | | |
| Módulo SHT30 | | |

## O que ainda falta

- Preencher fornecedor, preço e link de cada linha — é o trabalho da semana 1.
- Decidir a **mecânica de apoio** da célula de carga sob a colmeia, que não é uma peça de
  catálogo e provavelmente vira usinagem ou impressão.
- Conferir se algum item precisa de importação, que muda o prazo em semanas.
- As peças da Fase 5 (LoRa, painel, bateria de campo, microfone, invólucro) ganham a sua
  própria lista quando as decisões em aberto do guia de hardware forem tomadas.
