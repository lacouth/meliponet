# 4. O firmware

Para quem vai mexer em `firmware/`. Esta é a parte mais próxima da sua formação — o que
provavelmente é novo aqui não é o C++ nem o I²C, é a **forma de organizar e testar**.

## PlatformIO

Usamos PlatformIO em vez da IDE do Arduino. A diferença que importa: a configuração do
projeto (placa, bibliotecas, versões, flags) fica num arquivo versionado, o
`platformio.ini`, em vez de espalhada nas preferências da sua máquina.

Isso elimina uma classe inteira de problema — "compila na minha máquina e não na sua",
porque cada um tinha uma versão diferente de uma biblioteca.

```ini
[env:esp32c6]
platform = espressif32
board = esp32-c6-devkitc-1
framework = arduino
lib_deps =
    bblanchon/ArduinoJson@^7.2.0
    robtillaart/SHT31@^0.5.0
    bogde/HX711@^0.7.5
```

Repare que cada biblioteca tem **versão fixada**. Não é preciosismo: uma atualização
silenciosa de biblioteca já quebrou muito projeto que funcionava.

## Dois ambientes

```ini
[platformio]
default_envs = esp32c6
```

| Ambiente | Onde roda | Para quê |
|---|---|---|
| `esp32c6` | no hardware | o firmware de verdade |
| `native` | **no seu PC** | testar a lógica pura, sem hardware |

O ambiente `native` é a ideia mais importante deste documento.

## Testar firmware sem hardware

O ciclo normal de firmware é lento: compila, grava, abre o monitor serial, provoca a
condição, olha o `printf`. Cada volta leva minutos, e testar um caso de borda —
"o que acontece se o peso for exatamente -0,004 kg?" — é quase impraticável.

A saída é **separar a lógica pura do acesso ao hardware**.

- Ler o registrador do SHT30 exige hardware.
- Converter a leitura em inteiro escalado, montar o JSON, decidir se uma flag deve ser
  ligada, gerenciar o spool: **não exige nada**. É aritmética e lógica.

Toda a segunda categoria mora em código que não inclui `Arduino.h`, compila no PC e roda
em milissegundos:

```bash
pio test -e native -d firmware
```

O exemplo concreto é `lib/MelipoNet/TelemetryCodec`. Ele não inclui `Arduino.h`, não
aloca memória, e é exatamente o que o teste dos vetores dourados exercita. Sem isso,
verificar que o C++ concorda com o Python exigiria um ESP32 ligado e uma rede
funcionando — e ninguém faria isso a cada commit.

**Regra de projeto:** nada que possa ser testado sem hardware deve depender do Arduino.

## A estrutura

```
firmware/
├── platformio.ini          placa, bibliotecas, ambientes
├── src/
│   └── main.cpp            setup() e loop() — só orquestra
├── lib/
│   ├── MelipoSensors/         ShtPair, LoadCell        (precisa de hardware)
│   ├── MelipoNet/             WifiLink, MqttPublisher,
│   │                          TelemetryCodec, Spool     (codec é puro)
│   └── MelipoCore/            Config (NVS), Scheduler
└── test/native/
    └── test_codec/         roda no PC
```

### Interface comum para os sensores

Cada sensor é um objeto com a mesma interface:

```cpp
bool begin();
bool read(Reading &out);
Status status() const;
```

Assim o laço principal não conhece detalhes de hardware. Trocar o SHT30 por outro
sensor, ou acrescentar o microfone na Fase 5, não mexe no `main.cpp`.

E note: `read()` devolve `bool`. Um sensor que falhou **não devolve zero** — ele avisa
que falhou, o campo é omitido da mensagem e uma flag explica. Isso é a mesma regra do
contrato, do lado do firmware.

## O que o firmware precisa fazer (Fase 3)

1. **Ler os dois SHT30.** Mesmo barramento I²C, endereços 0x44 (interno) e 0x45
   (externo). Sensor ausente ou travado vira flag, não trava a leitura.
2. **Ler a célula de carga** pelo HX711, com tara e escala guardadas na NVS.
3. **Conectar no WiFi e sincronizar o relógio por NTP.** Com WiFi, o horário vem da
   rede — o problema de deriva de relógio só aparece na Fase 5, com LoRa.
4. **Publicar por MQTT**, QoS 1, no tópico `meliponet/v1/<node_id>/telemetry`.
5. **Guardar em buffer quando a rede cai** (spool em LittleFS) e drenar ao reconectar,
   preservando `seq` e `ts` originais.

## Coisas que se aprende quebrando

**`seq` tem que sobreviver a reset.** Guarde na NVS. Se o nó reiniciar e recomeçar do 1,
a plataforma vai descartar tudo como reenvio duplicado — corretamente, pela restrição
`UNIQUE (node_id, seq)` — e o nó ficará mudo sem que nada acuse. Isso já aconteceu com o
*simulador* durante o desenvolvimento; em campo teria sido pior.

**Credenciais não vão no código.** Senha de WiFi e do broker moram na NVS, configuradas
por serial ou portal cativo. Código vai para o GitHub; senha no fonte vaza.

**Buffer pequeno demais não deve truncar.** O `encode()` devolve 0 e uma string vazia se
o buffer não couber, em vez de escrever um JSON pela metade. Um JSON truncado seria
recusado pelo ingestor como "malformado", sem indicação de que a causa foi o buffer do
nó — você perderia horas procurando no lugar errado.

**`float` de 32 bits não é `double`.** No ESP32, `float` tem ~7 dígitos significativos.
É outro motivo para as métricas trafegarem como inteiros.

## Fluxo de trabalho

```bash
# 1. lógica pura, no PC — segundos
pio test -e native -d firmware

# 2. compila para o alvo
pio run -e esp32c6 -d firmware

# 3. grava e abre o monitor serial
pio run -e esp32c6 -d firmware -t upload -t monitor

# 4. veja o JSON cru chegando ao broker, antes de olhar o banco
mosquitto_sub -t 'meliponet/v1/#' -v
```

O passo 4 é o mais útil na depuração: ele separa "o nó está publicando errado" de "a
plataforma está lendo errado". Sem ele, você fica olhando um gráfico vazio sem saber de
que lado está o problema.

## Calibração e verificação

- **SHT30**: compare contra um termo-higrômetro de referência.
- **HX711**: use massas-padrão em **vários pontos** da faixa, não só um. Um ponto só
  ajusta a escala e esconde a não-linearidade.
- **Consumo**: meça por estado (dormindo, lendo, transmitindo). É o que vai comprovar
  a autonomia de ≥ 15 dias prometida na meta M5 do PIBITI.

→ Próximo: [Engenharia de software](05-engenharia-de-software.md)
