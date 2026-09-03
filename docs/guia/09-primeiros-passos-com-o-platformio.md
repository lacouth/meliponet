# 9. Primeiros passos com o PlatformIO

Para quem **nunca usou** o PlatformIO. O [documento do firmware](04-o-firmware.md)
explica por que o projeto o escolheu e como ele está configurado aqui; este ensina a
operá-lo, fazendo.

A prática tem duas partes:

| | O que exige | Quanto leva |
|---|---|---|
| **Parte 1** — no computador | só o PC | uns 20 minutos |
| **Parte 2** — na placa | um ESP32-C6 e um cabo USB | uns 10 minutos |

**A Parte 1 é para todos**, inclusive quem ainda não tem placa. Isso não é um consolo:
é a ideia central do projeto. A maior parte do firmware do MelipoNet é testada no PC, e
quem só souber trabalhar com a placa na mão vai ficar parado toda vez que o hardware
faltar.

E a prática não é um "hello world" solto. Você vai escrever, em miniatura, **a função
mais importante do firmware** — a que converte a leitura de um sensor no inteiro que
trafega na mensagem. No fim, vai abrir a versão de verdade e reconhecê-la.

## Instalar

```bash
uv tool install platformio      # ou: pipx install platformio
pio --version
```

Se `pio` não for encontrado, `~/.local/bin` não está no seu `PATH`.

Não use `pip install platformio`: distribuições recentes recusam instalação no Python do
sistema. O motivo está em [Primeira contribuição](06-primeira-contribuicao.md).

---

## Parte 1 — no computador

### 1. Criar o projeto

```bash
mkdir ~/pio-primeiro && cd ~/pio-primeiro
pio project init
```

Repare no que apareceu:

| | Para que serve |
|---|---|
| `platformio.ini` | **a configuração do projeto** — placa, bibliotecas, flags |
| `src/` | o programa principal |
| `lib/` | as bibliotecas do próprio projeto |
| `test/` | os testes |
| `include/` | cabeçalhos compartilhados (não vamos usar) |
| `.gitignore` | já vem pronto, ignorando `.pio/` |

O `.gitignore` merece um segundo de atenção: `.pio/` é onde ficam o compilador baixado,
os objetos e o binário. É conteúdo gerado, pesa centenas de megabytes e **nunca** vai
para o git. O PlatformIO já sabe disso e cria o arquivo por você.

O `platformio.ini` nasceu praticamente vazio, só com comentários. Ele é o coração do
projeto: **tudo o que a IDE do Arduino guardaria nas preferências da sua máquina, aqui
fica num arquivo versionado.** É por isso que "compila na minha máquina e não na sua"
deixa de acontecer.

### 2. Escrever o `platformio.ini`

Apague o conteúdo e escreva:

```ini
[env:native]
platform = native
test_framework = unity
build_flags = -std=c++17
```

Linha por linha:

- **`[env:native]`** — um *ambiente*. Um projeto pode ter vários, e você escolhe qual
  usar com `-e`. Vamos criar um segundo na Parte 2.
- **`platform = native`** — este ambiente compila **para o seu computador**, com o gcc
  que você já tem. Nada de placa, nada de gravação.
- **`test_framework = unity`** — a biblioteca de testes. O PlatformIO baixa sozinho na
  primeira execução.
- **`build_flags = -std=c++17`** — a versão do C++.

### 3. A função

Crie `lib/Termometro/Termometro.h`:

```cpp
#pragma once

#include <stdint.h>

// Converte uma temperatura em graus Celsius no inteiro escalado do contrato:
// centesimos de grau. 30,12 C vira 3012.
int32_t centesimosDeGrau(double celsius);
```

E `lib/Termometro/Termometro.cpp`:

```cpp
#include "Termometro.h"

#include <math.h>

int32_t centesimosDeGrau(double celsius) {
  return static_cast<int32_t>(llround(celsius * 100.0));
}
```

Uma pasta dentro de `lib/` com um `.h` e um `.cpp` é uma biblioteca do projeto. O
PlatformIO descobre sozinho — não é preciso listar nada.

### 4. O teste

Crie `test/test_termometro/test_termometro.cpp`:

```cpp
#include <unity.h>

#include "Termometro.h"

namespace {

void test_conversao_simples(void) {
  TEST_ASSERT_EQUAL_INT32(3012, centesimosDeGrau(30.12));
  TEST_ASSERT_EQUAL_INT32(2500, centesimosDeGrau(25.0));
}

}  // namespace

void setUp(void) {}
void tearDown(void) {}

int main(int, char **) {
  UNITY_BEGIN();
  RUN_TEST(test_conversao_simples);
  return UNITY_END();
}
```

