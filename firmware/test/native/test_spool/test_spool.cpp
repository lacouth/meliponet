// Verifica o buffer de mensagens pendentes.
//
// Em hardware, exercitar lotacao e reinicio exigiria dias de rede fora. Com o
// armazenamento injetado, os mesmos cenarios rodam em milissegundos no PC -- que e
// exatamente por que `ArmazenamentoDoSpool` e uma interface e nao uma chamada direta ao
// LittleFS.

#include <string.h>
#include <unity.h>

#include <map>
#include <string>

#include "Spool.h"

using meliponet::ArmazenamentoDoSpool;
using meliponet::Spool;

namespace {

// Armazenamento em memoria. Substitui o LittleFS nos testes.
class ArmazenamentoEmMemoria : public ArmazenamentoDoSpool {
 public:
  bool escrever(uint32_t posicao, const char *conteudo, size_t tamanho) override {
    if (falhar_escrita_) {
      return false;
    }
    posicoes_[posicao] = std::string(conteudo, tamanho);
    return true;
  }

  size_t ler(uint32_t posicao, char *saida, size_t capacidade) override {
    auto it = posicoes_.find(posicao);
    if (it == posicoes_.end() || it->second.size() >= capacidade) {
      return 0;
    }
    memcpy(saida, it->second.data(), it->second.size());
    saida[it->second.size()] = '\0';
    return it->second.size();
  }

  bool apagar(uint32_t posicao) override {
    posicoes_.erase(posicao);
    return true;
  }

  void falharEscritas(bool falhar) { falhar_escrita_ = falhar; }

