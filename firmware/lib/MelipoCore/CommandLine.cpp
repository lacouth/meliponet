#include "CommandLine.h"

#include <string.h>

namespace meliponet {

bool Arg::equals(const char *other) const {
  if (text == nullptr || other == nullptr) {
    return false;
  }
  return strlen(other) == length && strncmp(text, other, length) == 0;
}

size_t splitArgs(const char *line, Arg *out, size_t max_args) {
  if (line == nullptr || out == nullptr || max_args == 0) {
    return 0;
  }

  size_t found = 0;
  const char *cursor = line;

  while (found < max_args) {
    while (*cursor == ' ') {
      ++cursor;
    }
    if (*cursor == '\0') {
      break;
    }

    if (found + 1 == max_args) {
      // O ultimo pedido leva o resto da linha, espacos inclusive.
      out[found].text = cursor;
      out[found].length = strlen(cursor);
      ++found;
      break;
    }

    const char *end = cursor;
    while (*end != '\0' && *end != ' ') {
      ++end;
    }
    out[found].text = cursor;
    out[found].length = static_cast<size_t>(end - cursor);
    ++found;
    cursor = end;
  }

  return found;
}

bool copyArg(const Arg &arg, char *dest, size_t capacity) {
  if (dest == nullptr || !fits(arg, capacity)) {
    return false;
  }
  if (arg.length > 0) {
    memcpy(dest, arg.text, arg.length);
  }
  dest[arg.length] = '\0';
  return true;
}

bool parseCount(const Arg &arg, uint32_t maximum, uint32_t &out) {
  if (arg.empty()) {
    return false;
  }

  uint32_t value = 0;
  for (size_t i = 0; i < arg.length; ++i) {
    const char digit = arg.text[i];
    if (digit < '0' || digit > '9') {
      return false;
    }
    value = value * 10 + static_cast<uint32_t>(digit - '0');
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

bool parsePort(const Arg &arg, uint16_t &port) {
  uint32_t value = 0;
  // Porta 0 e reservada, e o teto de 65535 sai do proprio protocolo.
  if (!parseCount(arg, 65535, value)) {
    return false;
  }
  port = static_cast<uint16_t>(value);
  return true;
}

}  // namespace meliponet