É o mesmo formato dos testes reais do projeto — compare depois com
`firmware/test/native/test_core/test_core.cpp`. Cada teste é uma função `void`, e o
`main` lista as que devem rodar. `setUp` e `tearDown` rodam antes e depois de cada
teste; aqui não precisamos delas, mas o Unity exige que existam.

### 5. Rodar

```bash
pio test -e native
```

Da primeira vez ele baixa o Unity. Depois:

```
test/test_termometro/test_termometro.cpp:19: test_conversao_simples	[PASSED]
-------------- native:test_termometro [PASSED] Took 3.34 seconds --------------
```

Pronto: você acabou de compilar e testar código de firmware **sem nenhum hardware**, em
três segundos.

---

## A parte que ensina de verdade

Você tem um teste verde. Isso não significa que ele sirva para alguma coisa. Vamos
provar.

Troque a implementação pelo jeito "óbvio" de converter — cortar em vez de arredondar:

```cpp
int32_t centesimosDeGrau(double celsius) {
  return static_cast<int32_t>(celsius * 100.0);   // sem llround
}
```

Rode de novo:

```
test/test_termometro/test_termometro.cpp:19: test_conversao_simples	[PASSED]
```

**Passou.** Duas implementações diferentes, o mesmo teste verde. Agora acrescente o caso
que as separa:

```cpp
// O caso que separa uma implementacao da outra: 30,125 esta exatamente no meio.
void test_empate(void) {
  TEST_ASSERT_EQUAL_INT32(3013, centesimosDeGrau(30.125));
  TEST_ASSERT_EQUAL_INT32(-1, centesimosDeGrau(-0.005));
}
```

(e não esqueça do `RUN_TEST(test_empate);` no `main`)

```
test/test_termometro/test_termometro.cpp:14: test_empate: Expected 3013 Was 3012	[FAILED]
```

Agora sim. Devolva o `llround` e veja os dois passarem.

### Por que esses números

| Entrada | Cortando | Arredondando |
|---|---|---|
| 30,12 | 3012 | 3012 |
| 25,0 | 2500 | 2500 |
| **30,125** | 3012 | **3013** |
| **−0,005** | 0 | **−1** |

30,125 está exatamente no meio entre 3012 e 3013 centésimos. Os valores "normais" que
você escolheria naturalmente para um teste não distinguem as duas implementações — só os
empates distinguem.

**A lição, que vale para tudo o que você vai escrever neste projeto: um teste que passa
nas duas implementações não testa nada.** Por isso a regra do repositório é escrever o
teste *antes* da correção e **vê-lo falhar**. Um teste que nunca falhou é uma suposição,
não uma verificação.

E isto não é um exercício artificial. Esse arredondamento é justamente o problema que
[o contrato](02-o-contrato.md) resolve: se o ESP32 arredondasse 30,125 para um lado e o
Python para o outro, o sistema funcionaria 99,9% das vezes e falharia em leituras
específicas que ninguém consegue reproduzir.

---

## Parte 2 — na placa

Se você não tem uma placa ainda, pule para a próxima seção. Nada do que vem depois
depende disto.

### 1. Um segundo ambiente

Acrescente ao `platformio.ini`, **sem apagar o `[env:native]`**:

```ini
[env:esp32c6]
platform = https://github.com/pioarduino/platform-espressif32/releases/download/55.03.311/platform-espressif32.zip
board = esp32-c6-devkitc-1
framework = arduino
monitor_speed = 115200
test_ignore = *
```

Duas linhas pedem explicação:

**O `platform` é uma URL, não `espressif32`.** O platform oficial do PlatformIO parou no
Arduino core 2.x, e o ESP32-C6 só ganhou suporte no 3.x — com o oficial, o build falha
com *"This board doesn't support arduino framework!"*. O fork `pioarduino` é o caminho
que a comunidade usa para os chips novos. A versão está fixada de propósito: apontar
para "a mais recente" trocaria o compilador por baixo do projeto sem ninguém pedir.

**`test_ignore = *`** faz `pio test` continuar rodando só no ambiente `native`. Sem essa
linha, ele tentaria rodar os testes na placa também.

### 2. O programa

Escreva `src/main.cpp`:

