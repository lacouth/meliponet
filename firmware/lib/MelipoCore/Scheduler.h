// Politica de tempo do ciclo de amostragem.
//
// Isolada num lugar so para que a migracao a deep sleep na Fase 5 seja localizada: o
// laco principal pergunta "ja e hora?" e nao sabe se a resposta vem de um contador de
// millis() ou de um despertar por timer RTC.
//
// O detalhe que justifica o teste: `millis()` volta a zero a cada ~49,7 dias. Um no em
// campo passa por isso, e a forma ingenua -- `if (now > next_)` -- trava a amostragem
// para sempre quando acontece. A subtracao sem sinal abaixo atravessa a volta
// corretamente.

#pragma once

#include <stdint.h>

namespace meliponet {

class Scheduler {
 public:
  // `interval_ms` e o periodo entre amostras. `start_ms` e o instante inicial.
  Scheduler(uint32_t interval_ms, uint32_t start_ms)
      : interval_ms_(interval_ms), last_ms_(start_ms) {}

  // Verdadeiro se ja passou um intervalo desde a ultima amostra.
  //
  // A comparacao e feita sobre a diferenca sem sinal, e nao sobre os instantes: assim
  // ela continua correta quando o contador da a volta.
  bool due(uint32_t now_ms) const { return (now_ms - last_ms_) >= interval_ms_; }

  // Registra que a amostra foi tomada em `now_ms`.
  void mark(uint32_t now_ms) { last_ms_ = now_ms; }

  // Quanto falta, em milissegundos. Zero quando ja venceu.
  uint32_t remaining(uint32_t now_ms) const {
    const uint32_t elapsed = now_ms - last_ms_;
    return elapsed >= interval_ms_ ? 0u : interval_ms_ - elapsed;
  }

  uint32_t interval() const { return interval_ms_; }
  void setInterval(uint32_t interval_ms) { interval_ms_ = interval_ms; }

 private:
  uint32_t interval_ms_;
  uint32_t last_ms_;
};

}  // namespace meliponet
