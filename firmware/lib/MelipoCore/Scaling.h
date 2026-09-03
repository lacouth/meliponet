// Conversao de leitura fisica para o inteiro escalado do contrato.
//
// Esta e a unica passagem de ponto flutuante para inteiro no firmware, e ela precisa
// concordar com contracts/canonical.py -- caso contrario o simulador e o firmware
// produziriam inteiros diferentes para a mesma leitura, e a divergencia apareceria
// so em algumas leituras especificas.
//
// A regra canonica e: multiplique em double, depois arredonde o produto com empate
// para longe do zero. Ou seja, exatamente `llround(value * 10^places)`. A ordem
// importa: arredondar o valor original com aritmetica decimal exata daria outro
// resultado em ~23% dos valores da forma x.xx5, e nao seria reproduzivel aqui.

#pragma once

#include <stdint.h>

namespace meliponet {

// Resultado da conversao. Uma leitura invalida nao vira zero: ela vira `ok == false`,
// e quem chamou omite o campo e liga a flag correspondente. Zero significaria "o
// sensor leu zero", que e uma afirmacao diferente de "nao sabemos".
struct Scaled {
  int32_t value = 0;
  bool ok = false;
};

// Tudo o que o firmware precisa saber sobre uma grandeza medida, num lugar so: quantas
// casas decimais ela tem no contrato e em que faixa uma leitura dela e plausivel.
//
// Antes essas tres informacoes viviam separadas (um `enum class Scale`, uma constante de
// minimo e uma de maximo), e as tres precisavam ser repetidas juntas em cada chamada --
// doze vezes, entre a montagem da mensagem e a leitura de bancada. Repetir e a forma
// mais facil de trocar a faixa de uma grandeza pela de outra sem que nada acuse.
struct Metric {
  int decimals;
  double minimum;
  double maximum;
};

// As faixas sao as do *sensor*, nao as da *colmeia*: -40 a 85 graus e o que um SHT30
// consegue medir. Julgar se 45 graus faz sentido para aquela colmeia naquele horario e
// trabalho da validacao semantica na plataforma, que tem o historico para isso. O
// firmware so recusa o que nenhum sensor sao poderia ter produzido.
constexpr Metric kTemperature{2, -40.0, 85.0};   // centesimos de grau Celsius
constexpr Metric kHumidity{2, 0.0, 100.0};       // centesimos de ponto percentual
constexpr Metric kWeight{3, -5.0, 100.0};        // gramas; celula de 50 kg, com folga,
                                                 // e deriva de tara da peso levemente
                                                 // negativo
constexpr Metric kVoltage{2, 0.0, 6.0};          // centesimos de volt

// Converte `reading` no inteiro escalado com `decimals` casas decimais.
//
// Devolve `ok == false` para NaN, infinito e para valores que estourariam int32_t --
// um sensor com defeito eletrico produz exatamente esse tipo de leitura, e ela nao
// pode virar um numero plausivel no banco.
//
// O parametro e `double` de proposito, mesmo que os sensores entreguem `float`: a
// promocao float->double e exata, e e em double que a regra canonica esta definida.
Scaled scale(double reading, int decimals);

// Converte aplicando tambem a faixa de plausibilidade da grandeza. Fora da faixa,
// `ok == false`.
Scaled scaleInRange(double reading, const Metric &metric);

}  // namespace meliponet
