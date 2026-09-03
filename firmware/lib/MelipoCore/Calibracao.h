// Conversao de contagem bruta do HX711 para quilogramas.
//
// A matematica fica separada do driver para poder ser testada no PC. Ela e simples --
// duas operacoes -- mas erra-la produz uma serie de peso inteira errada, e o erro so
// apareceria comparando com uma balanca em campo.

#pragma once

#include <stdint.h>

namespace meliponet {

// Calibracao de uma celula de carga.
//
// `tara` e a contagem bruta com a colmeia vazia. `contagens_por_kg` e quantas contagens
// o HX711 devolve por quilograma. As duas vem da rotina de calibracao com massas-padrao
// e ficam guardadas na NVS -- refazer a calibracao a cada boot exigiria esvaziar a
// colmeia, o que e absurdo em campo.
struct Calibracao {
  int32_t tara = 0;
  // Zero por padrao, e nao 1.0: um no recem-gravado, ou com a NVS apagada, precisa
  // reportar `hx711_fault` em vez de inventar um peso. Um padrao "plausivel" faria a
  // calibracao ausente passar despercebida ate alguem comparar com uma balanca de
  // verdade em campo -- e a serie ate la seria lixo com aparencia de dado.
  double contagens_por_kg = 0.0;

  bool valida() const {
    // Zero ou negativo indica calibracao ausente, nao feita ou corrompida. Usa-la
    // produziria divisao por zero ou peso com o sinal invertido.
    return contagens_por_kg > 0.0;
  }
};

// Resultado da conversao. `ok == false` quando a calibracao nao e utilizavel -- caso em
// que o campo de peso e omitido da telemetria e a flag `hx711_fault` acende, em vez de
// enviar um numero inventado.
struct Peso {
  double kg = 0.0;
  bool ok = false;
};

// Converte contagem bruta em quilogramas.
Peso paraQuilogramas(int32_t contagem, const Calibracao &calibracao);

// Calcula a calibracao a partir de duas medicoes: a contagem com a balanca vazia e a
// contagem com uma massa-padrao conhecida.
//
// Devolve uma calibracao invalida se as duas contagens forem iguais ou a massa for nula
// -- situacao que indica celula desconectada ou massa nao colocada, e que sem esta
// checagem viraria uma divisao por zero.
Calibracao calcularCalibracao(int32_t contagem_vazia, int32_t contagem_com_massa,
                              double massa_kg);

}  // namespace meliponet
