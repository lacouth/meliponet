// MelipoSense -- firmware do no sensor.
//
// Fase 3 (prototipo): le os dois SHT30 e a celula de carga e publica a telemetria
// direto no broker MQTT por WiFi, no mesmo topico e formato que o gateway LoRa usara na
// Fase 5.
//
// Este arquivo so **orquestra**. Ele nao sabe converter uma leitura em inteiro escalado,
// nem decidir qual flag acender, nem gerir a fila do spool -- essas decisoes moram em
// lib/, sem dependencia do Arduino, e sao exercitadas por `pio test -e native` no PC.
// A separacao nao e estetica: e o que permite testar as decisoes dificeis sem ter o
// hardware na mao, e sem esperar dias por uma queda de rede real.

#include <Arduino.h>

#include "Calibration.h"
#include "Config.h"
#include "LittleFsSpoolStorage.h"
#include "LoadCell.h"
#include "MqttPublisher.h"
#include "Sample.h"
#include "Scheduler.h"
#include "ShtPair.h"
#include "Spool.h"
#include "TelemetryCodec.h"
#include "WifiLink.h"

namespace {

// Pinos. Ajuste conforme a placa do lote.
constexpr int kI2cSda = 6;
constexpr int kI2cScl = 7;
constexpr int kHx711Data = 4;
constexpr int kHx711Clock = 5;
constexpr int kBatteryAdc = 0;

// O divisor resistivo da bateria: 2 x 100 kOhm, entao a tensao lida e metade da real.
constexpr double kBatteryDivider = 2.0;
constexpr double kAdcReferenceV = 3.3;
constexpr double kAdcMaxCount = 4095.0;

meliponet::Config g_config;
meliponet::ShtPair g_sht;
meliponet::LoadCell g_load_cell;
meliponet::WifiLink g_wifi;
meliponet::MqttPublisher g_mqtt;
meliponet::LittleFsSpoolStorage g_storage;
meliponet::Spool *g_spool = nullptr;
meliponet::Scheduler *g_scheduler = nullptr;

meliponet::Reading readBattery() {
  const int raw = analogRead(kBatteryAdc);
  if (raw <= 0) {
    return meliponet::Reading::fault();
  }
  return meliponet::Reading::ok((raw / kAdcMaxCount) * kAdcReferenceV * kBatteryDivider);
}

// Tenta publicar; se falhar, guarda no spool. Nunca descarta em silencio.
void publishOrSpool(const char *payload, size_t length) {
  if (g_mqtt.publish(payload, length)) {
    return;
  }
  if (!g_spool->push(payload, length)) {
    Serial.println("[erro] falha ao guardar no spool; medicao perdida");
  } else {
    Serial.printf("[spool] guardada; %u pendentes\n",
                  static_cast<unsigned>(g_spool->size()));
  }
}

// Drena o spool, uma mensagem por vez. Uma por chamada, e nao todas de uma vez, para
// nao segurar o laco principal por minutos apos uma queda longa -- o que atrasaria a
// proxima amostragem e criaria uma lacuna nova enquanto se recupera da antiga.
void drainSpool() {
  if (g_spool->empty() || !g_mqtt.connected()) {
    return;
  }

  char buffer[meliponet::kMaxTelemetryJson];
  const size_t length = g_spool->peek(buffer, sizeof(buffer));
  if (length == 0) {
    g_spool->pop();  // entrada ilegivel: descarta para nao travar a fila
    return;
  }

  // So remove depois da confirmacao: remover antes perderia a mensagem se a publicacao
  // falhasse, que e justamente o cenario em que o spool existe.
  if (g_mqtt.publish(buffer, length)) {
    g_spool->pop();
  }
}

void sample() {
  const meliponet::ShtReadings sht = g_sht.read();

  meliponet::SensorSnapshot sensors;
  sensors.temp_in = sht.temp_in;
  sensors.rh_in = sht.rh_in;
  sensors.temp_out = sht.temp_out;
  sensors.rh_out = sht.rh_out;
  sensors.weight = g_load_cell.read();
  sensors.battery = readBattery();
  sensors.rssi_valid = g_wifi.rssi(sensors.rssi);

  const char *timestamp = g_wifi.timestamp();
  if (timestamp == nullptr) {
    // Sem relogio confiavel nao ha o que gravar: um `ts` inventado poluiria a serie de
    // forma difícil de desfazer depois. Melhor pular esta amostra e tentar sincronizar.
    Serial.println("[aviso] relogio nao sincronizado; amostra descartada");
    g_wifi.syncClock();
    return;
  }

  meliponet::SampleContext context;
  context.node_id = meliponet::nodeId();
  context.seq = meliponet::nextSequence();
  context.timestamp = timestamp;
  context.clock_synced = g_wifi.clockSynced();

  const meliponet::Telemetry telemetry = meliponet::buildTelemetry(context, sensors);

  char payload[meliponet::kMaxTelemetryJson];
  const size_t length = meliponet::encode(telemetry, payload, sizeof(payload));
  if (length == 0) {
    Serial.println("[erro] telemetria nao coube no buffer");
    return;
  }

  Serial.printf("[amostra] %s\n", payload);
  publishOrSpool(payload, length);
}

// Console serial de preparacao do dispositivo. E por aqui que as credenciais entram na
// NVS, em vez de irem no codigo-fonte.
void handleSerial() {
  if (!Serial.available()) {
    return;
  }
  String line = Serial.readStringUntil('\n');
  line.trim();

  if (line.startsWith("wifi ")) {
    const int space = line.indexOf(' ', 5);
    if (space < 0) {
      Serial.println("uso: wifi <ssid> <senha>");
      return;
    }
    strncpy(g_config.wifi_ssid, line.substring(5, space).c_str(), meliponet::kMaxSsidLength - 1);
    strncpy(g_config.wifi_password, line.substring(space + 1).c_str(),
            meliponet::kMaxPasswordLength - 1);
    meliponet::saveConfig(g_config);
    Serial.println("wifi gravado; reinicie");

  } else if (line.startsWith("broker ")) {
    strncpy(g_config.mqtt_host, line.substring(7).c_str(), meliponet::kMaxHostLength - 1);
    meliponet::saveConfig(g_config);
    Serial.println("broker gravado; reinicie");

  } else if (line == "tara") {
    int32_t raw = 0;
    if (!g_load_cell.readRaw(raw)) {
      Serial.println("HX711 nao respondeu");
      return;
    }
    g_config.calibration.offset = raw;
    meliponet::saveConfig(g_config);
    Serial.printf("tara = %ld\n", static_cast<long>(raw));

  } else if (line.startsWith("calibrar ")) {
    // Uso: coloque uma massa-padrao conhecida e mande `calibrar <kg>`.
    // Verifique depois em varios pontos da faixa, e nao so neste: um ponto so ajusta a
    // escala e esconde a nao-linearidade da celula.
    const double known_kg = line.substring(9).toDouble();
    int32_t raw = 0;
    if (!g_load_cell.readRaw(raw)) {
      Serial.println("HX711 nao respondeu");
      return;
    }
    const meliponet::LoadCellCalibration cal =
        meliponet::calibrate(g_config.calibration.offset, raw, known_kg);
    if (!cal.valid()) {
      Serial.println("calibracao invalida: confira a massa e a ligacao da celula");
      return;
    }
    g_config.calibration = cal;
    g_load_cell.setCalibration(cal);
    meliponet::saveConfig(g_config);
    Serial.printf("escala = %.2f contagens/kg\n", cal.counts_per_kg);

  } else if (line == "estado") {
    Serial.printf("no        %s\n", meliponet::nodeId());
    Serial.printf("wifi      %s\n", g_wifi.connected() ? "conectado" : "desconectado");
    Serial.printf("broker    %s\n", g_mqtt.connected() ? "conectado" : "desconectado");
    Serial.printf("relogio   %s\n", g_wifi.clockSynced() ? "sincronizado" : "NAO sincronizado");
    Serial.printf("sht int   %s\n", g_sht.insidePresent() ? "ok" : "ausente");
    Serial.printf("sht ext   %s\n", g_sht.outsidePresent() ? "ok" : "ausente");
    Serial.printf("calibrac. %s\n", g_config.calibration.valid() ? "ok" : "AUSENTE");
    Serial.printf("spool     %u pendentes, %u descartadas\n",
                  static_cast<unsigned>(g_spool->size()),
                  static_cast<unsigned>(g_spool->dropped()));

  } else if (line == "ajuda" || line == "?") {
    Serial.println("wifi <ssid> <senha> | broker <host> | tara | calibrar <kg> | estado");
  }
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.printf("\nMelipoSense %s\n", meliponet::nodeId());

  g_config = meliponet::loadConfig();

  uint32_t head = 0;
  uint32_t count = 0;
  static meliponet::Spool spool(g_storage);
  g_spool = &spool;
  if (g_storage.begin(head, count)) {
    // Restaura a fila do reinicio: mensagens guardadas antes de uma queda de energia
    // continuam pendentes, em vez de virarem lacuna.
    g_spool->restore(head, count);
    Serial.printf("[spool] %u mensagens recuperadas\n", static_cast<unsigned>(count));
  }

  static meliponet::Scheduler scheduler(g_config.sample_interval_s * 1000UL, millis());
  g_scheduler = &scheduler;

  if (!g_sht.begin(kI2cSda, kI2cScl)) {
    Serial.println("[aviso] nenhum SHT30 respondeu");
  }
  if (!g_load_cell.begin(kHx711Data, kHx711Clock, g_config.calibration)) {
    Serial.println("[aviso] HX711 nao respondeu");
  }
  if (!g_config.calibration.valid()) {
    Serial.println("[aviso] celula sem calibracao: use `tara` e `calibrar <kg>`");
  }

  if (!g_config.usable()) {
    // Sem credenciais nao ha o que tentar. Ficar em laco de reconexao gastaria bateria
    // sem chance de sucesso; melhor esperar a configuracao pelo serial.
    Serial.println("[config] sem wifi ou broker; use `wifi` e `broker`. `ajuda` lista tudo.");
    return;
  }

  if (g_wifi.begin(g_config.wifi_ssid, g_config.wifi_password)) {
    g_wifi.syncClock();
    g_mqtt.begin(meliponet::nodeId(), g_config.mqtt_host, g_config.mqtt_port,
                 g_config.mqtt_username, g_config.mqtt_password);
  }
}

void loop() {
  handleSerial();

  if (!g_config.usable() || g_scheduler == nullptr) {
    delay(100);
    return;
  }

  const uint32_t now = millis();
  g_wifi.maintain(now);
  g_mqtt.maintain(now);
  g_mqtt.loop();

  if (g_wifi.connected() && !g_wifi.clockSynced()) {
    g_wifi.syncClock();
  }

  if (g_scheduler->due(now)) {
    g_scheduler->mark(now);
    sample();
  }

  drainSpool();
  delay(50);
}
