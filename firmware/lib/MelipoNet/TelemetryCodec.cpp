#include "TelemetryCodec.h"

namespace meliponet {
namespace {

// Escritor que nunca estoura o buffer: uma vez que a capacidade acaba, ele apenas
// marca o overflow e para de escrever. Assim a checagem de tamanho fica em um lugar
// so, em vez de repetida a cada campo.
class Writer {
 public:
  Writer(char *out, size_t capacity) : out_(out), capacity_(capacity) {}

  void raw(const char *text) {
    for (const char *p = text; *p != '\0'; ++p) {
      put(*p);
    }
  }

  void put(char c) {
    if (length_ + 1 >= capacity_) {
      overflow_ = true;
      return;
    }
    out_[length_++] = c;
  }

  // Emite uma string JSON. As strings do contrato (node_id, ts, gateway_id) sao
  // ASCII controlado, mas escapamos aspas e barras invertidas mesmo assim: um
  // gateway_id malformado nao pode virar um JSON invalido rio abaixo.
  void quoted(const char *text) {
    put('"');
    for (const char *p = text; *p != '\0'; ++p) {
      if (*p == '"' || *p == '\\') {
        put('\\');
      }
      put(*p);
    }
    put('"');
  }

  // Renderiza um inteiro escalado inserindo a virgula decimal. Com `decimals` zero,
  // emite o inteiro puro.
  // Recebe int64_t para acomodar `seq`, que e um uint32_t e nao caberia em int32_t
  // na parte alta da faixa, alem de tornar segura a negacao de INT32_MIN.
  void scaled(int64_t value, int decimals) {
    int64_t magnitude = value;
    const bool negative = magnitude < 0;
    if (negative) {
      magnitude = -magnitude;
    }

    char digits[24];
    size_t count = 0;
    do {
      digits[count++] = static_cast<char>('0' + magnitude % 10);
      magnitude /= 10;
    } while (magnitude != 0);

    // Zeros a esquerda para que 12 gramas com 3 casas vire "0.012".
    while (count < static_cast<size_t>(decimals) + 1) {
      digits[count++] = '0';
    }

    // Um valor que arredonda para zero nao pode sair como "-0.00".
    if (negative) {
      bool all_zero = true;
      for (size_t i = 0; i < count; ++i) {
        if (digits[i] != '0') {
          all_zero = false;
          break;
        }
      }
      if (!all_zero) {
        put('-');
      }
    }

    for (size_t i = count; i > 0; --i) {
      if (decimals > 0 && i == static_cast<size_t>(decimals)) {
        put('.');
      }
      put(digits[i - 1]);
    }
  }

  bool overflow() const { return overflow_; }
  size_t length() const { return length_; }

  size_t finish() {
    if (overflow_ || capacity_ == 0) {
      if (capacity_ > 0) {
        out_[0] = '\0';
      }
      return 0;
    }
    out_[length_] = '\0';
    return length_;
  }

 private:
  char *out_;
  size_t capacity_;
  size_t length_ = 0;
  bool overflow_ = false;
};

class ObjectWriter {
 public:
  explicit ObjectWriter(Writer &writer) : writer_(writer) { writer_.put('{'); }

  void key(const char *name) {
    if (first_) {
      first_ = false;
    } else {
      writer_.put(',');
    }
    writer_.quoted(name);
    writer_.put(':');
  }

  void close() { writer_.put('}'); }

 private:
  Writer &writer_;
  bool first_ = true;
};

struct FlagName {
  Flag flag;
  const char *name;
};

// Ordem canonica de emissao das flags.
constexpr FlagName kFlagNames[] = {
    {Flag::sht_in_fault, "sht_in_fault"}, {Flag::sht_out_fault, "sht_out_fault"},
    {Flag::hx711_fault, "hx711_fault"},   {Flag::mic_fault, "mic_fault"},
    {Flag::low_batt, "low_batt"},         {Flag::clock_unsynced, "clock_unsynced"},
    {Flag::spooled, "spooled"},
};

struct NumericField {
  Field field;
  const char *name;
  int decimals;
  int32_t Telemetry::*member;
};

// Ordem canonica de emissao dos campos numericos escalares, com a escala de cada um.
constexpr NumericField kNumericFields[] = {
    {Field::temp_in_c, "temp_in_c", 2, &Telemetry::temp_in_c},
    {Field::temp_out_c, "temp_out_c", 2, &Telemetry::temp_out_c},
    {Field::rh_in_pct, "rh_in_pct", 2, &Telemetry::rh_in_pct},
    {Field::rh_out_pct, "rh_out_pct", 2, &Telemetry::rh_out_pct},
    {Field::weight_kg, "weight_kg", 3, &Telemetry::weight_kg},
    {Field::vbat_v, "vbat_v", 2, &Telemetry::vbat_v},
    {Field::rssi, "rssi", 0, &Telemetry::rssi},
    {Field::snr, "snr", 1, &Telemetry::snr},
    {Field::sound_rms, "sound_rms", 1, &Telemetry::sound_rms},
};

constexpr int kSoundBandDecimals = 1;

}  // namespace

size_t encode(const Telemetry &telemetry, char *out, size_t capacity) {
  Writer writer(out, capacity);
  ObjectWriter object(writer);

  object.key("schema");
  writer.quoted("meliponet.telemetry.v1");

  object.key("node_id");
  writer.quoted(telemetry.node_id);

  object.key("seq");
  writer.scaled(static_cast<int64_t>(telemetry.seq), 0);

  object.key("ts");
  writer.quoted(telemetry.ts);

  for (const NumericField &field : kNumericFields) {
    if (!has(telemetry.present, field.field)) {
      continue;
    }
    object.key(field.name);
    writer.scaled(telemetry.*(field.member), field.decimals);
  }

  if (has(telemetry.present, Field::sound_bands)) {
    object.key("sound_bands");
    writer.put('[');
    for (size_t i = 0; i < kSoundBandCount; ++i) {
      if (i > 0) {
        writer.put(',');
      }
      writer.scaled(telemetry.sound_bands[i], kSoundBandDecimals);
    }
    writer.put(']');
  }

  if (has(telemetry.present, Field::gateway_id)) {
    object.key("gateway_id");
    writer.quoted(telemetry.gateway_id);
  }

  if (telemetry.flags != Flag::none) {
    object.key("flags");
    writer.put('[');
    bool first = true;
    for (const FlagName &entry : kFlagNames) {
      if (!has(telemetry.flags, entry.flag)) {
        continue;
      }
      if (!first) {
        writer.put(',');
      }
      first = false;
      writer.quoted(entry.name);
    }
    writer.put(']');
  }

  object.close();
  return writer.finish();
}

}  // namespace meliponet
