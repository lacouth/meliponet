// Armazenamento do spool em LittleFS.
//
// A implementacao real da interface `ArmazenamentoDoSpool`. A logica de fila fica em
// `Spool` e a reconstrucao apos reinicio em `SpoolRecuperacao`, ambas testadas no PC;
// aqui so mora o acesso ao sistema de arquivos.

#pragma once

#include "Spool.h"

namespace meliponet {

class SpoolEmLittleFS : public ArmazenamentoDoSpool {
 public:
  // Monta o sistema de arquivos e formata se preciso. Devolve o estado da fila
  // encontrado, para que `Spool::restaurar` possa reconstrui-la apos um reinicio.
  bool iniciar(uint32_t &inicio, uint32_t &quantidade);

  bool escrever(uint32_t posicao, const char *conteudo, size_t tamanho) override;
  size_t ler(uint32_t posicao, char *saida, size_t capacidade) override;
  bool apagar(uint32_t posicao) override;

 private:
  bool montado_ = false;
};

}  // namespace meliponet
