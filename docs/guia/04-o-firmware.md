# 4. O firmware

Para quem vai mexer em `firmware/`. Esta é a parte mais próxima da sua formação — o que
provavelmente é novo aqui não é o C++ nem o I²C, é a **forma de organizar e testar**.

> **Nunca usou o PlatformIO?** Faça antes a prática de
> [Primeiros passos com o PlatformIO](09-primeiros-passos-com-o-platformio.md): meia hora,
> criando um projeto do zero. Este documento aqui é a referência do firmware do projeto e
> assume que você já sabe operar a ferramenta.

## PlatformIO

Usamos PlatformIO em vez da IDE do Arduino. A diferença que importa: a configuração do
projeto (placa, bibliotecas, versões, flags) fica num arquivo versionado, o
`platformio.ini`, em vez de espalhada nas preferências da sua máquina.

Isso elimina uma classe inteira de problema — "compila na minha máquina e não na sua",
porque cada um tinha uma versão diferente de uma biblioteca.

```ini
[env:esp32c6]
platform = https://github.com/pioarduino/platform-espressif32/releases/download/55.03.311/platform-espressif32.zip
board = esp32-c6-devkitc-1
framework = arduino
lib_deps =
    knolleary/PubSubClient@^2.8
    robtillaart/SHT31@^0.5.0
    bogde/HX711@^0.7.5
```

Repare que cada biblioteca tem **versão fixada**. Não é preciosismo: uma atualização
silenciosa de biblioteca já quebrou muito projeto que funcionava.

E repare no `platform`: não é o `espressif32` oficial. O platform oficial do PlatformIO
parou no Arduino core 2.x, e o **ESP32-C6 só ganhou suporte no core 3.x** — com o
oficial, o build falha com *"This board doesn't support arduino framework!"*. O fork
`pioarduino` é o caminho que a comunidade usa para os chips novos (C6, H2, P4). A
versão está fixada pelo mesmo motivo das bibliotecas.

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

O exemplo concreto é `lib/MelipoCore/Telemetria`. Ele não inclui `Arduino.h`, não
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
│   ├── MelipoCore/         LÓGICA PURA — compila no PC e no ESP32
│   │                       Escala, Amostra, Calibracao, Agenda,
│   │                       Telemetria, Spool, SpoolRecuperacao,
│   │                       Recuo, LinhaDeComando
│   └── MelipoHardware/     FALA COM O HARDWARE — só compila no ESP32
│                           SensoresSht, CelulaDeCarga, ConexaoWifi,
│                           PublicadorMqtt, Configuracao (NVS),
│                           SpoolEmLittleFS
└── test/native/            roda no PC, sem placa
    ├── test_telemetria/  test_escala/   test_amostra/
    ├── test_spool/       test_console/  test_recuperacao/
    └── test_calibracao_e_agenda/
```

Os nomes estão em português, como os comentários e o guia. A exceção são os nomes que
**aparecem no JSON** — `temp_in_c`, `weight_kg`, `node_id`, `Campo::rssi`,
`Flag::sht_in_fault` — que ficam escritos letra por letra como o contrato os escreve. Uma
segunda grafia para o mesmo campo só criaria confusão na hora de comparar o que o nó
enviou com o que o banco guardou.

**A divisão das pastas é a regra do projeto, materializada.** `MelipoCore` não inclui
`Arduino.h` em lugar nenhum; `MelipoHardware` fica de fora do build nativo com uma
linha só no `platformio.ini`:

```ini
lib_ignore = MelipoHardware
```

Isso tem que ser por **pasta**, não por arquivo: o PlatformIO compila todos os arquivos
de uma pasta de biblioteca. Misturar código puro e código de hardware na mesma pasta
faz o build nativo falhar procurando `WiFi.h` — foi assim que a estrutura chegou a
esta forma.

### Interface comum para os sensores

Cada sensor é um objeto com a mesma forma:

```cpp
bool iniciar(...);   // detecta o sensor; devolve falso se ele não responder
Leitura ler();       // uma medida, ou Leitura::falha()
```

Assim o laço principal não conhece detalhes de hardware. Trocar o SHT30 por outro
sensor, ou acrescentar o microfone na Fase 5, não mexe no `main.cpp`.

E note o tipo de retorno. `Leitura` não é um `double`:

```cpp
struct Leitura {
  double valor = 0.0;
  bool valida = false;

