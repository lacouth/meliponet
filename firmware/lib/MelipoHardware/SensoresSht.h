// Os dois SHT30 da colmeia, no mesmo barramento I2C.
//
// O interno fica no endereco 0x44 e o externo no 0x45 -- o SHT30 tem o endereco
// selecionavel por um pino, o que permite os dois compartilharem o barramento sem
// multiplexador.
//
// A falha de um sensor nao pode derrubar o outro nem travar o ciclo. Operar com apenas
// um SHT30 e um caso valido e esperado: em campo, o sensor externo e o mais exposto a
// poeira, umidade e a propria atividade das abelhas, que depositam cerume e propolis.

#pragma once

#include "Amostra.h"

namespace meliponet {

constexpr uint8_t kEnderecoDoShtInterno = 0x44;
constexpr uint8_t kEnderecoDoShtExterno = 0x45;

// Leituras pareadas de temperatura e umidade.
struct LeiturasSht {
  Leitura temp_int;
  Leitura ur_int;
  Leitura temp_ext;
  Leitura ur_ext;
};

class SensoresSht {
 public:
  // Inicializa o barramento e detecta quais sensores respondem. Devolve verdadeiro se
  // **ao menos um** respondeu -- nenhum sensor presente e o unico caso em que nao ha o
  // que medir.
  bool iniciar(int pino_sda, int pino_scl);

  // Le os dois sensores. Cada leitura carrega o proprio `valida`, de modo que a falha de
  // um nao contamina o outro.
  LeiturasSht ler();

  bool internoPresente() const { return interno_presente_; }
  bool externoPresente() const { return externo_presente_; }

 private:
  bool interno_presente_ = false;
  bool externo_presente_ = false;
};

}  // namespace meliponet
