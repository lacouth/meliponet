#include "Config.h"

#include <Preferences.h>
#include <WiFi.h>
#include <string.h>

namespace meliponet {
namespace {

constexpr const char *kNamespace = "meliponet";

Preferences g_prefs;
char g_node_id[9] = {0};

void copyString(char *destination, size_t capacity, const String &value) {
  strncpy(destination, value.c_str(), capacity - 1);
  destination[capacity - 1] = '\0';
}

}  // namespace

Config loadConfig() {
  Config config;
  g_prefs.begin(kNamespace, true);

  copyString(config.wifi_ssid, kMaxSsidLength, g_prefs.getString("ssid", ""));
  copyString(config.wifi_password, kMaxPasswordLength, g_prefs.getString("wifi_pw", ""));
  copyString(config.mqtt_host, kMaxHostLength, g_prefs.getString("mqtt_host", ""));
  config.mqtt_port = g_prefs.getUShort("mqtt_port", 1883);
  copyString(config.mqtt_username, kMaxSsidLength, g_prefs.getString("mqtt_user", ""));
  copyString(config.mqtt_password, kMaxPasswordLength, g_prefs.getString("mqtt_pw", ""));
  config.sample_interval_s = g_prefs.getULong("interval_s", 300);
  config.calibration.offset = g_prefs.getInt("cal_offset", 0);
  // Zero por padrao: sem calibracao gravada, o peso e omitido e a flag hx711_fault
  // acende, em vez de o no inventar um valor.
  config.calibration.counts_per_kg = g_prefs.getDouble("cal_scale", 0.0);

  g_prefs.end();
  return config;
}

bool saveConfig(const Config &config) {
  g_prefs.begin(kNamespace, false);

  g_prefs.putString("ssid", config.wifi_ssid);
  g_prefs.putString("wifi_pw", config.wifi_password);
  g_prefs.putString("mqtt_host", config.mqtt_host);
  g_prefs.putUShort("mqtt_port", config.mqtt_port);
  g_prefs.putString("mqtt_user", config.mqtt_username);
  g_prefs.putString("mqtt_pw", config.mqtt_password);
  g_prefs.putULong("interval_s", config.sample_interval_s);
  g_prefs.putInt("cal_offset", config.calibration.offset);
  g_prefs.putDouble("cal_scale", config.calibration.counts_per_kg);

  g_prefs.end();
  return true;
}

uint32_t nextSequence() {
  g_prefs.begin(kNamespace, false);
  const uint32_t current = g_prefs.getULong("seq", 0);
  const uint32_t next = current + 1;
  g_prefs.putULong("seq", next);
  g_prefs.end();
  return next;
}

const char *nodeId() {
  if (g_node_id[0] == '\0') {
    uint8_t mac[6] = {0};
    WiFi.macAddress(mac);
    snprintf(g_node_id, sizeof(g_node_id), "%02X%02X%02X%02X", mac[2], mac[3], mac[4], mac[5]);
  }
  return g_node_id;
}

}  // namespace meliponet