  static Leitura obtida(double v) { return {v, true}; }
  static Leitura falha() { return {}; }
};
```

Um sensor que falhou **não devolve zero** — ele devolve `Leitura::falha()`, o campo é
omitido da mensagem e uma flag explica. Zero significaria "a colmeia estava a 0 grau",
que é uma afirmação falsa sobre o mundo; ausente significa "não sabemos", que é verdade.
Essa distinção é a regra mais importante do projeto inteiro, e é ela que o tipo carrega.

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

**Buffer pequeno demais não deve truncar.** O `serializar()` devolve 0 e uma string vazia se
o buffer não couber, em vez de escrever um JSON pela metade. Um JSON truncado seria
recusado pelo ingestor como "malformado", sem indicação de que a causa foi o buffer do
nó — você perderia horas procurando no lugar errado.

**`float` de 32 bits não é `double`.** No ESP32, `float` tem ~7 dígitos significativos.
É outro motivo para as métricas trafegarem como inteiros.

**Um cabeçalho traz os próprios tipos.** Se um `.h` usa `size_t`, ele inclui
`<stddef.h>` — não conta com o arquivo que o inclui ter feito isso antes. Esse erro não
aparece no build nativo se o arquivo não for compilado lá, e só surge no build do
alvo.

## Quatro defeitos que este firmware já teve

Os arquivos do `lib/` apontam para cá. São histórias de verdade, e cada uma explica por
que um pedaço do código tem a forma esquisita que tem. Vale ler antes de "simplificar"
algum deles.

### `millis()` volta a zero a cada 49,7 dias

`millis()` devolve um `uint32_t` de milissegundos. Passados ~49,7 dias, ele dá a volta e
recomeça do zero. Um nó em campo passa por isso.

A forma ingênua de agendar é guardar o instante da próxima vez e comparar:

```cpp
if (agora > proxima) { ... }        // ERRADO
```

Com `proxima` alto (de antes da volta) e `agora` baixo (depois dela), essa condição fica
falsa **pelos próximos 49,7 dias**. A amostragem simplesmente para, e nada no serial
acusa.

A forma correta compara a **diferença**, em aritmética sem sinal:

```cpp
if (agora - ultima >= intervalo) { ... }   // certo, atravessa a volta
```

A subtração sem sinal dá o resultado certo mesmo quando o contador deu a volta, porque a
aritmética de `uint32_t` é modular. É a regra de `Agenda` e de `Recuo`, e o teste
`test_calibracao_e_agenda` a exercita justamente no ponto da virada — coisa que em
hardware exigiria 49,7 dias de espera.

### O recuo que travava para sempre

A lógica de nova tentativa vivia solta dentro de `WifiLink` e duplicada em
`MqttPublisher`. Tinha dois defeitos, e nenhum teste os alcançava porque estavam num
arquivo que não compila no PC.

O primeiro era uma guarda invertida: quanto mais tempo passava desde a última tentativa,
mais ela **recusava** tentar de novo. Como voltava sem atualizar o instante da próxima
tentativa, a diferença só crescia — e uma queda de rede mais de cinco minutos depois da
reconexão anterior era definitiva até alguém reiniciar a placa.

O segundo era a comparação sobre instantes, e não sobre a diferença: o mesmo defeito da
seção acima.

Hoje isso é a classe `Recuo`, com teste nativo. A regra que sobrou: **`registrarTentativa`
precisa ser chamada em toda tentativa, inclusive nas que falham** — não chamá-la foi o que
travou a versão anterior.

### O anel do spool dando a volta

O spool é um anel de arquivos numerados de 0 a 511. Depois de uma queda de energia, o
único estado que sobrevive é *quais posições têm arquivo* — o início e a contagem da fila
precisam ser deduzidos daí.

A dedução ingênua é "o início é a menor posição ocupada". Ela vale enquanto a fila não deu
a volta no anel, e falha em silêncio quando dá. Com as posições 510, 511, 0 e 1 ocupadas,
ela conclui início 0 e contagem 4, reivindicando as posições 0 a 3: as posições 2 e 3
estão vazias e são descartadas como ilegíveis, enquanto as duas mensagens **realmente mais
antigas** ficam órfãs no flash e são recontadas a cada boot seguinte.

A dedução correta é: a fila é o **maior trecho contíguo circular** de posições ocupadas.
É o que `deduzirEstadoDaFila` faz — uma função pura, para poder ser testada com o anel
dado a volta, com o anel cheio e com estado inconsistente, cenários que em hardware
exigiriam provocar quedas de energia em momentos específicos.

### O MQTT configurado dentro do `if` do WiFi

`PublicadorMqtt::configurar` guarda servidor, tópicos e credenciais; `manter` é quem
conecta. Antes, a configuração acontecia **dentro do `if`** que testava a conexão do WiFi.

Um nó que subisse mais rápido que o roteador — rotina depois de uma falta de energia —
ficava com servidor e tópicos vazios. Toda tentativa posterior ia para `0.0.0.0:0` com
tópico vazio. O WiFi reconectava sozinho, o nó parecia saudável no `estado`, e nunca mais
publicava nada até alguém reiniciar a placa.

Por isso o `setup()` chama `configurar` **sempre**, antes e independentemente de o WiFi
ter subido.

## Por que as métricas são inteiros, e não `float`

Duas regras do contrato dependem uma da outra, e vale ver as duas juntas.

**Formatar `float` não é reproduzível entre plataformas.** A `printf` da newlib do ESP32
não arredonda igual à glibc do PC, o ESP32 calcula em `float` de 32 bits, e empates como
30,125 caem para lados diferentes. Se o firmware emitisse `snprintf("%.2f", 30.125)` e o
simulador emitisse o equivalente em Python, os dois produziriam JSONs diferentes para a
mesma leitura — e a divergência apareceria só em algumas leituras, o pior tipo de bug.

Com inteiros o arredondamento acontece **uma vez só**, na camada de sensores, e a saída do
codec é idêntica byte a byte à do Python. É exatamente isso que o `test_telemetria`
verifica contra `contracts/testdata/vectors.h`.

**A ordem da conta importa.** A regra canônica é: multiplique em `double`, depois arredonde
o produto, com empate para longe do zero — `llround(valor * 10^casas)`, que é o que
`escalar()` faz. Arredondar o valor original com aritmética decimal exata daria outro
resultado em cerca de 23% dos valores da forma `x.xx5`, e não seria reproduzível no ESP32,
que não tem como calcular a expansão decimal exata de um `double`.

## Acrescentar um comando ao console

É a contribuição de entrada do firmware: pequena, útil, e passa por todo o caminho
(código, build, gravação, bancada). Em `src/main.cpp`, são dois passos.

**1. Escreva a função.** Ela recebe a linha já dividida e não devolve nada:

```cpp
void comandoIntervalo(const Comando &cmd) {
  if (cmd.quantidade < 2) {
    Serial.println("uso: intervalo <segundos>");
    return;
  }
  uint32_t segundos = 0;
  if (!lerNumero(cmd.argumento[1], 3600, segundos)) {
    Serial.println("intervalo invalido (1 a 3600); nada foi gravado");
    return;
  }
  g_configuracao.intervalo_amostra_s = segundos;
  gravarConfiguracao(g_configuracao);
  Serial.printf("intervalo = %lu s; reinicie\n", (unsigned long)segundos);
}
```

**2. Ponha uma linha na tabela**, junto das outras:

```cpp
{"intervalo", comandoIntervalo, "intervalo <s>                periodo entre amostras"},
```

Pronto. O `ajuda` percorre essa mesma tabela, então o comando novo já aparece nele — não
há uma segunda lista para lembrar de atualizar.

Repare no padrão das funções existentes, porque ele não é enfeite:

- **valide tudo antes de gravar qualquer coisa.** O `comandoWifi` confere o tamanho do
  ssid *e* o da senha antes de copiar qualquer um dos dois: gravar o ssid e recusar a
  senha deixaria a configuração pela metade.
- **comando recusado não altera nada.** `lerNumero` e `lerPorta` não tocam na variável de
  saída quando recusam, para que um valor digitado errado não apague o que já valia.
- **nunca ecoe uma senha.** O monitor serial vai para o log do terminal de quem preparou o
  nó, e de lá para um print numa conversa.

## Fluxo de trabalho

```bash
# 1. lógica pura, no PC — segundos
pio test -e native -d firmware

