// Verifica o buffer de mensagens pendentes.
//
// Em hardware, exercitar lotacao e reinicio exigiria dias de rede fora. Com o
// armazenamento injetado, os mesmos cenarios rodam em milissegundos no PC -- que e
// exatamente por que `SpoolStorage` e uma interface e nao uma chamada direta ao
// LittleFS.

#include <string.h>
#include <unity.h>

#include <map>
#include <string>

#include "Spool.h"

using meliponet::Spool;
using meliponet::SpoolStorage;

namespace {

// Armazenamento em memoria. Substitui o LittleFS nos testes.
class MemoryStorage : public SpoolStorage {
 public:
  bool write(uint32_t slot, const char *payload, size_t length) override {
    if (fail_writes_) {
      return false;
    }
    slots_[slot] = std::string(payload, length);
    ++writes_;
    return true;
  }

  size_t read(uint32_t slot, char *out, size_t capacity) override {
    auto it = slots_.find(slot);
    if (it == slots_.end() || it->second.size() >= capacity) {
      return 0;
    }
    memcpy(out, it->second.data(), it->second.size());
    out[it->second.size()] = '\0';
    return it->second.size();
  }

  bool erase(uint32_t slot) override {
    slots_.erase(slot);
    return true;
  }

  size_t occupied() const { return slots_.size(); }
  void failWrites(bool fail) { fail_writes_ = fail; }

 private:
  std::map<uint32_t, std::string> slots_;
  bool fail_writes_ = false;
  size_t writes_ = 0;
};

void push(Spool &spool, const char *text) { spool.push(text, strlen(text)); }

std::string peek(Spool &spool) {
  char buffer[256];
  const size_t length = spool.peek(buffer, sizeof(buffer));
  return length ? std::string(buffer, length) : std::string();
}

void test_fila_vazia(void) {
  MemoryStorage storage;
  Spool spool(storage);

  TEST_ASSERT_TRUE(spool.empty());
  TEST_ASSERT_EQUAL_size_t(0, spool.size());
  TEST_ASSERT_FALSE(spool.pop());
  TEST_ASSERT_EQUAL_size_t(0, peek(spool).size());
}

// Ordem de chegada: a serie precisa chegar ordenada ao banco.
void test_drena_do_mais_antigo_para_o_mais_novo(void) {
  MemoryStorage storage;
  Spool spool(storage);

  push(spool, "um");
  push(spool, "dois");
  push(spool, "tres");

  TEST_ASSERT_EQUAL_size_t(3, spool.size());
  TEST_ASSERT_EQUAL_STRING("um", peek(spool).c_str());
  spool.pop();
  TEST_ASSERT_EQUAL_STRING("dois", peek(spool).c_str());
  spool.pop();
  TEST_ASSERT_EQUAL_STRING("tres", peek(spool).c_str());
  spool.pop();
  TEST_ASSERT_TRUE(spool.empty());
}

// peek e pop sao separados de proposito: so se remove apos o broker confirmar. Se
// removesse antes, uma publicacao falha perderia a mensagem -- justamente o cenario em
// que o spool existe.
void test_peek_nao_remove(void) {
  MemoryStorage storage;
  Spool spool(storage);
  push(spool, "mensagem");

  TEST_ASSERT_EQUAL_STRING("mensagem", peek(spool).c_str());
  TEST_ASSERT_EQUAL_STRING("mensagem", peek(spool).c_str());
  TEST_ASSERT_EQUAL_size_t(1, spool.size());
}

// Quando lota, descarta a MAIS ANTIGA. Dado recente vale mais para o manejo, e a perda
// fica registrada na `seq` do lado da plataforma de qualquer forma.
void test_lotacao_descarta_a_mais_antiga(void) {
  MemoryStorage storage;
  Spool spool(storage);

  for (size_t i = 0; i < meliponet::kSpoolCapacity; ++i) {
    push(spool, std::to_string(i).c_str());
  }
  TEST_ASSERT_TRUE(spool.full());
  TEST_ASSERT_EQUAL_STRING("0", peek(spool).c_str());

  push(spool, "nova");

  TEST_ASSERT_EQUAL_size_t(meliponet::kSpoolCapacity, spool.size());
  TEST_ASSERT_EQUAL_UINT32(1, spool.dropped());
  // A "0" saiu; a mais antiga agora e a "1".
  TEST_ASSERT_EQUAL_STRING("1", peek(spool).c_str());
}

// O contador de descartes e um indicador de qualidade: se cresce, a rede fica fora
// tempo demais para o tamanho do buffer.
void test_contador_de_descartes(void) {
  MemoryStorage storage;
  Spool spool(storage);

  for (size_t i = 0; i < meliponet::kSpoolCapacity + 5; ++i) {
    push(spool, "x");
  }

  TEST_ASSERT_EQUAL_UINT32(5, spool.dropped());
}

// A fila e circular: apos dar a volta, os indices reaproveitados nao podem embaralhar
// a ordem.
void test_indices_circulam_sem_embaralhar(void) {
  MemoryStorage storage;
  Spool spool(storage);

  // Enche, esvazia, e enche de novo -- forcando os indices a darem a volta.
  for (size_t i = 0; i < meliponet::kSpoolCapacity; ++i) {
    push(spool, "antigo");
  }
  while (!spool.empty()) {
    spool.pop();
  }
  push(spool, "primeira");
  push(spool, "segunda");

  TEST_ASSERT_EQUAL_STRING("primeira", peek(spool).c_str());
  spool.pop();
  TEST_ASSERT_EQUAL_STRING("segunda", peek(spool).c_str());
}

// Apos um reset, a fila e reconstruida a partir do que sobrou no armazenamento.
void test_restauracao_apos_reinicio(void) {
  MemoryStorage storage;
  {
    Spool spool(storage);
    push(spool, "a");
    push(spool, "b");
    push(spool, "c");
    spool.pop();  // "a" foi entregue antes do reset
  }

  Spool recuperado(storage);
  recuperado.restore(1, 2);

  TEST_ASSERT_EQUAL_size_t(2, recuperado.size());
  TEST_ASSERT_EQUAL_STRING("b", peek(recuperado).c_str());
}

// Falha de escrita no armazenamento nao pode ser silenciosa: quem chamou precisa saber
// que a mensagem nao foi guardada.
void test_falha_de_escrita_e_reportada(void) {
  MemoryStorage storage;
  Spool spool(storage);
  storage.failWrites(true);

  TEST_ASSERT_FALSE(spool.push("x", 1));
  TEST_ASSERT_TRUE(spool.empty());
}

void test_push_invalido(void) {
  MemoryStorage storage;
  Spool spool(storage);

  TEST_ASSERT_FALSE(spool.push(nullptr, 10));
  TEST_ASSERT_FALSE(spool.push("x", 0));
  TEST_ASSERT_TRUE(spool.empty());
}

}  // namespace

void setUp(void) {}
void tearDown(void) {}

int main(int, char **) {
  UNITY_BEGIN();
  RUN_TEST(test_fila_vazia);
  RUN_TEST(test_drena_do_mais_antigo_para_o_mais_novo);
  RUN_TEST(test_peek_nao_remove);
  RUN_TEST(test_lotacao_descarta_a_mais_antiga);
  RUN_TEST(test_contador_de_descartes);
  RUN_TEST(test_indices_circulam_sem_embaralhar);
  RUN_TEST(test_restauracao_apos_reinicio);
  RUN_TEST(test_falha_de_escrita_e_reportada);
  RUN_TEST(test_push_invalido);
  return UNITY_END();
}
