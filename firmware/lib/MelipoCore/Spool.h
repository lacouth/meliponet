// Buffer local das mensagens que nao puderam ser enviadas.
//
// O meio rural paraibano tem conectividade intermitente. Sem spool, cada queda de rede
// viraria uma lacuna permanente na serie -- e lacuna e exatamente o que o Edital 17 se
// propoe a medir e minimizar. Com spool, a queda vira apenas atraso.
//
// Tres decisoes governam a fila: quando lota, descarta-se a **mais antiga**; a mensagem
// e guardada **ja serializada**, para preservar a `seq` e o `ts` da medicao; e a drenagem
// vai da mais antiga para a mais nova. O porque de cada uma esta em
// docs/guia/04-o-firmware.md.
//
// O acesso ao armazenamento e injetado (`ArmazenamentoDoSpool`) para que a logica de fila
// possa ser exercitada no PC, sem LittleFS e sem ESP32.

#pragma once

#include <stddef.h>
#include <stdint.h>

namespace meliponet {

// Numero maximo de mensagens guardadas. A ~350 bytes por mensagem, 512 entradas ficam em
// ~180 kB -- cerca de 42 horas de coleta a uma amostra por 5 minutos.
constexpr size_t kCapacidadeDoSpool = 512;

// Interface de armazenamento. A implementacao real usa LittleFS; a de teste usa memoria.
class ArmazenamentoDoSpool {
 public:
  virtual ~ArmazenamentoDoSpool() = default;

  // Grava `conteudo` na posicao `posicao`. Devolve falso em erro de escrita.
  virtual bool escrever(uint32_t posicao, const char *conteudo, size_t tamanho) = 0;

  // Le o conteudo de `posicao` em `saida`. Devolve o tamanho lido, ou 0 se vazio ou se
  // nao couber em `capacidade`.
  virtual size_t ler(uint32_t posicao, char *saida, size_t capacidade) = 0;

  // Apaga `posicao`.
  virtual bool apagar(uint32_t posicao) = 0;
};

// Fila persistente de mensagens pendentes.
class Spool {
 public:
  explicit Spool(ArmazenamentoDoSpool &armazenamento) : armazenamento_(armazenamento) {}

  // Enfileira `conteudo`. Se a fila estiver cheia, descarta a mensagem mais antiga e
  // devolve `true` mesmo assim -- perder a mais antiga e a politica, nao um erro.
  // Devolve `false` apenas se o armazenamento falhar.
  bool guardar(const char *conteudo, size_t tamanho);

  // Le a mensagem mais antiga sem remove-la. Devolve o tamanho, ou 0 se vazia.
  //
  // Separar a leitura da remocao e deliberado: so se remove depois que o broker
  // confirmou a entrega. Remover antes perderia a mensagem se a publicacao falhasse --
  // que e justamente o cenario em que o spool existe.
  size_t espiar(char *saida, size_t capacidade);

  // Remove a mensagem mais antiga. Chame apos a publicacao ter sido confirmada.
  bool remover();

  size_t quantidade() const { return quantidade_; }
  bool vazio() const { return quantidade_ == 0; }
  bool cheio() const { return quantidade_ >= kCapacidadeDoSpool; }

  // Quantas mensagens foram descartadas por lotacao desde o inicio. E um indicador de
  // qualidade: se este numero cresce, a rede esta fora tempo demais para o tamanho do
  // buffer.
  uint32_t descartadas() const { return descartadas_; }

  // Restaura a fila apos um reinicio, a partir do que sobrou no armazenamento.
  void restaurar(uint32_t inicio, uint32_t quantidade);

  uint32_t inicio() const { return inicio_; }

 private:
  ArmazenamentoDoSpool &armazenamento_;
  uint32_t inicio_ = 0;      // posicao da mensagem mais antiga
  size_t quantidade_ = 0;    // quantas estao guardadas
  uint32_t descartadas_ = 0;

  uint32_t posicaoEm(size_t deslocamento) const {
    return static_cast<uint32_t>((inicio_ + deslocamento) % kCapacidadeDoSpool);
  }
};

}  // namespace meliponet
