// Reconstrucao da fila do spool apos um reinicio.
//
// O spool e um anel de arquivos numerados. Apos uma queda de energia, o unico estado que
// sobrevive e **quais posicoes tem arquivo** -- o inicio e a contagem precisam ser
// deduzidos dai.
//
// A deducao correta e: a fila e o **maior trecho contiguo circular** de posicoes
// ocupadas. A deducao ingenua ("o inicio e a menor posicao ocupada") falha em silencio
// quando o anel da a volta; o exemplo esta em docs/guia/04-o-firmware.md.
//
// Esta funcao e pura justamente para poder ser exercitada com anel dado a volta, anel
// cheio e estado inconsistente -- cenarios que em hardware exigiriam provocar quedas de
// energia em momentos especificos.

#pragma once

#include <stdint.h>

namespace meliponet {

struct EstadoDaFila {
  uint32_t inicio = 0;
  uint32_t quantidade = 0;
  // Posicoes ocupadas que ficaram fora do trecho escolhido. Acontece quando uma queda de
  // energia interrompeu uma escrita, deixando o anel com mais de um trecho. Sao apagadas
  // na recuperacao: mante-las faria a contagem crescer a cada boot.
  uint32_t orfaos = 0;
};

// Deduz a fila a partir do mapa de posicoes ocupadas.
//
// `ocupados` tem `capacidade` posicoes. Um anel cheio nao tem como revelar onde a fila
// comeca, entao o inicio e assumido em zero -- a ordem de algumas mensagens pode sair
// trocada nesse caso, o que e melhor do que descartar todas.
EstadoDaFila deduzirEstadoDaFila(const bool *ocupados, uint32_t capacidade);

}  // namespace meliponet
