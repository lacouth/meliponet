# 07. O mutante que ninguém pega

**Área:** firmware e plataforma · **Tempo:** ~1 h · **Treino — e pode virar um PR**

## Por que este exercício existe

Nos três exercícios anteriores, quase toda mutação derrubou algum teste. Isso dá uma
sensação boa e enganosa: a de que a suíte cobre tudo.

Não cobre. Este exercício mostra três mutações que **passam em todos os testes** — e as
três são defeitos de verdade, do tipo que só apareceria em campo. Você vai encontrá-las,
entender por que a suíte não as vê, e escrever o teste que falta.

E aqui a saída deixa de ser treino: **os testes que você escrever podem virar um pull
request.** Eles são exatamente o tipo de contribuição que o projeto quer — um teste que
fecha um buraco descoberto de propósito.

## Antes de começar

- Exercícios [04](04-mutantes-do-firmware.md), [05](05-mutantes-da-plataforma.md) e
  [06](06-mutante-do-contrato.md) feitos.
- `./verificar` verde agora.

**Combine antes de começar.** Cada um dos três testes é uma contribuição; duas pessoas
escrevendo o mesmo desperdiça o trabalho de uma. O exercício em si — aplicar, rodar,
entender — todo mundo faz.

## O método

Para cada mutante, o ciclo é:

1. Aplique a mutação e rode a suíte. **Confirme que nada falha.**
2. **Não reverta ainda.** Com o mutante aplicado, escreva um teste que o pegue — e
   veja-o falhar.
3. Reverta o mutante (`git restore`) e rode o teste de novo. Ele tem de **passar**.
4. Só um teste que já falhou prova alguma coisa. É por isso que a ordem é esta.

---

## Mutante A — o agendamento perto da volta de `millis()`

**Arquivo:** `firmware/lib/MelipoCore/Agenda.h`, método `venceu`.

```cpp
// antes
  bool venceu(uint32_t agora_ms) const { return (agora_ms - ultima_ms_) >= intervalo_ms_; }

// depois
  bool venceu(uint32_t agora_ms) const { return agora_ms >= ultima_ms_ + intervalo_ms_; }
```

