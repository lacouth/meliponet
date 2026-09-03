#include "Telemetria.h"

namespace meliponet {
namespace {

// Escritor que nunca estoura o buffer: uma vez que a capacidade acaba, ele apenas marca
// o estouro e para de escrever. Assim a checagem de tamanho fica em um lugar so, em vez
// de repetida a cada campo.
class Escritor {
 public:
  Escritor(char *saida, size_t capacidade) : saida_(saida), capacidade_(capacidade) {}

  void por(char c) {
    if (tamanho_ + 1 >= capacidade_) {
      estourou_ = true;
      return;
    }
    saida_[tamanho_++] = c;
  }

  // Emite uma string JSON. As strings do contrato (node_id, ts, gateway_id) sao ASCII
  // controlado, mas escapamos aspas e barras invertidas mesmo assim: um gateway_id
  // malformado nao pode virar um JSON invalido rio abaixo.
  void entreAspas(const char *texto) {
    por('"');
    for (const char *p = texto; *p != '\0'; ++p) {
      if (*p == '"' || *p == '\\') {
        por('\\');
      }
      por(*p);
    }
    por('"');
  }

  // Renderiza um inteiro escalado inserindo a virgula decimal. Com `casas` zero, emite o
  // inteiro puro.
  //
  // Recebe int64_t para acomodar `seq`, que e um uint32_t e nao caberia em int32_t na
  // parte alta da faixa, alem de tornar segura a negacao de INT32_MIN.
  void escalado(int64_t valor, int casas) {
    int64_t modulo = valor;
    const bool negativo = modulo < 0;
    if (negativo) {
      modulo = -modulo;
    }

    char digitos[24];
    size_t quantos = 0;
    do {
      digitos[quantos++] = static_cast<char>('0' + modulo % 10);
      modulo /= 10;
    } while (modulo != 0);

    // Zeros a esquerda para que 12 gramas com 3 casas vire "0.012".
    while (quantos < static_cast<size_t>(casas) + 1) {
      digitos[quantos++] = '0';
    }

    // Um valor que arredonda para zero nao pode sair como "-0.00".
    if (negativo && !soZeros(digitos, quantos)) {
      por('-');
    }

    for (size_t i = quantos; i > 0; --i) {
      if (casas > 0 && i == static_cast<size_t>(casas)) {
        por('.');
      }
      por(digitos[i - 1]);
    }
  }

  size_t finalizar() {
    if (estourou_ || capacidade_ == 0) {
      if (capacidade_ > 0) {
        saida_[0] = '\0';
      }
      return 0;
    }
    saida_[tamanho_] = '\0';
    return tamanho_;
  }

 private:
  static bool soZeros(const char *digitos, size_t quantos) {
    for (size_t i = 0; i < quantos; ++i) {
      if (digitos[i] != '0') {
        return false;
      }
    }
    return true;
  }

  char *saida_;
  size_t capacidade_;
  size_t tamanho_ = 0;
  bool estourou_ = false;
};

// Cuida das chaves e das virgulas do objeto JSON, para que quem escreve os campos nao
// precise lembrar se aquele e o primeiro.
class EscritorDeObjeto {
 public:
  explicit EscritorDeObjeto(Escritor &escritor) : escritor_(escritor) { escritor_.por('{'); }

  void chave(const char *nome) {
    if (primeira_) {
      primeira_ = false;
    } else {
      escritor_.por(',');
    }
    escritor_.entreAspas(nome);
    escritor_.por(':');
  }

  void fechar() { escritor_.por('}'); }

