# 02. Uma mensagem até o gráfico

**Tempo:** ~30 min · **Treino**

## Por que este exercício existe

Você vai passar semanas escrevendo o firmware que produz essa mensagem. Antes disso, vale
mandá-la **à mão**, uma vez, e ver o que acontece com ela do outro lado — inclusive quando
está errada.

Assim, quando o seu nó não conseguir entregar nada, você já vai saber separar duas coisas
que parecem uma só: "a plataforma está recusando" e "a plataforma não está recebendo".

Neste exercício você não muda nenhuma linha de código.

## Antes de começar

O servidor precisa estar no ar (exercício 01). Deixe-o rodando num terminal e trabalhe em
outro.

## Passos

### 1. Mande uma leitura válida

Da raiz do repositório:

```bash
curl -i -X POST http://127.0.0.1:5000/api/v1/telemetria \
  -H 'Content-Type: application/json' \
  --data @contracts/exemplos/02-completa.json
```

Anote o código de resposta e o corpo. Depois **repita o mesmo comando** e compare.

### 2. Encontre a sua leitura no banco

```bash
sqlite3 meliponet-dev.sqlite3 \
  "SELECT time, node_id, seq, temp_in_c, weight_kg FROM measurements
   WHERE node_id = 'A4C1380F' ORDER BY time DESC LIMIT 3;"
```

### 3. Mande três mensagens erradas

Uma de cada vez, e **leia o motivo** que volta:

```bash
for arquivo in 01-sem-seq 03-sem-metrica 08-ts-sem-fuso; do
  echo "--- $arquivo"
  curl -s -X POST http://127.0.0.1:5000/api/v1/telemetria \
    -H 'Content-Type: application/json' \
    --data @contracts/exemplos/invalidas/$arquivo.json
  echo
done
```

Agora ache as três no banco:

```bash
sqlite3 meliponet-dev.sqlite3 "SELECT reason, topic FROM ingest_rejects ORDER BY id DESC LIMIT 3;"
```

### 4. Responda

Por escrito, no seu rascunho:

1. O que mudou entre a **primeira** e a **segunda** vez que você mandou
   `02-completa.json`? Por que a plataforma responde assim, em vez de responder erro?
2. A leitura que você mandou apareceu em algum gráfico? Por quê?
3. Por que uma mensagem recusada é **guardada** em vez de simplesmente descartada?
4. `03-sem-metrica.json` tem `vbat_v` e mesmo assim é recusada. Qual é a regra, e por que
   ela existe?

<details>
<summary>Respostas — abra depois de escrever as suas</summary>

**1.** A primeira responde `201` (gravou); a segunda, `200` com `"repetida": true`. A
plataforma reconhece o par (`node_id`, `seq`) e trata a repetição como **reenvio**, não
como erro — é exatamente o que o nó faz quando drena o que guardou durante uma queda de
rede. Se isso respondesse erro, o firmware guardaria a cópia local para sempre e a memória
do nó encheria por causa de uma leitura que a plataforma já tinha.

**2.** Provavelmente não. O `node_id` `A4C1380F` do exemplo não está vinculado a nenhuma
colmeia no seu banco, e o campo `colmeia` da resposta veio `null`. A leitura **está
gravada** — ela aparece no gráfico assim que alguém fizer o vínculo em Cadastros, e é por
isso que o nó desconhecido é auto-cadastrado em vez de ter suas leituras descartadas.

**3.** Porque "não chegou dado" e "chegou dado que eu recusei" são coisas diferentes, e
só a segunda tem explicação. A tabela `ingest_rejects` guarda o motivo e um pedaço do
payload — é o que permite descobrir, meses depois, que aquele nó estava mandando JSON
cortado ao meio, em vez de concluir que "a colmeia parou de mandar dados". A proporção de
leituras recusadas também é um indicador de qualidade que o projeto se compromete a
reportar.

**4.** Toda mensagem precisa de **ao menos uma grandeza da colmeia** — temperatura,
umidade ou peso. `vbat_v` e `rssi` descrevem o nó, não a colmeia. Sem essa regra, um nó
com todos os sensores quebrados encheria o banco de linhas que não medem nada, e a
contagem de leituras diria que está tudo bem.
</details>

## Critério de pronto

- [ ] Você viu `201` na primeira vez e `200` na segunda, com o mesmo arquivo
- [ ] Você encontrou a sua leitura em `measurements` pelo `sqlite3`
- [ ] Você encontrou as três recusas em `ingest_rejects`, com motivos diferentes
- [ ] Você escreveu as quatro respostas antes de abrir o gabarito

## Pistas

<details>
<summary>`curl: (7) Failed to connect`</summary>

O servidor não está no ar, ou está noutra porta. Volte ao terminal do `flask run` e
confira o endereço que ele imprimiu.
</details>

<details>
<summary>`sqlite3: command not found`</summary>

Instale o cliente (`sudo pacman -S sqlite`, `sudo apt install sqlite3`) ou faça a mesma
consulta em Python:

```bash
platform/.venv/bin/python -c "
import sqlite3
con = sqlite3.connect('meliponet-dev.sqlite3')
for linha in con.execute('SELECT time, node_id, seq FROM measurements ORDER BY time DESC LIMIT 3'):
    print(linha)"
```
</details>

<details>
<summary>A consulta não devolve nada</summary>

Confira que você está na raiz do repositório e que o arquivo do banco é o mesmo que o
servidor está usando — o `DATABASE_URL` que você exportou diz qual é.
</details>

## O que levar daqui

**A resposta HTTP é o seu principal instrumento de depuração** enquanto você escreve o
firmware. Ela diz, na hora, se a mensagem foi aceita e, quando não foi, exatamente o que
está errado.

**Reenvio não é erro.** Essa decisão da plataforma é o que permite ao nó ser simples: ele
guarda o que não conseguiu mandar e manda de novo, sem precisar saber o que a plataforma
já tem.

→ Próximo: [Onde eu mexo?](03-onde-eu-mexo.md)
