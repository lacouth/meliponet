#include "SensoresSht.h"

#include <SHT31.h>
#include <Wire.h>

namespace meliponet {
namespace {

SHT31 g_interno(kEnderecoDoShtInterno);
SHT31 g_externo(kEnderecoDoShtExterno);

// Le um sensor, devolvendo leituras invalidas se ele nao responder. O SHT31 devolve NaN
// quando a leitura falha, e NaN precisa virar `Leitura::falha()` aqui em vez de
// escorregar para a serializacao.
void lerUm(SHT31 &sensor, bool presente, Leitura &temperatura, Leitura &umidade) {
  if (!presente || !sensor.read()) {
    temperatura = Leitura::falha();
    umidade = Leitura::falha();
    return;
  }

  const float t = sensor.getTemperature();
  const float u = sensor.getHumidity();
  temperatura = isnan(t) ? Leitura::falha() : Leitura::obtida(t);
  umidade = isnan(u) ? Leitura::falha() : Leitura::obtida(u);
}

}  // namespace

bool SensoresSht::iniciar(int pino_sda, int pino_scl) {
  Wire.begin(pino_sda, pino_scl);

  interno_presente_ = g_interno.begin() && g_interno.isConnected();
  externo_presente_ = g_externo.begin() && g_externo.isConnected();

  return interno_presente_ || externo_presente_;
}

LeiturasSht SensoresSht::ler() {
  LeiturasSht leituras;
  lerUm(g_interno, interno_presente_, leituras.temp_int, leituras.ur_int);
  lerUm(g_externo, externo_presente_, leituras.temp_ext, leituras.ur_ext);
  return leituras;
}

}  // namespace meliponet