 private:
  Escritor &escritor_;
  bool primeira_ = true;
};

struct NomeDeFlag {
  uint32_t flag;
  const char *nome;
};

// Ordem canonica de emissao das flags.
constexpr NomeDeFlag kNomesDasFlags[] = {
    {Flag::sht_in_fault, "sht_in_fault"}, {Flag::sht_out_fault, "sht_out_fault"},
    {Flag::hx711_fault, "hx711_fault"},   {Flag::mic_fault, "mic_fault"},
    {Flag::low_batt, "low_batt"},         {Flag::clock_unsynced, "clock_unsynced"},
    {Flag::spooled, "spooled"},
};

constexpr int kCasasDasBandasDeSom = 1;

// Emite `"nome":valor` se o campo estiver presente; se nao estiver, nao escreve nada --
// campo ausente e omitido, nunca vira zero.
//
// Cada chamada em `serializar` diz, numa linha so, tudo o que aquele campo precisa: qual
// bit o liga, como ele se chama no JSON e quantas casas decimais tem.
void emitirSePresente(EscritorDeObjeto &objeto, Escritor &escritor, uint32_t presentes,
                      uint32_t campo, const char *nome, int32_t valor, int casas) {
  if (!contem(presentes, campo)) {
    return;
  }
  objeto.chave(nome);
  escritor.escalado(valor, casas);
}

}  // namespace

size_t serializar(const Telemetria &t, char *saida, size_t capacidade) {
  Escritor escritor(saida, capacidade);
  EscritorDeObjeto objeto(escritor);

  objeto.chave("schema");
  escritor.entreAspas("meliponet.telemetry.v1");

  objeto.chave("node_id");
  escritor.entreAspas(t.node_id);

  objeto.chave("seq");
  escritor.escalado(static_cast<int64_t>(t.seq), 0);

  objeto.chave("ts");
  escritor.entreAspas(t.ts);

  // Ordem canonica dos campos numericos. Trocar duas linhas de lugar aqui muda a ordem
  // das chaves no JSON, e o teste dos vetores dourados acusa na hora.
  const uint32_t p = t.presentes;
  emitirSePresente(objeto, escritor, p, Campo::temp_in_c, "temp_in_c", t.temp_in_c, 2);
  emitirSePresente(objeto, escritor, p, Campo::temp_out_c, "temp_out_c", t.temp_out_c, 2);
  emitirSePresente(objeto, escritor, p, Campo::rh_in_pct, "rh_in_pct", t.rh_in_pct, 2);
  emitirSePresente(objeto, escritor, p, Campo::rh_out_pct, "rh_out_pct", t.rh_out_pct, 2);
  emitirSePresente(objeto, escritor, p, Campo::weight_kg, "weight_kg", t.weight_kg, 3);
  emitirSePresente(objeto, escritor, p, Campo::vbat_v, "vbat_v", t.vbat_v, 2);
  emitirSePresente(objeto, escritor, p, Campo::rssi, "rssi", t.rssi, 0);
  emitirSePresente(objeto, escritor, p, Campo::snr, "snr", t.snr, 1);
  emitirSePresente(objeto, escritor, p, Campo::sound_rms, "sound_rms", t.sound_rms, 1);

  if (contem(p, Campo::sound_bands)) {
    objeto.chave("sound_bands");
    escritor.por('[');
    for (size_t i = 0; i < kQuantidadeDeBandasDeSom; ++i) {
      if (i > 0) {
        escritor.por(',');
      }
      escritor.escalado(t.sound_bands[i], kCasasDasBandasDeSom);
    }
    escritor.por(']');
  }

  if (contem(p, Campo::gateway_id)) {
    objeto.chave("gateway_id");
    escritor.entreAspas(t.gateway_id);
  }

  if (t.flags != Flag::nenhuma) {
    objeto.chave("flags");
    escritor.por('[');
    bool primeira = true;
    for (const NomeDeFlag &entrada : kNomesDasFlags) {
      if (!contem(t.flags, entrada.flag)) {
        continue;
      }
      if (!primeira) {
        escritor.por(',');
      }
      primeira = false;
      escritor.entreAspas(entrada.nome);
    }
    escritor.por(']');
  }

  objeto.fechar();
  return escritor.finalizar();
}

}  // namespace meliponet
