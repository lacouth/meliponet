// Politica de nova tentativa com recuo exponencial.
//
// Existe porque a versao anterior desta logica, escrita solta dentro de WifiLink e
// duplicada em MqttPublisher, tinha dois defeitos que so apareceriam em campo depois de
// horas ou de semanas ligadas -- e nenhum teste os alcancava, porque estavam num
// arquivo que nao compila no PC.
//
// O primeiro era uma guarda invertida: quanto mais tempo passava desde a ultima
// tentativa, mais ela **recusava** tentar de novo. Como retornava sem atualizar o
// instante da proxima tentativa, a diferenca so crescia, e uma queda de rede mais de
// cinco minutos depois da reconexao anterior era definitiva ate alguem reiniciar a
// placa.
//
// O segundo era a comparacao `now < next`, feita sobre os instantes em vez da
// diferenca. Ela para de valer quando `millis()` da a volta, aos ~49,7 dias: com
// `next` alto de antes da volta e `now` baixo depois dela, a guarda bloqueia todas as
// tentativas por outros 49,7 dias.
//
// Aqui a decisao e sempre tomada sobre `now - last`, aritmetica sem sinal que atravessa
// a volta corretamente -- a mesma regra que o Scheduler ja usava para a amostragem.

#pragma once

#include <stdint.h>

namespace meliponet {

class Backoff {
 public:
  // `minimum_ms` e o intervalo da primeira tentativa; `maximum_ms` e o teto. O teto
  // importa: sem ele, uma queda longa levaria o intervalo a horas, e o no demoraria
  // demais a voltar quando o sinal retornasse.
  constexpr Backoff(uint32_t minimum_ms, uint32_t maximum_ms)
      : minimum_ms_(minimum_ms), maximum_ms_(maximum_ms), interval_ms_(minimum_ms) {}

  // Verdadeiro se ja e hora de tentar de novo.
  //
  // A primeira chamada sempre libera: um no recem-ligado nao deve esperar um intervalo
  // antes da primeira tentativa de conexao.
  bool ready(uint32_t now_ms) const {
    return !attempted_ || (now_ms - last_attempt_ms_) >= interval_ms_;
  }

  // Registra que uma tentativa foi feita e dobra o intervalo ate o teto.
  //
  // Precisa ser chamada em **toda** tentativa, inclusive nas que falham -- e nao
  // chama-la foi o que travou a versao anterior.
  void recordAttempt(uint32_t now_ms) {
    last_attempt_ms_ = now_ms;
    attempted_ = true;
    const uint32_t doubled = interval_ms_ * 2;
    interval_ms_ = (doubled > maximum_ms_ || doubled < interval_ms_) ? maximum_ms_ : doubled;
  }

  // Registra sucesso: o intervalo volta ao minimo, para que a proxima queda seja
  // atendida rapido.
  void recordSuccess() {
    interval_ms_ = minimum_ms_;
    attempted_ = false;
  }

  uint32_t interval() const { return interval_ms_; }

 private:
  uint32_t minimum_ms_;
  uint32_t maximum_ms_;
  uint32_t interval_ms_;
  uint32_t last_attempt_ms_ = 0;
  bool attempted_ = false;
};

}  // namespace meliponet
