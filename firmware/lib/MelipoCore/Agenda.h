// Politica de tempo do ciclo de amostragem.
//
// Isolada num lugar so para que a migracao a deep sleep na Fase 5 seja localizada: o
// laco principal pergunta "ja e hora?" e nao sabe se a resposta vem de um contador de
// `millis()` ou de um despertar por timer RTC.
//
// Toda decisao e tomada sobre a diferenca `agora - ultima`, aritmetica sem sinal, e
// nunca comparando instantes: assim ela continua correta quando `millis()` da a volta,
// aos ~49,7 dias. Um no em campo passa por isso. Ver docs/guia/04-o-firmware.md.

#pragma once

#include <stdint.h>

namespace meliponet {

class Agenda {
 public:
  // Nasce parada, e comeca a contar em `iniciar`. Poder ser construida sem argumentos e
  // o que permite que ela seja uma variavel global comum no `main.cpp`: o intervalo vem
  // da NVS e o instante inicial vem de `millis()`, e nenhum dos dois existe ainda quando
  // as globais sao construidas, antes do `setup()`.
  Agenda() = default;

  // `intervalo_ms` e o periodo entre amostras. `agora_ms` e o instante em que a contagem
  // comeca.
  void iniciar(uint32_t intervalo_ms, uint32_t agora_ms) {
    intervalo_ms_ = intervalo_ms;
    ultima_ms_ = agora_ms;
  }

  // Verdadeiro se ja passou um intervalo desde a ultima amostra.
  bool venceu(uint32_t agora_ms) const { return (agora_ms - ultima_ms_) >= intervalo_ms_; }

  // Registra que a amostra foi tomada em `agora_ms`.
  void marcar(uint32_t agora_ms) { ultima_ms_ = agora_ms; }

  // Quanto falta, em milissegundos. Zero quando ja venceu.
  uint32_t falta(uint32_t agora_ms) const {
    const uint32_t decorrido = agora_ms - ultima_ms_;
    return decorrido >= intervalo_ms_ ? 0u : intervalo_ms_ - decorrido;
  }

  uint32_t intervalo() const { return intervalo_ms_; }
  void definirIntervalo(uint32_t intervalo_ms) { intervalo_ms_ = intervalo_ms; }

 private:
  uint32_t intervalo_ms_ = 0;
  uint32_t ultima_ms_ = 0;
};

}  // namespace meliponet
