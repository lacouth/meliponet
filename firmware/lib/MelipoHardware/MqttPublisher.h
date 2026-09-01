// Publicacao da telemetria no broker.
//
// Publica em `meliponet/v1/<node_id>/telemetry` com QoS 1 -- o mesmo topico e o mesmo
// formato que o gateway LoRa usara na Fase 5. Do broker para dentro, nada muda quando o
// transporte mudar.
//
// O Last Will em `meliponet/v1/<node_id>/status` e o que permite a plataforma detectar
// um no mudo: se o no cair sem se despedir, o proprio broker publica a mensagem de
// despedida por ele. Sem isso, "o no parou de enviar" e indistinguivel de "o no ainda
// nao chegou a hora de enviar".

#pragma once

#include <stddef.h>
#include <stdint.h>

namespace meliponet {

class MqttPublisher {
 public:
  // `node_id` precisa sobreviver ao objeto: os topicos sao montados uma vez no begin.
  bool begin(const char *node_id, const char *host, uint16_t port, const char *username,
             const char *password);

  bool connected();

  // Tenta reconectar com recuo. Devolve verdadeiro se esta conectado ao sair.
  bool maintain(uint32_t now_ms);

  // Publica a telemetria. Devolve falso se nao estiver conectado ou se a publicacao
  // falhar -- caso em que quem chamou deve guardar a mensagem no spool.
  bool publish(const char *payload, size_t length);

  // Precisa ser chamada com frequencia para manter a conexao viva.
  void loop();

 private:
  char telemetry_topic_[64] = {0};
  char status_topic_[64] = {0};
  char client_id_[32] = {0};
  const char *host_ = nullptr;
  uint16_t port_ = 1883;
  const char *username_ = nullptr;
  const char *password_ = nullptr;
  uint32_t next_attempt_ms_ = 0;
  uint32_t backoff_ms_ = 1000;
};

}  // namespace meliponet
