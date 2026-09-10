# 04. Mutantes da plataforma

**Tempo:** ~45 min · **Treino** — nada aqui é commitado

## Por que este exercício existe

Uma suíte verde é um número, e número não ensina nada. A forma mais rápida de descobrir o
que aqueles testes afirmam é **quebrar o código de propósito e ver quem reclama**: você
prevê qual teste vai cair, roda, e compara com o que aconteceu.

E há um agravante que vale conhecer antes: **os defeitos da plataforma são silenciosos.**
Um nó que para de publicar cedo ou tarde é notado. Uma consulta que esqueceu o filtro de
organização não quebra, não levanta erro e não aparece em teste de rota que só cheque o
status HTTP — ela apenas mostra a um meliponicultor as colmeias de outro, e o sistema
parece funcionar perfeitamente.

## Antes de começar

- Exercício [03](03-onde-eu-mexo.md) feito.
- `./verificar` verde agora.
- Leia [A plataforma](../guia/03-a-plataforma.md#servicesscopepy--quem-vê-o-quê).

**Mutante nunca é commitado.** `git restore` e `git status` depois de cada um.

Para cada mutação: **preveja**, aplique, rode, compare, reverta.

```bash
platform/.venv/bin/pytest platform/tests -q
```

---

## Mutação A — o escopo sem filtro

**Arquivo:** `platform/meliponet/services/scope.py`, função `hives_for`.

```python
# antes
    statement = select(Hive).join(Apiary, Hive.apiary_id == Apiary.id)
    if not user.role.sees_everything:
        statement = statement.where(Apiary.organization_id == user.organization_id)
    return statement

# depois
    statement = select(Hive).join(Apiary, Hive.apiary_id == Apiary.id)
    return statement
```

Agora todo mundo vê as colmeias de todo mundo. Antes de rodar, responda: **quantos testes
caem, e o painel principal (`/colmeias`) passa a vazar colmeia alheia?**

<details>
<summary>O que acontece</summary>

**Cinco** testes falham:

```
test_scope.py::test_meliponicultor_ve_apenas_a_propria_organizacao
test_scope.py::test_colmeia_alheia_nao_e_visivel
test_scope.py::test_escopo_acompanha_colmeia_nova
test_web.py::test_colmeia_alheia_responde_404
test_web.py::test_nao_se_edita_cadastro_alheio
```

Repare na divisão, que é deliberada: três em `test_scope.py`, que testam a **regra
isolada**, e dois em `test_web.py`, que testam se as **rotas de fato a aplicam**. O
cabeçalho de `test_web.py` explica por que os dois são necessários: *"a regra certa num
helper que ninguém chama não protege nada"*.

E agora a surpresa. Rode só este:

```bash
platform/.venv/bin/pytest platform/tests/test_web.py::test_dashboard_lista_apenas_colmeias_proprias -q
```

**Ele passa** — com o filtro removido. Por quê?

Porque o painel `/colmeias` não usa `hives_for`. Abra `blueprints/dashboard.py`, função
`index`: ele parte de `scope.apiaries_for(current_user)` e chega às colmeias pela relação
`apiary.hives`. O isolamento ali vem de **outro** helper, que você não quebrou.

A lição é desconfortável e vale mais que o resto do exercício: **"o teste passou" não
significa "aquele caminho está protegido"** — significa que *aquele* teste exercita *outro*
caminho. Um sistema com duas portas de entrada precisa das duas fechadas, e de um teste
para cada.
</details>

---

## Mutação B — a lacuna some do gráfico

**Arquivo:** `platform/meliponet/services/series.py`, função `_resample`.

```python
# antes
        members = buckets.get(bucket_time, [])

# depois
        members = buckets.get(bucket_time, [])
        if not members:
            bucket_time += step
            continue
```

Agora os baldes vazios são omitidos em vez de virarem `None`. Parece uma otimização
inofensiva: menos pontos, JSON menor, gráfico mais rápido.

<details>
<summary>O que acontece</summary>

**Dois** testes falham:

```
test_series.py::test_lacuna_vira_null_e_nao_ponto_ausente
test_series.py::test_serie_cobre_a_janela_inteira
```

O primeiro é o esperado. O segundo pega o efeito colateral: a grade de pontos deixa de
cobrir a janela inteira e passa a depender de quantas leituras chegaram.

E o efeito visual, que nenhum teste vê mas o docstring descreve: com os pontos vizinhos
encostados, **o Chart.js liga os dois por uma reta** e o buraco desaparece. O gráfico passa
a afirmar medições que ninguém fez — bem em cima do intervalo em que o sistema falhou.

É por isso que a `spanGaps` fica desligada no `_panel.html` e a reamostragem percorre
todos os baldes: são as duas metades da mesma decisão. Quebrar qualquer uma esconde a
perda, e a completude que o projeto promete medir vira ficção.
</details>

---

## Mutação C — a checagem de duplicata sai

**Arquivo:** `platform/meliponet/ingest/store.py`, função `store()`. Apague o bloco:

```python
    already = session.scalar(
        select(Measurement.id).where(
            Measurement.node_id == telemetry.node_id, Measurement.seq == telemetry.seq
        )
    )
    if already is not None:
        return StoreResult(stored=False, duplicate=True, measurement_id=already)
```

Um nó que drena o spool depois de uma queda reenvia mensagens que já chegaram. Sem essa
checagem, a série ganha pontos duplicados a cada reconexão — certo?

<details>
<summary>O que acontece</summary>

**Nenhum teste falha.** A suíte inteira continua verde, inclusive
`test_reenvio_do_spool_e_idempotente`, que existe exatamente para esse cenário.

Antes de concluir que o teste é inútil, entenda **por que** ele passa. Logo abaixo, no
mesmo `store()`:

```python
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        return StoreResult(stored=False, duplicate=True)
```

A restrição `UNIQUE (node_id, seq)` no banco é a **autoridade final**, e o `except` a trata
pelo que ela é: um reenvio, não um erro. O `SELECT` que você apagou era a primeira linha de
defesa; a segunda continuou lá e segurou o caso.

Isso se chama defesa em profundidade, e a pergunta certa passa a ser: **então o `SELECT`
serve para quê?** Duas coisas:

1. `StoreResult.measurement_id` deixa de ser preenchido nos duplicados — informação
   perdida para quem chama.
2. Sem ele, **todo** reenvio de spool provoca um `session.rollback()`. Um rollback desfaz
   a transação inteira, não só a linha recusada. Num ingestor que processasse várias
   mensagens na mesma sessão, um reenvio no meio do lote levaria as outras junto.

Nenhuma das duas é pega pela suíte hoje. Se você quiser transformar isso numa
contribuição, o teste é: gravar a `seq` 7, reenviar, e afirmar que
`resultado.measurement_id` não é `None`. Escreva-o, veja-o falhar com o mutante aplicado,
reverta o mutante e veja-o passar.
</details>

---

## Critério de pronto

- [ ] Você previu antes de rodar, nas três mutações
- [ ] Você rodou `test_dashboard_lista_apenas_colmeias_proprias` isolado na mutação A e
      entendeu por que ele passa
- [ ] Você consegue explicar por que a mutação C não derruba nada
- [ ] `git status` limpo e `pytest` verde de novo

## Pistas

<details>
<summary>O pytest reclama de import ou de sintaxe</summary>

`git diff` para ver o que você mexeu. Em Python, indentação errada é erro de sintaxe — se o
`continue` da mutação B não estiver dentro do `while`, nada compila.
</details>

<details>
<summary>Quero ver o efeito da mutação B no navegador, não só no teste</summary>

Aplique a mutação, suba o servidor e abra uma colmeia com o banco populado pelo simulador
(que injeta lacunas de propósito). Compare com um print de antes: os buracos somem e a
linha fica contínua.
</details>

## O que levar daqui

**"O teste passou" não é o mesmo que "aquele caminho está protegido".** A mutação A mostra
duas portas para a mesma sala, e um teste que só olha uma delas.

**Um teste pode passar por um motivo diferente do que você imagina.** Na mutação C, o que
segurou não foi o código que você apagou — foi a restrição do banco, duas camadas abaixo.

**Nem toda mutação sobrevivente é um teste ruim.** Às vezes é defesa em profundidade
funcionando. Distinguir os dois casos é o assunto do próximo exercício.

→ Próximo: [O mutante que ninguém pega](05-o-mutante-que-ninguem-pega.md)
