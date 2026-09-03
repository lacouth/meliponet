#include "Configuracao.h"

#include <Preferences.h>
#include <WiFi.h>
#include <string.h>

namespace meliponet {
namespace {

constexpr const char *kNamespace = "meliponet";

Preferences g_prefs;
char g_id_do_no[9] = {0};

void copiarString(char *destino, size_t capacidade, const String &valor) {
  strncpy(destino, valor.c_str(), capacidade - 1);
  destino[capacidade - 1] = '\0';
}

}  // namespace

// As chaves da NVS ("ssid", "wifi_pw", ...) ficam como estao mesmo que os campos do
// struct mudem de nome: trocar uma chave faz o no perder, em silencio, a configuracao
// que ja estava gravada nele.
Configuracao carregarConfiguracao() {
  Configuracao c;
  g_prefs.begin(kNamespace, true);

  copiarString(c.wifi_ssid, kMaxTamanhoDoSsid, g_prefs.getString("ssid", ""));
  copiarString(c.wifi_senha, kMaxTamanhoDaSenha, g_prefs.getString("wifi_pw", ""));
  copiarString(c.mqtt_host, kMaxTamanhoDoHost, g_prefs.getString("mqtt_host", ""));
  c.mqtt_porta = g_prefs.getUShort("mqtt_port", 1883);
  copiarString(c.mqtt_usuario, kMaxTamanhoDoUsuario, g_prefs.getString("mqtt_user", ""));
  copiarString(c.mqtt_senha, kMaxTamanhoDaSenha, g_prefs.getString("mqtt_pw", ""));
  c.intervalo_amostra_s = g_prefs.getULong("interval_s", 300);
  c.calibracao.tara = g_prefs.getInt("cal_offset", 0);
  // Zero por padrao: sem calibracao gravada, o peso e omitido e a flag hx711_fault
  // acende, em vez de o no inventar um valor.
  c.calibracao.contagens_por_kg = g_prefs.getDouble("cal_scale", 0.0);

  g_prefs.end();
  return c;
}

bool gravarConfiguracao(const Configuracao &c) {
  g_prefs.begin(kNamespace, false);

  g_prefs.putString("ssid", c.wifi_ssid);
  g_prefs.putString("wifi_pw", c.wifi_senha);
  g_prefs.putString("mqtt_host", c.mqtt_host);
  g_prefs.putUShort("mqtt_port", c.mqtt_porta);
  g_prefs.putString("mqtt_user", c.mqtt_usuario);
  g_prefs.putString("mqtt_pw", c.mqtt_senha);
  g_prefs.putULong("interval_s", c.intervalo_amostra_s);
  g_prefs.putInt("cal_offset", c.calibracao.tara);
  g_prefs.putDouble("cal_scale", c.calibracao.contagens_por_kg);

  g_prefs.end();
  return true;
}

uint32_t proximaSequencia() {
  g_prefs.begin(kNamespace, false);
  const uint32_t atual = g_prefs.getULong("seq", 0);
  const uint32_t proxima = atual + 1;
  g_prefs.putULong("seq", proxima);
  g_prefs.end();
  return proxima;
}

const char *idDoNo() {
  if (g_id_do_no[0] == '\0') {
    uint8_t mac[6] = {0};
    WiFi.macAddress(mac);
    snprintf(g_id_do_no, sizeof(g_id_do_no), "%02X%02X%02X%02X", mac[2], mac[3], mac[4],
             mac[5]);
  }
  return g_id_do_no;
}

}  // namespace meliponet
