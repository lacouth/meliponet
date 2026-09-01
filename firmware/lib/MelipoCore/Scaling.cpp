#include "Scaling.h"

#include <math.h>

namespace meliponet {
namespace {

constexpr double kPowersOfTen[] = {1.0, 10.0, 100.0, 1000.0};

// Faixa de int32_t como double, para checar o estouro antes da conversao. Comparar
// depois de converter seria tarde: a conversao de um double fora da faixa para
// int32_t e comportamento indefinido em C++.
constexpr double kMaxInt32 = 2147483647.0;
constexpr double kMinInt32 = -2147483648.0;

}  // namespace

Scaled scale(double reading, Scale scale) {
  if (!isfinite(reading)) {
    return {};
  }

  const double factor = kPowersOfTen[static_cast<int>(scale)];
  const double product = reading * factor;
  if (!isfinite(product) || product > kMaxInt32 || product < kMinInt32) {
    return {};
  }

  // llround arredonda ao mais proximo com empate para longe do zero, aplicado ao
  // produto -- que e precisamente a regra de contracts/canonical.py.
  return {static_cast<int32_t>(llround(product)), true};
}

Scaled scaleInRange(double reading, Scale unit, double minimum, double maximum) {
  if (!isfinite(reading) || reading < minimum || reading > maximum) {
    return {};
  }
  return scale(reading, unit);
}

}  // namespace meliponet
