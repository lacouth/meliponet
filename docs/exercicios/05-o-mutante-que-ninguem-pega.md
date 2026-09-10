# 05. O mutante que ninguém pega

**Tempo:** ~1 h · **Treino — e pode virar um PR**

## Por que este exercício existe

No exercício anterior, quase toda mutação derrubou algum teste. Isso dá uma sensação boa e
enganosa: a de que a suíte cobre tudo.

Não cobre. Este exercício mostra duas mutações que **passam em todos os testes** — e as
duas são defeitos de verdade, do tipo que só apareceria em campo, com o nó já dentro da
colmeia. Você vai aplicá-las, entender por que a suíte não as vê, e escrever o teste que
falta.

E aqui a saída deixa de ser treino: **os testes que você escrever podem virar um pull
request.** São exatamente o tipo de contribuição que o projeto quer — um teste que fecha um
buraco descoberto de propósito.

## Antes de começar

- Exercício [04](04-mutantes-da-plataforma.md) feito.
- `./verificar` verde agora.

**Combine antes de começar.** Cada um dos dois testes é uma contribuição; duas pessoas
escrevendo o mesmo desperdiça o trabalho de uma. O exercício em si — aplicar, rodar,
entender — todo mundo faz.

## O método

Para cada mutante, o ciclo é:

1. Aplique a mutação e rode a suíte. **Confirme que nada falha.**
2. **Não reverta ainda.** Com o mutante aplicado, escreva um teste que o pegue — e veja-o
   falhar.
3. Reverta o mutante (`git restore`) e rode o teste de novo. Ele tem de **passar**.
4. Só um teste que já falhou prova alguma coisa. É por isso que a ordem é esta.

---

## Mutante A — o reenvio que confunde dois nós

**Arquivo:** `platform/meliponet/ingest/store.py`, função `store`.

```python
# antes
        select(Measurement.id).where(
            Measurement.node_id == telemetry.node_id, Measurement.seq == telemetry.seq
        )

# depois
        select(Measurement.id).where(
            Measurement.seq == telemetry.seq
        )
```

Rode `platform/.venv/bin/pytest platform/tests`.

<details>
<summary>O que acontece, e por quê</summary>

**Tudo verde.**

`test_ingest.py` cobre bem o reenvio: manda a mesma `seq` duas vezes e exige que a segunda
seja marcada como duplicata. Mas as duas mensagens vêm **do mesmo nó**. Nenhum teste manda
a mesma `seq` de **nós diferentes**, e é exatamente aí que o `node_id` importa.

O que o mutante causa em campo: cada nó tem o seu próprio contador, e todo nó novo começa
perto de zero. Quando o segundo nó do meliponário for ligado, as primeiras leituras dele
terão `seq` que o primeiro nó já gastou — e todas serão **silenciosamente descartadas como
reenvio**. A colmeia nova aparece no cadastro, o nó aparece como visto agora, e o gráfico
fica vazio. Nenhum erro em lugar nenhum.

Repare no tipo de defeito: ele não existe com um nó só. Ele nasce no dia em que o projeto
cresce.
</details>

### O teste que falta

Em `platform/tests/test_ingest.py`:

```python
def test_seq_repetida_de_outro_no_nao_e_duplicata(scenario) -> None:
    """A duplicata e por (node_id, seq), nao por seq.

    Cada no tem o seu proprio contador, e todo no novo comeca perto de zero: sem o
    node_id na comparacao, as primeiras leituras do segundo no do meliponario seriam
    descartadas como reenvio, em silencio.
    """
    with session_scope() as session:
        primeiro = store(session, decode(message(1, node_id="A4C13800")))
    with session_scope() as session:
        outro = store(session, decode(message(1, node_id="7B21C904")))

    assert primeiro.stored
    assert outro.stored
    assert not outro.duplicate
```

---

## Mutante B — a medição no instante exato da instalação

**Arquivo:** `platform/meliponet/ingest/store.py`, função `resolve_hive`.

```python
# antes
            NodeAssignment.installed_at <= when,

# depois
            NodeAssignment.installed_at < when,
```

