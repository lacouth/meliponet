// Buffer local das mensagens que nao puderam ser enviadas.
//
// O meio rural paraibano tem conectividade intermitente. Sem spool, cada queda de rede
// viraria uma lacuna permanente na serie -- e lacuna e exatamente o que o Edital 17 se
// propoe a medir e minimizar. Com spool, a queda vira apenas atraso.
//
// Tres decisoes importam:
//
// **Fila circular com teto.** O armazenamento do ESP32 e pequeno e a rede pode ficar
// fora por dias. Quando lota, descarta-se a mensagem **mais antiga**, nao a mais nova:
// dado recente vale mais para o manejo, e a lacuna resultante fica registrada na `seq`
// de qualquer forma.
//
// **`seq` e `ts` originais sao preservados.** A mensagem e guardada ja serializada. Um
// reenvio precisa carregar o instante em que foi *medida*, nao o da retransmissao, ou a
// serie ficaria com todos os pontos represados amontoados no momento da reconexao.
//
// **Ordem de chegada.** Drena do mais antigo para o mais novo, para que a serie chegue
// em ordem no banco.
//
// O acesso ao armazenamento e injetado (`SpoolStorage`) para que a logica de fila possa
// ser exercitada no PC, sem LittleFS e sem ESP32. Foi assim que se testou o
// comportamento de lotacao e de reinicio, que em hardware exigiria dias de espera.

#pragma once

#include <stddef.h>
#include <stdint.h>

namespace meliponet {

// Numero maximo de mensagens guardadas. A ~350 bytes por mensagem, 512 entradas ficam
// em ~180 kB -- cerca de 42 horas de coleta a uma amostra por 5 minutos.
constexpr size_t kSpoolCapacity = 512;

// Interface de armazenamento. A implementacao real usa LittleFS; a de teste usa
// memoria.
class SpoolStorage {
 public:
  virtual ~SpoolStorage() = default;

  // Grava `payload` sob o indice `slot`. Devolve falso em erro de escrita.
  virtual bool write(uint32_t slot, const char *payload, size_t length) = 0;

  // Le o conteudo de `slot` em `out`. Devolve o tamanho lido, ou 0 se vazio ou se nao
  // couber em `capacity`.
  virtual size_t read(uint32_t slot, char *out, size_t capacity) = 0;

  // Apaga `slot`.
  virtual bool erase(uint32_t slot) = 0;
};

// Fila persistente de mensagens pendentes.
class Spool {
 public:
  explicit Spool(SpoolStorage &storage) : storage_(storage) {}

  // Enfileira `payload`. Se a fila estiver cheia, descarta a mensagem mais antiga e
  // devolve `true` mesmo assim -- perder a mais antiga e a politica, nao um erro.
  // Devolve `false` apenas se o armazenamento falhar.
  bool push(const char *payload, size_t length);

  // Le a mensagem mais antiga sem remove-la. Devolve o tamanho, ou 0 se vazia.
  //
  // Separar a leitura da remocao e deliberado: so se remove depois que o broker
  // confirmou a entrega. Remover antes perderia a mensagem se a publicacao falhasse --
  // que e justamente o cenario em que o spool existe.
  size_t peek(char *out, size_t capacity);

  // Remove a mensagem mais antiga. Chame apos a publicacao ter sido confirmada.
  bool pop();

  size_t size() const { return count_; }
  bool empty() const { return count_ == 0; }
  bool full() const { return count_ >= kSpoolCapacity; }

  // Quantas mensagens foram descartadas por lotacao desde o inicio. E um indicador de
  // qualidade: se este numero cresce, a rede esta fora tempo demais para o tamanho do
  // buffer.
  uint32_t dropped() const { return dropped_; }

  // Restaura a fila apos um reinicio, a partir do que sobrou no armazenamento.
  void restore(uint32_t head, uint32_t count);

  uint32_t head() const { return head_; }

 private:
  SpoolStorage &storage_;
  uint32_t head_ = 0;   // indice da mensagem mais antiga
  size_t count_ = 0;    // quantas estao guardadas
  uint32_t dropped_ = 0;

  uint32_t slotAt(size_t offset) const {
    return static_cast<uint32_t>((head_ + offset) % kSpoolCapacity);
  }
};

}  // namespace meliponet
