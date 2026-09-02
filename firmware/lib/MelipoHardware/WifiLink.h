// Conexao WiFi e sincronizacao de relogio.
//
// Com WiFi, o horario vem do NTP e o problema de deriva de relogio nem existe -- ele so
// aparece na Fase 5, quando o transporte for LoRa e nao houver internet no no. Aqui, se
// o NTP nao responder, o no continua medindo e marca a flag `clock_unsynced`, para que a
// plataforma saiba que aquele `ts` nao e confiavel.
//
// A reconexao usa recuo exponencial: um no que tenta reconectar sem pausa em um
// meliponario sem sinal gasta bateria a toa e nao consegue mais rapido por isso.

#pragma once

#include <stdint.h>

#include "Backoff.h"

namespace meliponet {

class WifiLink {
 public:
  bool begin(const char *ssid, const char *password);

  bool connected() const;

  // Tenta reconectar respeitando o recuo. Chame no laco principal; ela retorna
  // imediatamente se ainda nao e hora de tentar de novo.
  void maintain(uint32_t now_ms);

  // Sincroniza o relogio por NTP. Devolve falso se nao houve resposta no tempo limite.
  bool syncClock();

  bool clockSynced() const { return clock_synced_; }

  // Instante atual em UTC no formato do contrato (RFC 3339 com sufixo Z).
  // Devolve nullptr se o relogio nunca foi sincronizado.
  const char *timestamp();

  // RSSI da associacao atual, em dBm.
  bool rssi(int32_t &out) const;

 private:
  const char *ssid_ = nullptr;
  const char *password_ = nullptr;
  bool clock_synced_ = false;
  // 1 s a 5 min. O teto importa: sem ele, uma queda longa levaria o intervalo a horas e
  // o no demoraria demais a voltar quando o sinal retornasse.
  Backoff backoff_{1000, 300000};
  char timestamp_[24] = {0};
};

}  // namespace meliponet
