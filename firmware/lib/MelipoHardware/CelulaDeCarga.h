// Celula de carga de 50 kg via HX711.
//
// A conversao contagem -> quilogramas mora em MelipoCore/Calibracao, testada no PC.
// Aqui fica apenas o que exige hardware: falar com o HX711 e mediar as leituras.

#pragma once

#include "Amostra.h"
#include "Calibracao.h"

namespace meliponet {

// Quantas leituras brutas mediar por medida. O HX711 e ruidoso; a media reduz o ruido
// sem custar tempo relevante num ciclo de 5 minutos.
constexpr uint8_t kLeiturasPorMedida = 10;

class CelulaDeCarga {
 public:
  bool iniciar(int pino_dados, int pino_clock, const Calibracao &calibracao);

  // Le e converte. Devolve `Leitura::falha()` se o HX711 nao responder ou se a
  // calibracao nao for utilizavel -- nunca um peso inventado, que dispararia o alerta de
  // queda abrupta e mandaria o meliponicultor ao meliponario a toa.
  Leitura ler();

  // Contagem bruta media, sem calibracao aplicada. E o que a rotina de calibracao usa.
  bool lerContagem(int32_t &saida);

  void definirCalibracao(const Calibracao &calibracao) { calibracao_ = calibracao; }
  const Calibracao &calibracao() const { return calibracao_; }

 private:
  Calibracao calibracao_;
  bool presente_ = false;
};

}  // namespace meliponet
