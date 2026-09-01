// MelipoSense -- ponto de entrada do firmware do no sensor.
//
// Fase 3 (prototipo): le os dois SHT30 e a celula de carga e publica a telemetria
// direto no broker MQTT por WiFi, no mesmo topico e formato que o gateway LoRa usara
// na Fase 5. O laco principal deliberadamente nao conhece detalhes de hardware -- ele
// so orquestra objetos com a interface begin()/read()/status().

#include <Arduino.h>

void setup() {
  Serial.begin(115200);
  // TODO(Fase 3.1): Config::load() a partir da NVS, ShtPair, LoadCell.
  // TODO(Fase 3.2): WifiLink, sincronizacao NTP, MqttPublisher, Spool.
}

void loop() {
  // TODO(Fase 3.3): Scheduler dispara a amostragem a cada MELIPO_SAMPLE_INTERVAL_S.
  delay(1000);
}
