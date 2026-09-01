// Verifica que o codec C++ reproduz, byte a byte, os vetores dourados gerados pelo
// lado Python em contracts/testdata/vectors.h.
//
// Este e o teste que impede o firmware e a plataforma de divergirem. Ele roda no PC
// (`pio test -e native`), sem hardware, e portanto pode ficar no CI.

#include <string.h>
#include <unity.h>

#include "TelemetryCodec.h"
#include "vectors.h"

using meliponet::Field;
using meliponet::Flag;
using meliponet::Telemetry;
using meliponet::testdata::kVectorCount;
using meliponet::testdata::kVectors;

namespace {

void test_vetores_dourados(void) {
  char buffer[meliponet::kMaxTelemetryJson];

  for (size_t i = 0; i < kVectorCount; ++i) {
    const auto &vector = kVectors[i];
    const size_t written = meliponet::encode(vector.telemetry, buffer, sizeof(buffer));

    TEST_ASSERT_EQUAL_size_t_MESSAGE(strlen(vector.expected_json), written, vector.name);
    TEST_ASSERT_EQUAL_STRING_MESSAGE(vector.expected_json, buffer, vector.name);
  }
}

// Um buffer pequeno demais precisa devolver 0 e string vazia. Emitir um JSON truncado
// seria pior: o ingestor o rejeitaria como malformado, sem indicacao de que a causa
// foi o buffer do no.
void test_buffer_insuficiente(void) {
  char buffer[16];
  const size_t written = meliponet::encode(kVectors[0].telemetry, buffer, sizeof(buffer));

  TEST_ASSERT_EQUAL_size_t(0, written);
  TEST_ASSERT_EQUAL_STRING("", buffer);
}

// Campo ausente do bitmask de presenca nao pode aparecer no JSON, mesmo que o membro
// da struct tenha valor -- e assim que "sensor com falha" se distingue de "sensor leu
// zero".
void test_campo_ausente_e_omitido(void) {
  Telemetry telemetry{};
  telemetry.node_id = "A4C1380F";
  telemetry.seq = 7;
  telemetry.ts = "2027-03-14T12:00:00Z";
  telemetry.temp_in_c = 3000;
  telemetry.temp_out_c = 9999;  // valor presente na struct, ausente do bitmask
  telemetry.present = Field::temp_in_c;

  char buffer[meliponet::kMaxTelemetryJson];
  meliponet::encode(telemetry, buffer, sizeof(buffer));

  TEST_ASSERT_NULL(strstr(buffer, "temp_out_c"));
  TEST_ASSERT_NOT_NULL(strstr(buffer, "\"temp_in_c\":30.00"));
}

// A ordem das flags no JSON e a canonica, nao a ordem em que foram atribuidas.
void test_flags_em_ordem_canonica(void) {
  Telemetry telemetry{};
  telemetry.node_id = "A4C1380F";
  telemetry.seq = 8;
  telemetry.ts = "2027-03-14T12:00:00Z";
  telemetry.weight_kg = 1000;
  telemetry.present = Field::weight_kg;
  telemetry.flags = Flag::spooled | Flag::low_batt | Flag::sht_in_fault;

  char buffer[meliponet::kMaxTelemetryJson];
  meliponet::encode(telemetry, buffer, sizeof(buffer));

  TEST_ASSERT_NOT_NULL(strstr(buffer, "\"flags\":[\"sht_in_fault\",\"low_batt\",\"spooled\"]"));
}

// seq e um uint32_t: a metade alta da faixa nao pode virar numero negativo no JSON.
void test_seq_alto(void) {
  Telemetry telemetry{};
  telemetry.node_id = "A4C1380F";
  telemetry.seq = 4294967295u;
  telemetry.ts = "2027-03-14T12:00:00Z";
  telemetry.weight_kg = 1000;
  telemetry.present = Field::weight_kg;

  char buffer[meliponet::kMaxTelemetryJson];
  meliponet::encode(telemetry, buffer, sizeof(buffer));

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
