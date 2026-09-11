# 07. O CSV, na camada certa

**Tempo:** ~1 h 15 · **Contribuição**

> **Combine antes de começar.** Este exercício e o [08](08-a-rota-que-entrega-o-arquivo.md)
> formam uma contribuição só, em duas partes. Só uma pessoa deve fazê-los.

## Por que este exercício existe

Hoje, tirar dados da plataforma exige acesso ao terminal do servidor. Uma exportação em CSV
resolve isso — e é a primeira vez, na trilha, que **o formato de saída é um contrato**: uma
planilha aberta no LibreOffice, ou um `pandas.read_csv` num script de análise, passam a
depender das suas colunas.

A tarefa inteira é grande demais para uma sentada, então ela vem em duas. Aqui você decide
o formato e escreve a função que produz as linhas, **sem nenhum HTTP no caminho**. No
[08](08-a-rota-que-entrega-o-arquivo.md) essa função vira um arquivo que alguém baixa.

A divisão não é só para encurtar: ela é a lição. Se a montagem das linhas precisasse de uma
requisição HTTP para acontecer, você não conseguiria fazer este exercício sozinho.

## Antes de começar

- Exercício [06](06-uma-janela-nova.md) feito.
- Releia [As camadas](../guia/03-a-plataforma.md#as-camadas-e-por-que-existem) e o
  pedido 4 do exercício [03](03-onde-eu-mexo.md).

```bash
git switch main && git pull
git switch -c plataforma/exportar-csv
```

## Passo 1 — as três decisões

Responda **antes** de escrever código. Escreva as respostas: elas vão para a descrição do
PR no exercício 08.

> **Decisão 1.** O CSV exporta os pontos **reamostrados** (o que o gráfico mostra) ou as
> medições **cruas** do banco?
>
> **Decisão 2.** Como um valor ausente aparece no CSV?
>
> **Decisão 3.** A exportação respeita a janela (`?janela=7d`) ou exporta tudo?

> **O conceito, para a decisão 1: cru e reamostrado não são o mesmo dado.**
> **Cru** é o que o nó mediu: uma linha por medição, a cada cinco minutos, exatamente como
> chegou. **Reamostrado** é o que o gráfico desenha: a janela dividida em baldes de tamanho
> fixo, um ponto por balde, com a média das medições que caíram nele — é o mecanismo do
> exercício [06](06-uma-janela-nova.md). A média já suavizou o ruído, e o número de linhas
> cai muito.
>
> A diferença importa porque um valor reamostrado **não é uma medição**: é uma conta que a
> plataforma fez, com um passo que a plataforma escolheu. Exportar isso sem dizer transforma
> uma escolha de interface num número que alguém vai publicar num artigo.

<details>
<summary>Como pensar cada uma — não há uma resposta só</summary>

**1.** As duas têm uso, e a diferença importa.

*Reamostrado* bate com a tela, é menor, e a média de cada balde já suavizou o ruído. Mas
**não é dado bruto**: quem for escrever um artigo com isso está publicando médias que a
plataforma calculou.

*Cru* é o que o nó mediu. É o que a curadoria dos dados precisa, e o que permite a outra
pessoa reamostrar do jeito dela.

Recomendação: comece pelo **cru**, e diga no CSV qual é. Se exportar reamostrado, o
cabeçalho ou o nome do arquivo precisa dizer o passo — senão o número vira uma média
anônima. Reaproveitar `series_service.series()` é conveniente; conveniência não é o critério
aqui.

**2.** Campo **vazio**, não `0`, não `NaN`, não `null`. É a mesma regra que atravessa o
sistema — a mesma que o roteiro do nó cobra do firmware — e é a que o `pandas.read_csv` lê
como `NaN` sem configuração nenhuma. Um `0` viraria uma medição falsa na análise de outra
pessoa, longe de você e sem contexto para desconfiar.

Este é o ponto do exercício inteiro que mais merece um teste.

**3.** Respeitar a janela é mais simples e mais previsível: o usuário exporta o que está
vendo. Exportar "tudo" precisa de um teto — trinta nós com anos de série não cabem numa
resposta HTTP.

Se seguir a janela, aproveite a validação que `hive_detail` já faz (janela desconhecida cai
no padrão). Repetir esse `if` numa terceira rota é sinal de que ele merece virar um
ajudante.
</details>

## Passo 2 — desenhe o cabeçalho

Antes do primeiro teste, escreva **a linha de cabeçalho exata** que o seu CSV vai ter, e a
primeira linha de dados de exemplo. Num papel serve.

```
time,temp_in_c,temp_out_c,rh_in_pct,rh_out_pct,weight_kg
2027-03-14T12:10:00Z,30.12,34.8,68.4,,12.483
```

**Confira:** na sua linha de exemplo, um valor ausente aparece como **nada entre duas
vírgulas** — é a decisão 2 tomando forma. E o horário tem o `Z`.

> **Por que o cabeçalho vem antes do teste.** O primeiro teste vai afirmar exatamente essa
> linha, na ordem. Escrevê-la primeiro força a decisão a ser consciente, em vez de ser "o
> que saiu do laço que eu escrevi".

## Passo 3 — os testes do serviço

Em `platform/tests/test_series.py` (a função ainda é de serviço; ela não sabe o que é HTTP).
Três testes:

| O que afirma | Por que importa |
|---|---|
| o cabeçalho tem as colunas do passo 2, na ordem | é o contrato do arquivo |
| uma medição conhecida vira a linha esperada | o caminho feliz |
| métrica `NULL` vira **campo vazio** | a regra central, do lado da exportação |

E um quarto que é fácil esquecer: **colmeia sem leitura nenhuma devolve só o cabeçalho**,
não uma lista vazia nem um erro. Um arquivo com cabeçalho e nenhuma linha é uma resposta
legítima: diz "não há dados neste período", que é diferente de "a exportação falhou".

```bash
platform/.venv/bin/pytest platform/tests/test_series.py -q
```

**Todos têm de falhar** — a função nem existe ainda. Repare em *como* falham: um
`AttributeError` ou `ImportError` é o esperado agora.

## Passo 4 — a função, no serviço

Em `services/series.py`, ou num `services/export.py` novo. Ela recebe a sessão e o que
precisa saber da colmeia, e devolve as linhas. **Sem `request`, sem `current_user`, sem
saber o que é um cabeçalho HTTP.**

Assim ela pode ser chamada por um relatório em PDF, por um script de curadoria e pelo
teste — que é a razão de as camadas existirem. E permite testar a formatação sem subir
servidor: é o que você está fazendo agora.

Use o módulo `csv` da biblioteca padrão em vez de juntar strings com vírgula. Um nome de
colmeia com vírgula — "Colmeia 01, fundo" — quebraria o arquivo em silêncio, e o `csv`
resolve o escape sozinho.

> **O conceito: UTC num arquivo que viaja.** Grave os horários em UTC, no formato ISO 8601
> com o `Z`, como o contrato faz. A plataforma converte para o horário da Paraíba só na
> exibição — mas um CSV é um arquivo que sai daqui: vira anexo de e-mail, entra no script
> de outra pessoa, é aberto daqui a três anos. Sem o fuso explícito, ninguém consegue saber
> o que aquela coluna significa, e um horário local ainda por cima muda de significado
> quando o horário de verão vai e volta. Ver [A mensagem](../guia/02-a-mensagem.md).

## Passo 5 — verifique

```bash
./verificar plataforma
```

Os quatro testes passam, e nada mais quebrou.

## Critério de pronto

- [ ] As três decisões estão escritas e justificadas
- [ ] O cabeçalho foi desenhado antes do primeiro teste
- [ ] Os quatro testes falharam antes e passam depois
- [ ] O teste do campo vazio afirma **vazio**, e não `0` nem `None`
- [ ] A função está no serviço, e não importa nada de Flask
- [ ] `./verificar` verde

Ainda **não abra o PR**: ele é o fim do exercício 08.

## Pistas

<details>
<summary>Onde ponho a função: em `series.py` ou num `export.py` novo?</summary>

As duas se defendem, e a escolha vai na descrição do PR como uma quarta decisão. Em
`series.py` ela fica perto de quem já sabe montar série; num `export.py` ela fica perto do
que vier depois (exportar para outros formatos, exportar várias colmeias). Escolha e diga
por quê.
</details>

<details>
<summary>Os números saem com casas decimais demais</summary>

O mesmo problema que o contrato resolve com `CASAS_DECIMAIS`
(`contracts/mensagem.py`) — vale olhar como ele faz antes de inventar outro jeito. E
arredondar é uma decisão: quem for analisar os dados precisa saber que você arredondou.
</details>

<details>
<summary>Meu teste do campo vazio passa, mas eu não confio nele</summary>

Desconfiança justa. Faça o mutante: mude a função para escrever `0` no lugar do vazio e
rode o teste. Se ele não falhar, ele não estava afirmando o que você achava — é o método
do exercício [05](05-o-mutante-que-ninguem-pega.md).
</details>

## O que levar daqui

**O formato de saída é um contrato.** Quem consumir o CSV vai depender das colunas e do
fuso. Escolher com cuidado agora é mais barato do que mudar depois de alguém automatizar em
cima.

**A camada certa se reconhece pelo que ela não precisa saber.** Esta função não sabe o que
é HTTP — e é por isso que você conseguiu testá-la inteira sem subir servidor nenhum.

→ Próximo: [A rota que entrega o arquivo](08-a-rota-que-entrega-o-arquivo.md)
