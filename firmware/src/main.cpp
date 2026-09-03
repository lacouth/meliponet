// MelipoSense -- firmware do no sensor.
//
// Fase 3 (prototipo): le os dois SHT30 e a celula de carga e publica a telemetria direto
// no broker MQTT por WiFi, no mesmo topico e formato que o gateway LoRa usara na Fase 5.
//
// Este arquivo so **orquestra**. Ele nao sabe converter uma leitura em inteiro escalado,
// nem decidir qual flag acender, nem gerir a fila do spool -- essas decisoes moram em
// lib/, sem dependencia do Arduino, e sao exercitadas por `pio test -e native` no PC.
// A separacao nao e estetica: e o que permite testar as decisoes dificeis sem ter o
// hardware na mao, e sem esperar dias por uma queda de rede real.

#include <Arduino.h>

#include "Agenda.h"
#include "Amostra.h"
#include "Calibracao.h"
#include "CelulaDeCarga.h"
#include "ConexaoWifi.h"
#include "Configuracao.h"
#include "LinhaDeComando.h"
#include "PublicadorMqtt.h"
#include "SensoresSht.h"
#include "Spool.h"
#include "SpoolEmLittleFS.h"
#include "Telemetria.h"

// Todo o firmware vive no namespace `meliponet`. Abri-lo aqui, uma vez, evita repetir
// `meliponet::` em cada uma das dezenas de chamadas deste arquivo.
using namespace meliponet;