 private:
  std::map<uint32_t, std::string> posicoes_;
  bool falhar_escrita_ = false;
};

void guardar(Spool &spool, const char *texto) { spool.guardar(texto, strlen(texto)); }

std::string espiar(Spool &spool) {
  char buffer[256];
  const size_t tamanho = spool.espiar(buffer, sizeof(buffer));
  return tamanho ? std::string(buffer, tamanho) : std::string();
}

void test_fila_vazia(void) {
  ArmazenamentoEmMemoria armazenamento;
  Spool spool(armazenamento);

  TEST_ASSERT_TRUE(spool.vazio());
  TEST_ASSERT_EQUAL_size_t(0, spool.quantidade());
  TEST_ASSERT_FALSE(spool.remover());
  TEST_ASSERT_EQUAL_size_t(0, espiar(spool).size());
}

// Ordem de chegada: a serie precisa chegar ordenada ao banco.
void test_drena_do_mais_antigo_para_o_mais_novo(void) {
  ArmazenamentoEmMemoria armazenamento;
  Spool spool(armazenamento);

  guardar(spool, "um");
  guardar(spool, "dois");
  guardar(spool, "tres");

  TEST_ASSERT_EQUAL_size_t(3, spool.quantidade());
  TEST_ASSERT_EQUAL_STRING("um", espiar(spool).c_str());
  spool.remover();
  TEST_ASSERT_EQUAL_STRING("dois", espiar(spool).c_str());
  spool.remover();
  TEST_ASSERT_EQUAL_STRING("tres", espiar(spool).c_str());
  spool.remover();
  TEST_ASSERT_TRUE(spool.vazio());
}

// `espiar` e `remover` sao separados de proposito: so se remove apos o broker confirmar.
// Se removesse antes, uma publicacao falha perderia a mensagem -- justamente o cenario
// em que o spool existe.
void test_espiar_nao_remove(void) {
  ArmazenamentoEmMemoria armazenamento;
  Spool spool(armazenamento);
  guardar(spool, "mensagem");

  TEST_ASSERT_EQUAL_STRING("mensagem", espiar(spool).c_str());
  TEST_ASSERT_EQUAL_STRING("mensagem", espiar(spool).c_str());
  TEST_ASSERT_EQUAL_size_t(1, spool.quantidade());
}

// Quando lota, descarta a MAIS ANTIGA. Dado recente vale mais para o manejo, e a perda
// fica registrada na `seq` do lado da plataforma de qualquer forma.
void test_lotacao_descarta_a_mais_antiga(void) {
  ArmazenamentoEmMemoria armazenamento;
  Spool spool(armazenamento);

  for (size_t i = 0; i < meliponet::kCapacidadeDoSpool; ++i) {
    guardar(spool, std::to_string(i).c_str());
  }
  TEST_ASSERT_TRUE(spool.cheio());
  TEST_ASSERT_EQUAL_STRING("0", espiar(spool).c_str());

  guardar(spool, "nova");

  TEST_ASSERT_EQUAL_size_t(meliponet::kCapacidadeDoSpool, spool.quantidade());
  TEST_ASSERT_EQUAL_UINT32(1, spool.descartadas());
  // A "0" saiu; a mais antiga agora e a "1".
  TEST_ASSERT_EQUAL_STRING("1", espiar(spool).c_str());
}

// O contador de descartes e um indicador de qualidade: se cresce, a rede fica fora tempo
// demais para o tamanho do buffer.
void test_contador_de_descartes(void) {
  ArmazenamentoEmMemoria armazenamento;
  Spool spool(armazenamento);

  for (size_t i = 0; i < meliponet::kCapacidadeDoSpool + 5; ++i) {
    guardar(spool, "x");
  }

  TEST_ASSERT_EQUAL_UINT32(5, spool.descartadas());
}

// A fila e circular: apos dar a volta, as posicoes reaproveitadas nao podem embaralhar a
// ordem.
void test_posicoes_circulam_sem_embaralhar(void) {
  ArmazenamentoEmMemoria armazenamento;
  Spool spool(armazenamento);

  // Enche, esvazia, e enche de novo -- forcando as posicoes a darem a volta.
  for (size_t i = 0; i < meliponet::kCapacidadeDoSpool; ++i) {
    guardar(spool, "antigo");
  }
  while (!spool.vazio()) {
    spool.remover();
  }
  guardar(spool, "primeira");
  guardar(spool, "segunda");

  TEST_ASSERT_EQUAL_STRING("primeira", espiar(spool).c_str());
  spool.remover();
  TEST_ASSERT_EQUAL_STRING("segunda", espiar(spool).c_str());
}

// Apos um reset, a fila e reconstruida a partir do que sobrou no armazenamento.
void test_restauracao_apos_reinicio(void) {
  ArmazenamentoEmMemoria armazenamento;
  {
    Spool spool(armazenamento);
    guardar(spool, "a");
    guardar(spool, "b");
    guardar(spool, "c");
    spool.remover();  // "a" foi entregue antes do reset
  }

  Spool recuperado(armazenamento);
  recuperado.restaurar(1, 2);

  TEST_ASSERT_EQUAL_size_t(2, recuperado.quantidade());
  TEST_ASSERT_EQUAL_STRING("b", espiar(recuperado).c_str());
}

// Falha de escrita no armazenamento nao pode ser silenciosa: quem chamou precisa saber
// que a mensagem nao foi guardada.
void test_falha_de_escrita_e_reportada(void) {
  ArmazenamentoEmMemoria armazenamento;
  Spool spool(armazenamento);
  armazenamento.falharEscritas(true);

  TEST_ASSERT_FALSE(spool.guardar("x", 1));
  TEST_ASSERT_TRUE(spool.vazio());
}

void test_guardar_invalido(void) {
  ArmazenamentoEmMemoria armazenamento;
  Spool spool(armazenamento);

  TEST_ASSERT_FALSE(spool.guardar(nullptr, 10));
  TEST_ASSERT_FALSE(spool.guardar("x", 0));
  TEST_ASSERT_TRUE(spool.vazio());
}

}  // namespace

void setUp(void) {}
void tearDown(void) {}

int main(int, char **) {
  UNITY_BEGIN();
  RUN_TEST(test_fila_vazia);
  RUN_TEST(test_drena_do_mais_antigo_para_o_mais_novo);
  RUN_TEST(test_espiar_nao_remove);
  RUN_TEST(test_lotacao_descarta_a_mais_antiga);
  RUN_TEST(test_contador_de_descartes);
  RUN_TEST(test_posicoes_circulam_sem_embaralhar);
  RUN_TEST(test_restauracao_apos_reinicio);
  RUN_TEST(test_falha_de_escrita_e_reportada);
  RUN_TEST(test_guardar_invalido);
  return UNITY_END();
}
