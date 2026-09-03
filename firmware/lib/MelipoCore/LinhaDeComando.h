// Leitura da linha de comando do console serial.
//
// Fica aqui, em MelipoCore, e nao dentro do `main.cpp`, por um motivo pratico: o console
// e por onde as credenciais entram no no, e um erro de divisao de argumentos grava
// metade de uma senha. O sintoma em campo -- "conecta no WiFi mas nunca publica" -- e
// identico ao de senha errada, ao de broker errado e ao de firewall, e depurar isso
// custa uma viagem. Sendo codigo puro, a divisao e exercitada no PC.
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
constexpr size_t kMaxArgumentos = 3;

// Comprimento maximo de um argumento, contando o terminador -- dimensionado pelo maior
// campo que o console grava, que e a senha.
constexpr size_t kMaxTamanhoDoArgumento = 65;

// Uma linha ja dividida. Os argumentos sao strings comuns, terminadas em nulo: dao para
// comparar com `strcmp`, imprimir com `%s` e copiar com as funcoes de sempre.
struct Comando {
  char argumento[kMaxArgumentos][kMaxTamanhoDoArgumento] = {};
  size_t quantidade = 0;

  // Verdadeiro se algum argumento era maior do que cabia e foi cortado. Quem trata o
  // comando deve **recusar a linha inteira** nesse caso: gravar uma senha pela metade
  // produz um no que tenta autenticar para sempre, e nada no serial explica o motivo.
  bool truncado = false;

  // Verdadeiro se o comando digitado e `nome`.
  bool ehComando(const char *nome) const;
};

// Divide `linha` em ate `kMaxArgumentos` argumentos separados por espaco, ignorando
// espacos repetidos. O ultimo leva o resto da linha.
//
// Espera a linha ja sem o `\r\n` e sem brancos nas pontas -- e o que `String::trim()`
// entrega do lado do Arduino.
Comando dividirLinha(const char *linha);

// Verdadeiro se `texto` cabe num buffer de `capacidade` bytes, contando o terminador.
bool cabeEm(const char *texto, size_t capacidade);

// Copia `texto` para `destino`, sempre terminando em nulo.
//
// Devolve falso e **nao toca em `destino`** se nao couber -- pela mesma razao do
// `truncado` acima.
bool copiarTexto(char *destino, size_t capacidade, const char *texto);

// Converte `texto` num inteiro em 1..`maximo`. Devolve falso para vazio, texto nao
// numerico, zero ou acima do teto -- e nesse caso **nao altera `saida`**, para que um
// comando recusado nunca troque o valor que ja estava valendo.
bool lerNumero(const char *texto, uint32_t maximo, uint32_t &saida);

// Converte `texto` numa porta TCP valida. Devolve falso para vazio, texto nao numerico,
// zero ou acima de 65535.
bool lerPorta(const char *texto, uint16_t &porta);

}  // namespace meliponet
