// Calibracao da celula de carga e politica de tempo do ciclo.

#include <unity.h>

#include "Calibration.h"
#include "Scheduler.h"

using meliponet::calibrate;
using meliponet::LoadCellCalibration;
using meliponet::Scheduler;
using meliponet::toKilograms;
using meliponet::Weight;

namespace {

void test_conversao_de_peso(void) {
  // 20 000 contagens de tara, 8 000 contagens por quilo.
  const LoadCellCalibration cal{20000, 8000.0};

  TEST_ASSERT_EQUAL_INT32(0, static_cast<int32_t>(toKilograms(20000, cal).kilograms));
  TEST_ASSERT_TRUE(toKilograms(120000, cal).ok);
  // 120 000 - 20 000 = 100 000 contagens / 8 000 = 12,5 kg
  TEST_ASSERT_EQUAL_INT32(12500,
                          static_cast<int32_t>(toKilograms(120000, cal).kilograms * 1000));
}

// Calibracao ausente ou corrompida na NVS nao pode virar um peso inventado.
void test_calibracao_invalida_recusa(void) {
  TEST_ASSERT_FALSE(toKilograms(1000, LoadCellCalibration{}).ok);
  TEST_ASSERT_FALSE(toKilograms(1000, LoadCellCalibration{0, 0.0}).ok);
  TEST_ASSERT_FALSE(toKilograms(1000, LoadCellCalibration{0, -8000.0}).ok);
}

void test_calculo_da_calibracao(void) {
  // Vazia em 20 000; com 5 kg padrao, 60 000. Logo 8 000 contagens por quilo.
  const LoadCellCalibration cal = calibrate(20000, 60000, 5.0);

  TEST_ASSERT_TRUE(cal.valid());
  TEST_ASSERT_EQUAL_INT32(20000, cal.offset);
  TEST_ASSERT_EQUAL_INT32(8000, static_cast<int32_t>(cal.counts_per_kg));
}

// Celula desconectada da a mesma contagem com e sem massa. Sem esta checagem seria uma
// divisao por zero.
void test_celula_desconectada_na_calibracao(void) {
  TEST_ASSERT_FALSE(calibrate(20000, 20000, 5.0).valid());
  TEST_ASSERT_FALSE(calibrate(20000, 60000, 0.0).valid());
  TEST_ASSERT_FALSE(calibrate(20000, 60000, -5.0).valid());
}

// Contagem menor com massa aplicada significa celula invertida. Aceitar produziria
// pesos negativos crescentes durante toda a coleta.
void test_celula_invertida_e_recusada(void) {
  TEST_ASSERT_FALSE(calibrate(60000, 20000, 5.0).valid());
}

// A subtracao em 64 bits protege contra o estouro entre extremos da faixa de int32_t.
void test_extremos_da_faixa_nao_estouram(void) {
  const LoadCellCalibration cal{-2000000000, 8000.0};
  const Weight w = toKilograms(2000000000, cal);

  TEST_ASSERT_TRUE(w.ok);
  TEST_ASSERT_TRUE(w.kilograms > 0.0);
}

void test_agendamento(void) {
  Scheduler scheduler;
  scheduler.begin(300000, 1000);  // 5 min, iniciada em t=1s

  TEST_ASSERT_FALSE(scheduler.due(1000));
  TEST_ASSERT_FALSE(scheduler.due(300999));
  TEST_ASSERT_TRUE(scheduler.due(301000));

  scheduler.mark(301000);
  TEST_ASSERT_FALSE(scheduler.due(301000));
  TEST_ASSERT_EQUAL_UINT32(300000, scheduler.remaining(301000));
}

// O caso que justifica o teste: millis() volta a zero a cada ~49,7 dias, e um nó em
// campo passa por isso. A forma ingênua (`now > next`) travaria a amostragem para
// sempre; a subtração sem sinal atravessa a volta.
void test_volta_do_contador_de_millis(void) {
  const uint32_t quase_no_fim = 0xFFFFFF00u;
  Scheduler scheduler;
  scheduler.begin(1000, quase_no_fim);

  TEST_ASSERT_FALSE(scheduler.due(quase_no_fim + 500));
  // 0xFFFFFF00 + 1000 dá a volta e vira 0x000002E8.
  TEST_ASSERT_TRUE(scheduler.due(quase_no_fim + 1000));
  TEST_ASSERT_TRUE(scheduler.due(0x00000300u));
}

}  // namespace

void setUp(void) {}
void tearDown(void) {}

int main(int, char **) {
  UNITY_BEGIN();
  RUN_TEST(test_conversao_de_peso);
  RUN_TEST(test_calibracao_invalida_recusa);
  RUN_TEST(test_calculo_da_calibracao);
  RUN_TEST(test_celula_desconectada_na_calibracao);
  RUN_TEST(test_celula_invertida_e_recusada);
  RUN_TEST(test_extremos_da_faixa_nao_estouram);
  RUN_TEST(test_agendamento);
  RUN_TEST(test_volta_do_contador_de_millis);
  return UNITY_END();
}
