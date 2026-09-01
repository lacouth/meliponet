#include "Calibration.h"

#include <math.h>

namespace meliponet {

Weight toKilograms(int32_t raw, const LoadCellCalibration &calibration) {
  if (!calibration.valid()) {
    return {};
  }
  // A subtracao e feita em 64 bits: `raw` e `offset` sao ambos int32_t e a diferenca
  // entre extremos da faixa estouraria um int32_t.
  const double counts = static_cast<double>(static_cast<int64_t>(raw) - calibration.offset);
  const double kilograms = counts / calibration.counts_per_kg;
  if (!isfinite(kilograms)) {
    return {};
  }
  return {kilograms, true};
}

LoadCellCalibration calibrate(int32_t empty_raw, int32_t loaded_raw, double known_kg) {
  if (known_kg <= 0.0 || !isfinite(known_kg) || empty_raw == loaded_raw) {
    return {};
  }

  const double span = static_cast<double>(static_cast<int64_t>(loaded_raw) - empty_raw);
  const double counts_per_kg = span / known_kg;
  if (!isfinite(counts_per_kg) || counts_per_kg <= 0.0) {
    // Contagem menor com massa aplicada significa celula invertida ou mal ligada.
    // Aceitar isso produziria pesos negativos crescentes durante toda a coleta.
    return {};
  }

  return {empty_raw, counts_per_kg};
}

}  // namespace meliponet
