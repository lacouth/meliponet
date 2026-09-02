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

#include "Backoff.h"

namespace meliponet {

class MqttPublisher {
 public:
  // Guarda servidor, topicos e credenciais. **Nao** depende de haver rede: e chamada
  // sempre, mesmo com o WiFi fora, e a conexao fica por conta de `maintain`.
  //
  // A separacao e o conserto de um defeito real: antes, a configuracao acontecia dentro
  // do `if` que testava a conexao do WiFi. Um no que subisse mais rapido que o roteador
  // -- rotina depois de uma falta de energia -- ficava com servidor e topicos vazios, e
  // toda tentativa posterior ia para 0.0.0.0:0 com topico vazio. O WiFi reconectava, o
  // no parecia saudavel, e nunca mais publicava nada ate alguem reiniciar a placa.
  //
  // `node_id` precisa sobreviver ao objeto: os topicos sao montados uma vez aqui.
  void configure(const char *node_id, const char *host, uint16_t port, const char *username,
                 const char *password);

  bool configured() const { return configured_; }

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
  bool configured_ = false;
  // 1 s a 1 min: o broker volta mais rapido que o roteador, entao o teto e menor que o
  // do WiFi.
  Backoff backoff_{1000, 60000};
};

}  // namespace meliponet