# 2. compila para o alvo
pio run -e esp32c6 -d firmware

# 3. grava e abre o monitor serial
pio run -e esp32c6 -d firmware -t upload -t monitor

# 4. no monitor serial: os sensores estão lendo? (não precisa de rede nenhuma)
ler

# 5. veja o JSON cru chegando ao broker, antes de olhar o banco
mosquitto_sub -t 'meliponet/v1/#' -v
```

Os passos 4 e 5 existem pelo mesmo motivo: **separar as camadas antes de depurar**. O 4
responde "os sensores estão lendo?" sem envolver WiFi, broker nem plataforma. O 5
responde "o nó está publicando?" sem envolver o banco nem o dashboard. Sem eles, você
fica olhando um gráfico vazio sem saber de que lado está o problema — e as causas
possíveis vão de um fio solto a um filtro errado numa consulta SQL.

## Testar os sensores na bancada

Você não precisa de rede, broker, nem plataforma para verificar a eletrônica. A ligação
de cada peça — pinos, cuidados de alimentação e a ordem segura de energizar — está em
[O hardware](10-o-hardware.md). Com a placa alimentada só pelo cabo USB:

```
ler          uma leitura agora
ler 30       trinta leituras, uma por segundo
sondar       redetecta os sensores, sem reiniciar
```

A saída mostra cada grandeza em unidade física **e** no inteiro escalado que iria para a
mensagem:

```
[leitura 1/1]
  temp int  30.115 C  (escalado: 3012)
  ur int    68.402 %  (escalado: 6840)
  temp ext  ausente
  ur ext    ausente
  hx711     118472 contagens
  peso      12.483 kg  (escalado: 12483)
  bateria   3.921 V  (escalado: 392)
