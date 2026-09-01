#include "ShtPair.h"

#include <SHT31.h>
#include <Wire.h>

namespace meliponet {
namespace {

SHT31 g_inside(kShtAddressInside);
SHT31 g_outside(kShtAddressOutside);

// Le um sensor, devolvendo leituras invalidas se ele nao responder. O SHT31 devolve
// NaN quando a leitura falha, e NaN precisa virar `Reading::fault()` aqui em vez de
// escorregar para a serializacao.
void readOne(SHT31 &sensor, bool present, Reading &temperature, Reading &humidity) {
  if (!present || !sensor.read()) {
    temperature = Reading::fault();
    humidity = Reading::fault();
    return;
  }

  const float t = sensor.getTemperature();
  const float h = sensor.getHumidity();
  temperature = isnan(t) ? Reading::fault() : Reading::ok(t);
  humidity = isnan(h) ? Reading::fault() : Reading::ok(h);
}

}  // namespace

bool ShtPair::begin(int sda_pin, int scl_pin) {
  Wire.begin(sda_pin, scl_pin);

  inside_present_ = g_inside.begin() && g_inside.isConnected();
  outside_present_ = g_outside.begin() && g_outside.isConnected();

  return inside_present_ || outside_present_;
}

ShtReadings ShtPair::read() {
  ShtReadings readings;
  readOne(g_inside, inside_present_, readings.temp_in, readings.rh_in);
  readOne(g_outside, outside_present_, readings.temp_out, readings.rh_out);
  return readings;
}

}  // namespace meliponet
