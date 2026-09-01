// Armazenamento do spool em LittleFS.
//
// A implementacao real da interface `SpoolStorage`. A logica de fila fica em `Spool`,
// testada no PC com um armazenamento em memoria; aqui so mora o acesso ao sistema de
// arquivos.

#pragma once

#include "Spool.h"

namespace meliponet {

class LittleFsSpoolStorage : public SpoolStorage {
 public:
  // Monta o sistema de arquivos e formata se preciso. Devolve o estado da fila
  // encontrado, para que `Spool::restore` possa reconstrui-la apos um reinicio.
  bool begin(uint32_t &head, uint32_t &count);

  bool write(uint32_t slot, const char *payload, size_t length) override;
  size_t read(uint32_t slot, char *out, size_t capacity) override;
  bool erase(uint32_t slot) override;

 private:
  bool mounted_ = false;
};

}  // namespace meliponet
