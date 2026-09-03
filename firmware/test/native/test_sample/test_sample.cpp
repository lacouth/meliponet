// Verifica a decisao mais facil de errar do firmware: o que entra na mensagem, o que e
// omitido, e quais flags acendem.
//
// O erro aqui nao trava nada -- ele produz uma serie plausivel porem errada, que so
// seria notada semanas depois olhando o banco. Dai o teste.

#include <string.h>
#include <unity.h>

#include "Sample.h"
#include "TelemetryCodec.h"

using namespace meliponet;

namespace {

SampleContext context() {
  SampleContext ctx;
  ctx.node_id = "A4C13800";
  ctx.seq = 42;
  ctx.timestamp = "2027-03-14T12:05:00Z";
  return ctx;
}

SensorSnapshot healthy() {
  SensorSnapshot s;
  s.temp_in = Reading::ok(30.12);
  s.rh_in = Reading::ok(68.4);
  s.temp_out = Reading::ok(34.8);
  s.rh_out = Reading::ok(41.2);
  s.weight = Reading::ok(12.483);
  s.battery = Reading::ok(3.92);
  s.rssi = -58;
  s.rssi_valid = true;
  return s;
}

void test_leitura_completa(void) {
  const Telemetry t = meliponet::buildTelemetry(context(), healthy());

  TEST_ASSERT_EQUAL_INT32(3012, t.temp_in_c);
  TEST_ASSERT_EQUAL_INT32(12483, t.weight_kg);
  TEST_ASSERT_TRUE(has(t.present, Field::temp_out_c));
  // Nenhuma flag: todos os sensores responderam e a bateria esta boa.
  TEST_ASSERT_TRUE(t.flags == Flag::none);
}

// O caso central: sensor que falhou nao vira zero.
void test_sensor_externo_ausente_omite_campos_e_liga_flag(void) {
  SensorSnapshot sensors = healthy();
  sensors.temp_out = Reading::fault();
  sensors.rh_out = Reading::fault();

  const Telemetry t = meliponet::buildTelemetry(context(), sensors);

  TEST_ASSERT_FALSE(has(t.present, Field::temp_out_c));
  TEST_ASSERT_FALSE(has(t.present, Field::rh_out_pct));
  TEST_ASSERT_TRUE(has(t.flags, Flag::sht_out_fault));
  // O sensor interno continua intacto: a falha de um nao contamina o outro.
  TEST_ASSERT_TRUE(has(t.present, Field::temp_in_c));
  TEST_ASSERT_FALSE(has(t.flags, Flag::sht_in_fault));

  // E a mensagem serializada de fato nao carrega o campo.
  char buffer[meliponet::kMaxTelemetryJson];
  meliponet::encode(t, buffer, sizeof(buffer));
  TEST_ASSERT_NULL(strstr(buffer, "temp_out_c"));
  TEST_ASSERT_NOT_NULL(strstr(buffer, "\"sht_out_fault\""));
}

// Um SHT30 mede temperatura e umidade no mesmo chip: meia leitura significa chip com
// problema, e o campo bom tambem e descartado por nao ser confiavel sozinho.
void test_meia_leitura_do_sht_liga_a_flag(void) {
  SensorSnapshot sensors = healthy();
  sensors.rh_in = Reading::fault();

  const Telemetry t = meliponet::buildTelemetry(context(), sensors);

  TEST_ASSERT_TRUE(has(t.flags, Flag::sht_in_fault));
}

// Leitura fisicamente impossivel e tratada como falha de sensor, nao enviada.
void test_leitura_absurda_e_descartada(void) {
  SensorSnapshot sensors = healthy();
  sensors.temp_in = Reading::ok(230.0);  // nenhum SHT30 são produz isso

  const Telemetry t = meliponet::buildTelemetry(context(), sensors);

  TEST_ASSERT_FALSE(has(t.present, Field::temp_in_c));
  TEST_ASSERT_TRUE(has(t.flags, Flag::sht_in_fault));
}

void test_bateria_baixa(void) {
  SensorSnapshot sensors = healthy();
  sensors.battery = Reading::ok(3.41);

  const Telemetry t = meliponet::buildTelemetry(context(), sensors);

  TEST_ASSERT_TRUE(has(t.flags, Flag::low_batt));
  // O valor continua sendo enviado: a flag qualifica a leitura, não a substitui.
  TEST_ASSERT_TRUE(has(t.present, Field::vbat_v));
  TEST_ASSERT_EQUAL_INT32(341, t.vbat_v);
}

void test_relogio_nao_sincronizado_e_reenvio(void) {
  SampleContext ctx = context();
  ctx.clock_synced = false;
  ctx.from_spool = true;

  const Telemetry t = meliponet::buildTelemetry(ctx, healthy());

  TEST_ASSERT_TRUE(has(t.flags, Flag::clock_unsynced));
  TEST_ASSERT_TRUE(has(t.flags, Flag::spooled));
}

// Um HX711 desconectado nao pode virar "a colmeia pesa 0 kg" -- isso dispararia o
// alerta de queda abrupta de peso e mandaria o meliponicultor ao meliponario a toa.
void test_celula_de_carga_desconectada(void) {
  SensorSnapshot sensors = healthy();
  sensors.weight = Reading::fault();

  const Telemetry t = meliponet::buildTelemetry(context(), sensors);

  TEST_ASSERT_FALSE(has(t.present, Field::weight_kg));
  TEST_ASSERT_TRUE(has(t.flags, Flag::hx711_fault));
}

// Sem WiFi associado nao ha RSSI; o campo e opcional no contrato justamente por isso.
void test_rssi_ausente(void) {
  SensorSnapshot sensors = healthy();
  sensors.rssi_valid = false;

  const Telemetry t = meliponet::buildTelemetry(context(), sensors);

  TEST_ASSERT_FALSE(has(t.present, Field::rssi));
}

// A mensagem montada precisa ser serializavel: a montagem e o codec sao peças
// diferentes, e nada garante que combinam a nao ser um teste que use as duas.
void test_mensagem_montada_serializa(void) {
  const Telemetry t = meliponet::buildTelemetry(context(), healthy());

  char buffer[meliponet::kMaxTelemetryJson];
  const size_t written = meliponet::encode(t, buffer, sizeof(buffer));

  TEST_ASSERT_TRUE(written > 0);
  TEST_ASSERT_EQUAL_STRING(
      "{\"schema\":\"meliponet.telemetry.v1\",\"node_id\":\"A4C13800\",\"seq\":42,"
      "\"ts\":\"2027-03-14T12:05:00Z\",\"temp_in_c\":30.12,\"temp_out_c\":34.80,"
      "\"rh_in_pct\":68.40,\"rh_out_pct\":41.20,\"weight_kg\":12.483,\"vbat_v\":3.92,"
      "\"rssi\":-58}",
      buffer);
}

}  // namespace

void setUp(void) {}
void tearDown(void) {}

int main(int, char **) {
  UNITY_BEGIN();
  RUN_TEST(test_leitura_completa);
  RUN_TEST(test_sensor_externo_ausente_omite_campos_e_liga_flag);
  RUN_TEST(test_meia_leitura_do_sht_liga_a_flag);
  RUN_TEST(test_leitura_absurda_e_descartada);
  RUN_TEST(test_bateria_baixa);
  RUN_TEST(test_relogio_nao_sincronizado_e_reenvio);
  RUN_TEST(test_celula_de_carga_desconectada);
  RUN_TEST(test_rssi_ausente);
  RUN_TEST(test_mensagem_montada_serializa);
  return UNITY_END();
}