Rode a suíte de novo.

<details>
<summary>O que acontece, e por quê</summary>

**Tudo verde.** E este é o mais sutil dos dois.

`test_ingest.py` cobre o remanejamento, o reenvio e a leitura anterior à instalação — mas
todos os instantes que ele usa estão a dias de distância das bordas
(`installed_at - timedelta(days=1)`, `mudanca + timedelta(days=1)`). Nenhum teste usa
**exatamente** `installed_at`.

Com o mutante, uma medição feita no segundo exato em que o nó foi instalado fica com
`hive_id = NULL` — e, por [D-02](../defeitos-conhecidos.md#d-02), **não é reatribuída
depois**. Ela some do gráfico para sempre, sem erro nenhum.

É uma leitura só, o que parece pouco. Mas repare no cenário: alguém em campo instala o nó
e registra o horário no formulário. Se o horário registrado coincidir com o de uma medição
— e ele *tende* a coincidir, porque a pessoa acabou de ligar o nó — a primeira leitura da
colmeia é a que se perde. Justamente a que alguém vai procurar para conferir se deu certo.
</details>

### O teste que falta

Ainda em `platform/tests/test_ingest.py`. Tem uma sutileza — leia a pista se travar:

```python
def test_medicao_no_instante_exato_da_instalacao(scenario) -> None:
    """A fronteira do periodo de instalacao pertence ao periodo."""
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

Para cada um dos dois:

- [ ] Você confirmou que a suíte fica verde com o mutante aplicado
- [ ] Você escreveu o teste **com o mutante ainda aplicado** e o viu falhar
- [ ] Você reverteu o mutante e viu o teste passar
- [ ] `git status` não tem nenhum mutante — só, se for o caso, os testes novos

E no fim: `./verificar` verde.

## Pistas

<details>
<summary>Mutante B: meu teste falha mesmo sem o mutante</summary>

É a armadilha dos microssegundos, e vale entendê-la.

O `installed_at` da fixture `scenario` é `datetime.now(UTC) - timedelta(days=30)` — com
microssegundos. Mas o helper `message()` formata o `ts` com `"%Y-%m-%dT%H:%M:%SZ"`, que
**trunca no segundo**, como manda o contrato.

Resultado: o `ts` que chega é alguns microssegundos *anterior* ao `installed_at`, e a
medição cai fora do período — corretamente. "O instante exato" é inalcançável enquanto o
`installed_at` tiver fração de segundo. Por isso o teste começa recuando o vínculo para um
instante com `.replace(microsecond=0)`.
</details>

<details>
<summary>Meu teste não compila: falta import</summary>

`test_ingest.py` já importa quase tudo. Confira que estão lá `datetime`, `UTC`,
`timedelta`, `NodeAssignment` e `select` — os dois últimos já são usados por
`test_no_remanejado_atribui_pela_data_da_medicao`.
</details>

## Se for virar um PR

Um teste novo é uma contribuição completa. Siga
[o ciclo](../guia/05-como-trabalhamos.md#o-ciclo-do-começo-ao-pull-request), e na descrição
conte a história que este exercício te deu:

- **o que muda:** o teste que faltava;
- **por quê:** a mutação exata que passava despercebida, e o que ela causaria em campo;
- **como verificou:** aplicou a mutação, viu o teste falhar, reverteu, viu passar.

Esse terceiro item é o que separa um teste que prova algo de um teste que só ocupa espaço.

**Não commite a mutação.** Ela é a sua evidência, não a entrega.

## O que levar daqui

**Suíte verde não significa código correto.** Significa que ninguém escreveu ainda o teste
que pega aquele erro.

**Erros moram nas fronteiras** — e "fronteira" não é só um valor limite: é também o segundo
nó, a segunda organização, o segundo de qualquer coisa. Os dois mutantes deste exercício
são invisíveis num sistema com um nó só.

**Escrever o teste com o bug ainda aplicado é a única forma de saber que ele funciona.**

→ Próximo: [Uma janela nova](06-uma-janela-nova.md)
