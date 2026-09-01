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

// Escalas do contrato, em casas decimais.
enum class Scale : int {
  Temperature = 2,  // centesimos de grau Celsius
  Humidity = 2,     // centesimos de ponto percentual
  Weight = 3,       // gramas
  Voltage = 2,      // centesimos de volt
  Sound = 1,        // decimos de unidade
};

// Resultado da conversao. Uma leitura invalida nao vira zero: ela vira `ok == false`,
// e quem chamou omite o campo e liga a flag correspondente. Zero significaria "o
// sensor leu zero", que e uma afirmacao diferente de "nao sabemos".
struct Scaled {
  int32_t value = 0;
  bool ok = false;
};

// Converte `reading` no inteiro escalado de `scale`.
//
// Devolve `ok == false` para NaN, infinito e para valores que estourariam int32_t --
// um sensor com defeito eletrico produz exatamente esse tipo de leitura, e ela nao
// pode virar um numero plausivel no banco.
//
// O parametro e `double` de proposito, mesmo que os sensores entreguem `float`: a
// promocao float->double e exata, e e em double que a regra canonica esta definida.
Scaled scale(double reading, Scale scale);

// Converte com limites de plausibilidade fisica. Fora da faixa, `ok == false`.
//
// A faixa aqui e a do *sensor*, nao a da *colmeia*: -40 a 85 graus e o que um SHT30
// consegue medir. Julgar se 45 graus faz sentido para aquela colmeia naquele horario
// e trabalho da validacao semantica na plataforma, que tem o historico para isso. O
// firmware so recusa o que nenhum sensor sao poderia ter produzido.
Scaled scaleInRange(double reading, Scale scale, double minimum, double maximum);

}  // namespace meliponet
