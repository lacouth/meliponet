#include "SpoolRecovery.h"

namespace meliponet {

QueueState deriveQueueState(const bool *occupied, uint32_t capacity) {
  if (occupied == nullptr || capacity == 0) {
    return {};
  }

  uint32_t total = 0;
  for (uint32_t slot = 0; slot < capacity; ++slot) {
    if (occupied[slot]) {
      ++total;
    }
  }
  if (total == 0) {
    return {};
  }
  if (total == capacity) {
    // Anel cheio: nao ha lacuna que revele onde a fila comeca.
    return {0, capacity, 0};
  }

  // Procura o maior trecho contiguo, percorrendo o anel a partir de um slot vazio --
  // assim nenhum trecho e cortado ao meio pelo inicio da varredura.
  uint32_t start = 0;
  while (occupied[start]) {
    ++start;
  }

  uint32_t best_head = 0;
  uint32_t best_count = 0;
  uint32_t run_head = 0;
  uint32_t run_count = 0;

  for (uint32_t step = 0; step < capacity; ++step) {
    const uint32_t slot = (start + step) % capacity;
    if (occupied[slot]) {
      if (run_count == 0) {
        run_head = slot;
      }
      ++run_count;
      if (run_count > best_count) {
        best_count = run_count;
        best_head = run_head;
      }
    } else {
      run_count = 0;
    }
  }

  return {best_head, best_count, total - best_count};
}

}  // namespace meliponet