```cpp
#include <Arduino.h>

#include "Termometro.h"

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\nOla, ESP32-C6");
  pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
  static uint32_t contador = 0;
  ++contador;

  const double temperatura_falsa = 30.0 + (contador % 8) * 0.125;
  Serial.printf("%lu  %.3f C  ->  %ld centesimos\n", static_cast<unsigned long>(contador),
                temperatura_falsa, static_cast<long>(centesimosDeGrau(temperatura_falsa)));

  digitalWrite(LED_BUILTIN, contador % 2);
  delay(1000);
}
```

Repare que a **mesma biblioteca** que você testou no PC está sendo usada aqui, sem
mudança nenhuma. É exatamente assim que o `MelipoCore` funciona no projeto de verdade.

### 3. Gravar

```bash
pio run -e esp32c6 -t upload -t monitor
```

O `-t monitor` abre o monitor serial logo depois de gravar. Você deve ver:

```
Ola, ESP32-C6
1  30.125 C  ->  3013 centesimos
2  30.250 C  ->  3025 centesimos
3  30.375 C  ->  3038 centesimos
```

Para sair do monitor: `Ctrl+C`.

**O critério de sucesso é o texto aparecendo**, não o LED. O LED embutido da DevKitC-1
não é um LED comum: é um RGB endereçável (WS2812) no GPIO 8. O core 3.x esconde isso
atrás do `LED_BUILTIN`, e o `digitalWrite` acima funciona — mas se ele não acender,
confira primeiro se o texto está saindo, porque aí o problema é outro.

Se o `upload` falhar por permissão, faltam as regras de acesso à porta USB:

```bash
sudo pacman -S platformio-core-udev     # Arch
```

Outras distribuições: `docs.platformio.org/en/latest/core/installation/udev-rules.html`.

---

## Agora no projeto de verdade

```bash
git clone https://github.com/lacouth/meliponet.git
cd meliponet
pio test -e native -d firmware
```

São **61 testes**, e rodam em menos de cinco segundos. Nenhum deles precisa de hardware.

O `-d firmware` diz onde está o `platformio.ini` — é o que permite rodar de dentro da
raiz do repositório em vez de entrar na pasta.

Agora abra `firmware/lib/MelipoCore/Escala.cpp` e ache a função `escalar()`. É a sua
`centesimosDeGrau`, generalizada: em vez de fixar 100, ela recebe quantas casas decimais
a métrica usa — temperatura em centésimos, peso em gramas. E o comentário do arquivo
explica, com mais detalhe do que aqui, por que a regra é multiplicar em `double` e
arredondar o produto.

Se você tem placa, o passo seguinte é o firmware de verdade:

```bash
pio run -e esp32c6 -d firmware -t upload -t monitor
```

e, no monitor, o comando `ler` — que mostra os sensores com o valor físico e o inteiro
escalado lado a lado. Os detalhes estão em [O firmware](04-o-firmware.md).

Pode apagar o `~/pio-primeiro` quando quiser. Ele já cumpriu o papel.

---

## Erros comuns

| Sintoma | Causa |
|---|---|
| `pio: command not found` | `~/.local/bin` fora do `PATH` |
| `This board doesn't support arduino framework!` | `platform = espressif32` (o oficial) em vez da URL do `pioarduino` |
| `Permission denied: '/dev/ttyACM0'` | regras udev não instaladas |
| O monitor mostra caracteres embaralhados | `monitor_speed` diferente do `Serial.begin()` |
| `pio run -e native` reclama que não há o que compilar | no ambiente `native` o `src/` não é usado: rode `pio test -e native` |
| `error: 'Serial' was not declared` no ambiente `native` | código de Arduino num ambiente que não tem Arduino — é o erro que a separação `MelipoCore`/`MelipoHardware` existe para evitar |

## O que levar daqui

**A configuração é um arquivo, não uma preferência.** O `platformio.ini` vai no git, e
todo mundo compila com a mesma placa, as mesmas bibliotecas e as mesmas versões.

**Dois ambientes, e o do PC é onde o trabalho acontece.** Compilar para a placa é o passo
final, não o primeiro. Quase tudo que se erra em firmware — conversão, decisão, fila,
tempo — pode ser exercitado em segundos no computador.

**Teste que não falha não prova nada.** Você viu duas implementações diferentes passarem
no mesmo teste. É a razão de a regra do projeto ser escrever o teste antes da correção e
vê-lo falhar primeiro.

→ Próximo: [O firmware](04-o-firmware.md)
