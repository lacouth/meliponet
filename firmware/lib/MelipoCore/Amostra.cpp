#include "Amostra.h"

namespace meliponet {
namespace {

// Aplica a escala e, se der certo, marca o campo como presente. Se nao der, o campo
// simplesmente nao entra na mensagem -- e quem chamou liga a flag.
bool atribuir(int32_t &destino, uint32_t &presentes, uint32_t campo, const Leitura &leitura,
              const Metrica &metrica) {
  if (!leitura.valida) {
    return false;
  }
  const Escalado escalado = escalarNaFaixa(leitura.valor, metrica);
  if (!escalado.ok) {
    return false;
  }
  destino = escalado.valor;
  presentes |= campo;
  return true;
}

}  // namespace

Telemetria montarTelemetria(const ContextoDaAmostra &contexto,
                            const LeiturasDosSensores &sensores) {
  Telemetria t;
  t.node_id = contexto.node_id;
  t.seq = contexto.seq;
  t.ts = contexto.ts;

  // Cada linha liga uma leitura de sensor ao campo do contrato que ela alimenta.
  const bool temp_int_ok =
      atribuir(t.temp_in_c, t.presentes, Campo::temp_in_c, sensores.temp_int, kTemperatura);
  const bool ur_int_ok =
      atribuir(t.rh_in_pct, t.presentes, Campo::rh_in_pct, sensores.ur_int, kUmidade);
  const bool temp_ext_ok =
      atribuir(t.temp_out_c, t.presentes, Campo::temp_out_c, sensores.temp_ext, kTemperatura);
  const bool ur_ext_ok =
      atribuir(t.rh_out_pct, t.presentes, Campo::rh_out_pct, sensores.ur_ext, kUmidade);
  const bool peso_ok =
      atribuir(t.weight_kg, t.presentes, Campo::weight_kg, sensores.peso, kPeso);
  const bool bateria_ok =
      atribuir(t.vbat_v, t.presentes, Campo::vbat_v, sensores.bateria, kTensao);

  // Um SHT30 mede temperatura e umidade no mesmo chip: se um dos dois nao veio, o sensor
  // esta com problema, e uma flag so descreve os dois campos.
  if (!temp_int_ok || !ur_int_ok) {
    t.flags |= Flag::sht_in_fault;
  }
  if (!temp_ext_ok || !ur_ext_ok) {
    t.flags |= Flag::sht_out_fault;
  }
  if (!peso_ok) {
    t.flags |= Flag::hx711_fault;
  }
  if (bateria_ok && sensores.bateria.valor < kTensaoDeBateriaBaixaV) {
    t.flags |= Flag::low_batt;
  }

  if (sensores.rssi_valido) {
    t.rssi = sensores.rssi;
    t.presentes |= Campo::rssi;
  }

  if (!contexto.relogio_sincronizado) {
    t.flags |= Flag::clock_unsynced;
  }
  if (contexto.veio_do_spool) {
    t.flags |= Flag::spooled;
  }

  return t;
}

}  // namespace meliponet