namespace {

// Pinos. Ajuste conforme a placa do lote.
constexpr int kPinoSda = 6;
constexpr int kPinoScl = 7;
constexpr int kPinoDadosHx711 = 4;
constexpr int kPinoClockHx711 = 5;
constexpr int kPinoAdcDaBateria = 0;

// O divisor resistivo da bateria: 2 x 100 kOhm, entao a tensao lida e metade da real.
constexpr double kDivisorDaBateria = 2.0;
constexpr double kReferenciaDoAdcV = 3.3;
constexpr double kContagemMaximaDoAdc = 4095.0;

// Quantas leituras seguidas o comando `ler` aceita repetir. O teto existe para que um
// numero digitado errado nao prenda o console por horas.
constexpr uint32_t kMaxLeiturasDeBancada = 600;

Configuracao g_configuracao;
SensoresSht g_sht;
CelulaDeCarga g_celula;
ConexaoWifi g_wifi;
PublicadorMqtt g_mqtt;
SpoolEmLittleFS g_armazenamento;
Spool g_spool(g_armazenamento);
Agenda g_agenda;

// Se o `setup` chegou a configurar rede e amostragem. O laco principal se guia por esta
// bandeira, e nao por `g_configuracao.utilizavel()`: a configuracao pelo console serial
// pode tornar `utilizavel()` verdadeiro no meio da execucao, e o laco entraria com a
// conexao WiFi e o publicador ainda nao configurados. Por isso os comandos de
// configuracao pedem reinicio.
bool g_operando = false;

Leitura lerBateria() {
  const int contagem = analogRead(kPinoAdcDaBateria);
  if (contagem <= 0) {
    return Leitura::falha();
  }
  return Leitura::obtida((contagem / kContagemMaximaDoAdc) * kReferenciaDoAdcV *
                         kDivisorDaBateria);
}

// Tenta publicar; se falhar, guarda no spool. Nunca descarta em silencio.
void publicarOuGuardar(const char *conteudo, size_t tamanho) {
  if (g_mqtt.publicar(conteudo, tamanho)) {
    return;
  }
  if (!g_spool.guardar(conteudo, tamanho)) {
    Serial.println("[erro] falha ao guardar no spool; medicao perdida");
  } else {
    Serial.printf("[spool] guardada; %u pendentes\n",
                  static_cast<unsigned>(g_spool.quantidade()));
  }
}

// Drena o spool, uma mensagem por vez. Uma por chamada, e nao todas de uma vez, para nao
// segurar o laco principal por minutos apos uma queda longa -- o que atrasaria a proxima
// amostragem e criaria uma lacuna nova enquanto se recupera da antiga.
void drenarSpool() {
  if (g_spool.vazio() || !g_mqtt.conectado()) {
    return;
  }

  char buffer[kTamanhoMaximoDoJson];
  const size_t tamanho = g_spool.espiar(buffer, sizeof(buffer));
  if (tamanho == 0) {
    g_spool.remover();  // entrada ilegivel: descarta para nao travar a fila
    return;
  }

  // So remove depois da confirmacao: remover antes perderia a mensagem se a publicacao
  // falhasse, que e justamente o cenario em que o spool existe.
  if (g_mqtt.publicar(buffer, tamanho)) {
    g_spool.remover();
  }
}

void amostrar() {
  const LeiturasSht sht = g_sht.ler();

  LeiturasDosSensores sensores;
  sensores.temp_int = sht.temp_int;
  sensores.ur_int = sht.ur_int;
  sensores.temp_ext = sht.temp_ext;
  sensores.ur_ext = sht.ur_ext;
  sensores.peso = g_celula.ler();
  sensores.bateria = lerBateria();
  sensores.rssi_valido = g_wifi.rssi(sensores.rssi);

  const char *instante = g_wifi.instanteAtual();
  if (instante == nullptr) {
    // Sem relogio confiavel nao ha o que gravar: um `ts` inventado poluiria a serie de
    // forma dificil de desfazer depois. Melhor pular esta amostra e tentar sincronizar.
    Serial.println("[aviso] relogio nao sincronizado; amostra descartada");
    g_wifi.sincronizarRelogio();
    return;
  }

  ContextoDaAmostra contexto;
  contexto.node_id = idDoNo();
  contexto.seq = proximaSequencia();
  contexto.ts = instante;
  contexto.relogio_sincronizado = g_wifi.relogioSincronizado();

  const Telemetria telemetria = montarTelemetria(contexto, sensores);

  char conteudo[kTamanhoMaximoDoJson];
  const size_t tamanho = serializar(telemetria, conteudo, sizeof(conteudo));
  if (tamanho == 0) {
    Serial.println("[erro] telemetria nao coube no buffer");
    return;
  }

  Serial.printf("[amostra] %s\n", conteudo);
  publicarOuGuardar(conteudo, tamanho);
}

// Imprime uma leitura em unidade fisica e, ao lado, o inteiro escalado que iria para a
// mensagem.
//
// Mostrar o par lado a lado e o ponto do comando: e na bancada que a regra central do
// contrato -- metrica nenhuma trafega como float -- deixa de ser um paragrafo de
// documento e vira uma coisa que se ve. 30,12 C vira 3012, e nao "30.12".
void imprimirLeitura(const char *rotulo, const Leitura &leitura, const char *unidade,
                     const Metrica &metrica) {
  if (!leitura.valida) {
    Serial.printf("  %-9s ausente\n", rotulo);
    return;
  }

  const Escalado escalado = escalarNaFaixa(leitura.valor, metrica);
  if (!escalado.ok) {
    // Fora da faixa fisica do sensor: a mensagem real omitiria o campo e ligaria a flag.
    // Dizer isso aqui evita a conclusao errada de que o valor seria enviado.
    Serial.printf("  %-9s %.3f %s  FORA DA FAIXA -- seria omitida da mensagem\n", rotulo,
                  leitura.valor, unidade);
    return;
  }

  Serial.printf("  %-9s %.3f %s  (escalado: %ld)\n", rotulo, leitura.valor, unidade,
                static_cast<long>(escalado.valor));
}

// Leitura imediata dos sensores, para a bancada.
//
// Nao toca em WiFi, MQTT, relogio nem `seq`, de proposito: o objetivo e verificar
// sensores, ligacao e calibracao numa mesa, com a placa alimentada so pelo cabo USB.
// Consumir `seq` aqui seria pior do que inutil -- cada teste de bancada abriria uma
// lacuna permanente na serie do no depois de instalado, e a lacuna e exatamente o
// indicador que o projeto se compromete a minimizar.
void lerNaBancada(uint32_t repeticoes) {
  for (uint32_t i = 1; i <= repeticoes; ++i) {
    const LeiturasSht sht = g_sht.ler();

    Serial.printf("[leitura %lu/%lu]\n", static_cast<unsigned long>(i),
                  static_cast<unsigned long>(repeticoes));
    imprimirLeitura("temp int", sht.temp_int, "C", kTemperatura);
    imprimirLeitura("ur int", sht.ur_int, "%", kUmidade);
    imprimirLeitura("temp ext", sht.temp_ext, "C", kTemperatura);
    imprimirLeitura("ur ext", sht.ur_ext, "%", kUmidade);

    // A contagem bruta e lida uma vez e reaproveitada na conversao. Chamar `ler()` aqui
    // repetiria as dez leituras mediadas do HX711 -- um segundo inteiro a mais por
    // iteracao, para chegar ao mesmo numero.
    int32_t contagem = 0;
    if (g_celula.lerContagem(contagem)) {
      // A contagem bruta aparece mesmo sem calibracao gravada, e e isso que permite
      // conferir a ligacao da celula antes de calibrar: apertar a plataforma com a mao
      // move a contagem.
      Serial.printf("  %-9s %ld contagens\n", "hx711", static_cast<long>(contagem));
      const Peso peso = paraQuilogramas(contagem, g_celula.calibracao());
      imprimirLeitura("peso", peso.ok ? Leitura::obtida(peso.kg) : Leitura::falha(), "kg",
                      kPeso);
    } else {
      Serial.printf("  %-9s sem resposta -- confira alimentacao e os fios DT/SCK\n", "hx711");
    }

    imprimirLeitura("bateria", lerBateria(), "V", kTensao);

    if (i < repeticoes) {
      delay(1000);
    }
  }
}

// --- comandos do console -----------------------------------------------------------
//
// E por aqui que as credenciais entram na NVS, em vez de irem no codigo-fonte.
//
// Cada comando e uma funcao pequena que recebe a linha ja dividida, e a tabela
// `kComandos`, logo abaixo delas, liga o nome digitado a funcao. **Para acrescentar um
// comando novo: escreva a funcao aqui e ponha uma linha na tabela.** O `ajuda` percorre
// a mesma tabela, entao ele nao tem como ficar desatualizado.

void comandoWifi(const Comando &cmd) {
  if (cmd.quantidade < 3) {
    Serial.println("uso: wifi <ssid> <senha>");
    return;
  }
  // Os dois tamanhos sao conferidos **antes** de copiar qualquer um: gravar o ssid e
  // recusar a senha deixaria a configuracao pela metade.
  if (!cabeEm(cmd.argumento[1], kMaxTamanhoDoSsid) ||
      !cabeEm(cmd.argumento[2], kMaxTamanhoDaSenha)) {
    Serial.println("ssid ou senha longos demais; nada foi gravado");
    return;
  }
  copiarTexto(g_configuracao.wifi_ssid, kMaxTamanhoDoSsid, cmd.argumento[1]);
  copiarTexto(g_configuracao.wifi_senha, kMaxTamanhoDaSenha, cmd.argumento[2]);
  gravarConfiguracao(g_configuracao);
  Serial.println("wifi gravado; reinicie");
}

void comandoBroker(const Comando &cmd) {
  if (cmd.quantidade < 2) {
    Serial.println("uso: broker <host> [porta]");
    return;
  }
  // Sem porta explicita, mantem a que ja estava gravada -- trocar so o host nao pode
  // devolver a porta ao padrao sem avisar.
  uint16_t porta = g_configuracao.mqtt_porta;
  if (cmd.quantidade >= 3 && !lerPorta(cmd.argumento[2], porta)) {
    Serial.println("porta invalida (1..65535); nada foi gravado");
    return;
  }
  if (!copiarTexto(g_configuracao.mqtt_host, kMaxTamanhoDoHost, cmd.argumento[1])) {
    Serial.println("host longo demais; nada foi gravado");
    return;
  }
  g_configuracao.mqtt_porta = porta;
  gravarConfiguracao(g_configuracao);
  Serial.printf("broker gravado (%s:%u); reinicie\n", g_configuracao.mqtt_host,
                static_cast<unsigned>(g_configuracao.mqtt_porta));
}

void comandoMqtt(const Comando &cmd) {
  // Sem argumentos, apaga: e o caminho para um broker de desenvolvimento com
  // `allow_anonymous true`, e a unica forma de tirar uma credencial errada da NVS sem
  // apagar a particao inteira.
  if (cmd.quantidade == 1) {
    g_configuracao.mqtt_usuario[0] = '\0';
    g_configuracao.mqtt_senha[0] = '\0';
    gravarConfiguracao(g_configuracao);
    Serial.println("credenciais do broker apagadas; reinicie");
    return;
  }
  if (cmd.quantidade < 3) {
    Serial.println("uso: mqtt <usuario> <senha>   (sem argumentos, apaga)");
    return;
  }
  if (!cabeEm(cmd.argumento[1], kMaxTamanhoDoUsuario) ||
      !cabeEm(cmd.argumento[2], kMaxTamanhoDaSenha)) {
    Serial.println("usuario ou senha longos demais; nada foi gravado");
    return;
  }
  copiarTexto(g_configuracao.mqtt_usuario, kMaxTamanhoDoUsuario, cmd.argumento[1]);
  copiarTexto(g_configuracao.mqtt_senha, kMaxTamanhoDaSenha, cmd.argumento[2]);
  gravarConfiguracao(g_configuracao);
  // A senha nunca e ecoada: o monitor serial vai para o log do terminal de quem preparou
  // o no, e de la para um print numa conversa.
  Serial.printf("credenciais gravadas para %s; reinicie\n", g_configuracao.mqtt_usuario);
}

void comandoTara(const Comando &) {
  int32_t contagem = 0;
  if (!g_celula.lerContagem(contagem)) {
    Serial.println("HX711 nao respondeu");
    return;
  }
  g_configuracao.calibracao.tara = contagem;
  // A celula precisa receber a calibracao nova junto, e nao so a NVS. Sem esta linha o
  // objeto seguia com o zero que recebeu no boot: a leitura logo apos a tara saia com a
  // tara antiga, e so um reinicio fazia a nova valer. Na bancada isso leva a pessoa a
  // repetir a tara varias vezes achando que ela nao pegou.
  g_celula.definirCalibracao(g_configuracao.calibracao);
  gravarConfiguracao(g_configuracao);
  Serial.printf("tara = %ld\n", static_cast<long>(contagem));
}

void comandoCalibrar(const Comando &cmd) {
  // Uso: coloque uma massa-padrao conhecida e mande `calibrar <kg>`.
  // Verifique depois em varios pontos da faixa, e nao so neste: um ponto so ajusta a
  // escala e esconde a nao-linearidade da celula.
  if (cmd.quantidade < 2) {
    Serial.println("uso: calibrar <kg>");
    return;
  }
  // `atof` devolve 0.0 para texto nao numerico, e `calcularCalibracao` recusa massa <= 0.
  const double massa_kg = atof(cmd.argumento[1]);
  int32_t contagem = 0;
  if (!g_celula.lerContagem(contagem)) {
    Serial.println("HX711 nao respondeu");
    return;
  }
  const Calibracao nova =
      calcularCalibracao(g_configuracao.calibracao.tara, contagem, massa_kg);
  if (!nova.valida()) {
    Serial.println("calibracao invalida: confira a massa e a ligacao da celula");
    return;
  }
  g_configuracao.calibracao = nova;
  g_celula.definirCalibracao(nova);
  gravarConfiguracao(g_configuracao);
  Serial.printf("escala = %.2f contagens/kg\n", nova.contagens_por_kg);
}

void comandoLer(const Comando &cmd) {
  // Repeticoes opcionais: `ler 30` acompanha meia hora de deriva, ou mostra o peso
  // mudando enquanto se poe massa na plataforma. Sem argumento, uma leitura so.
  uint32_t repeticoes = 1;
  if (cmd.quantidade >= 2 &&
      !lerNumero(cmd.argumento[1], kMaxLeiturasDeBancada, repeticoes)) {
    Serial.printf("uso: ler [n]   (1 a %lu)\n",
                  static_cast<unsigned long>(kMaxLeiturasDeBancada));
    return;
  }
  lerNaBancada(repeticoes);
}

void comandoSondar(const Comando &) {
  // Os sensores sao detectados uma vez, no boot. Na bancada isso atrapalha: ligar um
  // SHT30 depois de a placa subir deixa o sensor marcado como ausente ate alguem
  // reiniciar. Este comando refaz a deteccao sem reiniciar.
  const bool sht_ok = g_sht.iniciar(kPinoSda, kPinoScl);
  const bool celula_ok =
      g_celula.iniciar(kPinoDadosHx711, kPinoClockHx711, g_configuracao.calibracao);
  Serial.printf("sht int   %s\n", g_sht.internoPresente() ? "ok" : "ausente");
  Serial.printf("sht ext   %s\n", g_sht.externoPresente() ? "ok" : "ausente");
  Serial.printf("hx711     %s\n", celula_ok ? "ok" : "ausente");
  if (!sht_ok && !celula_ok) {
    Serial.println("nenhum sensor respondeu: confira alimentacao, fios e enderecos I2C");
  }
}

void comandoEstado(const Comando &) {
  Serial.printf("no        %s\n", idDoNo());
  Serial.printf("wifi      %s\n", g_wifi.conectado() ? "conectado" : "desconectado");
  Serial.printf("broker    %s em %s:%u\n", g_mqtt.conectado() ? "conectado" : "desconectado",
                g_configuracao.mqtt_host,
                static_cast<unsigned>(g_configuracao.mqtt_porta));
  Serial.printf("mqtt auth %s, senha %s\n",
                g_configuracao.mqtt_usuario[0] != '\0' ? g_configuracao.mqtt_usuario
                                                       : "anonimo",
                g_configuracao.mqtt_senha[0] != '\0' ? "definida" : "ausente");
  Serial.printf("relogio   %s\n",
                g_wifi.relogioSincronizado() ? "sincronizado" : "NAO sincronizado");
  Serial.printf("sht int   %s\n", g_sht.internoPresente() ? "ok" : "ausente");
  Serial.printf("sht ext   %s\n", g_sht.externoPresente() ? "ok" : "ausente");
  Serial.printf("calibrac. %s\n", g_configuracao.calibracao.valida() ? "ok" : "AUSENTE");
  Serial.printf("spool     %u pendentes, %u descartadas\n",
                static_cast<unsigned>(g_spool.quantidade()),
                static_cast<unsigned>(g_spool.descartadas()));
}

// Definido depois da tabela, porque e a tabela que ele percorre.
void comandoAjuda(const Comando &cmd);

// O nome digitado, a funcao que o atende, e a linha que o `ajuda` imprime.
struct ComandoDoConsole {
  const char *nome;
  void (*executar)(const Comando &);
  const char *ajuda;
};

constexpr ComandoDoConsole kComandos[] = {
    {"wifi", comandoWifi, "wifi <ssid> <senha>          credenciais da rede"},
    {"broker", comandoBroker, "broker <host> [porta]        endereco do broker MQTT"},
    {"mqtt", comandoMqtt,
     "mqtt <usuario> <senha>       credenciais do broker (sem argumentos, apaga)"},
    {"tara", comandoTara, "tara                         zera a celula com a colmeia vazia"},
    {"calibrar", comandoCalibrar,
     "calibrar <kg>                calibra com uma massa-padrao conhecida"},
    {"ler", comandoLer, "ler [n]                      le os sensores agora, sem publicar nada"},
    {"sondar", comandoSondar, "sondar                       redetecta os sensores, sem reiniciar"},
    {"estado", comandoEstado, "estado                       sensores, conexoes, calibracao e spool"},
    {"ajuda", comandoAjuda, "ajuda                        esta lista"},
    {"?", comandoAjuda, "?                            o mesmo que `ajuda`"},
};

void comandoAjuda(const Comando &) {
  for (const ComandoDoConsole &entrada : kComandos) {
    Serial.println(entrada.ajuda);
  }
}

// Le uma linha do serial e entrega ao comando correspondente.
void atenderConsole() {
  if (!Serial.available()) {
    return;
  }
  String linha = Serial.readStringUntil('\n');
  linha.trim();

  const Comando cmd = dividirLinha(linha.c_str());
  if (cmd.quantidade == 0) {
    return;
  }
  // Um argumento maior do que cabe derruba a linha inteira, e nao so aquele argumento:
  // gravar meia senha produz um no que tenta autenticar para sempre sem que nada no
  // serial explique o motivo.
  if (cmd.truncado) {
    Serial.println("argumento longo demais; nada foi gravado");
    return;
  }

  for (const ComandoDoConsole &entrada : kComandos) {
    if (cmd.ehComando(entrada.nome)) {
      entrada.executar(cmd);
      return;
    }
  }

  Serial.printf("comando desconhecido: %s  (use `ajuda`)\n", cmd.argumento[0]);
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.printf("\nMelipoSense %s\n", idDoNo());

  g_configuracao = carregarConfiguracao();

  uint32_t inicio = 0;
  uint32_t quantidade = 0;
  if (g_armazenamento.iniciar(inicio, quantidade)) {
    // Restaura a fila do reinicio: mensagens guardadas antes de uma queda de energia
    // continuam pendentes, em vez de virarem lacuna.
    g_spool.restaurar(inicio, quantidade);
    Serial.printf("[spool] %u mensagens recuperadas\n", static_cast<unsigned>(quantidade));
  }

  g_agenda.iniciar(g_configuracao.intervalo_amostra_s * 1000UL, millis());

  if (!g_sht.iniciar(kPinoSda, kPinoScl)) {
    Serial.println("[aviso] nenhum SHT30 respondeu");
  }
  if (!g_celula.iniciar(kPinoDadosHx711, kPinoClockHx711, g_configuracao.calibracao)) {
    Serial.println("[aviso] HX711 nao respondeu");
  }
  if (!g_configuracao.calibracao.valida()) {
    Serial.println("[aviso] celula sem calibracao: use `tara` e `calibrar <kg>`");
  }

  if (!g_configuracao.utilizavel()) {
    // Sem credenciais nao ha o que tentar. Ficar em laco de reconexao gastaria bateria
    // sem chance de sucesso; melhor esperar a configuracao pelo serial.
    Serial.println("[config] sem wifi ou broker; use `wifi` e `broker`. `ajuda` lista tudo.");
    // Nao publicar nao impede testar: `ler` funciona sem rede nenhuma, e e assim que a
    // bancada verifica sensores e calibracao antes de o no ter para onde enviar.
    Serial.println("[config] para conferir os sensores agora, use `ler`.");
    return;
  }

  // O MQTT e configurado **sempre**, e nao so quando o WiFi sobe de primeira. Um no que
  // liga mais rapido que o roteador -- rotina depois de uma falta de energia -- ficaria
  // com servidor e topicos vazios, e nunca mais publicaria nada, mesmo depois de o WiFi
  // reconectar sozinho.
  g_mqtt.configurar(idDoNo(), g_configuracao.mqtt_host, g_configuracao.mqtt_porta,
                    g_configuracao.mqtt_usuario, g_configuracao.mqtt_senha);

  if (g_wifi.iniciar(g_configuracao.wifi_ssid, g_configuracao.wifi_senha)) {
    g_wifi.sincronizarRelogio();
    g_mqtt.manter(millis());
  } else {
    Serial.println("[aviso] wifi indisponivel no boot; reconexao em segundo plano");
  }

  g_operando = true;
}

void loop() {
  atenderConsole();

  if (!g_operando) {
    delay(100);
    return;
  }

  const uint32_t agora = millis();
  g_wifi.manter(agora);
  g_mqtt.manter(agora);
  g_mqtt.processar();

  if (g_wifi.conectado() && !g_wifi.relogioSincronizado()) {
    g_wifi.sincronizarRelogio();
  }

  if (g_agenda.venceu(agora)) {
    g_agenda.marcar(agora);
    amostrar();
  }

  drenarSpool();
  delay(50);
}
