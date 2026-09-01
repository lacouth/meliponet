// Verifica que a conversao leitura fisica -> inteiro escalado do firmware reproduz a
// regra canonica do contrato.
//
// Este e o par do teste do codec: la se verifica a serializacao, aqui a quantizacao.
// Juntos, cobrem todo o caminho do float lido do sensor ate os bytes que saem no ar.

#include <math.h>
#include <string.h>
#include <unity.h>

#include "Scaling.h"
#include "vectors.h"

using meliponet::Scale;
using meliponet::Scaled;
using meliponet::testdata::kScalingVectorCount;
using meliponet::testdata::kScalingVectors;

namespace {

void test_vetores_de_escala(void) {
  for (size_t i = 0; i < kScalingVectorCount; ++i) {
    const auto &vector = kScalingVectors[i];
    const Scaled result = meliponet::scale(vector.reading, vector.unit);

    TEST_ASSERT_TRUE_MESSAGE(result.ok, vector.field);
    TEST_ASSERT_EQUAL_INT32_MESSAGE(vector.expected, result.value, vector.field);
  }
}

// NaN e infinito nao podem virar um numero plausivel no banco. Um sensor com defeito
// eletrico produz exatamente esse tipo de leitura.
void test_valores_nao_finitos_sao_recusados(void) {
  TEST_ASSERT_FALSE(meliponet::scale(NAN, Scale::Temperature).ok);
  TEST_ASSERT_FALSE(meliponet::scale(INFINITY, Scale::Temperature).ok);
  TEST_ASSERT_FALSE(meliponet::scale(-INFINITY, Scale::Weight).ok);
}

// Converter um double fora da faixa de int32_t e comportamento indefinido em C++; a
// checagem tem de acontecer antes da conversao.
void test_estouro_de_faixa_e_recusado(void) {
  TEST_ASSERT_FALSE(meliponet::scale(1e12, Scale::Weight).ok);
  TEST_ASSERT_FALSE(meliponet::scale(-1e12, Scale::Weight).ok);
}

void test_faixa_do_sensor(void) {
  // Dentro da faixa do SHT30.
  TEST_ASSERT_TRUE(meliponet::scaleInRange(30.0, Scale::Temperature, -40.0, 85.0).ok);
  // Fora: nenhum SHT30 são produz isso.
  TEST_ASSERT_FALSE(meliponet::scaleInRange(120.0, Scale::Temperature, -40.0, 85.0).ok);
  TEST_ASSERT_FALSE(meliponet::scaleInRange(-60.0, Scale::Temperature, -40.0, 85.0).ok);
  // Os limites são inclusivos.
  TEST_ASSERT_TRUE(meliponet::scaleInRange(85.0, Scale::Temperature, -40.0, 85.0).ok);
}

// Peso levemente negativo por deriva de tara e aceito: descartar aqui esconderia a
// deriva, que a curadoria precisa poder detectar.
void test_peso_negativo_por_deriva_e_aceito(void) {
  const Scaled result = meliponet::scaleInRange(-0.012, Scale::Weight, -5.0, 100.0);

  TEST_ASSERT_TRUE(result.ok);
  TEST_ASSERT_EQUAL_INT32(-12, result.value);
}

}  // namespace

void setUp(void) {}
void tearDown(void) {}

int main(int, char **) {
  UNITY_BEGIN();
  RUN_TEST(test_vetores_de_escala);
  RUN_TEST(test_valores_nao_finitos_sao_recusados);
  RUN_TEST(test_estouro_de_faixa_e_recusado);
  RUN_TEST(test_faixa_do_sensor);
  RUN_TEST(test_peso_negativo_por_deriva_e_aceito);
  return UNITY_END();
}
