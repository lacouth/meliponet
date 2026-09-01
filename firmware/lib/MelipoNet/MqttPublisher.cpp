#include "MqttPublisher.h"

#include <PubSubClient.h>
#include <WiFi.h>
#include <stdio.h>

namespace meliponet {
namespace {

constexpr uint32_t kMinBackoffMs = 1000;
constexpr uint32_t kMaxBackoffMs = 60000;

// O contrato limita a mensagem a bem menos que isso; o buffer do PubSubClient tem 256
// bytes por padrao, pequeno demais para a telemetria completa.
constexpr uint16_t kBufferSize = 512;

WiFiClient g_wifi;
PubSubClient g_mqtt(g_wifi);

}  // namespace

bool MqttPublisher::begin(const char *node_id, const char *host, uint16_t port,
                          const char *username, const char *password) {
  host_ = host;
  port_ = port;
  username_ = (username != nullptr && username[0] != '\0') ? username : nullptr;
  password_ = password;

  snprintf(telemetry_topic_, sizeof(telemetry_topic_), "meliponet/v1/%s/telemetry", node_id);
  snprintf(status_topic_, sizeof(status_topic_), "meliponet/v1/%s/status", node_id);
  snprintf(client_id_, sizeof(client_id_), "meliponode-%s", node_id);

  g_mqtt.setServer(host_, port_);
  g_mqtt.setBufferSize(kBufferSize);
  g_mqtt.setKeepAlive(60);

  return maintain(millis());
}

bool MqttPublisher::connected() { return g_mqtt.connected(); }

bool MqttPublisher::maintain(uint32_t now_ms) {
  if (g_mqtt.connected()) {
    backoff_ms_ = kMinBackoffMs;
    return true;
  }
  if (next_attempt_ms_ != 0 && now_ms < next_attempt_ms_) {
    return false;
  }
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  // O Last Will fica retido: quem assinar depois de o no cair ainda ve o estado. E o
  // "online" publicado na conexao tambem e retido, para que o par de mensagens conte a
  // historia completa a qualquer assinante que chegue depois.
  const bool ok = g_mqtt.connect(client_id_, username_, password_, status_topic_, 1, true,
                                 "offline", true);
  if (ok) {
    g_mqtt.publish(status_topic_, "online", true);
    backoff_ms_ = kMinBackoffMs;
    return true;
  }

  next_attempt_ms_ = now_ms + backoff_ms_;
  backoff_ms_ = backoff_ms_ * 2 > kMaxBackoffMs ? kMaxBackoffMs : backoff_ms_ * 2;
  return false;
}

bool MqttPublisher::publish(const char *payload, size_t length) {
  if (!g_mqtt.connected()) {
    return false;
  }
  return g_mqtt.publish(telemetry_topic_, reinterpret_cast<const uint8_t *>(payload), length,
                        false);
}

void MqttPublisher::loop() { g_mqtt.loop(); }

}  // namespace meliponet
