# 08. A rota que entrega o arquivo

**Tempo:** ~1 h · **Contribuição**

> Continuação do [07](07-o-csv-na-camada-certa.md). Mesma branch, mesmo PR.

## Por que este exercício existe

Você tem uma função que produz as linhas certas. Falta transformá-la num arquivo que
alguém baixa — e essa metade tem preocupações que a outra não tinha: quem pode baixar o
quê, como o navegador sabe que aquilo é um arquivo, e que nome ele ganha no disco de quem
baixou.

A preocupação mais séria é a primeira. **Toda rota nova é uma porta nova para o escopo.**

## Antes de começar

- Exercício [07](07-o-csv-na-camada-certa.md) feito, com os quatro testes verdes.
- Servidor no ar e banco populado (exercício [01](01-plataforma-no-ar.md)).
- Você está na mesma branch `plataforma/exportar-csv`.

## Passo 1 — o teste do escopo, primeiro

Em `platform/tests/test_web.py`, e **antes** da rota existir:

| O que afirma | Por que importa |
|---|---|
| colmeia própria devolve `200` e um corpo que começa pelo cabeçalho | o caminho feliz |
| colmeia **de outra organização** responde `404` | o escopo, que falha em silêncio |

Copie o padrão de `test_colmeia_alheia_responde_404`
(`platform/tests/test_web.py:84`) — achar onde a coisa já é feita de forma parecida vale
mais do que inventar um jeito novo.

> **O conceito: por que 404 e não 403.**
> `403 Proibido` e `404 Não encontrado` parecem igualmente seguros: nos dois casos a pessoa
> não recebe o dado. Mas eles dizem coisas diferentes. Um `403` afirma *"este recurso
> existe, e você não pode vê-lo"* — e alguém percorrendo `/colmeia/1/csv`,
> `/colmeia/2/csv`, `/colmeia/3/csv` descobre, pelo padrão das respostas, **quantas
> colmeias existem e com quais números**, sem ver um único dado. O `404` diz apenas *"para
> você, isso não existe"*, que é indistinguível de um número que ninguém usou.
>
> A regra do projeto: fora do seu escopo, a resposta é `404`. Ver
> [A plataforma](../guia/03-a-plataforma.md).

```bash
platform/.venv/bin/pytest platform/tests/test_web.py -q
```

Os dois falham: a rota ainda não existe, e o Flask responde `404` a tudo — inclusive ao
primeiro teste, que esperava `200`. **Repare que o teste do escopo passa pelo motivo
errado.** É o caso clássico de teste que passa sem provar nada, e é por isso que o outro
teste existe: sem ele, você não saberia distinguir "a rota protege" de "a rota não existe".

## Passo 2 — a rota, com o escopo

Em `blueprints/dashboard.py`. Use **`_load_hive`**
(`platform/meliponet/blueprints/dashboard.py:95`), que já resolve escopo e 404 de uma vez
— não escreva uma consulta nova. O comentário dentro dele explica por quê.

Comece devolvendo **texto puro**, sem se preocupar com cabeçalho nenhum. O objetivo deste
passo é só um: os dois testes do passo 1 passam.

**Confira:** `pytest platform/tests/test_web.py -q` verde, e
`pytest platform/tests/test_series.py -q` continua verde.

## Passo 3 — os cabeçalhos HTTP

Agora o navegador precisa saber que aquilo é um arquivo, e não uma página.

> **O conceito: o corpo não diz o que ele é; os cabeçalhos dizem.**
> A resposta HTTP tem duas partes. O **corpo** são os bytes; os **cabeçalhos** são o
> bilhete que os acompanha, e é por eles que o navegador decide o que fazer. Dois importam
> aqui:
>
> - `Content-Type: text/csv; charset=utf-8` — "isto é um CSV, em UTF-8". Sem isso o
>   navegador trata como texto e mostra na tela; e sem o `charset`, os acentos viram
>   símbolos.
> - `Content-Disposition: attachment; filename=...` — "não mostre, salve; e chame assim".
>
> É a mesma ideia do `Content-Type: application/json` que o nó manda no POST, do outro lado
> do sistema.

