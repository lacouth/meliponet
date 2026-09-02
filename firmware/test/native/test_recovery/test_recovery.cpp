// Recuo exponencial e reconstrucao da fila do spool.
//
// As duas logicas viviam soltas dentro de arquivos que so compilam no ESP32, fora do
// alcance de qualquer teste -- e as duas estavam erradas de formas que so apareceriam
// em campo, depois de horas ou semanas ligadas. Estao aqui, puras, por isso.

#include <string.h>
#include <unity.h>

#include "Backoff.h"
#include "SpoolRecovery.h"

using meliponet::Backoff;
using meliponet::deriveQueueState;
using meliponet::QueueState;

namespace {

// ----- recuo exponencial -----

void test_primeira_tentativa_e_imediata(void) {
  Backoff backoff(1000, 300000);

  // Um no recem-ligado nao deve esperar antes da primeira tentativa de conexao.
  TEST_ASSERT_TRUE(backoff.ready(0));
  TEST_ASSERT_TRUE(backoff.ready(12345));
}

void test_recuo_dobra_ate_o_teto(void) {
  Backoff backoff(1000, 8000);

  backoff.recordAttempt(0);
  TEST_ASSERT_EQUAL_UINT32(2000, backoff.interval());
  backoff.recordAttempt(2000);
  TEST_ASSERT_EQUAL_UINT32(4000, backoff.interval());
  backoff.recordAttempt(6000);
  TEST_ASSERT_EQUAL_UINT32(8000, backoff.interval());
  // No teto, para de crescer -- caso contrario o no demoraria demais a voltar quando o
  // sinal retornasse.
  backoff.recordAttempt(14000);
  TEST_ASSERT_EQUAL_UINT32(8000, backoff.interval());
}

void test_espera_o_intervalo(void) {
  Backoff backoff(1000, 300000);
  backoff.recordAttempt(10000);

  TEST_ASSERT_FALSE(backoff.ready(10500));
  TEST_ASSERT_FALSE(backoff.ready(11999));
  TEST_ASSERT_TRUE(backoff.ready(12000));
}

void test_sucesso_volta_ao_minimo(void) {
  Backoff backoff(1000, 300000);
  for (int i = 0; i < 5; ++i) {
    backoff.recordAttempt(i * 1000);
  }
  TEST_ASSERT_TRUE(backoff.interval() > 1000);

  backoff.recordSuccess();

  TEST_ASSERT_EQUAL_UINT32(1000, backoff.interval());
  TEST_ASSERT_TRUE(backoff.ready(0));
}

// O bug que travava a reconexao: uma espera muito maior que o intervalo tem de liberar
// a tentativa, nao recusa-la. A guarda anterior fazia o oposto, e como retornava sem
// registrar a tentativa, a diferenca so crescia -- o no nunca mais tentava.
void test_espera_longa_libera_em_vez_de_bloquear(void) {
  Backoff backoff(1000, 300000);
  backoff.recordAttempt(1000);

  TEST_ASSERT_TRUE(backoff.ready(1000 + 7199000));
  TEST_ASSERT_TRUE(backoff.ready(1000 + 86400000));
}

// O segundo bug: comparar instantes em vez da diferenca para de valer quando millis()
// da a volta, aos ~49,7 dias. Um no em campo passa por isso.
void test_volta_do_contador_de_millis(void) {
  Backoff backoff(1000, 300000);
  const uint32_t antes_da_volta = 0xFFFFFF00u;

  backoff.recordAttempt(antes_da_volta);

  // 0xFFFFFF00 + 1000 da a volta e vira um numero pequeno. A comparacao ingenua
  // `now < next` bloquearia por outros 49,7 dias; a diferenca sem sinal nao.
  TEST_ASSERT_FALSE(backoff.ready(antes_da_volta + 500));
  TEST_ASSERT_TRUE(backoff.ready(antes_da_volta + 2000));
}

// ----- reconstrucao da fila -----

QueueState derive(const char *mapa) {
  static bool occupied[16];
  const uint32_t capacity = static_cast<uint32_t>(strlen(mapa));
  for (uint32_t i = 0; i < capacity; ++i) {
    occupied[i] = mapa[i] == 'x';
  }
  return deriveQueueState(occupied, capacity);
}

void test_fila_vazia(void) {
  const QueueState state = derive("........");

  TEST_ASSERT_EQUAL_UINT32(0, state.head);
  TEST_ASSERT_EQUAL_UINT32(0, state.count);
}

void test_fila_contigua(void) {
  const QueueState state = derive("..xxx...");

  TEST_ASSERT_EQUAL_UINT32(2, state.head);
  TEST_ASSERT_EQUAL_UINT32(3, state.count);
  TEST_ASSERT_EQUAL_UINT32(0, state.orphaned);
}

// O caso que a deducao anterior errava em silencio. Slots 6, 7, 0 e 1 ocupados: ela
// concluia cabeca 0 e contagem 4, reivindicando 0 a 3 -- descartando 2 e 3 como
// ilegiveis e deixando as duas mensagens mais antigas orfas no flash.
void test_anel_que_deu_a_volta(void) {
  const QueueState state = derive("xx....xx");

  TEST_ASSERT_EQUAL_UINT32(6, state.head);
  TEST_ASSERT_EQUAL_UINT32(4, state.count);
  TEST_ASSERT_EQUAL_UINT32(0, state.orphaned);
}

void test_anel_cheio(void) {
  const QueueState state = derive("xxxxxxxx");

  // Sem lacuna nao ha como saber onde a fila comeca; assume zero e mantem todas, o que
  // e melhor do que descartar.
  TEST_ASSERT_EQUAL_UINT32(0, state.head);
  TEST_ASSERT_EQUAL_UINT32(8, state.count);
}

void test_uma_unica_mensagem(void) {
  const QueueState state = derive(".....x..");

  TEST_ASSERT_EQUAL_UINT32(5, state.head);
  TEST_ASSERT_EQUAL_UINT32(1, state.count);
}

// Uma queda de energia no meio de uma escrita pode deixar o anel com mais de um trecho.
// Fica com o maior e reporta o resto como orfao, para que a recuperacao os apague --
// mante-los faria a contagem crescer a cada boot.
void test_estado_inconsistente_fica_com_o_maior_trecho(void) {
  const QueueState state = derive("x..xxx..");

  TEST_ASSERT_EQUAL_UINT32(3, state.head);
  TEST_ASSERT_EQUAL_UINT32(3, state.count);
  TEST_ASSERT_EQUAL_UINT32(1, state.orphaned);
}

void test_trecho_que_da_a_volta_vence_o_contiguo(void) {
  // Trecho que da a volta tem 4 (slots 6,7,0,1); o contiguo no meio tem 2.
  const QueueState state = derive("xx.xx.xx");

  TEST_ASSERT_EQUAL_UINT32(6, state.head);
  TEST_ASSERT_EQUAL_UINT32(4, state.count);
  TEST_ASSERT_EQUAL_UINT32(2, state.orphaned);
}

void test_entrada_invalida(void) {
  const QueueState state = deriveQueueState(nullptr, 8);

  TEST_ASSERT_EQUAL_UINT32(0, state.count);
}

}  // namespace

void setUp(void) {}
void tearDown(void) {}

int main(int, char **) {
  UNITY_BEGIN();
  RUN_TEST(test_primeira_tentativa_e_imediata);
  RUN_TEST(test_recuo_dobra_ate_o_teto);
  RUN_TEST(test_espera_o_intervalo);
  RUN_TEST(test_sucesso_volta_ao_minimo);
  RUN_TEST(test_espera_longa_libera_em_vez_de_bloquear);
  RUN_TEST(test_volta_do_contador_de_millis);
  RUN_TEST(test_fila_vazia);
  RUN_TEST(test_fila_contigua);
  RUN_TEST(test_anel_que_deu_a_volta);
  RUN_TEST(test_anel_cheio);
  RUN_TEST(test_uma_unica_mensagem);
  RUN_TEST(test_estado_inconsistente_fica_com_o_maior_trecho);
  RUN_TEST(test_trecho_que_da_a_volta_vence_o_contiguo);
  RUN_TEST(test_entrada_invalida);
  return UNITY_END();
}
