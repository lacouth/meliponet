// Leitura da linha de comando do console serial.
//
// Fica aqui, em MelipoCore, e nao dentro do `main.cpp`, por um motivo pratico: o
// console e por onde as credenciais entram no no, e um erro de divisao de argumentos
// grava metade de uma senha. O sintoma em campo -- "conecta no WiFi mas nunca publica"
// -- e identico ao de senha errada, ao de broker errado e ao de firewall, e depurar
// isso custa uma viagem. Sendo codigo puro, a divisao e exercitada no PC.
//
// A regra que governa o resto: **o ultimo argumento pedido leva o resto da linha**,
// espacos inclusive. Senha com espaco e comum e legitima; dividir no primeiro branco
// truncaria em silencio.

#pragma once

#include <stddef.h>
#include <stdint.h>

namespace meliponet {

// Um argumento: aponta para dentro da linha original, sem copiar nem alocar.
struct Arg {
  const char *text = nullptr;
  size_t length = 0;

  bool empty() const { return length == 0; }

  // Compara com uma palavra terminada em nulo. Nao usa strcmp porque `text` nao e
  // terminado: ele aponta para o meio da linha.
  bool equals(const char *other) const;
};

// Divide `line` em ate `max_args` argumentos separados por espaco, ignorando espacos
// repetidos. O ultimo argumento pedido leva o resto da linha.
//
// Espera a linha ja sem o `\r\n` e sem brancos nas pontas -- e o que `String::trim()`
// entrega do lado do Arduino.
//
// Devolve quantos argumentos foram encontrados; 0 para linha vazia ou so com espacos.
size_t splitArgs(const char *line, Arg *out, size_t max_args);

// Verdadeiro se `arg` cabe num buffer de `capacity` bytes, contando o terminador.
inline bool fits(const Arg &arg, size_t capacity) { return arg.length + 1 <= capacity; }

// Copia `arg` para `dest`, sempre terminando em nulo.
//
// Devolve falso e **nao toca em `dest`** se nao couber. Quem chama deve recusar o
// comando inteiro em vez de gravar truncado: uma senha cortada pela metade e
// indistinguivel de uma senha errada na hora de depurar, e o no fica tentando
// autenticar para sempre sem que nada no serial explique o motivo.
bool copyArg(const Arg &arg, char *dest, size_t capacity);

// Converte `arg` num inteiro em 1..`maximum`. Devolve falso para vazio, texto nao
// numerico, zero ou acima do teto -- e nesse caso **nao altera `out`**, para que um
// comando recusado nunca troque o valor que ja estava valendo.
bool parseCount(const Arg &arg, uint32_t maximum, uint32_t &out);

// Converte `arg` numa porta TCP valida. Devolve falso para vazio, texto nao numerico,
// zero ou acima de 65535.
bool parsePort(const Arg &arg, uint16_t &port);

}  // namespace meliponet
