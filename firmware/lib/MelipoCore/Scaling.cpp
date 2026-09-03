#include "Scaling.h"

#include <math.h>

namespace meliponet {
namespace {

constexpr double kPowersOfTen[] = {1.0, 10.0, 100.0, 1000.0};
constexpr int kMaxDecimals = 3;

// Faixa de int32_t como double, para checar o estouro antes da conversao. Comparar
// depois de converter seria tarde: a conversao de um double fora da faixa para
// int32_t e comportamento indefinido em C++.
constexpr double kMaxInt32 = 2147483647.0;
constexpr double kMinInt32 = -2147483648.0;

}  // namespace

Scaled scale(double reading, int decimals) {
  // Sem esta guarda, um numero de casas fora do previsto leria fora do vetor acima.
  if (decimals < 0 || decimals > kMaxDecimals) {
    return {};
  }
  if (!isfinite(reading)) {
    return {};
  }

  const double factor = kPowersOfTen[decimals];
  const double product = reading * factor;
  if (!isfinite(product) || product > kMaxInt32 || product < kMinInt32) {
    return {};
  }

  // llround arredonda ao mais proximo com empate para longe do zero, aplicado ao
  // produto -- que e precisamente a regra de contracts/canonical.py.
  return {static_cast<int32_t>(llround(product)), true};
}

Scaled scaleInRange(double reading, const Metric &metric) {
  if (!isfinite(reading) || reading < metric.minimum || reading > metric.maximum) {
    return {};
  }
  return scale(reading, metric.decimals);
}

}  // namespace meliponet
