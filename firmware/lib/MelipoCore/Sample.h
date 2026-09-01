// Montagem da telemetria a partir das leituras dos sensores.
//
// Esta e a peca que decide **o que entra na mensagem e o que e omitido**, e por isso
// ela e logica pura, sem nenhuma dependencia de hardware: e a decisao mais facil de
// errar do firmware, e a que so apareceria semanas depois, como uma serie estranha no
// banco.
//
// A regra que a governa: sensor com falha **omite o campo e liga a flag**. Nunca envia
// zero. Zero significa "a colmeia estava a 0 grau" -- uma afirmacao falsa sobre o
// mundo. Ausente significa "nao sabemos", que e verdade. A plataforma conta com essa
// distincao para calcular os indicadores de completude.

#pragma once

#include <stdint.h>

#include "Scaling.h"
#include "TelemetryCodec.h"

namespace meliponet {

// Faixas fisicas dos sensores usados. Nao sao faixas biologicas: o que e plausivel
// para *aquela colmeia naquele horario* e julgado pela validacao semantica da
// plataforma, que tem o historico. O firmware so recusa o que nenhum sensor sao
// poderia ter produzido.
constexpr double kSht30MinTempC = -40.0;
constexpr double kSht30MaxTempC = 85.0;
constexpr double kSht30MinRhPct = 0.0;
constexpr double kSht30MaxRhPct = 100.0;
constexpr double kMinWeightKg = -5.0;   // deriva de tara produz peso levemente negativo
constexpr double kMaxWeightKg = 100.0;  // celula de 50 kg, com folga
constexpr double kMinVoltageV = 0.0;
constexpr double kMaxVoltageV = 6.0;

// Tensao abaixo da qual a flag `low_batt` acende. O 18650 entrega pouco abaixo disso.
constexpr double kLowBatteryV = 3.50;

// Uma leitura de sensor: o valor e se ele foi obtido. `valid == false` distingue
// "sensor nao respondeu" de "sensor leu zero".
struct Reading {
  double value = 0.0;
  bool valid = false;

  static Reading ok(double v) { return {v, true}; }
  static Reading fault() { return {}; }
};

// O que os sensores produziram num ciclo de amostragem.
struct SensorSnapshot {
  Reading temp_in;
  Reading rh_in;
  Reading temp_out;
  Reading rh_out;
  Reading weight;
  Reading battery;
  int32_t rssi = 0;
  bool rssi_valid = false;
};

// Identidade e estado do no no momento da amostragem.
struct SampleContext {
  const char *node_id = "";
  uint32_t seq = 0;
  const char *timestamp = "";
  // Falso quando o NTP nao respondeu e o horario e estimado. Vira a flag
  // `clock_unsynced`, para que a plataforma saiba que aquele `ts` nao e confiavel.
  bool clock_synced = true;
  // Verdadeiro quando a mensagem esta sendo reenviada do spool apos uma queda de rede.
  bool from_spool = false;
};

// Monta a telemetria. Campos cujo sensor falhou ficam ausentes, e as flags explicam.
Telemetry buildTelemetry(const SampleContext &context, const SensorSnapshot &sensors);

}  // namespace meliponet
