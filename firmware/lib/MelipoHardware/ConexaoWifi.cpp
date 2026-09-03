#include "ConexaoWifi.h"

#include <WiFi.h>
#include <time.h>

namespace meliponet {
namespace {

constexpr uint32_t kEsperaDoNtpMs = 10000;

// Ano de 2023 em epoch. Serve para distinguir "relogio sincronizado" de "relogio ainda
// no valor de fabrica", que comeca em 1970.
constexpr time_t kEpochPlausivel = 1672531200;

}  // namespace

bool ConexaoWifi::iniciar(const char *ssid, const char *senha) {
  ssid_ = ssid;
  senha_ = senha;

  WiFi.mode(WIFI_STA);
  // O ESP32 desliga o WiFi ao dormir por padrao; com o no acordado o tempo todo nesta
  // fase, manter o modem ligado evita reconexoes desnecessarias.
  WiFi.setSleep(false);
  WiFi.begin(ssid_, senha_);

  const uint32_t limite = millis() + 20000;
  while (WiFi.status() != WL_CONNECTED && millis() < limite) {
    delay(200);
  }
  return conectado();
}

bool ConexaoWifi::conectado() const { return WiFi.status() == WL_CONNECTED; }

void ConexaoWifi::manter(uint32_t agora_ms) {
  if (conectado()) {
    recuo_.registrarSucesso();
    return;
  }

  // Sem credenciais nao ha o que tentar. Chegar aqui com ssid_ nulo significaria
  // WiFi.begin(nullptr, ...), que trava a placa.
  if (ssid_ == nullptr) {
    return;
  }

  if (!recuo_.podeTentar(agora_ms)) {
    return;
  }

  // Registra a tentativa **antes** de faze-la: se WiFi.begin bloquear ou a funcao sair
  // por outro caminho, o recuo ja avancou. Nao registrar foi o que travou a versao
  // anterior desta funcao para sempre.
  recuo_.registrarTentativa(agora_ms);

  WiFi.disconnect();
  WiFi.begin(ssid_, senha_);
}

bool ConexaoWifi::sincronizarRelogio() {
  if (!conectado()) {
    return false;
  }

  configTime(0, 0, "pool.ntp.org", "a.st1.ntp.br");

  const uint32_t limite = millis() + kEsperaDoNtpMs;
  while (millis() < limite) {
    const time_t agora = time(nullptr);
    if (agora > kEpochPlausivel) {
      relogio_sincronizado_ = true;
      return true;
    }
    delay(200);
  }
  return false;
}

const char *ConexaoWifi::instanteAtual() {
  const time_t agora = time(nullptr);
  if (agora < kEpochPlausivel) {
    return nullptr;
  }

  struct tm utc;
  gmtime_r(&agora, &utc);
  strftime(instante_, sizeof(instante_), "%Y-%m-%dT%H:%M:%SZ", &utc);
  return instante_;
}

bool ConexaoWifi::rssi(int32_t &saida) const {
  if (!conectado()) {
    return false;
  }
  saida = WiFi.RSSI();
  return true;
}

}  // namespace meliponet