Esta é **exatamente** a forma ingênua que [O firmware](../guia/04-o-firmware.md#millis-volta-a-zero-a-cada-497-dias)
descreve como errada, e que a `Agenda` foi escrita para evitar. Existe até um teste
chamado `test_volta_do_contador_de_millis`.

Rode `pio test -e native -d firmware`.

<details>
<summary>O que acontece, e por quê</summary>

**63 succeeded.** Nada falha — nem o teste que tem "volta do contador" no nome.

Vale entender direito, porque é sutil. O teste existente faz:

```cpp
const uint32_t quase_no_fim = 0xFFFFFF00u;
agenda.iniciar(1000, quase_no_fim);
TEST_ASSERT_FALSE(agenda.venceu(quase_no_fim + 500));
TEST_ASSERT_TRUE(agenda.venceu(quase_no_fim + 1000));
TEST_ASSERT_TRUE(agenda.venceu(0x00000300u));
```

Repare que `quase_no_fim + 500` e `quase_no_fim + 1000` **também dão a volta** — são
`uint32_t`. E `ultima_ms_ + intervalo_ms_`, dentro do mutante, dá a volta do mesmo jeito.
As duas versões giram juntas, e concordam em todos os três pontos que o teste escolheu.

O caso em que elas discordam é outro: **`agora` ainda não deu a volta, mas a soma já deu.**

```
ultima_ms_ = 0xFFFFFF00      intervalo = 1000
ultima_ms_ + intervalo       = 0x000002E8   (deu a volta)
agora_ms   = 0xFFFFFF80      (so 128 ms se passaram)

correto:  0xFFFFFF80 - 0xFFFFFF00 = 128 >= 1000?      false  -> nao amostra
mutante:  0xFFFFFF80 >= 0x000002E8?                    TRUE  -> AMOSTRA JA
```

O mutante dispara **antes da hora**. E não uma vez: durante todo o último intervalo antes
da volta, `venceu` devolve verdadeiro a cada passagem pelo `loop()`. O nó dispara uma rajada
de amostras, cada uma consumindo uma `seq` da NVS, uma vez a cada 49,7 dias.

O teste existente não é ruim — ele pega a forma **mais** ingênua (`agora > proxima`, com
`proxima` guardado). Só não alcança esta.
</details>

### O teste que falta

Acrescente em `firmware/test/native/test_calibracao_e_agenda/test_calibracao_e_agenda.cpp`
(e não esqueça do `RUN_TEST` no `main`):

```cpp
// Perto da volta, `ultima + intervalo` tambem da a volta -- e quem compara instantes
// passa a disparar ANTES da hora, a cada passagem pelo laco, por 49,7 dias.
void test_nao_dispara_antes_da_hora_perto_da_volta(void) {
  Agenda agenda;
  agenda.iniciar(1000, 0xFFFFFF00u);

  // So 128 ms se passaram: ainda nao e hora.
  TEST_ASSERT_FALSE(agenda.venceu(0xFFFFFF80u));
}
```

Com o mutante: `Expected FALSE Was TRUE [FAILED]`. Sem o mutante: passa.

---

## Mutante B — a bateria exatamente no limiar

**Arquivo:** `firmware/lib/MelipoCore/Amostra.cpp`, em `montarTelemetria`.

```cpp
// antes
  if (bateria_ok && sensores.bateria.valor < kTensaoDeBateriaBaixaV) {

// depois
  if (bateria_ok && sensores.bateria.valor <= kTensaoDeBateriaBaixaV) {
```

Um caractere.

<details>
<summary>O que acontece, e por quê</summary>

**63 succeeded.** O `test_bateria_baixa` usa 3,41 V (abaixo do limiar) e o cenário saudável
usa 3,92 V (acima). **Nenhum dos dois é exatamente 3,50 V** — e o limiar é justamente o
único ponto onde `<` e `<=` discordam.

É o erro clássico de fronteira, e o motivo de ele sobreviver é sempre o mesmo: os valores
que a gente escolhe naturalmente para um teste são valores "bem no meio", confortáveis. É
a mesma lição do
[empate 30,125](../guia/09-primeiros-passos-com-o-platformio.md#a-parte-que-ensina-de-verdade),
de outro ângulo.

Neste caso a consequência é pequena — uma flag `low_batt` a mais numa bateria exatamente
no limiar. Mas a técnica de encontrá-lo é a mesma que encontra os grandes: **teste a
fronteira, não o meio.**
</details>

### O teste que falta

Em `firmware/test/native/test_amostra/test_amostra.cpp`:

```cpp
// A fronteira exata: o limiar e "abaixo de 3,50 V", entao 3,50 V nao acende a flag.
// Os demais testes usam 3,41 e 3,92 -- valores confortaveis, que nao distinguem
// `<` de `<=`.
void test_bateria_exatamente_no_limiar(void) {
  LeiturasDosSensores sensores = tudoSadio();
  sensores.bateria = Leitura::obtida(3.50);

  const Telemetria t = meliponet::montarTelemetria(contexto(), sensores);

  TEST_ASSERT_FALSE(contem(t.flags, Flag::low_batt));
}
```

---

## Mutante C — a medição no instante exato da instalação

**Arquivo:** `platform/meliponet/ingest/store.py`, função `resolve_hive`.

```python
# antes
            NodeAssignment.installed_at <= when,

# depois
            NodeAssignment.installed_at < when,
```

Rode `platform/.venv/bin/pytest platform/tests -q`.

<details>
<summary>O que acontece, e por quê</summary>

**Tudo verde.** E este é o mais grave dos três.

`test_ingest.py` cobre o remanejamento, o spool, a leitura anterior à instalação — mas
todos os instantes que ele usa estão a dias de distância das bordas
(`installed_at - timedelta(days=1)`, `mudanca + timedelta(days=1)`). Nenhum teste usa
**exatamente** `installed_at`.

Com o mutante, uma medição feita no segundo exato em que o nó foi instalado fica com
`hive_id = NULL` — e, por [D-02](../defeitos-conhecidos.md#d-02), **não é reatribuída
depois**. Ela some do gráfico para sempre, sem erro nenhum.

É uma leitura só, o que parece pouco. Mas repare no cenário em que isso acontece: alguém em
campo instala o nó e registra o horário no formulário. Se o horário registrado coincidir
com o de uma medição — e ele *tende* a coincidir, porque a pessoa acabou de ligar o nó — a
primeira leitura da colmeia é a que se perde. Justamente a que alguém vai procurar para
conferir se deu certo.
</details>

### O teste que falta

Em `platform/tests/test_ingest.py`. Tem uma sutileza — leia a pista se travar:

```python
def test_medicao_no_instante_exato_da_instalacao(scenario) -> None:
    """A fronteira do periodo de instalacao pertence ao periodo.

    Os demais testes ficam a dias das bordas; nenhum exercita o instante exato. Com
    `installed_at < when` no lugar de `<=`, a primeira leitura da colmeia -- justamente
    a que alguem vai procurar para conferir se a instalacao deu certo -- ficaria orfa
    para sempre, porque D-02 nao reatribui o passado.
    """
    # O `ts` do contrato tem resolucao de um segundo. Sem zerar os microssegundos, o
    # "instante exato" seria inalcancavel por uma mensagem de verdade.
    quando = (datetime.now(UTC) - timedelta(days=10)).replace(microsecond=0)
    with session_scope() as session:
        vinculo = session.scalar(
            select(NodeAssignment).where(NodeAssignment.node_id == scenario.node_pk)
        )
        vinculo.installed_at = quando

    with session_scope() as session:
        resultado = store(session, decode(message(1, ts=quando)))

    assert resultado.hive_id == scenario.hive_id


def test_um_segundo_antes_da_instalacao_fica_sem_colmeia(scenario) -> None:
    """O par do teste acima: um teste de fronteira precisa dos dois lados dela."""
    quando = (datetime.now(UTC) - timedelta(days=10)).replace(microsecond=0)
    with session_scope() as session:
        vinculo = session.scalar(
            select(NodeAssignment).where(NodeAssignment.node_id == scenario.node_pk)
        )
        vinculo.installed_at = quando

    with session_scope() as session:
        resultado = store(session, decode(message(2, ts=quando - timedelta(seconds=1))))

    assert resultado.hive_id is None
```

Repare no segundo teste: **um teste de fronteira precisa dos dois lados.** Só o primeiro
passaria também numa implementação que atribuísse *tudo* à colmeia, ignorando o período.

---

## Critério de pronto

Para cada um dos três:

- [ ] Você confirmou que a suíte fica verde com o mutante aplicado
- [ ] Você escreveu o teste **com o mutante ainda aplicado** e o viu falhar
- [ ] Você reverteu o mutante e viu o teste passar
- [ ] `git status` não tem nenhum mutante — só, se for o caso, os testes novos

E no fim: `./verificar` verde.

## Pistas

<details>
<summary>Mutante C: meu teste falha mesmo sem o mutante</summary>

É a armadilha dos microssegundos, e vale entendê-la.

O `installed_at` da fixture `scenario` é `datetime.now(UTC) - timedelta(days=30)` — com
microssegundos. Mas o helper `message()` formata o `ts` com `"%Y-%m-%dT%H:%M:%SZ"`, que
**trunca no segundo**, como manda o contrato.

Resultado: o `ts` que chega é alguns microssegundos *anterior* ao `installed_at`, e a
medição cai fora do período — corretamente. "O instante exato" é inalcançável enquanto o
`installed_at` tiver fração de segundo.

Por isso o teste começa recuando o vínculo para um instante com `.replace(microsecond=0)`.
</details>

<details>
<summary>Mutante A: não sei de onde vieram os números 0xFFFFFF00 e 0xFFFFFF80</summary>

`0xFFFFFF00` é 256 ms antes de `millis()` dar a volta. `0xFFFFFF80` é 128 ms depois dele —
ou seja, ainda **antes** da volta. Com intervalo de 1000 ms, só 128 ms se passaram, então
`venceu` tem de devolver falso. O mutante devolve verdadeiro porque a soma
`0xFFFFFF00 + 1000` já deu a volta e virou um número pequeno.

Se quiser ver os números, `printf("%u\n", 0xFFFFFF00u + 1000u)` num programa qualquer.
</details>

<details>
<summary>Meu teste C não compila: falta import</summary>

`test_ingest.py` já importa quase tudo. Confira que estão lá `datetime`, `UTC`,
`timedelta`, `NodeAssignment` e `select` — os dois últimos já são usados por
`test_no_remanejado_atribui_pela_data_da_medicao`.
</details>

## Se for virar um PR

Um teste novo é uma contribuição completa. Siga
[Primeira contribuição](../guia/06-primeira-contribuicao.md#o-ciclo-de-trabalho), e na
descrição conte a história que este exercício te deu:

- **o que muda:** o teste de fronteira que faltava;
- **por quê:** a mutação exata que passava despercebida, e o que ela causaria em campo;
- **como verificou:** aplicou a mutação, viu o teste falhar, reverteu, viu passar.

Esse terceiro item é o que separa um teste que prova algo de um teste que só ocupa espaço —
e é a mesma verificação que os commits do projeto descrevem quando corrigem um defeito.

**Não commite a mutação.** Ela é a sua evidência, não a entrega.

## O que levar daqui

**Suíte verde não significa código correto.** Significa que ninguém escreveu ainda o teste
que pega aquele erro.

**Erros moram nas fronteiras.** Os três mutantes deste exercício são fronteiras: a volta do
contador, o valor exato do limiar, o instante exato da instalação. Nenhum teste
"confortável" os alcança, porque valores confortáveis ficam longe das bordas de propósito.

**Escrever o teste com o bug ainda aplicado é a única forma de saber que ele funciona.** É
a regra do repositório, e agora você a viu funcionar três vezes.

→ Próximo: [Uma janela nova](08-uma-janela-nova.md)
