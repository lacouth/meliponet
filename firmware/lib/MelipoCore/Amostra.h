// Montagem da telemetria a partir das leituras dos sensores.
//
// Esta e a peca que decide **o que entra na mensagem e o que e omitido**, e por isso ela
// e logica pura, sem nenhuma dependencia de hardware: e a decisao mais facil de errar do
// firmware, e a que so apareceria semanas depois, como uma serie estranha no banco.
//
// A regra que a governa: sensor com falha **omite o campo e liga a flag**. Nunca envia
// zero. Zero significa "a colmeia estava a 0 grau" -- uma afirmacao falsa sobre o mundo.
// Ausente significa "nao sabemos", que e verdade. A plataforma conta com essa distincao
// para calcular os indicadores de completude.

#pragma once

#include <stdint.h>

#include "Escala.h"
#include "Telemetria.h"

namespace meliponet {

// As casas decimais e a faixa plausivel de cada grandeza estao em Escala.h, nas
// constantes `kTemperatura`, `kUmidade`, `kPeso` e `kTensao`.

// Tensao abaixo da qual a flag `low_batt` acende. O 18650 entrega pouco abaixo disso.
constexpr double kTensaoDeBateriaBaixaV = 3.50;

// Uma leitura de sensor: o valor e se ele foi obtido. `valida == false` distingue
// "sensor nao respondeu" de "sensor leu zero".
struct Leitura {
  double valor = 0.0;
  bool valida = false;

  static Leitura obtida(double v) { return {v, true}; }
  static Leitura falha() { return {}; }
};

// O que os sensores produziram num ciclo de amostragem.
struct LeiturasDosSensores {
  Leitura temp_int;
  Leitura ur_int;
  Leitura temp_ext;
  Leitura ur_ext;
  Leitura peso;
  Leitura bateria;
  int32_t rssi = 0;
  bool rssi_valido = false;
};

// Identidade e estado do no no momento da amostragem. `node_id`, `seq` e `ts` sao os
// campos obrigatorios do contrato, e por isso mantem a grafia dele.
struct ContextoDaAmostra {
  const char *node_id = "";
  uint32_t seq = 0;
  const char *ts = "";
  // Falso quando o NTP nao respondeu e o horario e estimado. Vira a flag
  // `clock_unsynced`, para que a plataforma saiba que aquele `ts` nao e confiavel.
  bool relogio_sincronizado = true;
  // Verdadeiro quando a mensagem esta sendo reenviada do spool apos uma queda de rede.
  bool veio_do_spool = false;
};

// Monta a telemetria. Campos cujo sensor falhou ficam ausentes, e as flags explicam.
Telemetria montarTelemetria(const ContextoDaAmostra &contexto,
                            const LeiturasDosSensores &sensores);

}  // namespace meliponet
