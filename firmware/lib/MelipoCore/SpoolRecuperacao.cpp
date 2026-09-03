#include "SpoolRecuperacao.h"

namespace meliponet {

EstadoDaFila deduzirEstadoDaFila(const bool *ocupados, uint32_t capacidade) {
  if (ocupados == nullptr || capacidade == 0) {
    return {};
  }

  uint32_t total = 0;
  for (uint32_t posicao = 0; posicao < capacidade; ++posicao) {
    if (ocupados[posicao]) {
      ++total;
    }
  }
  if (total == 0) {
    return {};
  }
  if (total == capacidade) {
    // Anel cheio: nao ha lacuna que revele onde a fila comeca.
    return {0, capacidade, 0};
  }

  // Procura o maior trecho contiguo, percorrendo o anel a partir de uma posicao vazia --
  // assim nenhum trecho e cortado ao meio pelo inicio da varredura.
  uint32_t partida = 0;
  while (ocupados[partida]) {
    ++partida;
  }

  uint32_t melhor_inicio = 0;
  uint32_t melhor_quantidade = 0;
  uint32_t trecho_inicio = 0;
  uint32_t trecho_quantidade = 0;

  for (uint32_t passo = 0; passo < capacidade; ++passo) {
    const uint32_t posicao = (partida + passo) % capacidade;
    if (ocupados[posicao]) {
      if (trecho_quantidade == 0) {
        trecho_inicio = posicao;
      }
      ++trecho_quantidade;
      if (trecho_quantidade > melhor_quantidade) {
        melhor_quantidade = trecho_quantidade;
        melhor_inicio = trecho_inicio;
      }
    } else {
      trecho_quantidade = 0;
    }
  }

  return {melhor_inicio, melhor_quantidade, total - melhor_quantidade};
}

}  // namespace meliponet
