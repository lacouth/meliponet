#include "Spool.h"

namespace meliponet {

bool Spool::push(const char *payload, size_t length) {
  if (payload == nullptr || length == 0) {
    return false;
  }

  if (full()) {
    // Descarta a mais antiga para abrir espaco. A perda fica visivel na `seq` do lado
    // da plataforma, e contada aqui em `dropped_`.
    if (!storage_.erase(head_)) {
      return false;
    }
    head_ = static_cast<uint32_t>((head_ + 1) % kSpoolCapacity);
    --count_;
    ++dropped_;
  }

  const uint32_t slot = slotAt(count_);
  if (!storage_.write(slot, payload, length)) {
    return false;
  }
  ++count_;
  return true;
}

size_t Spool::peek(char *out, size_t capacity) {
  if (empty() || out == nullptr || capacity == 0) {
    return 0;
  }
  return storage_.read(head_, out, capacity);
}

bool Spool::pop() {
  if (empty()) {
    return false;
  }
  if (!storage_.erase(head_)) {
    return false;
  }
  head_ = static_cast<uint32_t>((head_ + 1) % kSpoolCapacity);
  --count_;
  return true;
}

void Spool::restore(uint32_t head, uint32_t count) {
  head_ = head % kSpoolCapacity;
  count_ = count > kSpoolCapacity ? kSpoolCapacity : count;
}

}  // namespace meliponet
