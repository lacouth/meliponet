# 07. Exportar CSV

**Tempo:** ~2 h · **Contribuição**

> **Combine antes de começar.** Vira um PR; só uma pessoa deve fazê-lo.

## Por que este exercício existe

É o exercício mais completo do bloco: rota nova, serviço novo, escopo, caso vazio e três
decisões de projeto que não têm resposta óbvia. Ele também entrega algo que o projeto
precisa de verdade — hoje, tirar dados da plataforma exige acesso ao terminal do servidor.

E ele é o primeiro em que **o formato de saída é um contrato**. Uma planilha que alguém
abre no LibreOffice, ou um `pandas.read_csv` num script de análise, passam a depender das
suas colunas.

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
PR.

> **Decisão 1.** O CSV exporta os pontos **reamostrados** (o que o gráfico mostra) ou as
> medições **cruas** do banco?
>
> **Decisão 2.** Como um valor ausente aparece no CSV?
>
> **Decisão 3.** A exportação respeita a janela (`?janela=7d`) ou exporta tudo?

<details>
<summary>Como pensar cada uma — não há uma resposta só</summary>

**1.** As duas têm uso, e a diferença importa.

*Reamostrado* é o que o usuário vê no gráfico. Bate com a tela, é menor, e a média de cada
balde já suavizou o ruído. Mas **não é dado bruto**: quem for escrever um artigo com isso
está publicando médias que a plataforma calculou, com um passo que a plataforma escolheu.

*Cru* é o que o nó mediu. É o que a curadoria dos dados precisa, e o que permite a outra
pessoa reamostrar do jeito dela.

Recomendação: comece pelo **cru**, e diga no CSV qual é. Se exportar reamostrado, o
cabeçalho ou o nome do arquivo precisa dizer o passo — senão o número vira uma média
anônima. Reaproveitar `series_service.series()` é conveniente; conveniência não é o critério
aqui.

**2.** Campo **vazio**, não `0`, não `NaN`, não `null`. É a mesma regra que atravessa o
sistema — e é a que o `pandas.read_csv` lê como
`NaN` sem configuração nenhuma. Um `0` viraria uma medição falsa na análise de outra
pessoa, longe de você e sem contexto para desconfiar.

Este é o ponto do exercício inteiro que mais merece um teste.

**3.** Respeitar a janela é mais simples e mais previsível: o usuário exporta o que está
vendo. Exportar "tudo" precisa de um teto — trinta nós com anos de série não cabem numa
resposta HTTP.

Se seguir a janela, aproveite a validação que `hive_detail` já faz (janela desconhecida cai
no padrão). Repetir esse `if` numa terceira rota é sinal de que ele merece virar um
ajudante.
</details>

## Passo 2 — os testes, primeiro

Em `platform/tests/test_web.py`. No mínimo quatro:

| O que afirma | Por que importa |
|---|---|
| o cabeçalho tem as colunas esperadas, na ordem | é o contrato do arquivo |
| uma medição conhecida vira a linha esperada | o caminho feliz |
| métrica `NULL` vira **campo vazio** | a regra central, do lado da exportação |
| colmeia alheia responde **404** | o escopo, que falha em silêncio |

O quarto é o mais importante e o mais fácil de esquecer. Copie o padrão de
`test_colmeia_alheia_responde_404` — e lembre por que é 404 e não 403: um 403 confirmaria
que aquele id existe.

Vale ainda um quinto: colmeia **sem leitura nenhuma** devolve só o cabeçalho, e não um
erro.

```bash
platform/.venv/bin/pytest platform/tests/test_web.py -q
```

Todos têm de falhar — a rota nem existe ainda.

## Passo 3 — implemente, na camada certa

**No serviço** (`services/series.py` ou um `services/export.py` novo): a função que produz
as linhas. Sem saber o que é HTTP, sem `request`, sem `current_user`.

Assim ela pode ser chamada por um relatório em PDF, por um script de curadoria e
pelo teste — que é a razão de as camadas existirem. E permite testar a formatação sem subir
servidor.

**Na view** (`blueprints/dashboard.py`): a rota, o escopo e os cabeçalhos HTTP.

Duas coisas que a view precisa acertar:

