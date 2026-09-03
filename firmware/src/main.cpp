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
#include "CommandLine.h"
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
meliponet::Spool g_spool(g_storage);
meliponet::Scheduler g_scheduler;

// Se o `setup` chegou a configurar rede e amostragem. O laco principal se guia por esta
// bandeira, e nao por `g_config.usable()`: a configuracao pelo console serial pode
// tornar `usable()` verdadeiro no meio da execucao, e o laco entraria com WifiLink e
// MqttPublisher ainda nao configurados. Por isso os comandos de configuracao pedem
// reinicio.
bool g_running = false;

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
  if (!g_spool.push(payload, length)) {
    Serial.println("[erro] falha ao guardar no spool; medicao perdida");
  } else {
    Serial.printf("[spool] guardada; %u pendentes\n",
                  static_cast<unsigned>(g_spool.size()));
  }
}

// Drena o spool, uma mensagem por vez. Uma por chamada, e nao todas de uma vez, para
// nao segurar o laco principal por minutos apos uma queda longa -- o que atrasaria a
// proxima amostragem e criaria uma lacuna nova enquanto se recupera da antiga.
void drainSpool() {
  if (g_spool.empty() || !g_mqtt.connected()) {
    return;
  }

  char buffer[meliponet::kMaxTelemetryJson];
  const size_t length = g_spool.peek(buffer, sizeof(buffer));
  if (length == 0) {
    g_spool.pop();  // entrada ilegivel: descarta para nao travar a fila
    return;
  }

  // So remove depois da confirmacao: remover antes perderia a mensagem se a publicacao
  // falhasse, que e justamente o cenario em que o spool existe.
  if (g_mqtt.publish(buffer, length)) {
    g_spool.pop();
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

// Quantas leituras seguidas o comando `ler` aceita repetir. O teto existe para que um
// numero digitado errado nao prenda o console por horas.
constexpr uint32_t kMaxBenchReadings = 600;

// Imprime uma leitura em unidade fisica e, ao lado, o inteiro escalado que iria para a
// mensagem.
//
// Mostrar o par lado a lado e o ponto do comando: e na bancada que a regra central do
// contrato -- metrica nenhuma trafega como float -- deixa de ser um paragrafo de
// documento e vira uma coisa que se ve. 30,12 C vira 3012, e nao "30.12".
void printReading(const char *label, const meliponet::Reading &reading, const char *unit,
                  const meliponet::Metric &metric) {
  if (!reading.valid) {
    Serial.printf("  %-9s ausente\n", label);
    return;
  }

  const meliponet::Scaled scaled = meliponet::scaleInRange(reading.value, metric);
  if (!scaled.ok) {
    // Fora da faixa fisica do sensor: a mensagem real omitiria o campo e ligaria a
    // flag. Dizer isso aqui evita a conclusao errada de que o valor seria enviado.
    Serial.printf("  %-9s %.3f %s  FORA DA FAIXA -- seria omitida da mensagem\n", label,
                  reading.value, unit);
    return;
  }

  Serial.printf("  %-9s %.3f %s  (escalado: %ld)\n", label, reading.value, unit,
                static_cast<long>(scaled.value));
}

// Leitura imediata dos sensores, para a bancada.
//
// Nao toca em WiFi, MQTT, relogio nem `seq`, de proposito: o objetivo e verificar
// sensores, ligacao e calibracao numa mesa, com a placa alimentada so pelo cabo USB.
// Consumir `seq` aqui seria pior do que inutil -- cada teste de bancada abriria uma
// lacuna permanente na serie do no depois de instalado, e a lacuna e exatamente o
// indicador que o projeto se compromete a minimizar.
void benchRead(uint32_t repetitions) {
  for (uint32_t i = 1; i <= repetitions; ++i) {
    const meliponet::ShtReadings sht = g_sht.read();

    Serial.printf("[leitura %lu/%lu]\n", static_cast<unsigned long>(i),
                  static_cast<unsigned long>(repetitions));
    printReading("temp int", sht.temp_in, "C", meliponet::kTemperature);
    printReading("ur int", sht.rh_in, "%", meliponet::kHumidity);
    printReading("temp ext", sht.temp_out, "C", meliponet::kTemperature);
    printReading("ur ext", sht.rh_out, "%", meliponet::kHumidity);

    // A contagem bruta e lida uma vez e reaproveitada na conversao. Chamar `read()`
    // aqui repetiria as dez leituras mediadas do HX711 -- um segundo inteiro a mais
    // por iteracao, para chegar ao mesmo numero.
    int32_t raw = 0;
    if (g_load_cell.readRaw(raw)) {
      // A contagem bruta aparece mesmo sem calibracao gravada, e e isso que permite
      // conferir a ligacao da celula antes de calibrar: apertar a plataforma com a mao
      // move a contagem.
      Serial.printf("  %-9s %ld contagens\n", "hx711", static_cast<long>(raw));
      const meliponet::Weight weight = meliponet::toKilograms(raw, g_load_cell.calibration());
      printReading("peso", weight.ok ? meliponet::Reading::ok(weight.kilograms)
                                     : meliponet::Reading::fault(),
                   "kg", meliponet::kWeight);
    } else {
      Serial.printf("  %-9s sem resposta -- confira alimentacao e os fios DT/SCK\n", "hx711");
    }

    printReading("bateria", readBattery(), "V", meliponet::kVoltage);

    if (i < repetitions) {
      delay(1000);
    }
  }
}

// --- comandos do console -----------------------------------------------------------
//
// E por aqui que as credenciais entram na NVS, em vez de irem no codigo-fonte.
//
// Cada comando e uma funcao pequena que recebe a linha ja dividida, e a tabela
// `kCommands`, logo abaixo delas, liga o nome digitado a funcao. **Para acrescentar um
// comando novo: escreva a funcao aqui e ponha uma linha na tabela.** O `ajuda` percorre
// a mesma tabela, entao ele nao tem como ficar desatualizado.

void cmdWifi(const meliponet::Command &cmd) {
  if (cmd.count < 3) {
    Serial.println("uso: wifi <ssid> <senha>");
    return;
  }
  // Os dois tamanhos sao conferidos **antes** de copiar qualquer um: gravar o ssid e
  // recusar a senha deixaria a configuracao pela metade.
  if (!meliponet::fitsIn(cmd.arg[1], meliponet::kMaxSsidLength) ||
      !meliponet::fitsIn(cmd.arg[2], meliponet::kMaxPasswordLength)) {
    Serial.println("ssid ou senha longos demais; nada foi gravado");
    return;
  }
  meliponet::copyText(g_config.wifi_ssid, meliponet::kMaxSsidLength, cmd.arg[1]);
  meliponet::copyText(g_config.wifi_password, meliponet::kMaxPasswordLength, cmd.arg[2]);
  meliponet::saveConfig(g_config);
  Serial.println("wifi gravado; reinicie");
}

void cmdBroker(const meliponet::Command &cmd) {
  if (cmd.count < 2) {
    Serial.println("uso: broker <host> [porta]");
    return;
  }
  // Sem porta explicita, mantem a que ja estava gravada -- trocar so o host nao pode
  // devolver a porta ao padrao sem avisar.
  uint16_t port = g_config.mqtt_port;
  if (cmd.count >= 3 && !meliponet::parsePort(cmd.arg[2], port)) {
    Serial.println("porta invalida (1..65535); nada foi gravado");
    return;
  }
  if (!meliponet::copyText(g_config.mqtt_host, meliponet::kMaxHostLength, cmd.arg[1])) {
    Serial.println("host longo demais; nada foi gravado");
    return;
  }
  g_config.mqtt_port = port;
  meliponet::saveConfig(g_config);
  Serial.printf("broker gravado (%s:%u); reinicie\n", g_config.mqtt_host,
                static_cast<unsigned>(g_config.mqtt_port));
}

void cmdMqtt(const meliponet::Command &cmd) {
  // Sem argumentos, apaga: e o caminho para um broker de desenvolvimento com
  // `allow_anonymous true`, e a unica forma de tirar uma credencial errada da NVS sem
  // apagar a particao inteira.
  if (cmd.count == 1) {
    g_config.mqtt_username[0] = '\0';
    g_config.mqtt_password[0] = '\0';
    meliponet::saveConfig(g_config);
    Serial.println("credenciais do broker apagadas; reinicie");
    return;
  }
  if (cmd.count < 3) {
    Serial.println("uso: mqtt <usuario> <senha>   (sem argumentos, apaga)");
    return;
  }
  if (!meliponet::fitsIn(cmd.arg[1], meliponet::kMaxUsernameLength) ||
      !meliponet::fitsIn(cmd.arg[2], meliponet::kMaxPasswordLength)) {
    Serial.println("usuario ou senha longos demais; nada foi gravado");
    return;
  }
  meliponet::copyText(g_config.mqtt_username, meliponet::kMaxUsernameLength, cmd.arg[1]);
  meliponet::copyText(g_config.mqtt_password, meliponet::kMaxPasswordLength, cmd.arg[2]);
  meliponet::saveConfig(g_config);
  // A senha nunca e ecoada: o monitor serial vai para o log do terminal de quem
  // preparou o no, e de la para um print numa conversa.
  Serial.printf("credenciais gravadas para %s; reinicie\n", g_config.mqtt_username);
}

void cmdTare(const meliponet::Command &) {
  int32_t raw = 0;
  if (!g_load_cell.readRaw(raw)) {
    Serial.println("HX711 nao respondeu");
    return;
  }
  g_config.calibration.offset = raw;
  // A celula precisa receber a calibracao nova junto, e nao so a NVS. Sem esta linha o
  // objeto seguia com o zero que recebeu no boot: a leitura logo apos a tara saia com o
  // offset antigo, e so um reinicio fazia a tara valer. Na bancada isso leva a pessoa a
  // repetir a tara varias vezes achando que ela nao pegou.
  g_load_cell.setCalibration(g_config.calibration);
  meliponet::saveConfig(g_config);
  Serial.printf("tara = %ld\n", static_cast<long>(raw));
}

void cmdCalibrate(const meliponet::Command &cmd) {
  // Uso: coloque uma massa-padrao conhecida e mande `calibrar <kg>`.
  // Verifique depois em varios pontos da faixa, e nao so neste: um ponto so ajusta a
  // escala e esconde a nao-linearidade da celula.
  if (cmd.count < 2) {
    Serial.println("uso: calibrar <kg>");
    return;
  }
  // `atof` devolve 0.0 para texto nao numerico, e `calibrate` recusa massa <= 0.
  const double known_kg = atof(cmd.arg[1]);
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
}

void cmdRead(const meliponet::Command &cmd) {
  // Repeticoes opcionais: `ler 30` acompanha meia hora de deriva, ou mostra o peso
  // mudando enquanto se poe massa na plataforma. Sem argumento, uma leitura so.
  uint32_t repetitions = 1;
  if (cmd.count >= 2 && !meliponet::parseCount(cmd.arg[1], kMaxBenchReadings, repetitions)) {
    Serial.printf("uso: ler [n]   (1 a %lu)\n", static_cast<unsigned long>(kMaxBenchReadings));
    return;
  }
  benchRead(repetitions);
}

void cmdProbe(const meliponet::Command &) {
  // Os sensores sao detectados uma vez, no boot. Na bancada isso atrapalha: ligar um
  // SHT30 depois de a placa subir deixa o sensor marcado como ausente ate alguem
  // reiniciar. Este comando refaz a deteccao sem reiniciar.
  const bool sht_ok = g_sht.begin(kI2cSda, kI2cScl);
  const bool cell_ok = g_load_cell.begin(kHx711Data, kHx711Clock, g_config.calibration);
  Serial.printf("sht int   %s\n", g_sht.insidePresent() ? "ok" : "ausente");
  Serial.printf("sht ext   %s\n", g_sht.outsidePresent() ? "ok" : "ausente");
  Serial.printf("hx711     %s\n", cell_ok ? "ok" : "ausente");
  if (!sht_ok && !cell_ok) {
    Serial.println("nenhum sensor respondeu: confira alimentacao, fios e enderecos I2C");
  }
}

void cmdStatus(const meliponet::Command &) {
  Serial.printf("no        %s\n", meliponet::nodeId());
  Serial.printf("wifi      %s\n", g_wifi.connected() ? "conectado" : "desconectado");
  Serial.printf("broker    %s em %s:%u\n", g_mqtt.connected() ? "conectado" : "desconectado",
                g_config.mqtt_host, static_cast<unsigned>(g_config.mqtt_port));
  Serial.printf("mqtt auth %s, senha %s\n",
                g_config.mqtt_username[0] != '\0' ? g_config.mqtt_username : "anonimo",
                g_config.mqtt_password[0] != '\0' ? "definida" : "ausente");
  Serial.printf("relogio   %s\n", g_wifi.clockSynced() ? "sincronizado" : "NAO sincronizado");
  Serial.printf("sht int   %s\n", g_sht.insidePresent() ? "ok" : "ausente");
  Serial.printf("sht ext   %s\n", g_sht.outsidePresent() ? "ok" : "ausente");
  Serial.printf("calibrac. %s\n", g_config.calibration.valid() ? "ok" : "AUSENTE");
  Serial.printf("spool     %u pendentes, %u descartadas\n",
                static_cast<unsigned>(g_spool.size()),
                static_cast<unsigned>(g_spool.dropped()));
}

// Definida depois da tabela, porque e a tabela que ela percorre.
void cmdHelp(const meliponet::Command &cmd);

// O nome digitado, a funcao que o atende, e a linha que o `ajuda` imprime.
struct ConsoleCommand {
  const char *name;
  void (*run)(const meliponet::Command &);
  const char *help;
};

constexpr ConsoleCommand kCommands[] = {
    {"wifi", cmdWifi, "wifi <ssid> <senha>          credenciais da rede"},
    {"broker", cmdBroker, "broker <host> [porta]        endereco do broker MQTT"},
    {"mqtt", cmdMqtt,
     "mqtt <usuario> <senha>       credenciais do broker (sem argumentos, apaga)"},
    {"tara", cmdTare, "tara                         zera a celula com a colmeia vazia"},
    {"calibrar", cmdCalibrate,
     "calibrar <kg>                calibra com uma massa-padrao conhecida"},
    {"ler", cmdRead, "ler [n]                      le os sensores agora, sem publicar nada"},
    {"sondar", cmdProbe, "sondar                       redetecta os sensores, sem reiniciar"},
    {"estado", cmdStatus, "estado                       sensores, conexoes, calibracao e spool"},
    {"ajuda", cmdHelp, "ajuda                        esta lista"},
    {"?", cmdHelp, "?                            o mesmo que `ajuda`"},
};

void cmdHelp(const meliponet::Command &) {
  for (const ConsoleCommand &entry : kCommands) {
    Serial.println(entry.help);
  }
}

// Le uma linha do serial e entrega ao comando correspondente.
void handleSerial() {
  if (!Serial.available()) {
    return;
  }
  String line = Serial.readStringUntil('\n');
  line.trim();

  const meliponet::Command cmd = meliponet::splitLine(line.c_str());
  if (cmd.count == 0) {
    return;
  }
  // Um argumento maior do que cabe derruba a linha inteira, e nao so aquele argumento:
  // gravar meia senha produz um no que tenta autenticar para sempre sem que nada no
  // serial explique o motivo.
  if (cmd.truncated) {
    Serial.println("argumento longo demais; nada foi gravado");
    return;
  }

  for (const ConsoleCommand &entry : kCommands) {
    if (cmd.is(entry.name)) {
      entry.run(cmd);
      return;
    }
  }

  Serial.printf("comando desconhecido: %s  (use `ajuda`)\n", cmd.arg[0]);
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.printf("\nMelipoSense %s\n", meliponet::nodeId());

  g_config = meliponet::loadConfig();

  uint32_t head = 0;
  uint32_t count = 0;
  if (g_storage.begin(head, count)) {
    // Restaura a fila do reinicio: mensagens guardadas antes de uma queda de energia
    // continuam pendentes, em vez de virarem lacuna.
    g_spool.restore(head, count);
    Serial.printf("[spool] %u mensagens recuperadas\n", static_cast<unsigned>(count));
  }

  g_scheduler.begin(g_config.sample_interval_s * 1000UL, millis());

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
    // Nao publicar nao impede testar: `ler` funciona sem rede nenhuma, e e assim que a
    // bancada verifica sensores e calibracao antes de o no ter para onde enviar.
    Serial.println("[config] para conferir os sensores agora, use `ler`.");
    return;
  }

  // O MQTT e configurado **sempre**, e nao so quando o WiFi sobe de primeira. Um no que
  // liga mais rapido que o roteador -- rotina depois de uma falta de energia -- ficaria
  // com servidor e topicos vazios, e nunca mais publicaria nada, mesmo depois de o WiFi
  // reconectar sozinho.
  g_mqtt.configure(meliponet::nodeId(), g_config.mqtt_host, g_config.mqtt_port,
                   g_config.mqtt_username, g_config.mqtt_password);

  if (g_wifi.begin(g_config.wifi_ssid, g_config.wifi_password)) {
    g_wifi.syncClock();
    g_mqtt.maintain(millis());
  } else {
    Serial.println("[aviso] wifi indisponivel no boot; reconexao em segundo plano");
  }

  g_running = true;
}

void loop() {
  handleSerial();

  if (!g_running) {
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

  if (g_scheduler.due(now)) {
    g_scheduler.mark(now);
    sample();
  }

  drainSpool();
  delay(50);
}
