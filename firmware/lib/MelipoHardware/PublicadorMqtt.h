// Publicacao da telemetria no broker.
//
// Publica em `meliponet/v1/<node_id>/telemetry` com QoS 1 -- o mesmo topico e o mesmo
// formato que o gateway LoRa usara na Fase 5. Do broker para dentro, nada muda quando o
// transporte mudar.
//
// O Last Will em `meliponet/v1/<node_id>/status` e o que permite a plataforma detectar
// um no mudo: se o no cair sem se despedir, o proprio broker publica a mensagem de
// despedida por ele.

#pragma once

#include <stddef.h>
#include <stdint.h>

#include "Recuo.h"

namespace meliponet {

class PublicadorMqtt {
 public:
  // Guarda servidor, topicos e credenciais. **Nao** depende de haver rede: e chamada
  // sempre, mesmo com o WiFi fora, e a conexao fica por conta de `manter`. Separar as
  // duas coisas foi o conserto de um defeito real, contado em
  // docs/guia/04-o-firmware.md.
  //
  // `node_id` precisa sobreviver ao objeto: os topicos sao montados uma vez aqui.
  void configurar(const char *node_id, const char *host, uint16_t porta, const char *usuario,
                  const char *senha);

  bool configurado() const { return configurado_; }

  bool conectado();

  // Tenta reconectar com recuo. Devolve verdadeiro se esta conectado ao sair.
  bool manter(uint32_t agora_ms);

  // Publica a telemetria. Devolve falso se nao estiver conectado ou se a publicacao
  // falhar -- caso em que quem chamou deve guardar a mensagem no spool.
  bool publicar(const char *conteudo, size_t tamanho);

  // Precisa ser chamada com frequencia para manter a conexao viva.
  void processar();

 private:
  char topico_de_telemetria_[64] = {0};
  char topico_de_estado_[64] = {0};
  char id_do_cliente_[32] = {0};
  const char *host_ = nullptr;
  uint16_t porta_ = 1883;
  const char *usuario_ = nullptr;
  const char *senha_ = nullptr;
  bool configurado_ = false;
  // 1 s a 1 min: o broker volta mais rapido que o roteador, entao o teto e menor que o
  // do WiFi.
  Recuo recuo_{1000, 60000};
};

}  // namespace meliponet