```

Três coisas para reparar nessa saída:

**O par unidade/escalado é a regra do contrato acontecendo.** 30,115 °C vira `3012`, não
`30.115`. É a única passagem de ponto flutuante para inteiro no firmware, e aqui ela fica
visível. Ver o arredondamento com os próprios olhos ensina mais do que
[o documento do contrato](02-o-contrato.md).

**`ausente` não é zero.** O SHT30 externo desligado aparece como `ausente`, e na mensagem
real o campo seria **omitido** com uma flag ligada — nunca enviado como `0`. Desligue um
sensor de propósito e confira: é a distinção mais importante do projeto inteiro, e custa
dez segundos de bancada para entendê-la.

**A contagem bruta do HX711 aparece mesmo sem calibração.** É o que permite conferir a
ligação da célula antes de calibrar: aperte a plataforma com a mão e veja a contagem se
mover. Se ela não se move, o problema é elétrico, e nenhuma calibração vai consertar.

`ler` não toca em WiFi, MQTT, relógio nem no contador `seq` — testar na bancada não pode
abrir lacuna na série do nó depois de instalado.

O `sondar` existe porque os sensores são detectados **uma vez, no boot**. Se você ligar
um SHT30 com a placa já rodando, ele fica marcado como ausente até alguém reiniciar. Em
campo isso é um defeito ([D-05](../defeitos-conhecidos.md#d-05)); na bancada, onde se
liga e desliga sensor o tempo todo, `sondar` resolve na hora.

## Calibração e verificação

- **SHT30**: compare contra um termo-higrômetro de referência.
- **HX711**: use massas-padrão em **vários pontos** da faixa, não só um. Um ponto só
  ajusta a escala e esconde a não-linearidade.
- **Consumo**: meça por estado (dormindo, lendo, transmitindo). É o que vai comprovar
  a autonomia de ≥ 15 dias prometida na meta M5 do PIBITI.

→ Próximo: [O hardware](10-o-hardware.md)
