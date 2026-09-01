// Celula de carga de 50 kg via HX711.
//
// A conversao contagem -> quilogramas mora em MelipoCore/Calibration, testada no PC.
// Aqui fica apenas o que exige hardware: falar com o HX711 e mediar as leituras.

#pragma once

#include "Calibration.h"
#include "Sample.h"

namespace meliponet {

// Quantas leituras brutas mediar por amostra. O HX711 e ruidoso; a media reduz o ruido
// sem custar tempo relevante num ciclo de 5 minutos.
constexpr uint8_t kLoadCellSamples = 10;

class LoadCell {
 public:
  bool begin(int data_pin, int clock_pin, const LoadCellCalibration &calibration);

  // Le e converte. Devolve `Reading::fault()` se o HX711 nao responder ou se a
  // calibracao nao for utilizavel -- nunca um peso inventado, que dispararia o alerta
  // de queda abrupta e mandaria o meliponicultor ao meliponario a toa.
  Reading read();

  // Contagem bruta media, sem calibracao aplicada. E o que a rotina de calibracao usa.
  bool readRaw(int32_t &out);

  void setCalibration(const LoadCellCalibration &calibration) { calibration_ = calibration; }
  const LoadCellCalibration &calibration() const { return calibration_; }

 private:
  LoadCellCalibration calibration_;
  bool present_ = false;
};

}  // namespace meliponet
