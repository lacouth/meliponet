#include "LoadCell.h"

#include <HX711.h>

namespace meliponet {
namespace {

HX711 g_scale;

}  // namespace

bool LoadCell::begin(int data_pin, int clock_pin, const LoadCellCalibration &calibration) {
  g_scale.begin(data_pin, clock_pin);
  calibration_ = calibration;

  // `is_ready()` so responde se o HX711 estiver alimentado e conectado. Sem esta
  // checagem, um cabo solto produziria leituras de zero indistinguiveis de uma colmeia
  // vazia.
  present_ = g_scale.wait_ready_timeout(1000);
  return present_;
}

bool LoadCell::readRaw(int32_t &out) {
  if (!present_ || !g_scale.wait_ready_timeout(1000)) {
    return false;
  }
  out = static_cast<int32_t>(g_scale.read_average(kLoadCellSamples));
  return true;
}

Reading LoadCell::read() {
  int32_t raw = 0;
  if (!readRaw(raw)) {
    return Reading::fault();
  }

  const Weight weight = toKilograms(raw, calibration_);
  return weight.ok ? Reading::ok(weight.kilograms) : Reading::fault();
}

}  // namespace meliponet
