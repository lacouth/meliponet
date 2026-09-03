#include "CommandLine.h"

#include <string.h>

namespace meliponet {
namespace {

// Copia ate `capacity - 1` caracteres de `text` (parando antes de `end`) e termina em
// nulo. Devolve verdadeiro se coube inteiro.
bool copyPiece(char *dest, size_t capacity, const char *text, const char *end) {
  const size_t length = static_cast<size_t>(end - text);
  const bool fits = length + 1 <= capacity;
  const size_t copied = fits ? length : capacity - 1;

  memcpy(dest, text, copied);
  dest[copied] = '\0';
  return fits;
}

}  // namespace

bool Command::is(const char *name) const {
  return name != nullptr && count > 0 && strcmp(arg[0], name) == 0;
}

Command splitLine(const char *line) {
  Command command;
  if (line == nullptr) {
    return command;
  }

  const char *cursor = line;
  while (command.count < kMaxArgs) {
    while (*cursor == ' ') {
      ++cursor;
    }
    if (*cursor == '\0') {
      break;
    }

    // Onde este argumento termina: no proximo espaco -- ou no fim da linha, se este for
    // o ultimo, que e como uma senha com espaco chega inteira.
    const char *end = cursor;
    if (command.count + 1 == kMaxArgs) {
      end = cursor + strlen(cursor);
    } else {
      while (*end != '\0' && *end != ' ') {
        ++end;
      }
    }

    if (!copyPiece(command.arg[command.count], kMaxArgLength, cursor, end)) {
      command.truncated = true;
    }
    ++command.count;
    cursor = end;
  }

  return command;
}

bool fitsIn(const char *text, size_t capacity) {
  return text != nullptr && strlen(text) + 1 <= capacity;
}

bool copyText(char *dest, size_t capacity, const char *text) {
  if (dest == nullptr || !fitsIn(text, capacity)) {
    return false;
  }
  strcpy(dest, text);
  return true;
}

bool parseCount(const char *text, uint32_t maximum, uint32_t &out) {
  if (text == nullptr || text[0] == '\0') {
    return false;
  }

  uint32_t value = 0;
  for (const char *p = text; *p != '\0'; ++p) {
    if (*p < '0' || *p > '9') {
      return false;
    }
    value = value * 10 + static_cast<uint32_t>(*p - '0');
    // Compara a cada digito, e nao so no fim: assim uma entrada absurdamente longa e
    // recusada em vez de dar a volta no inteiro e virar um numero pequeno e plausivel.
    if (value > maximum) {
      return false;
    }
  }

  if (value == 0) {
    return false;
  }

  out = value;
  return true;
}

bool parsePort(const char *text, uint16_t &port) {
  uint32_t value = 0;
  // Porta 0 e reservada, e o teto de 65535 sai do proprio protocolo.
  if (!parseCount(text, 65535, value)) {
    return false;
  }
  port = static_cast<uint16_t>(value);
  return true;
}

}  // namespace meliponet
