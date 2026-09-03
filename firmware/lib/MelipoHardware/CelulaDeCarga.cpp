#include "CelulaDeCarga.h"

#include <HX711.h>

namespace meliponet {
namespace {

HX711 g_balanca;

}  // namespace

bool CelulaDeCarga::iniciar(int pino_dados, int pino_clock, const Calibracao &calibracao) {
  g_balanca.begin(pino_dados, pino_clock);
  calibracao_ = calibracao;

  // `wait_ready_timeout` so responde se o HX711 estiver alimentado e conectado. Sem esta
  // checagem, um cabo solto produziria leituras de zero indistinguiveis de uma colmeia
  // vazia.
  presente_ = g_balanca.wait_ready_timeout(1000);
  return presente_;
}

bool CelulaDeCarga::lerContagem(int32_t &saida) {
  if (!presente_ || !g_balanca.wait_ready_timeout(1000)) {
    return false;
  }
  saida = static_cast<int32_t>(g_balanca.read_average(kLeiturasPorMedida));
  return true;
}

Leitura CelulaDeCarga::ler() {
  int32_t contagem = 0;
  if (!lerContagem(contagem)) {
    return Leitura::falha();
  }

  const Peso peso = paraQuilogramas(contagem, calibracao_);
  return peso.ok ? Leitura::obtida(peso.kg) : Leitura::falha();
}

}  // namespace meliponet