- **o escopo**, com `_load_hive`, que já resolve escopo e 404 de uma vez — não escreva uma
  consulta nova;
- **os cabeçalhos**: `Content-Type: text/csv; charset=utf-8` e um `Content-Disposition` com
  um nome de arquivo que se distinga de outros (nome da colmeia e período; cuidado com
  acentos e espaços).

Use o módulo `csv` da biblioteca padrão em vez de juntar strings com vírgula. Um nome de
colmeia com vírgula — "Colmeia 01, fundo" — quebraria o arquivo em silêncio, e o `csv`
resolve o escape sozinho.

> **E os horários?** Grave em **UTC**, no formato ISO 8601 com o `Z`, como o contrato faz.
> A plataforma converte para o horário da Paraíba só na exibição, e um CSV é um arquivo que
> vai viajar — vira anexo de e-mail, entra num script de outra pessoa. Sem fuso explícito,
> ninguém consegue saber o que aquela coluna significa.

## Passo 4 — verifique

```bash
./verificar plataforma
```

E de verdade, com o banco populado:

```bash
curl -s "http://127.0.0.1:5000/colmeia/1/csv" | head -5
```

(Vai devolver a página de login: a rota exige autenticação, e isso é bom sinal. Para ver o
conteúdo, baixe pelo navegador já logado.)

Abra o arquivo numa planilha. É o teste que nenhum `pytest` faz: as colunas estão
legíveis? Os números têm o número certo de casas? Os campos vazios aparecem vazios?

## Passo 5 — commit e PR

Na descrição, as **três decisões do passo 1** com a justificativa de cada uma. É isso que
transforma um PR de código num PR revisável: quem revisa precisa poder discordar da decisão,
não só do código.

## Critério de pronto

- [ ] As três decisões estão escritas e justificadas
- [ ] Os quatro testes falharam antes e passam depois
- [ ] O teste da colmeia alheia devolve **404**
- [ ] A montagem das linhas está no serviço, não na view
- [ ] Você abriu o arquivo numa planilha
- [ ] `./verificar` verde

## Pistas

<details>
<summary>Como devolvo um arquivo em vez de HTML no Flask?</summary>

Uma `Response` com o corpo, o `mimetype` e o cabeçalho `Content-Disposition`. Monte o corpo
com `io.StringIO` e `csv.writer`.

Comece devolvendo texto puro e confira no navegador; os cabeçalhos são o último ajuste.
</details>

<details>
<summary>Meu CSV abre com tudo numa coluna só no LibreOffice</summary>

Separador. O `csv.writer` usa vírgula, e um LibreOffice em português costuma esperar ponto
e vírgula. Não mude o separador por isso: vírgula é o padrão do formato e o que qualquer
ferramenta de análise espera. Na hora de importar, a planilha deixa escolher.

Se quiser resolver mesmo assim, isso é uma quarta decisão — e ela vai na descrição do PR
como as outras.
</details>

<details>
<summary>Os acentos saem errados</summary>

Codifique em UTF-8 e diga isso no `Content-Type`. Alguns Excel antigos precisam de BOM;
adicionar BOM é outra decisão consciente, com custo (ferramentas Unix passam a ver três
bytes estranhos no começo).
</details>

<details>
<summary>Preciso mesmo de uma função no serviço? A view não resolveria?</summary>

Resolveria, e é exatamente por isso que o exercício insiste. Releia o pedido 3 do exercício
[03](03-onde-eu-mexo.md): o custo de deixar na view não aparece hoje — aparece quando o
relatório em PDF precisar das mesmas linhas e alguém tiver de simular uma requisição HTTP
para gerá-las.
</details>

## O que levar daqui

**O formato de saída é um contrato.** Quem consumir o CSV vai depender das colunas e do
fuso. Escolher com cuidado agora é mais barato do que mudar depois de alguém automatizar em
cima.

**Toda rota nova é uma porta nova para o escopo.** A regra concentrada em `scope.py` só
protege quem a chama — e uma rota de exportação que a esquece vaza a série inteira de outra
organização, sem erro nenhum.

**Um PR bom explica decisões, não só código.** As três perguntas do passo 1 são o conteúdo
real desta contribuição.

→ Próximo: [Sua primeira contribuição](08-sua-primeira-contribuicao.md)
