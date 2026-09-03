// Codec da telemetria MelipoNet v1.
//
// Espelha as regras de contracts/canonical.py. A regra que governa este arquivo:
// **toda metrica e um inteiro escalado**, nao um float. Temperatura em centesimos de
// grau, peso em gramas, umidade em centesimos de ponto percentual. A serializacao so
// insere a virgula decimal no inteiro.
//
// O motivo e que a alternativa -- formatar float com snprintf("%.2f") -- nao e
// reproduzivel entre plataformas: a printf da newlib do ESP32 nao arredonda igual a
// glibc do PC, o ESP32 calcula em float de 32 bits, e empates como 30.125 caem para
// lados diferentes. Com inteiros o arredondamento acontece uma vez so, na camada de
// sensores, e a saida deste codec e identica byte a byte a do Python -- que e o que o
// teste contra contracts/testdata/vectors.h verifica.
//
// O codec nao aloca memoria e nao depende do Arduino, de modo a rodar tanto no
// ESP32-C6 quanto no ambiente `native` do PlatformIO.

#pragma once

#include <stddef.h>
#include <stdint.h>

namespace meliponet {

// Os campos opcionais e as condicoes detectadas pelo no viajam como **bits dentro de um
// numero**: cada constante abaixo acende um bit, e juntar varias e so um `|`.
//
//     telemetry.present = Field::temp_in_c | Field::weight_kg;
//     if (has(telemetry.present, Field::rssi)) { ... }
//
// Sao `uint32_t` simples de proposito. A versao anterior usava `enum class`, que e mais
// seguro contra trocar um conjunto pelo outro, mas obrigava a sobrecarregar `|`, `|=` e
// a escrever `static_cast<uint32_t>` em toda comparacao -- catorze linhas de maquinaria
// antes da primeira linha util.

// Campos opcionais efetivamente presentes na mensagem. Campo ausente e **omitido** do
// JSON, nunca emitido como null ou como zero: um sensor com falha precisa ser
// distinguivel de um sensor que leu zero.
//
// Os nomes sao os do contrato, iguais as chaves do JSON, para que a correspondencia
// entre o campo aqui e a chave la seja obvia.
namespace Field {
constexpr uint32_t none = 0;
constexpr uint32_t temp_in_c = 1u << 0;
constexpr uint32_t temp_out_c = 1u << 1;
constexpr uint32_t rh_in_pct = 1u << 2;
constexpr uint32_t rh_out_pct = 1u << 3;
constexpr uint32_t weight_kg = 1u << 4;
constexpr uint32_t vbat_v = 1u << 5;
constexpr uint32_t rssi = 1u << 6;
constexpr uint32_t snr = 1u << 7;
constexpr uint32_t sound_rms = 1u << 8;
constexpr uint32_t sound_bands = 1u << 9;
constexpr uint32_t gateway_id = 1u << 10;
}  // namespace Field

// Condicoes detectadas pelo proprio no. A ordem das constantes e a ordem canonica de
// emissao no JSON, para que a saida nao dependa da ordem de deteccao.
namespace Flag {
constexpr uint32_t none = 0;
constexpr uint32_t sht_in_fault = 1u << 0;
constexpr uint32_t sht_out_fault = 1u << 1;
constexpr uint32_t hx711_fault = 1u << 2;
constexpr uint32_t mic_fault = 1u << 3;
constexpr uint32_t low_batt = 1u << 4;
constexpr uint32_t clock_unsynced = 1u << 5;
constexpr uint32_t spooled = 1u << 6;
}  // namespace Flag

// Verdadeiro se `member` esta aceso dentro de `set`.
constexpr bool has(uint32_t set, uint32_t member) { return (set & member) != 0; }

constexpr size_t kSoundBandCount = 4;

// Buffer com folga para a maior mensagem possivel (no completo da Fase 5, todos os
// campos presentes e todas as flags ligadas).
constexpr size_t kMaxTelemetryJson = 512;

// Uma leitura pronta para transmissao. A ordem dos membros e a ordem canonica de
// serializacao do contrato, e o cabecalho gerado contracts/testdata/vectors.h depende
// dela para usar inicializadores designados.
struct Telemetry {
  const char *node_id = "";
  uint32_t seq = 0;
  const char *ts = "";
  int32_t temp_in_c = 0;    // centesimos de grau Celsius
  int32_t temp_out_c = 0;   // centesimos de grau Celsius
  int32_t rh_in_pct = 0;    // centesimos de ponto percentual
  int32_t rh_out_pct = 0;   // centesimos de ponto percentual
  int32_t weight_kg = 0;    // gramas
  int32_t vbat_v = 0;       // centesimos de volt
  int32_t rssi = 0;         // dBm
  int32_t snr = 0;          // decimos de dB
  int32_t sound_rms = 0;    // decimos de unidade RMS
  int32_t sound_bands[kSoundBandCount] = {0, 0, 0, 0};  // decimos de unidade
  const char *gateway_id = "";
  uint32_t flags = Flag::none;
  uint32_t present = Field::none;
};

// Serializa `telemetry` na forma canonica em `out`.
//
// Devolve o numero de caracteres escritos (sem o terminador), ou 0 se o buffer for
// pequeno demais -- caso em que `out` fica com uma string vazia em vez de um JSON
// truncado, que o ingestor rejeitaria como malformado sem saber o motivo.
size_t encode(const Telemetry &telemetry, char *out, size_t capacity);

}  // namespace meliponet
