#include "Escala.h"

#include <math.h>

namespace meliponet {
namespace {

constexpr double kPotenciasDeDez[] = {1.0, 10.0, 100.0, 1000.0};
constexpr int kMaxCasas = 3;

// Faixa de int32_t como double, para checar o estouro antes da conversao. Comparar
// depois de converter seria tarde: a conversao de um double fora da faixa para int32_t e
// comportamento indefinido em C++.
constexpr double kMaiorInt32 = 2147483647.0;
constexpr double kMenorInt32 = -2147483648.0;

}  // namespace

Escalado escalar(double leitura, int casas) {
  // Sem esta guarda, um numero de casas fora do previsto leria fora do vetor acima.
  if (casas < 0 || casas > kMaxCasas) {
    return {};
  }
  if (!isfinite(leitura)) {
    return {};
  }

  const double produto = leitura * kPotenciasDeDez[casas];
  if (!isfinite(produto) || produto > kMaiorInt32 || produto < kMenorInt32) {
    return {};
  }

  // llround arredonda ao mais proximo com empate para longe do zero, aplicado ao produto
  // -- que e precisamente a regra de contracts/canonical.py.
  return {static_cast<int32_t>(llround(produto)), true};
}

Escalado escalarNaFaixa(double leitura, const Metrica &metrica) {
  if (!isfinite(leitura) || leitura < metrica.minimo || leitura > metrica.maximo) {
    return {};
  }
  return escalar(leitura, metrica.casas);
}

}  // namespace meliponet
