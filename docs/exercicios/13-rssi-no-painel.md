# 13. RSSI no painel

**Área:** plataforma · **Tempo:** ~1 h · **Treino ou contribuição**

## Por que este exercício existe

O `rssi` chega do nó, é validado, é gravado numa coluna — e **nunca é mostrado**. É dado
coletado que ninguém vê.

E é justamente o dado que responde à pergunta mais frequente de quem instala um nó: *"o
sinal aqui dentro da caixa é bom o suficiente?"*. Hoje, para respondê-la, é preciso abrir o
banco no terminal.

O exercício é pequeno de propósito. O que ele treina é o cuidado com o caso vazio — o
`rssi` é **opcional** no contrato, e a interface tem de dizer "não sabemos" em vez de
inventar um número.

## Antes de começar

- Exercício [08](08-uma-janela-nova.md) feito.
- Banco populado pelo simulador (ele emite `rssi` em toda mensagem).
- Leia `platform/meliponet/templates/_panel.html`, os quatro cards do topo.

```bash
git switch main && git pull
git switch -c plataforma/rssi-no-painel
```

## Passo 1 — entenda o caso vazio antes de desenhar

> **Pergunta 1.** Em que situações `latest.rssi` é `None`?
>
> **Pergunta 2.** O filtro `num` já existe em `blueprints/dashboard.py`. O que ele faz com
> `None`, e por que isso é uma decisão e não um detalhe?

<details>
<summary>Respostas</summary>

**1.** Pelo menos três, e elas não significam a mesma coisa:

- o nó estava **sem WiFi associado** quando mediu — `test_rssi_ausente` no firmware cobre
  exatamente isso, e o campo é opcional no contrato por causa desse caso;
- a mensagem veio de um **gateway LoRa** da Fase 5, onde quem tem RSSI é o gateway;
- **não há leitura nenhuma** na janela (`latest` é `None`).

**2.**

```python
@bp.app_template_filter("num")
def num(value: float | None, digits: int = 1, suffix: str = "") -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}{suffix}"
```

Ele devolve um travessão. É a mesma regra do contrato, agora na camada de apresentação:
**ausente não é zero.** Um card mostrando `0 dBm` afirmaria um sinal excelente onde não há
sinal nenhum — a versão visual do erro que os testes de `test_amostra.cpp` impedem no
firmware.

Repare que o filtro concentra essa decisão num lugar só. Se cada template escrevesse o seu
`if`, um deles esqueceria.
</details>

## Passo 2 — o teste, primeiro

Em `platform/tests/test_web.py`. Dois testes, porque um caso de borda precisa dos dois
lados:

1. com uma medição que **tem** `rssi`, a página da colmeia mostra o valor com a unidade;
2. com uma medição **sem** `rssi`, a página não quebra e mostra o travessão.

O padrão para montar as medições está em `test_series.py`, função `fill` — e as fixtures
`scenario` e `login` já dão colmeia e usuário autenticado.

```bash
platform/.venv/bin/pytest platform/tests/test_web.py -q
```

Os dois têm de falhar. O segundo pode passar por acidente (a página realmente não quebra
hoje) — se for o caso, torne a asserção mais específica: procure pelo **rótulo** do card,
que ainda não existe.

## Passo 3 — o card

Em `_panel.html`, seguindo a forma dos quatro que já estão lá: um `label`, um `value` e uma
`note`.

Duas escolhas suas, e as duas merecem uma linha na mensagem do commit:

- **Onde ele entra.** Um quinto card muda a grade; talvez ele caiba melhor na linha de
  frescor, ao lado da completude, que já fala de qualidade do enlace.
- **O que a `note` diz.** Um número em dBm não significa nada para um meliponicultor. Uma
  nota como *"acima de −70 dBm é confortável"* transforma o dado em informação. Se você não
  souber o limiar, é melhor não inventar — diga isso no PR e pergunte.

## Passo 4 — verifique

```bash
./verificar plataforma
```

E olhe no navegador. Deixe o simulador emitindo em tempo real e veja o card mudar:

```bash
platform/.venv/bin/python -m simulator --transporte direto --historico 0 --tempo-real
```

Para conferir o caso vazio sem esperar, apague o `rssi` de uma leitura direto no banco:

```bash
sqlite3 meliponet-dev.sqlite3 \
  "UPDATE measurements SET rssi = NULL WHERE id = (SELECT MAX(id) FROM measurements);"
```

Recarregue: o card tem de mostrar `—`, não `0`.

## Critério de pronto

- [ ] Os dois testes falharam antes e passam depois
- [ ] O card mostra `—` (não `0`) quando `rssi` é `NULL` — você viu isso no navegador
- [ ] `./verificar` verde
- [ ] Você não escreveu um `if` novo no template para o caso vazio

## Pistas

<details>
<summary>O card mostra `0 dBm` em vez de `—`</summary>

Você provavelmente usou `latest.rssi or 0`, ou um `default(0)` do Jinja. Use o filtro
`num`, que já trata `None`. Este é literalmente o erro que o exercício existe para treinar.

Cuidado também com `{% if latest.rssi %}`: em Jinja, `0` é falso. Um RSSI de exatamente
0 dBm é implausível na prática, mas o hábito de testar valor em vez de existência é o que
produz o bug do exercício [07](07-o-mutante-que-ninguem-pega.md). Prefira
`is not none`.
</details>

<details>
<summary>Meu teste não acha o texto na página</summary>

`/colmeia/<id>` renderiza `hive.html`, que inclui `_panel.html` — então o texto está no
corpo. Se não estiver, confira se a colmeia tem alguma medição na janela de 24 h: sem
leitura, `latest` é `None` e todos os cards mostram travessão.

Para depurar, imprima o corpo: `print(client.get(f"/colmeia/{scenario.hive_id}").get_data(as_text=True))`.
</details>

<details>
<summary>Isto vale como contribuição?</summary>

Vale — é uma das tarefas sugeridas em
[Primeira contribuição](../guia/06-primeira-contribuicao.md#tarefas-boas-para-começar).
Combine antes, para não ter dois PRs iguais.
</details>

## O que levar daqui

**A regra "ausente não é zero" atravessa o sistema inteiro.** Ela nasce no `Leitura` do
firmware, vira campo omitido no JSON, vira `NULL` no banco e vira travessão na tela. Quebrar
qualquer um dos elos faz o sistema mentir.

**Dado coletado e não mostrado é trabalho desperdiçado.** Vale procurar outros: leia
`models.py` e veja quantas colunas nenhuma tela lê ainda.

→ Próximo: [Exportar CSV](14-exportar-csv.md)
