// Verifica a decisao mais facil de errar do firmware: o que entra na mensagem, o que e
// omitido, e quais flags acendem.
//
// O erro aqui nao trava nada -- ele produz uma serie plausivel porem errada, que so
// seria notada semanas depois olhando o banco. Dai o teste.

#include <string.h>
#include <unity.h>

#include "Amostra.h"
#include "Telemetria.h"

using namespace meliponet;

namespace {

ContextoDaAmostra contexto() {
  ContextoDaAmostra ctx;
  ctx.node_id = "A4C13800";
  ctx.seq = 42;
  ctx.ts = "2027-03-14T12:05:00Z";
  return ctx;
}

LeiturasDosSensores tudoSadio() {
  LeiturasDosSensores s;
  s.temp_int = Leitura::obtida(30.12);
  s.ur_int = Leitura::obtida(68.4);
  s.temp_ext = Leitura::obtida(34.8);
  s.ur_ext = Leitura::obtida(41.2);
  s.peso = Leitura::obtida(12.483);
  s.bateria = Leitura::obtida(3.92);
  s.rssi = -58;
  s.rssi_valido = true;
  return s;
}

void test_leitura_completa(void) {
  const Telemetria t = meliponet::montarTelemetria(contexto(), tudoSadio());

  TEST_ASSERT_EQUAL_INT32(3012, t.temp_in_c);
  TEST_ASSERT_EQUAL_INT32(12483, t.weight_kg);
  TEST_ASSERT_TRUE(contem(t.presentes, Campo::temp_out_c));
  // Nenhuma flag: todos os sensores responderam e a bateria esta boa.
  TEST_ASSERT_TRUE(t.flags == Flag::nenhuma);
}

// O caso central: sensor que falhou nao vira zero.
void test_sensor_externo_ausente_omite_campos_e_liga_flag(void) {
  LeiturasDosSensores sensores = tudoSadio();
  sensores.temp_ext = Leitura::falha();
  sensores.ur_ext = Leitura::falha();

  const Telemetria t = meliponet::montarTelemetria(contexto(), sensores);

  TEST_ASSERT_FALSE(contem(t.presentes, Campo::temp_out_c));
  TEST_ASSERT_FALSE(contem(t.presentes, Campo::rh_out_pct));
  TEST_ASSERT_TRUE(contem(t.flags, Flag::sht_out_fault));
  // O sensor interno continua intacto: a falha de um nao contamina o outro.
  TEST_ASSERT_TRUE(contem(t.presentes, Campo::temp_in_c));
  TEST_ASSERT_FALSE(contem(t.flags, Flag::sht_in_fault));

  // E a mensagem serializada de fato nao carrega o campo.
  char buffer[meliponet::kTamanhoMaximoDoJson];
  meliponet::serializar(t, buffer, sizeof(buffer));
  TEST_ASSERT_NULL(strstr(buffer, "temp_out_c"));
  TEST_ASSERT_NOT_NULL(strstr(buffer, "\"sht_out_fault\""));
}

// Um SHT30 mede temperatura e umidade no mesmo chip: meia leitura significa chip com
// problema, e o campo bom tambem e descartado por nao ser confiavel sozinho.
void test_meia_leitura_do_sht_liga_a_flag(void) {
  LeiturasDosSensores sensores = tudoSadio();
  sensores.ur_int = Leitura::falha();

  const Telemetria t = meliponet::montarTelemetria(contexto(), sensores);

  TEST_ASSERT_TRUE(contem(t.flags, Flag::sht_in_fault));
}

// Leitura fisicamente impossivel e tratada como falha de sensor, nao enviada.
void test_leitura_absurda_e_descartada(void) {
  LeiturasDosSensores sensores = tudoSadio();
  sensores.temp_int = Leitura::obtida(230.0);  // nenhum SHT30 são produz isso

  const Telemetria t = meliponet::montarTelemetria(contexto(), sensores);

  TEST_ASSERT_FALSE(contem(t.presentes, Campo::temp_in_c));
  TEST_ASSERT_TRUE(contem(t.flags, Flag::sht_in_fault));
}

void test_bateria_baixa(void) {
  LeiturasDosSensores sensores = tudoSadio();
  sensores.bateria = Leitura::obtida(3.41);

  const Telemetria t = meliponet::montarTelemetria(contexto(), sensores);

  TEST_ASSERT_TRUE(contem(t.flags, Flag::low_batt));
  // O valor continua sendo enviado: a flag qualifica a leitura, não a substitui.
  TEST_ASSERT_TRUE(contem(t.presentes, Campo::vbat_v));
  TEST_ASSERT_EQUAL_INT32(341, t.vbat_v);
}

void test_relogio_nao_sincronizado_e_reenvio(void) {
  ContextoDaAmostra ctx = contexto();
  ctx.relogio_sincronizado = false;
  ctx.veio_do_spool = true;

  const Telemetria t = meliponet::montarTelemetria(ctx, tudoSadio());

  TEST_ASSERT_TRUE(contem(t.flags, Flag::clock_unsynced));
  TEST_ASSERT_TRUE(contem(t.flags, Flag::spooled));
}

// Um HX711 desconectado nao pode virar "a colmeia pesa 0 kg" -- isso dispararia o
// alerta de queda abrupta de peso e mandaria o meliponicultor ao meliponario a toa.
void test_celula_de_carga_desconectada(void) {
  LeiturasDosSensores sensores = tudoSadio();
  sensores.peso = Leitura::falha();

  const Telemetria t = meliponet::montarTelemetria(contexto(), sensores);

  TEST_ASSERT_FALSE(contem(t.presentes, Campo::weight_kg));
  TEST_ASSERT_TRUE(contem(t.flags, Flag::hx711_fault));
}

// Sem WiFi associado nao ha RSSI; o campo e opcional no contrato justamente por isso.
void test_rssi_ausente(void) {
  LeiturasDosSensores sensores = tudoSadio();
  sensores.rssi_valido = false;

  const Telemetria t = meliponet::montarTelemetria(contexto(), sensores);

  TEST_ASSERT_FALSE(contem(t.presentes, Campo::rssi));
}

// A mensagem montada precisa ser serializavel: a montagem e o codec sao peças
// diferentes, e nada garante que combinam a nao ser um teste que use as duas.
void test_mensagem_montada_serializa(void) {
  const Telemetria t = meliponet::montarTelemetria(contexto(), tudoSadio());

  char buffer[meliponet::kTamanhoMaximoDoJson];
  const size_t escritos = meliponet::serializar(t, buffer, sizeof(buffer));

  TEST_ASSERT_TRUE(escritos > 0);
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
