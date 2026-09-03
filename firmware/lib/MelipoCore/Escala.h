// Conversao de leitura fisica para o inteiro escalado do contrato.
//
// Esta e a unica passagem de ponto flutuante para inteiro no firmware inteiro, e ela
// precisa concordar com contracts/canonical.py: a regra e multiplicar em `double` e
// arredondar o produto com empate para longe do zero -- exatamente
// `llround(valor * 10^casas)`.
//
// Por que a ordem importa, e o que acontece quando as duas implementacoes discordam:
// docs/guia/04-o-firmware.md.

#pragma once

#include <stdint.h>

namespace meliponet {

// Resultado da conversao. Uma leitura invalida nao vira zero: ela vira `ok == false`, e
// quem chamou omite o campo e liga a flag correspondente. Zero significaria "o sensor
// leu zero", que e uma afirmacao diferente de "nao sabemos".
struct Escalado {
  int32_t valor = 0;
  bool ok = false;
};

// Tudo o que o firmware precisa saber sobre uma grandeza medida, num lugar so: quantas
// casas decimais ela tem no contrato e em que faixa uma leitura dela e plausivel.
struct Metrica {
  int casas;
  double minimo;
  double maximo;
};

// As faixas sao as do *sensor*, nao as da *colmeia*: -40 a 85 graus e o que um SHT30
// consegue medir. Julgar se 45 graus faz sentido para aquela colmeia naquele horario e
// trabalho da validacao semantica na plataforma, que tem o historico para isso. O
// firmware so recusa o que nenhum sensor sao poderia ter produzido.
constexpr Metrica kTemperatura{2, -40.0, 85.0};  // centesimos de grau Celsius
constexpr Metrica kUmidade{2, 0.0, 100.0};       // centesimos de ponto percentual
constexpr Metrica kPeso{3, -5.0, 100.0};         // gramas; celula de 50 kg com folga, e
                                                 // deriva de tara da peso levemente
                                                 // negativo
constexpr Metrica kTensao{2, 0.0, 6.0};          // centesimos de volt

// Converte `leitura` no inteiro escalado com `casas` casas decimais.
//
// Devolve `ok == false` para NaN, infinito e para valores que estourariam int32_t -- um
// sensor com defeito eletrico produz exatamente esse tipo de leitura, e ela nao pode
// virar um numero plausivel no banco.
//
// O parametro e `double` de proposito, mesmo que os sensores entreguem `float`: a
// promocao float->double e exata, e e em double que a regra canonica esta definida.
Escalado escalar(double leitura, int casas);

// Converte aplicando tambem a faixa de plausibilidade da grandeza. Fora da faixa,
// `ok == false`.
Escalado escalarNaFaixa(double leitura, const Metrica &metrica);

}  // namespace meliponet
