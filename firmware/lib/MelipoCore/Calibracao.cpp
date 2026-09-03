#include "Calibracao.h"

#include <math.h>

namespace meliponet {

Peso paraQuilogramas(int32_t contagem, const Calibracao &calibracao) {
  if (!calibracao.valida()) {
    return {};
  }
  // A subtracao e feita em 64 bits: os dois sao int32_t e a diferenca entre extremos da
  // faixa estouraria um int32_t.
  const double contagens =
      static_cast<double>(static_cast<int64_t>(contagem) - calibracao.tara);
  const double kg = contagens / calibracao.contagens_por_kg;
  if (!isfinite(kg)) {
    return {};
  }
  return {kg, true};
}

Calibracao calcularCalibracao(int32_t contagem_vazia, int32_t contagem_com_massa,
                              double massa_kg) {
  if (massa_kg <= 0.0 || !isfinite(massa_kg) || contagem_vazia == contagem_com_massa) {
    return {};
  }

  const double faixa =
      static_cast<double>(static_cast<int64_t>(contagem_com_massa) - contagem_vazia);
  const double contagens_por_kg = faixa / massa_kg;
  if (!isfinite(contagens_por_kg) || contagens_por_kg <= 0.0) {
    // Contagem menor com massa aplicada significa celula invertida ou mal ligada.
    // Aceitar isso produziria pesos negativos crescentes durante toda a coleta.
    return {};
  }

  return {contagem_vazia, contagens_por_kg};
}

}  // namespace meliponet
