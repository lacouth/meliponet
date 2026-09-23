# 06. Uma janela nova

**Tempo:** ~1 h · **Treino**

## Por que este exercício existe

É a menor mudança da plataforma que passa pelo caminho inteiro: teste primeiro, serviço,
interface, verificação. E ela tem uma recompensa embutida — você vai mexer num lugar só e
ver a interface acompanhar sozinha, o que é o pagamento de uma decisão de projeto tomada
antes de você chegar.

O objetivo aqui **não é a janela**. É praticar a ordem: teste, ver falhar, implementar, ver
passar.

## Antes de começar

- Bloco B feito (exercícios [04](04-mutantes-da-plataforma.md) e
  [05](05-o-mutante-que-ninguem-pega.md)).
- Leia [A plataforma](../guia/03-a-plataforma.md#as-camadas-e-por-que-existem).
- Banco populado pelo simulador, para ver o resultado no navegador.

```bash
git switch main && git pull
git switch -c plataforma/janela-de-90-dias
```

## A tarefa

Acrescentar uma janela de **90 dias** ao dashboard, com passo de reamostragem de 2 horas.

> **Pergunta, antes de codar:** com passo de 2 h, 90 dias dão quantos pontos? E se o passo
> fosse de 5 min, como o da janela de 24 h?

<details>
<summary>Resposta</summary>

Com passo de 2 h: `90 × 24 ÷ 2 = 1080` pontos por métrica.

Com passo de 5 min: `90 × 24 × 12 = 25 920` pontos por métrica — e são seis métricas mais o
diferencial térmico. Seriam mais de 180 mil números viajando por uma conexão rural para
desenhar um gráfico de algumas centenas de pixels de largura.

É por isso que o passo cresce com a janela. E é por isso que
[D-07](../defeitos-conhecidos.md#d-07) existe: mesmo reamostrando, a consulta ainda varre a
tabela bruta inteira antes de reduzir.
</details>

> **O conceito: reamostrar.** O nó mede a cada 5 minutos, mas o gráfico não desenha uma
> medição por pixel. A plataforma divide a janela em **baldes** de tamanho fixo — o *passo*
> — e produz um ponto por balde, com a média das medições que caíram nele. Trinta dias com
> passo de 2 h viram 360 pontos em vez de 8 640.
>
> O que **não** acontece é o balde vazio sumir: ele vira um ponto sem valor, e o gráfico
> mostra o buraco em vez de ligar os vizinhos por uma reta. Ligar esconderia a perda, e
> completude é justamente o que o projeto se compromete a medir. É por isso que toda janela
> tem passo, inclusive a de 24 h.

## Passos

### 0. Leia antes de escrever

Abra `platform/meliponet/servicos/serie.py` e anote três coisas — sem elas o passo 1 é
adivinhação:

| Onde | O que anotar |
|---|---|
| `JANELAS`, linha 31 | cada entrada é uma **tupla de três**: rótulo, duração total (`span`), passo (`step`). Todos os dois últimos são `timedelta` |
| `JANELA_PADRAO`, logo abaixo | é `"24h"` — e é para ele que cai toda janela desconhecida |
| `def series(...)`, linha 96 | a assinatura: `series(session, hive_id, window=JANELA_PADRAO)`, devolvendo uma lista de `Point` |

**Confira:** você consegue dizer, sem olhar de novo, qual dos três elementos da tupla é o
passo. Repare também no comentário acima de `JANELAS` — ele explica a decisão do balde
vazio da caixa acima.

### 1. O teste, primeiro

Em `platform/tests/test_serie.py`. Repare que já existe
`test_serie_cobre_a_janela_inteira`, que faz exatamente isso para 24 h — **copie o padrão
dele**, como manda o guia: achar onde a coisa já é feita de forma parecida vale mais do
que inventar um jeito novo.

O seu teste precisa afirmar duas coisas:

- a janela `90d` existe em `JANELAS`;
- a série devolvida por `series(session, hive_id, "90d")` tem o número de pontos que você
  calculou (com a folga de um, para o alinhamento das bordas).

A segunda é a que importa. Só a primeira passaria também com um passo errado — a janela
existiria e devolveria a quantidade de pontos de outra coisa.

### 2. Veja falhar

```bash
platform/.venv/bin/pytest platform/tests/test_serie.py -q
```

**Não pule este passo.** Um teste que nunca falhou é uma suposição, não uma verificação —
e você viu isso duas vezes no exercício [05](05-o-mutante-que-ninguem-pega.md).

Repare *como* ele falha. Se `JANELAS.get("90d")` cai no `JANELA_PADRAO`, o teste não vai
estourar com `KeyError`: ele vai receber a série de 24 h e falhar na contagem. Ler a
mensagem de falha e entender por que ela é aquela faz parte do exercício.

### 3. Implemente

Uma linha em `JANELAS`.

### 4. Veja passar, e veja o resto acompanhar

```bash
./verificar plataforma
```

Agora suba o servidor e abra uma colmeia.

> **O botão "Últimos 90 dias" apareceu sozinho. Por quê?**

<details>
<summary>Resposta</summary>

`templates/painel/colmeia.html` não tem os botões escritos à mão:

```html
{% for chave, janela_spec in janelas.items() %}
  <a href="{{ url_for('painel.detalhe_da_colmeia', colmeia_id=colmeia.id, janela=chave) }}"
     class="{{ 'on' if chave == janela else '' }}">{{ janela_spec[0] }}</a>
{% endfor %}
```

Ele **percorre o mesmo dicionário** que o serviço define. Uma fonte de verdade, um lugar
para mudar.

É o mesmo padrão da tabela `kComandos` do firmware, onde o `ajuda` percorre a mesma tabela
que despacha os comandos, e por isso não tem como ficar desatualizado. Quando você vir uma
lista escrita duas vezes no código, desconfie: uma delas vai envelhecer.

E repare no que a rota faz com uma janela inválida (`?janela=abc`): ela cai no
`JANELA_PADRAO` em vez de dar erro. Isso é deliberado — um link velho ou um parâmetro
digitado errado mostra o painel, não uma página de erro.
</details>

### 5. Commit

```bash
git status
git diff
git add -p
git commit
```

Na mensagem: o que muda numa linha, e o porquê num parágrafo — incluindo **por que 2 h de
passo**, que é a decisão real deste commit.

## Critério de pronto

- [ ] Você anotou as três coisas do passo 0 e sabe qual elemento da tupla é o passo
- [ ] O teste novo falhou antes da mudança e passa depois
- [ ] `./verificar` verde
- [ ] O botão apareceu na interface sem você tocar em nenhum template
- [ ] Você consegue explicar por que ele apareceu

## Pistas

<details>
<summary>Meu teste passa mesmo antes de eu mexer no `JANELAS`</summary>

Provavelmente você afirmou algo que já era verdade — por exemplo, que a série tem "mais de
100 pontos", o que a janela de 24 h também cumpre (288). Afirme o número exato que você
calculou.

Este é o mesmo erro do "teste que passa nas duas implementações". Se ele não falhou, ele
não está testando o que você acha.
</details>

<details>
<summary>A contagem dá um a mais (ou a menos) do que eu calculei</summary>

`_reamostrar` percorre de `_alinhar(since, step)` até `_alinhar(until, step)`, **inclusive** — e
os dois são alinhados para baixo. Dependendo de onde o instante atual cai dentro do balde,
sai um ponto a mais. Por isso o teste existente usa `in (288, 289)` em vez de um número
cravado.
</details>

<details>
<summary>Quero uma janela diferente de 90 dias</summary>

Pode. Escolha a sua e ajuste a conta — o exercício é o método, não o número. Só evite passo
que gere dezenas de milhares de pontos, pelo motivo da primeira pergunta.
</details>

## O que levar daqui

**Uma fonte de verdade.** A janela é definida uma vez e a interface acompanha. Quando algo
precisa ser escrito em dois lugares para funcionar, um dos dois vai ser esquecido.

**Ver o teste falhar é parte do teste.** E ler *como* ele falha ensina tanto quanto vê-lo
passar.

→ Próximo: [O CSV, na camada certa](07-o-csv-na-camada-certa.md)