O nome do arquivo merece pensamento: ele vai parar na pasta de downloads de alguém junto de
outros vinte. Nome da colmeia e período ajudam; acentos e espaços atrapalham.

**Confira:** baixe pelo navegador, já logado, e veja o arquivo chegar com o nome que você
escolheu — em vez de aparecer na tela.

## Passo 4 — abra numa planilha

```bash
./verificar plataforma
```

E depois o teste que nenhum `pytest` faz: **abra o arquivo baixado numa planilha.**

- as colunas estão legíveis e na ordem do passo 2 do exercício 07?
- os números têm o número certo de casas?
- os campos vazios aparecem vazios — e não como `0`?
- os acentos do nome da colmeia estão certos?

Um `curl` na rota, do terminal, vai devolver a **página de login**: a rota exige
autenticação, e isso é bom sinal.

## Passo 5 — commit e PR

Na descrição, as **três decisões do passo 1 do exercício 07**, com a justificativa de cada
uma, mais a escolha de onde a função foi morar. É isso que transforma um PR de código num
PR revisável: quem revisa precisa poder discordar da decisão, não só do código.

## Critério de pronto

- [ ] O teste da colmeia alheia devolve **404**, e você sabe dizer por que não é 403
- [ ] Os dois testes falharam antes e passam depois
- [ ] A rota usa `_load_hive`, e não uma consulta nova
- [ ] A montagem das linhas continua no serviço, não migrou para a view
- [ ] Você abriu o arquivo numa planilha
- [ ] O PR descreve as decisões, não só a mudança
- [ ] `./verificar` verde

## Pistas

<details>
<summary>Como devolvo um arquivo em vez de HTML no Flask?</summary>

Uma `Response` com o corpo, o `mimetype` e o cabeçalho `Content-Disposition`. Monte o corpo
com `io.StringIO` e `csv.writer`.

É o que o passo 2 quer dizer com "comece devolvendo texto puro": os cabeçalhos são o último
ajuste, não o primeiro.
</details>

<details>
<summary>Meu CSV abre com tudo numa coluna só no LibreOffice</summary>

Separador. O `csv.writer` usa vírgula, e um LibreOffice em português costuma esperar ponto
e vírgula. Não mude o separador por isso: vírgula é o padrão do formato e o que qualquer
ferramenta de análise espera. Na hora de importar, a planilha deixa escolher.

Se quiser resolver mesmo assim, isso é mais uma decisão — e ela vai na descrição do PR como
as outras.
</details>

<details>
<summary>Os acentos saem errados</summary>

Codifique em UTF-8 e diga isso no `Content-Type`. Alguns Excel antigos precisam de BOM;
adicionar BOM é outra decisão consciente, com custo (ferramentas Unix passam a ver três
bytes estranhos no começo).
</details>

<details>
<summary>Por que não faço a montagem das linhas aqui na view mesmo?</summary>

Funcionaria, e é exatamente por isso que os dois exercícios insistem. Releia o pedido 3 do
exercício [03](03-onde-eu-mexo.md): o custo de deixar na view não aparece hoje — aparece
quando o relatório em PDF precisar das mesmas linhas e alguém tiver de simular uma
requisição HTTP para gerá-las.
</details>

## O que levar daqui

**Toda rota nova é uma porta nova para o escopo.** A regra concentrada em `scope.py` só
protege quem a chama — e uma rota de exportação que a esquece vaza a série inteira de outra
organização, sem erro nenhum.

**Um teste pode passar pelo motivo errado.** O `404` do passo 1 já passava antes de a rota
existir. Só o par de testes distingue "protegido" de "inexistente".

**Um PR bom explica decisões, não só código.** As três perguntas do exercício 07 são o
conteúdo real desta contribuição.

→ Próximo: [Sua primeira contribuição](09-sua-primeira-contribuicao.md)
