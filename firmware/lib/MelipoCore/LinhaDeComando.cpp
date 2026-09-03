#include "LinhaDeComando.h"

#include <string.h>

namespace meliponet {
namespace {

// Copia ate `capacidade - 1` caracteres de `texto` (parando antes de `fim`) e termina em
// nulo. Devolve verdadeiro se coube inteiro.
bool copiarPedaco(char *destino, size_t capacidade, const char *texto, const char *fim) {
  const size_t tamanho = static_cast<size_t>(fim - texto);
  const bool coube = tamanho + 1 <= capacidade;
  const size_t copiados = coube ? tamanho : capacidade - 1;

  memcpy(destino, texto, copiados);
  destino[copiados] = '\0';
  return coube;
}

}  // namespace

bool Comando::ehComando(const char *nome) const {
  return nome != nullptr && quantidade > 0 && strcmp(argumento[0], nome) == 0;
}

Comando dividirLinha(const char *linha) {
  Comando comando;
  if (linha == nullptr) {
    return comando;
  }

  const char *cursor = linha;
  while (comando.quantidade < kMaxArgumentos) {
    while (*cursor == ' ') {
      ++cursor;
    }
    if (*cursor == '\0') {
      break;
    }

    // Onde este argumento termina: no proximo espaco -- ou no fim da linha, se este for
    // o ultimo, que e como uma senha com espaco chega inteira.
    const char *fim = cursor;
    if (comando.quantidade + 1 == kMaxArgumentos) {
      fim = cursor + strlen(cursor);
    } else {
      while (*fim != '\0' && *fim != ' ') {
        ++fim;
      }
    }

    if (!copiarPedaco(comando.argumento[comando.quantidade], kMaxTamanhoDoArgumento, cursor,
                      fim)) {
      comando.truncado = true;
    }
    ++comando.quantidade;
    cursor = fim;
  }

  return comando;
}

bool cabeEm(const char *texto, size_t capacidade) {
  return texto != nullptr && strlen(texto) + 1 <= capacidade;
}

bool copiarTexto(char *destino, size_t capacidade, const char *texto) {
  if (destino == nullptr || !cabeEm(texto, capacidade)) {
    return false;
  }
  strcpy(destino, texto);
  return true;
}

bool lerNumero(const char *texto, uint32_t maximo, uint32_t &saida) {
  if (texto == nullptr || texto[0] == '\0') {
    return false;
  }

  uint32_t valor = 0;
  for (const char *p = texto; *p != '\0'; ++p) {
    if (*p < '0' || *p > '9') {
      return false;
    }
    valor = valor * 10 + static_cast<uint32_t>(*p - '0');
    // Compara a cada digito, e nao so no fim: assim uma entrada absurdamente longa e
    // recusada em vez de dar a volta no inteiro e virar um numero pequeno e plausivel.
    if (valor > maximo) {
      return false;
    }
  }

  if (valor == 0) {
    return false;
  }

  saida = valor;
  return true;
}

bool lerPorta(const char *texto, uint16_t &porta) {
  uint32_t valor = 0;
  // Porta 0 e reservada, e o teto de 65535 sai do proprio protocolo.
  if (!lerNumero(texto, 65535, valor)) {
    return false;
  }
  porta = static_cast<uint16_t>(valor);
  return true;
}

}  // namespace meliponet
