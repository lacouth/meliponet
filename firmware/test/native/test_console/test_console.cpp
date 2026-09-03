// Divisao da linha de comando do console serial.
//
// Este e o caminho por onde as credenciais entram no no. Um erro aqui grava metade de
// uma senha, e o sintoma em campo -- conecta no WiFi, nunca publica -- e identico ao de
// broker errado, senha errada e firewall. Por isso a divisao e testada no PC.

#include <string.h>
#include <unity.h>

#include "CommandLine.h"

using namespace meliponet;

namespace {

void test_comando_sem_argumentos(void) {
  const Command cmd = splitLine("estado");

  TEST_ASSERT_EQUAL_size_t(1, cmd.count);
  TEST_ASSERT_EQUAL_STRING("estado", cmd.arg[0]);
  TEST_ASSERT_TRUE(cmd.is("estado"));
  TEST_ASSERT_FALSE(cmd.is("estad"));
  TEST_ASSERT_FALSE(cmd.is("estados"));
}

void test_linha_vazia(void) {
  TEST_ASSERT_EQUAL_size_t(0, splitLine("").count);
  TEST_ASSERT_EQUAL_size_t(0, splitLine("    ").count);
  TEST_ASSERT_EQUAL_size_t(0, splitLine(nullptr).count);
  // Linha vazia nao e comando nenhum.
  TEST_ASSERT_FALSE(splitLine("").is("estado"));
}

// O caso que motiva o modulo inteiro: senha com espaco.
void test_senha_com_espaco_chega_inteira(void) {
  const Command cmd = splitLine("wifi MinhaRede senha com espacos");

  TEST_ASSERT_EQUAL_size_t(3, cmd.count);
  TEST_ASSERT_EQUAL_STRING("wifi", cmd.arg[0]);
  TEST_ASSERT_EQUAL_STRING("MinhaRede", cmd.arg[1]);
  TEST_ASSERT_EQUAL_STRING("senha com espacos", cmd.arg[2]);
  TEST_ASSERT_FALSE(cmd.truncated);
}

void test_espacos_repetidos_sao_ignorados(void) {
  const Command cmd = splitLine("  wifi   MinhaRede   segredo");

  TEST_ASSERT_EQUAL_size_t(3, cmd.count);
  TEST_ASSERT_EQUAL_STRING("wifi", cmd.arg[0]);
  TEST_ASSERT_EQUAL_STRING("MinhaRede", cmd.arg[1]);
  // O ultimo argumento leva o resto **a partir do primeiro caractere util**: os espacos
  // antes dele nao entram na senha.
  TEST_ASSERT_EQUAL_STRING("segredo", cmd.arg[2]);
}

void test_argumentos_faltando(void) {
  const Command broker = splitLine("broker mqtt.ifpb.edu.br");

  TEST_ASSERT_EQUAL_size_t(2, broker.count);
  TEST_ASSERT_EQUAL_STRING("broker", broker.arg[0]);
  TEST_ASSERT_EQUAL_STRING("mqtt.ifpb.edu.br", broker.arg[1]);
  // Os argumentos nao preenchidos ficam vazios, nunca com lixo da linha anterior.
  TEST_ASSERT_EQUAL_STRING("", broker.arg[2]);

  // `mqtt` sozinho apaga as credenciais -- precisa ser distinguivel de `mqtt usuario`.
  TEST_ASSERT_EQUAL_size_t(1, splitLine("mqtt").count);
}

// A propriedade que o modulo existe para garantir: um argumento maior do que cabe e
// **sinalizado**, para que quem trata o comando recuse a linha inteira em vez de gravar
// meia senha.
void test_argumento_longo_demais_e_sinalizado(void) {
  char linha[16 + kMaxArgLength + 8] = "wifi rede ";
  for (size_t i = 0; i < kMaxArgLength + 4; ++i) {
    strcat(linha, "x");
  }

  const Command cmd = splitLine(linha);

  TEST_ASSERT_TRUE(cmd.truncated);
  TEST_ASSERT_EQUAL_size_t(3, cmd.count);
  // O que foi copiado continua sendo uma string valida, nunca um buffer sem terminador.
  TEST_ASSERT_EQUAL_size_t(kMaxArgLength - 1, strlen(cmd.arg[2]));

  // E uma linha comprida mas dentro do limite nao levanta a bandeira.
  TEST_ASSERT_FALSE(splitLine("wifi rede senha-comprida-porem-aceitavel").truncated);
}

void test_copia_recusa_o_que_nao_cabe(void) {
  const Command cmd = splitLine("mqtt ingest 123456789");

  char destino[8] = "intacto";
  // "123456789" tem 9 caracteres e nao cabe em 8 com o terminador.
  TEST_ASSERT_FALSE(fitsIn(cmd.arg[2], sizeof(destino)));
  TEST_ASSERT_FALSE(copyText(destino, sizeof(destino), cmd.arg[2]));
  // E o mais importante: recusar nao pode deixar lixo pela metade no destino.
  TEST_ASSERT_EQUAL_STRING("intacto", destino);

  char cabe[10] = {0};
  TEST_ASSERT_TRUE(copyText(cabe, sizeof(cabe), cmd.arg[2]));
  TEST_ASSERT_EQUAL_STRING("123456789", cabe);
}

void test_copia_no_limite_exato(void) {
  const Command cmd = splitLine("x 1234567");

  char destino[8] = {0};
  TEST_ASSERT_TRUE(fitsIn(cmd.arg[1], sizeof(destino)));
  TEST_ASSERT_TRUE(copyText(destino, sizeof(destino), cmd.arg[1]));
  TEST_ASSERT_EQUAL_STRING("1234567", destino);
}

void test_porta_valida(void) {
  uint16_t port = 0;

  TEST_ASSERT_TRUE(parsePort(splitLine("broker host 1883").arg[2], port));
  TEST_ASSERT_EQUAL_UINT16(1883, port);

  TEST_ASSERT_TRUE(parsePort(splitLine("broker host 8883").arg[2], port));
  TEST_ASSERT_EQUAL_UINT16(8883, port);

  TEST_ASSERT_TRUE(parsePort(splitLine("broker host 65535").arg[2], port));
  TEST_ASSERT_EQUAL_UINT16(65535, port);
}

void test_porta_invalida_nao_altera_a_atual(void) {
  uint16_t port = 1883;

  const char *recusadas[] = {"broker host 0",       "broker host 65536", "broker host 99999999",
                             "broker host 18a3",    "broker host -1",    "broker host 1883x",
                             "broker host 1883 lixo"};
  for (const char *linha : recusadas) {
    TEST_ASSERT_FALSE(parsePort(splitLine(linha).arg[2], port));
    // A porta de quem chamou fica como estava: comando recusado nao grava nada.
    TEST_ASSERT_EQUAL_UINT16(1883, port);
  }
}

void test_contagem_valida(void) {
  uint32_t n = 0;

  TEST_ASSERT_TRUE(parseCount(splitLine("ler 1").arg[1], 600, n));
  TEST_ASSERT_EQUAL_UINT32(1, n);

  TEST_ASSERT_TRUE(parseCount(splitLine("ler 600").arg[1], 600, n));
  TEST_ASSERT_EQUAL_UINT32(600, n);
}

void test_contagem_invalida_preserva_o_valor(void) {
  uint32_t n = 7;

  // Zero, acima do teto, nao numerico, e um numero longo o bastante para dar a volta
  // num inteiro de 32 bits se a checagem so acontecesse no fim.
  const char *recusadas[] = {"ler 0", "ler 601", "ler dez", "ler 4294967297", "ler 99999999999999"};
  for (const char *linha : recusadas) {
    TEST_ASSERT_FALSE(parseCount(splitLine(linha).arg[1], 600, n));
    TEST_ASSERT_EQUAL_UINT32(7, n);
  }

  // `ler` sozinho: nao ha argumento para converter, e o padrao de quem chamou vale.
  const Command sozinho = splitLine("ler");
  TEST_ASSERT_EQUAL_size_t(1, sozinho.count);
  TEST_ASSERT_FALSE(parseCount(sozinho.arg[1], 600, n));
  TEST_ASSERT_EQUAL_UINT32(7, n);
}

}  // namespace

void setUp(void) {}
void tearDown(void) {}

int main(int, char **) {
  UNITY_BEGIN();
  RUN_TEST(test_comando_sem_argumentos);
  RUN_TEST(test_linha_vazia);
  RUN_TEST(test_senha_com_espaco_chega_inteira);
  RUN_TEST(test_espacos_repetidos_sao_ignorados);
  RUN_TEST(test_argumentos_faltando);
  RUN_TEST(test_argumento_longo_demais_e_sinalizado);
  RUN_TEST(test_copia_recusa_o_que_nao_cabe);
  RUN_TEST(test_copia_no_limite_exato);
  RUN_TEST(test_porta_valida);
  RUN_TEST(test_porta_invalida_nao_altera_a_atual);
  RUN_TEST(test_contagem_valida);
  RUN_TEST(test_contagem_invalida_preserva_o_valor);
  return UNITY_END();
}
