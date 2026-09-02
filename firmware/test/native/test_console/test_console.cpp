// Divisao da linha de comando do console serial.
//
// Este e o caminho por onde as credenciais entram no no. Um erro aqui grava metade de
// uma senha, e o sintoma em campo -- conecta no WiFi, nunca publica -- e identico ao de
// broker errado, senha errada e firewall. Por isso a divisao e testada no PC.

#include <string.h>
#include <unity.h>

#include "CommandLine.h"

using meliponet::Arg;
using meliponet::copyArg;
using meliponet::fits;
using meliponet::parseCount;
using meliponet::parsePort;
using meliponet::splitArgs;

namespace {

// Compara um `Arg` com o texto esperado. `Arg::text` aponta para o meio da linha e nao
// e terminado em nulo, entao nao da para usar strcmp direto.
void assertArg(const char *expected, const Arg &arg) {
  TEST_ASSERT_EQUAL_size_t(strlen(expected), arg.length);
  TEST_ASSERT_EQUAL_STRING_LEN(expected, arg.text, arg.length);
}

void test_comando_sem_argumentos(void) {
  Arg args[3];
  TEST_ASSERT_EQUAL_size_t(1, splitArgs("estado", args, 3));
  assertArg("estado", args[0]);
  TEST_ASSERT_TRUE(args[0].equals("estado"));
  TEST_ASSERT_FALSE(args[0].equals("estad"));
  TEST_ASSERT_FALSE(args[0].equals("estados"));
}

void test_linha_vazia(void) {
  Arg args[3];
  TEST_ASSERT_EQUAL_size_t(0, splitArgs("", args, 3));
  TEST_ASSERT_EQUAL_size_t(0, splitArgs("    ", args, 3));
  TEST_ASSERT_EQUAL_size_t(0, splitArgs(nullptr, args, 3));
}

// O caso que motiva o modulo inteiro: senha com espaco.
void test_senha_com_espaco_chega_inteira(void) {
  Arg args[3];
  TEST_ASSERT_EQUAL_size_t(3, splitArgs("wifi MinhaRede senha com espacos", args, 3));
  assertArg("wifi", args[0]);
  assertArg("MinhaRede", args[1]);
  assertArg("senha com espacos", args[2]);
}

void test_espacos_repetidos_sao_ignorados(void) {
  Arg args[3];
  TEST_ASSERT_EQUAL_size_t(3, splitArgs("  wifi   MinhaRede   segredo", args, 3));
  assertArg("wifi", args[0]);
  assertArg("MinhaRede", args[1]);
  // O ultimo argumento leva o resto **a partir do primeiro caractere util**: os espacos
  // antes dele nao entram na senha.
  assertArg("segredo", args[2]);
}

void test_argumentos_faltando(void) {
  Arg args[3];
  TEST_ASSERT_EQUAL_size_t(2, splitArgs("broker mqtt.ifpb.edu.br", args, 3));
  assertArg("broker", args[1 - 1]);
  assertArg("mqtt.ifpb.edu.br", args[1]);

  // `mqtt` sozinho apaga as credenciais -- precisa ser distinguivel de `mqtt usuario`.
  TEST_ASSERT_EQUAL_size_t(1, splitArgs("mqtt", args, 3));
}

void test_copia_recusa_o_que_nao_cabe(void) {
  Arg args[3];
  splitArgs("mqtt ingest 123456789", args, 3);

  char destino[8] = "intacto";
  // "123456789" tem 9 caracteres e nao cabe em 8 com o terminador.
  TEST_ASSERT_FALSE(copyArg(args[2], destino, sizeof(destino)));
  // E o mais importante: recusar nao pode deixar lixo pela metade no destino.
  TEST_ASSERT_EQUAL_STRING("intacto", destino);

  char cabe[10] = {0};
  TEST_ASSERT_TRUE(copyArg(args[2], cabe, sizeof(cabe)));
  TEST_ASSERT_EQUAL_STRING("123456789", cabe);
}

void test_copia_no_limite_exato(void) {
  Arg args[2];
  splitArgs("x 1234567", args, 2);

  char destino[8] = {0};
  TEST_ASSERT_TRUE(fits(args[1], sizeof(destino)));
  TEST_ASSERT_TRUE(copyArg(args[1], destino, sizeof(destino)));
  TEST_ASSERT_EQUAL_STRING("1234567", destino);
}

void test_porta_valida(void) {
  Arg args[3];
  uint16_t port = 0;

  splitArgs("broker host 1883", args, 3);
  TEST_ASSERT_TRUE(parsePort(args[2], port));
  TEST_ASSERT_EQUAL_UINT16(1883, port);

  splitArgs("broker host 8883", args, 3);
  TEST_ASSERT_TRUE(parsePort(args[2], port));
  TEST_ASSERT_EQUAL_UINT16(8883, port);

  splitArgs("broker host 65535", args, 3);
  TEST_ASSERT_TRUE(parsePort(args[2], port));
  TEST_ASSERT_EQUAL_UINT16(65535, port);
}

void test_porta_invalida_nao_altera_a_atual(void) {
  Arg args[3];
  uint16_t port = 1883;

  const char *recusadas[] = {"broker host 0",       "broker host 65536", "broker host 99999999",
                             "broker host 18a3",    "broker host -1",    "broker host 1883x",
                             "broker host 1883 lixo"};
  for (const char *linha : recusadas) {
    splitArgs(linha, args, 3);
    TEST_ASSERT_FALSE(parsePort(args[2], port));
    // A porta de quem chamou fica como estava: comando recusado nao grava nada.
    TEST_ASSERT_EQUAL_UINT16(1883, port);
  }
}

void test_contagem_valida(void) {
  Arg args[2];
  uint32_t n = 0;

  splitArgs("ler 1", args, 2);
  TEST_ASSERT_TRUE(parseCount(args[1], 600, n));
  TEST_ASSERT_EQUAL_UINT32(1, n);

  splitArgs("ler 600", args, 2);
  TEST_ASSERT_TRUE(parseCount(args[1], 600, n));
  TEST_ASSERT_EQUAL_UINT32(600, n);
}

void test_contagem_invalida_preserva_o_valor(void) {
  Arg args[2];
  uint32_t n = 7;

  // Zero, acima do teto, nao numerico, e um numero longo o bastante para dar a volta
  // num inteiro de 32 bits se a checagem so acontecesse no fim.
  const char *recusadas[] = {"ler 0", "ler 601", "ler dez", "ler 4294967297", "ler 99999999999999"};
  for (const char *linha : recusadas) {
    splitArgs(linha, args, 2);
    TEST_ASSERT_FALSE(parseCount(args[1], 600, n));
    TEST_ASSERT_EQUAL_UINT32(7, n);
  }

  // `ler` sozinho: nao ha argumento para converter, e o padrao de quem chamou vale.
  TEST_ASSERT_EQUAL_size_t(1, splitArgs("ler", args, 2));
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
  RUN_TEST(test_copia_recusa_o_que_nao_cabe);
  RUN_TEST(test_copia_no_limite_exato);
  RUN_TEST(test_porta_valida);
  RUN_TEST(test_porta_invalida_nao_altera_a_atual);
  RUN_TEST(test_contagem_valida);
  RUN_TEST(test_contagem_invalida_preserva_o_valor);
  return UNITY_END();
}
