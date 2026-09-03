#include "PublicadorMqtt.h"

#include <PubSubClient.h>
#include <WiFi.h>
#include <stdio.h>

namespace meliponet {
namespace {

// O contrato limita a mensagem a bem menos que isso; o buffer do PubSubClient tem 256
// bytes por padrao, pequeno demais para a telemetria completa.
constexpr uint16_t kTamanhoDoBuffer = 512;

WiFiClient g_cliente_wifi;
PubSubClient g_mqtt(g_cliente_wifi);

}  // namespace

void PublicadorMqtt::configurar(const char *node_id, const char *host, uint16_t porta,
                                const char *usuario, const char *senha) {
  host_ = host;
  porta_ = porta;
  usuario_ = (usuario != nullptr && usuario[0] != '\0') ? usuario : nullptr;
  senha_ = senha;

  snprintf(topico_de_telemetria_, sizeof(topico_de_telemetria_), "meliponet/v1/%s/telemetry",
           node_id);
  snprintf(topico_de_estado_, sizeof(topico_de_estado_), "meliponet/v1/%s/status", node_id);
  snprintf(id_do_cliente_, sizeof(id_do_cliente_), "meliponode-%s", node_id);

  g_mqtt.setServer(host_, porta_);
  g_mqtt.setBufferSize(kTamanhoDoBuffer);
  g_mqtt.setKeepAlive(60);

  configurado_ = true;
}

bool PublicadorMqtt::conectado() { return g_mqtt.connected(); }

bool PublicadorMqtt::manter(uint32_t agora_ms) {
  if (g_mqtt.connected()) {
    recuo_.registrarSucesso();
    return true;
  }
  // Sem `configurar` nao ha servidor nem topicos; tentar conectar iria para 0.0.0.0:0.
  if (!configurado_) {
    return false;
  }
  if (!recuo_.podeTentar(agora_ms)) {
    return false;
  }
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }
  recuo_.registrarTentativa(agora_ms);

  // O Last Will fica retido: quem assinar depois de o no cair ainda ve o estado. E o
  // "online" publicado na conexao tambem e retido, para que o par de mensagens conte a
  // historia completa a qualquer assinante que chegue depois.
  const bool ok = g_mqtt.connect(id_do_cliente_, usuario_, senha_, topico_de_estado_, 1, true,
                                 "offline", true);
  if (ok) {
    g_mqtt.publish(topico_de_estado_, "online", true);
    recuo_.registrarSucesso();
    return true;
  }
  return false;
}

bool PublicadorMqtt::publicar(const char *conteudo, size_t tamanho) {
  if (!g_mqtt.connected()) {
    return false;
  }
  return g_mqtt.publish(topico_de_telemetria_, reinterpret_cast<const uint8_t *>(conteudo),
                        tamanho, false);
}

void PublicadorMqtt::processar() { g_mqtt.loop(); }

}  // namespace meliponet
