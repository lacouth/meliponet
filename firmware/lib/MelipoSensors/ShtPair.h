// Os dois SHT30 da colmeia, no mesmo barramento I²C.
//
// O interno fica no endereco 0x44 e o externo no 0x45 -- o SHT30 tem o endereco
// selecionavel por um pino, o que permite os dois compartilharem o barramento sem
// multiplexador.
//
// A falha de um sensor nao pode derrubar o outro nem travar o ciclo. Operar com apenas
// um SHT30 e um caso valido e esperado: em campo, o sensor externo e o mais exposto a
// poeira, umidade e a propria atividade das abelhas, que depositam cerume e propolis.

#pragma once

#include "Sample.h"

namespace meliponet {

constexpr uint8_t kShtAddressInside = 0x44;
constexpr uint8_t kShtAddressOutside = 0x45;

// Leituras pareadas de temperatura e umidade.
struct ShtReadings {
  Reading temp_in;
  Reading rh_in;
  Reading temp_out;
  Reading rh_out;
};

class ShtPair {
 public:
  // Inicializa o barramento e detecta quais sensores respondem. Devolve verdadeiro se
  // **ao menos um** respondeu -- nenhum sensor presente e o unico caso em que nao ha o
  // que medir.
  bool begin(int sda_pin, int scl_pin);

  // Le os dois sensores. Cada leitura carrega o proprio `valid`, de modo que a falha
  // de um nao contamina o outro.
  ShtReadings read();

  bool insidePresent() const { return inside_present_; }
  bool outsidePresent() const { return outside_present_; }

 private:
  bool inside_present_ = false;
  bool outside_present_ = false;
};

}  // namespace meliponet
