// Verifica que o codec C++ reproduz, byte a byte, os vetores dourados gerados pelo
// lado Python em contracts/testdata/vectors.h.
//
// Este e o teste que impede o firmware e a plataforma de divergirem. Ele roda no PC
// (`pio test -e native`), sem hardware, e portanto pode ficar no CI.

#include <string.h>
#include <unity.h>

#include "Telemetria.h"
#include "vectors.h"

using namespace meliponet;
using namespace meliponet::testdata;

namespace {

void test_vetores_dourados(void) {
  char buffer[meliponet::kTamanhoMaximoDoJson];

  for (size_t i = 0; i < kQuantidadeDeVetores; ++i) {
    const auto &vetor = kVetores[i];
    const size_t escritos = meliponet::serializar(vetor.telemetria, buffer, sizeof(buffer));

    TEST_ASSERT_EQUAL_size_t_MESSAGE(strlen(vetor.json_esperado), escritos, vetor.nome);
    TEST_ASSERT_EQUAL_STRING_MESSAGE(vetor.json_esperado, buffer, vetor.nome);
  }
}

// Um buffer pequeno demais precisa devolver 0 e string vazia. Emitir um JSON truncado
// seria pior: o ingestor o rejeitaria como malformado, sem indicacao de que a causa
// foi o buffer do no.
void test_buffer_insuficiente(void) {
  char buffer[16];
  const size_t escritos = meliponet::serializar(kVetores[0].telemetria, buffer, sizeof(buffer));

  TEST_ASSERT_EQUAL_size_t(0, escritos);
  TEST_ASSERT_EQUAL_STRING("", buffer);
}

// Campo ausente do bitmask de presenca nao pode aparecer no JSON, mesmo que o membro
// da struct tenha valor -- e assim que "sensor com falha" se distingue de "sensor leu
// zero".
void test_campo_ausente_e_omitido(void) {
  Telemetria telemetria{};
  telemetria.node_id = "A4C1380F";
  telemetria.seq = 7;
  telemetria.ts = "2027-03-14T12:00:00Z";
  telemetria.temp_in_c = 3000;
  telemetria.temp_out_c = 9999;  // valor presente na struct, ausente do bitmask
  telemetria.presentes = Campo::temp_in_c;

  char buffer[meliponet::kTamanhoMaximoDoJson];
  meliponet::serializar(telemetria, buffer, sizeof(buffer));

  TEST_ASSERT_NULL(strstr(buffer, "temp_out_c"));
  TEST_ASSERT_NOT_NULL(strstr(buffer, "\"temp_in_c\":30.00"));
}

// A ordem das flags no JSON e a canonica, nao a ordem em que foram atribuidas.
void test_flags_em_ordem_canonica(void) {
  Telemetria telemetria{};
  telemetria.node_id = "A4C1380F";
  telemetria.seq = 8;
  telemetria.ts = "2027-03-14T12:00:00Z";
  telemetria.weight_kg = 1000;
  telemetria.presentes = Campo::weight_kg;
  telemetria.flags = Flag::spooled | Flag::low_batt | Flag::sht_in_fault;

  char buffer[meliponet::kTamanhoMaximoDoJson];
  meliponet::serializar(telemetria, buffer, sizeof(buffer));

  TEST_ASSERT_NOT_NULL(strstr(buffer, "\"flags\":[\"sht_in_fault\",\"low_batt\",\"spooled\"]"));
}

// seq e um uint32_t: a metade alta da faixa nao pode virar numero negativo no JSON.
void test_seq_alto(void) {
  Telemetria telemetria{};
  telemetria.node_id = "A4C1380F";
  telemetria.seq = 4294967295u;
  telemetria.ts = "2027-03-14T12:00:00Z";
  telemetria.weight_kg = 1000;
  telemetria.presentes = Campo::weight_kg;

  char buffer[meliponet::kTamanhoMaximoDoJson];
  meliponet::serializar(telemetria, buffer, sizeof(buffer));

  TEST_ASSERT_NOT_NULL(strstr(buffer, "\"seq\":4294967295"));
}

}  // namespace

void setUp(void) {}
void tearDown(void) {}

int main(int, char **) {
  UNITY_BEGIN();
  RUN_TEST(test_vetores_dourados);
  RUN_TEST(test_buffer_insuficiente);
  RUN_TEST(test_campo_ausente_e_omitido);
  RUN_TEST(test_flags_em_ordem_canonica);
  RUN_TEST(test_seq_alto);
  return UNITY_END();
}
