#include "WifiLink.h"

#include <WiFi.h>
#include <time.h>

namespace meliponet {
namespace {

constexpr uint32_t kMinBackoffMs = 1000;
// Teto do recuo: cinco minutos. Sem teto, uma queda longa levaria o intervalo a horas,
// e o no demoraria demais a voltar quando o sinal retornasse.
constexpr uint32_t kMaxBackoffMs = 300000;
constexpr uint32_t kNtpTimeoutMs = 10000;

// Ano de 2023 em epoch. Serve para distinguir "relogio sincronizado" de "relogio ainda
// no valor de fabrica", que comeca em 1970.
constexpr time_t kPlausibleEpoch = 1672531200;

}  // namespace

bool WifiLink::begin(const char *ssid, const char *password) {
  ssid_ = ssid;
  password_ = password;

  WiFi.mode(WIFI_STA);
  // O ESP32 desliga o WiFi ao dormir por padrao; com o no acordado o tempo todo nesta
  // fase, manter o modem ligado evita reconexoes desnecessarias.
  WiFi.setSleep(false);
  WiFi.begin(ssid_, password_);

  const uint32_t deadline = millis() + 20000;
  while (WiFi.status() != WL_CONNECTED && millis() < deadline) {
    delay(200);
  }
  return connected();
}

bool WifiLink::connected() const { return WiFi.status() == WL_CONNECTED; }

void WifiLink::maintain(uint32_t now_ms) {
  if (connected()) {
    backoff_ms_ = kMinBackoffMs;
    return;
  }

  // Subtracao sem sinal: continua correta quando millis() da a volta.
  if ((now_ms - next_attempt_ms_) > kMaxBackoffMs && next_attempt_ms_ != 0) {
    return;
  }
  if (next_attempt_ms_ != 0 && now_ms < next_attempt_ms_) {
    return;
  }

  WiFi.disconnect();
  WiFi.begin(ssid_, password_);

  next_attempt_ms_ = now_ms + backoff_ms_;
  backoff_ms_ = backoff_ms_ * 2 > kMaxBackoffMs ? kMaxBackoffMs : backoff_ms_ * 2;
}

bool WifiLink::syncClock() {
  if (!connected()) {
    return false;
  }

  configTime(0, 0, "pool.ntp.org", "a.st1.ntp.br");

  const uint32_t deadline = millis() + kNtpTimeoutMs;
  while (millis() < deadline) {
    const time_t now = time(nullptr);
    if (now > kPlausibleEpoch) {
      clock_synced_ = true;
      return true;
    }
    delay(200);
  }
  return false;
}

const char *WifiLink::timestamp() {
  const time_t now = time(nullptr);
  if (now < kPlausibleEpoch) {
    return nullptr;
  }

  struct tm utc;
  gmtime_r(&now, &utc);
  strftime(timestamp_, sizeof(timestamp_), "%Y-%m-%dT%H:%M:%SZ", &utc);
  return timestamp_;
}

bool WifiLink::rssi(int32_t &out) const {
  if (!connected()) {
    return false;
  }
  out = WiFi.RSSI();
  return true;
}

}  // namespace meliponet
