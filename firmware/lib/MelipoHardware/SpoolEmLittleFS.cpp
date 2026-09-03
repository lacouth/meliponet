#include "SpoolEmLittleFS.h"

#include <LittleFS.h>
#include <stdio.h>

#include "SpoolRecuperacao.h"

namespace meliponet {
namespace {

constexpr const char *kDiretorio = "/spool";

void caminhoDaPosicao(uint32_t posicao, char *saida, size_t capacidade) {
  snprintf(saida, capacidade, "%s/%04u", kDiretorio, static_cast<unsigned>(posicao));
}

}  // namespace

bool SpoolEmLittleFS::iniciar(uint32_t &inicio, uint32_t &quantidade) {
  // O `true` formata se a montagem falhar: um sistema de arquivos corrompido nao pode
  // impedir o no de voltar a operar. Perde-se o que estava na fila, o que a plataforma
  // registra como lacuna -- melhor do que um no que nao inicia.
  montado_ = LittleFS.begin(true);
  if (!montado_) {
    return false;
  }
  LittleFS.mkdir(kDiretorio);

  // Monta o mapa de posicoes ocupadas e deixa a deducao da fila para
  // `deduzirEstadoDaFila`, que e pura e testada -- inclusive com o anel dado a volta, que
  // a versao anterior desta funcao errava em silencio.
  static bool ocupados[kCapacidadeDoSpool];
  for (uint32_t posicao = 0; posicao < kCapacidadeDoSpool; ++posicao) {
    char caminho[32];
    caminhoDaPosicao(posicao, caminho, sizeof(caminho));
    ocupados[posicao] = LittleFS.exists(caminho);
  }

  const EstadoDaFila estado = deduzirEstadoDaFila(ocupados, kCapacidadeDoSpool);

  // Apaga o que ficou fora do trecho escolhido. Sao restos de uma escrita interrompida
  // por queda de energia; mante-los faria a contagem crescer a cada boot seguinte.
  if (estado.orfaos > 0) {
    for (uint32_t posicao = 0; posicao < kCapacidadeDoSpool; ++posicao) {
      const bool dentro =
          ((posicao - estado.inicio + kCapacidadeDoSpool) % kCapacidadeDoSpool) <
          estado.quantidade;
      if (ocupados[posicao] && !dentro) {
        apagar(posicao);
      }
    }
  }

  inicio = estado.inicio;
  quantidade = estado.quantidade;
  return true;
}

bool SpoolEmLittleFS::escrever(uint32_t posicao, const char *conteudo, size_t tamanho) {
  if (!montado_) {
    return false;
  }
  char caminho[32];
  caminhoDaPosicao(posicao, caminho, sizeof(caminho));

  File arquivo = LittleFS.open(caminho, "w");
  if (!arquivo) {
    return false;
  }
  const size_t escritos =
      arquivo.write(reinterpret_cast<const uint8_t *>(conteudo), tamanho);
  arquivo.close();
  return escritos == tamanho;
}

size_t SpoolEmLittleFS::ler(uint32_t posicao, char *saida, size_t capacidade) {
  if (!montado_) {
    return 0;
  }
  char caminho[32];
  caminhoDaPosicao(posicao, caminho, sizeof(caminho));

  File arquivo = LittleFS.open(caminho, "r");
  if (!arquivo) {
    return 0;
  }
  const size_t tamanho = arquivo.size();
  if (tamanho >= capacidade) {
    arquivo.close();
    return 0;
  }
  const size_t lidos = arquivo.readBytes(saida, tamanho);
  saida[lidos] = '\0';
  arquivo.close();
  return lidos;
}

bool SpoolEmLittleFS::apagar(uint32_t posicao) {
  if (!montado_) {
    return false;
  }
  char caminho[32];
  caminhoDaPosicao(posicao, caminho, sizeof(caminho));
  return LittleFS.remove(caminho) || !LittleFS.exists(caminho);
}

}  // namespace meliponet
