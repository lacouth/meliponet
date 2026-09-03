// Politica de nova tentativa com recuo exponencial.
//
// Duas regras, e as duas existem porque a versao anterior desta logica errava nelas e
// deixava o no mudo em campo por dias (a historia esta em docs/guia/04-o-firmware.md):
//
// 1. A decisao e sempre tomada sobre `agora - ultima`, aritmetica sem sinal, e nunca
//    comparando instantes -- assim ela atravessa a volta de `millis()`.
// 2. `registrarTentativa` precisa ser chamada em **toda** tentativa, inclusive nas que
//    falham.

#pragma once

#include <stdint.h>

namespace meliponet {

class Recuo {
 public:
  // `minimo_ms` e o intervalo da primeira tentativa; `maximo_ms` e o teto. O teto
  // importa: sem ele, uma queda longa levaria o intervalo a horas, e o no demoraria
  // demais a voltar quando o sinal retornasse.
  constexpr Recuo(uint32_t minimo_ms, uint32_t maximo_ms)
      : minimo_ms_(minimo_ms), maximo_ms_(maximo_ms), intervalo_ms_(minimo_ms) {}

  // Verdadeiro se ja e hora de tentar de novo.
  //
  // A primeira chamada sempre libera: um no recem-ligado nao deve esperar um intervalo
  // antes da primeira tentativa de conexao.
  bool podeTentar(uint32_t agora_ms) const {
    return !tentou_ || (agora_ms - ultima_tentativa_ms_) >= intervalo_ms_;
  }

  // Registra que uma tentativa foi feita e dobra o intervalo ate o teto.
  void registrarTentativa(uint32_t agora_ms) {
    ultima_tentativa_ms_ = agora_ms;
    tentou_ = true;
    const uint32_t dobrado = intervalo_ms_ * 2;
    intervalo_ms_ = (dobrado > maximo_ms_ || dobrado < intervalo_ms_) ? maximo_ms_ : dobrado;
  }

  // Registra sucesso: o intervalo volta ao minimo, para que a proxima queda seja
  // atendida rapido.
  void registrarSucesso() {
    intervalo_ms_ = minimo_ms_;
    tentou_ = false;
  }

  uint32_t intervalo() const { return intervalo_ms_; }

 private:
  uint32_t minimo_ms_;
  uint32_t maximo_ms_;
  uint32_t intervalo_ms_;
  uint32_t ultima_tentativa_ms_ = 0;
  bool tentou_ = false;
};

}  // namespace meliponet
