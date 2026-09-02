// Reconstrucao da fila do spool apos um reinicio.
//
// O spool e um anel de arquivos numerados. Apos uma queda de energia, o unico estado
// que sobrevive e **quais slots tem arquivo** -- a cabeca e a contagem precisam ser
// deduzidas dai.
//
// A deducao ingenua -- "a cabeca e o menor indice ocupado" -- so vale enquanto a fila
// nao deu a volta no anel, e falha em silencio quando da. Com os slots 510, 511, 0 e 1
// ocupados, ela conclui cabeca 0 e contagem 4, reivindicando os slots 0 a 3: os slots 2
// e 3 estao vazios e sao descartados como ilegiveis, enquanto as duas mensagens
// realmente mais antigas ficam orfas no flash e sao recontadas a cada boot seguinte.
//
// A deducao correta e: a fila e o **maior trecho contiguo circular** de slots ocupados.
// Esta funcao e pura justamente para poder ser exercitada com anel dado a volta, anel
// cheio e estado inconsistente -- cenarios que em hardware exigiriam provocar quedas de
// energia em momentos especificos.

#pragma once

#include <stdint.h>

namespace meliponet {

struct QueueState {
  uint32_t head = 0;
  uint32_t count = 0;
  // Slots ocupados que ficaram fora do trecho escolhido. Acontece quando uma queda de
  // energia interrompeu uma escrita, deixando o anel com mais de um trecho. Sao
  // apagados na recuperacao: mante-los faria a contagem crescer a cada boot.
  uint32_t orphaned = 0;
};

// Deduz a fila a partir do mapa de slots ocupados.
//
// `occupied` tem `capacity` posicoes. Um anel cheio nao tem como revelar onde a fila
// comeca, entao a cabeca e assumida em zero -- a ordem de algumas mensagens pode sair
// trocada nesse caso, o que e melhor do que descartar todas.
QueueState deriveQueueState(const bool *occupied, uint32_t capacity);

}  // namespace meliponet
