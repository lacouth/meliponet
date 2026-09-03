// Configuracao do no, guardada na NVS.
//
// Credenciais **nunca** vao no codigo-fonte: o codigo vai para o GitHub, e uma senha
// commitada fica no historico para sempre. Aqui elas moram na memoria nao-volatil do
// proprio no, gravadas por comando serial na hora de preparar o dispositivo.
//
// A `seq` tambem vive aqui, porque precisa sobreviver a reset: um no que reinicia e
// recomeca do 1 tem todas as mensagens descartadas como duplicata, e fica mudo sem que
// nada acuse. Ver docs/guia/04-o-firmware.md.

#pragma once

#include <stddef.h>
#include <stdint.h>

#include "Calibracao.h"

namespace meliponet {

constexpr size_t kMaxTamanhoDoSsid = 33;
constexpr size_t kMaxTamanhoDaSenha = 65;
constexpr size_t kMaxTamanhoDoHost = 65;
// O usuario do broker nao tem relacao com o SSID -- dimensiona-lo pelo tamanho do SSID
// so funcionava por coincidencia, e apertaria o limite errado no dia em que o SSID
// mudasse de tamanho.
constexpr size_t kMaxTamanhoDoUsuario = 65;

struct Configuracao {
  char wifi_ssid[kMaxTamanhoDoSsid] = {0};
  char wifi_senha[kMaxTamanhoDaSenha] = {0};
  char mqtt_host[kMaxTamanhoDoHost] = {0};
  uint16_t mqtt_porta = 1883;
  char mqtt_usuario[kMaxTamanhoDoUsuario] = {0};
  char mqtt_senha[kMaxTamanhoDaSenha] = {0};
  uint32_t intervalo_amostra_s = 300;
  Calibracao calibracao;

  // Verdadeiro se ha o minimo para o no operar. Sem SSID ou host, o no nao tem como
  // publicar e deve entrar em modo de configuracao em vez de tentar e falhar em laco.
  bool utilizavel() const { return wifi_ssid[0] != '\0' && mqtt_host[0] != '\0'; }
};

// Carrega da NVS. Campos ausentes ficam com o padrao.
Configuracao carregarConfiguracao();

// Grava na NVS.
bool gravarConfiguracao(const Configuracao &configuracao);

// Le e incrementa o contador de sequencia, gravando o novo valor antes de devolver.
//
// Grava **antes** de usar, e nao depois de publicar: se o no reiniciar entre o uso e a
// gravacao, e melhor pular uma `seq` (que a plataforma registra como uma lacuna) do que
// reutilizar uma (que a plataforma descarta em silencio como duplicata, perdendo a
// leitura nova).
uint32_t proximaSequencia();

// Identificador do no: os 4 ultimos bytes do MAC, em hexadecimal maiusculo, conforme o
// contrato. Derivar do MAC evita ter de gravar um id unico em cada unidade do lote de
// 20, e o identificador sobrevive a apagar a NVS.
//
// Colisao e improvavel, nao impossivel -- por isso o comando `estado` imprime o id:
// conferi-lo e o primeiro passo diante de um no mudo.
const char *idDoNo();

}  // namespace meliponet
