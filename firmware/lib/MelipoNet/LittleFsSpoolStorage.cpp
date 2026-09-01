#include "LittleFsSpoolStorage.h"

#include <LittleFS.h>
#include <stdio.h>

namespace meliponet {
namespace {

constexpr const char *kDirectory = "/spool";

void slotPath(uint32_t slot, char *out, size_t capacity) {
  snprintf(out, capacity, "%s/%04u", kDirectory, static_cast<unsigned>(slot));
}

}  // namespace

bool LittleFsSpoolStorage::begin(uint32_t &head, uint32_t &count) {
  // O `true` formata se a montagem falhar: um sistema de arquivos corrompido nao pode
  // impedir o no de voltar a operar. Perde-se o que estava na fila, o que a plataforma
  // registra como lacuna -- melhor do que um no que nao inicia.
  mounted_ = LittleFS.begin(true);
  if (!mounted_) {
    return false;
  }
  LittleFS.mkdir(kDirectory);

  // Reconstroi a fila varrendo os arquivos existentes. Os nomes sao os indices, entao a
  // ordem lexicografica dos nomes com zeros a esquerda e a ordem da fila.
  uint32_t lowest = kSpoolCapacity;
  uint32_t found = 0;
  for (uint32_t slot = 0; slot < kSpoolCapacity; ++slot) {
    char path[32];
    slotPath(slot, path, sizeof(path));
    if (LittleFS.exists(path)) {
      if (slot < lowest) {
        lowest = slot;
      }
      ++found;
    }
  }

  head = found == 0 ? 0 : lowest;
  count = found;
  return true;
}

bool LittleFsSpoolStorage::write(uint32_t slot, const char *payload, size_t length) {
  if (!mounted_) {
    return false;
  }
  char path[32];
  slotPath(slot, path, sizeof(path));

  File file = LittleFS.open(path, "w");
  if (!file) {
    return false;
  }
  const size_t written = file.write(reinterpret_cast<const uint8_t *>(payload), length);
  file.close();
  return written == length;
}

size_t LittleFsSpoolStorage::read(uint32_t slot, char *out, size_t capacity) {
  if (!mounted_) {
    return 0;
  }
  char path[32];
  slotPath(slot, path, sizeof(path));

  File file = LittleFS.open(path, "r");
  if (!file) {
    return 0;
  }
  const size_t size = file.size();
  if (size >= capacity) {
    file.close();
    return 0;
  }
  const size_t read_bytes = file.readBytes(out, size);
  out[read_bytes] = '\0';
  file.close();
  return read_bytes;
}

bool LittleFsSpoolStorage::erase(uint32_t slot) {
  if (!mounted_) {
    return false;
  }
  char path[32];
  slotPath(slot, path, sizeof(path));
  return LittleFS.remove(path) || !LittleFS.exists(path);
}

}  // namespace meliponet
