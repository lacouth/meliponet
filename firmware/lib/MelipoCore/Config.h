// Configuracao do no, guardada na NVS.
//
// Credenciais **nunca** vao no codigo-fonte. O repositorio e publico para a equipe e
// vai para o GitHub; uma senha commitada fica no historico para sempre, e apaga-la num
// commit seguinte nao resolve -- ela precisa ser trocada. Aqui elas moram na memoria
// nao-volatil do proprio no, gravadas por comando serial na hora de preparar o
// dispositivo.
//
// A `seq` tambem vive aqui, e por um motivo especifico: ela precisa sobreviver a reset.
// Um no que reinicia e recomeca a sequencia em 1 tem todas as mensagens descartadas
// pela plataforma como reenvio duplicado -- corretamente, pela restricao
// UNIQUE (node_id, seq) -- e fica mudo sem que nada acuse. Isso ja aconteceu com o
// simulador durante o desenvolvimento; em campo teria custado uma viagem.

#pragma once

#include <stdint.h>

#include "Calibration.h"

namespace meliponet {

constexpr size_t kMaxSsidLength = 33;
constexpr size_t kMaxPasswordLength = 65;
constexpr size_t kMaxHostLength = 65;

struct Config {
  char wifi_ssid[kMaxSsidLength] = {0};
  char wifi_password[kMaxPasswordLength] = {0};
  char mqtt_host[kMaxHostLength] = {0};
  uint16_t mqtt_port = 1883;
  char mqtt_username[kMaxSsidLength] = {0};
  char mqtt_password[kMaxPasswordLength] = {0};
  uint32_t sample_interval_s = 300;
  LoadCellCalibration calibration;

  // Verdadeiro se ha o minimo para o no operar. Sem SSID ou host, o no nao tem como
  // publicar e deve entrar em modo de configuracao em vez de tentar e falhar em laco.
  bool usable() const { return wifi_ssid[0] != '\0' && mqtt_host[0] != '\0'; }
};

// Carrega da NVS. Campos ausentes ficam com o padrao.
Config loadConfig();

// Grava na NVS.
bool saveConfig(const Config &config);

// Le e incrementa o contador de sequencia, gravando o novo valor antes de devolver.
//
// Grava **antes** de usar, e nao depois de publicar: se o no reiniciar entre o uso e a
// gravacao, e melhor pular uma `seq` (que a plataforma registra como uma lacuna) do que
// reutilizar uma (que a plataforma descarta em silencio como duplicata, perdendo a
// leitura nova).
uint32_t nextSequence();

// Identificador do no: os 4 ultimos bytes do MAC, em hexadecimal maiusculo, conforme o
// contrato. Derivar do MAC evita ter de gravar um id unico em cada unidade do lote de
// 20 -- e dois nos jamais colidem.
const char *nodeId();

}  // namespace meliponet
