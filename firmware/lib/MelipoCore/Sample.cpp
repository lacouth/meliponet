#include "Sample.h"

namespace meliponet {
namespace {

// Aplica a escala e, se der certo, marca o campo como presente. Se nao der, o campo
// simplesmente nao entra na mensagem -- e o chamador liga a flag.
bool assign(int32_t &destination, uint32_t &present, uint32_t field,
            const Reading &reading, const Metric &metric) {
  if (!reading.valid) {
    return false;
  }
  const Scaled scaled = scaleInRange(reading.value, metric);
  if (!scaled.ok) {
    return false;
  }
  destination = scaled.value;
  present |= field;
  return true;
}

}  // namespace

Telemetry buildTelemetry(const SampleContext &context, const SensorSnapshot &sensors) {
  Telemetry telemetry;
  telemetry.node_id = context.node_id;
  telemetry.seq = context.seq;
  telemetry.ts = context.timestamp;

  const bool temp_in_ok = assign(telemetry.temp_in_c, telemetry.present, Field::temp_in_c,
                                 sensors.temp_in, kTemperature);
  const bool rh_in_ok = assign(telemetry.rh_in_pct, telemetry.present, Field::rh_in_pct,
                               sensors.rh_in, kHumidity);
  const bool temp_out_ok = assign(telemetry.temp_out_c, telemetry.present, Field::temp_out_c,
                                  sensors.temp_out, kTemperature);
  const bool rh_out_ok = assign(telemetry.rh_out_pct, telemetry.present, Field::rh_out_pct,
                                sensors.rh_out, kHumidity);
  const bool weight_ok = assign(telemetry.weight_kg, telemetry.present, Field::weight_kg,
                                sensors.weight, kWeight);
  const bool battery_ok = assign(telemetry.vbat_v, telemetry.present, Field::vbat_v,
                                 sensors.battery, kVoltage);

  // Um SHT30 mede temperatura e umidade no mesmo chip: se um dos dois nao veio, o
  // sensor esta com problema, e uma flag so descreve os dois campos.
  if (!temp_in_ok || !rh_in_ok) {
    telemetry.flags |= Flag::sht_in_fault;
  }
  if (!temp_out_ok || !rh_out_ok) {
    telemetry.flags |= Flag::sht_out_fault;
  }
  if (!weight_ok) {
    telemetry.flags |= Flag::hx711_fault;
  }
  if (battery_ok && sensors.battery.value < kLowBatteryV) {
    telemetry.flags |= Flag::low_batt;
  }

  if (sensors.rssi_valid) {
    telemetry.rssi = sensors.rssi;
    telemetry.present |= Field::rssi;
  }

  if (!context.clock_synced) {
    telemetry.flags |= Flag::clock_unsynced;
  }
  if (context.from_spool) {
    telemetry.flags |= Flag::spooled;
  }

  return telemetry;
}

}  // namespace meliponet
