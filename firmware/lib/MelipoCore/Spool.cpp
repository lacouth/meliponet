#include "Spool.h"

namespace meliponet {

bool Spool::guardar(const char *conteudo, size_t tamanho) {
  if (conteudo == nullptr || tamanho == 0) {
    return false;
  }

  if (cheio()) {
    // Descarta a mais antiga para abrir espaco. A perda fica visivel na `seq` do lado da
    // plataforma, e contada aqui em `descartadas_`.
    if (!armazenamento_.apagar(inicio_)) {
      return false;
    }
    inicio_ = static_cast<uint32_t>((inicio_ + 1) % kCapacidadeDoSpool);
    --quantidade_;
    ++descartadas_;
  }

  const uint32_t posicao = posicaoEm(quantidade_);
  if (!armazenamento_.escrever(posicao, conteudo, tamanho)) {
    return false;
  }
  ++quantidade_;
  return true;
}

size_t Spool::espiar(char *saida, size_t capacidade) {
  if (vazio() || saida == nullptr || capacidade == 0) {
    return 0;
  }
  return armazenamento_.ler(inicio_, saida, capacidade);
}

bool Spool::remover() {
  if (vazio()) {
    return false;
  }
  if (!armazenamento_.apagar(inicio_)) {
    return false;
  }
  inicio_ = static_cast<uint32_t>((inicio_ + 1) % kCapacidadeDoSpool);
  --quantidade_;
  return true;
}

void Spool::restaurar(uint32_t inicio, uint32_t quantidade) {
  inicio_ = inicio % kCapacidadeDoSpool;
  quantidade_ = quantidade > kCapacidadeDoSpool ? kCapacidadeDoSpool : quantidade;
}

}  // namespace meliponet
