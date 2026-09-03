// Leitura da linha de comando do console serial.
//
// Fica aqui, em MelipoCore, e nao dentro do `main.cpp`, por um motivo pratico: o
// console e por onde as credenciais entram no no, e um erro de divisao de argumentos
// grava metade de uma senha. O sintoma em campo -- "conecta no WiFi mas nunca publica"
// -- e identico ao de senha errada, ao de broker errado e ao de firewall, e depurar
// isso custa uma viagem. Sendo codigo puro, a divisao e exercitada no PC.
//
// A regra que governa o resto: **o ultimo argumento leva o resto da linha**, espacos
// inclusive. Senha com espaco e comum e legitima; dividir no primeiro branco truncaria
// em silencio.

#pragma once

#include <stddef.h>
#include <stdint.h>

namespace meliponet {

// Tres argumentos bastam para todos os comandos do console: o nome do comando e mais
// dois. O terceiro leva o resto da linha, e e assim que uma senha com espaco chega
// inteira.
constexpr size_t kMaxArgs = 3;

// Comprimento maximo de um argumento, contando o terminador -- dimensionado pelo maior
// campo que o console grava, que e a senha.
constexpr size_t kMaxArgLength = 65;

// Uma linha ja dividida. Os argumentos sao strings comuns, terminadas em nulo: dao para
// comparar com `strcmp`, imprimir com `%s` e copiar com as funcoes de sempre.
struct Command {
  char arg[kMaxArgs][kMaxArgLength] = {};
  size_t count = 0;

  // Verdadeiro se algum argumento era maior do que `kMaxArgLength` e foi cortado. Quem
  // trata o comando deve **recusar a linha inteira** nesse caso: gravar uma senha pela
  // metade produz um no que tenta autenticar para sempre, e nada no serial explica o
  // motivo.
  bool truncated = false;

  // Verdadeiro se o comando digitado e `name`.
  bool is(const char *name) const;
};

// Divide `line` em ate `kMaxArgs` argumentos separados por espaco, ignorando espacos
// repetidos. O ultimo leva o resto da linha.
//
// Espera a linha ja sem o `\r\n` e sem brancos nas pontas -- e o que `String::trim()`
// entrega do lado do Arduino.
Command splitLine(const char *line);

// Verdadeiro se `text` cabe num buffer de `capacity` bytes, contando o terminador.
bool fitsIn(const char *text, size_t capacity);

// Copia `text` para `dest`, sempre terminando em nulo.
//
// Devolve falso e **nao toca em `dest`** se nao couber -- pela mesma razao do
// `truncated` acima.
bool copyText(char *dest, size_t capacity, const char *text);

// Converte `text` num inteiro em 1..`maximum`. Devolve falso para vazio, texto nao
// numerico, zero ou acima do teto -- e nesse caso **nao altera `out`**, para que um
// comando recusado nunca troque o valor que ja estava valendo.
bool parseCount(const char *text, uint32_t maximum, uint32_t &out);

// Converte `text` numa porta TCP valida. Devolve falso para vazio, texto nao numerico,
// zero ou acima de 65535.
bool parsePort(const char *text, uint16_t &port);

}  // namespace meliponet
