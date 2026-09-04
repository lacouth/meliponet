# 01. Tudo verde

**Área:** todas · **Tempo:** ~30 min · **Treino**

## Por que este exercício existe

Duas coisas precisam estar no lugar antes de qualquer outra: o ambiente montado e o
hábito de olhar o histórico.

O ambiente é óbvio. O histórico não: a maior parte do que este projeto sabe não está no
código — está nas mensagens de commit, que explicam por que uma linha tem a forma
esquisita que tem. Quem só lê o código conclui que várias decisões são arbitrárias, e a
primeira coisa que faz é "simplificar" alguma delas.

## Antes de começar

Faça o ambiente de [Primeira contribuição](../guia/06-primeira-contribuicao.md#preparando-a-máquina).
Precisa de git, Python 3.11+ e PlatformIO.

## Passos

### 1. As quatro verificações, de uma vez

Na raiz do repositório:

```bash
./verificar
```

Você deve ver quatro etapas anunciadas e, no fim, `=== tudo verde`.

Se faltar alguma ferramenta, o script diz qual e como instalar. Se algum teste falhar numa
`main` recém-clonada, **isso é uma notícia** — avise, porque a `main` deveria estar sempre
verde.

Repare no que acabou de acontecer: sem placa nenhuma ligada, você verificou o codec do
firmware, a conversão de escala, a fila do spool, o isolamento por organização e a
concordância byte a byte entre C++ e Python. Em poucos segundos.

### 2. Veja o sistema rodando

Siga [Vendo o sistema rodar](../guia/06-primeira-contribuicao.md#vendo-o-sistema-rodar):
banco, usuário, 48 h de dados sintéticos, servidor.

Abra `http://127.0.0.1:5000`, entre, e gaste dez minutos:

- abra uma colmeia e alterne 24 h / 7 dias / 30 dias;
- **procure os buracos nos gráficos** — são lacunas injetadas de propósito pelo simulador;
- veja a linha tracejada do diferencial térmico;
- vá em **Cadastros** e olhe a tela de vínculo nó↔colmeia.

### 3. Leia três commits

O `--stat` mostra quais arquivos cada commit tocou. Leia a mensagem **inteira** dos três:

```bash
git log -1 --stat ae2206a    # firmware: a tara passa a valer na hora (D-04)
git log -1 --stat 6507c76    # plataforma: declara o pacote, consertando o CI
git log -1 --stat 7ea2093    # firmware: corrige tres defeitos que deixariam o no mudo
```

Para cada um, responda por escrito (num rascunho seu, não num arquivo do repositório):

1. **Qual era o sintoma no mundo?** Não o que estava errado no código — o que a pessoa
   que usava o sistema via acontecer.
2. **Por que ninguém tinha notado antes?**
3. **Como saber que a correção funcionou?**

<details>
<summary>Respostas — abra depois de escrever as suas</summary>

**`ae2206a` — a tara.**
*Sintoma:* quem tarava a célula e lia em seguida via o valor errado, concluía que "a tara
não pegou" e repetia o procedimento várias vezes, com a colmeia montada, sem que nada
indicasse o que estava acontecendo.
*Por que ninguém notou:* o comando `calibrar`, ao lado, sempre fez a chamada que faltava
no `tara` — a assimetria entre os dois é que era o defeito, e ela só aparece para quem usa
os dois em sequência na bancada.
*Como saber que funcionou:* não há teste automatizado, e o commit **diz isso
explicitamente** — o comando depende do Arduino e de um objeto que só existe com hardware.
A verificação fica na bancada: taras seguidas devem mudar a leitura imediatamente, sem
reiniciar. Repare que admitir a ausência de teste é parte da mensagem, não uma omissão.

**`6507c76` — o pacote não declarado.**
*Sintoma:* `pip install -e "platform[dev]"` falhava numa máquina limpa, e o job `pytest`
do CI morria antes de rodar qualquer teste — em **todo commit desde a Fase 2**, doze
commits seguidos.
*Por que ninguém notou:* um ambiente virtual criado *antes* de a pasta `migrations/`
existir continua funcionando para sempre. Só instalação limpa falha — ou seja, só o CI e
quem entra no projeto agora. É o modo de falha mais traiçoeiro que existe: funciona na
máquina de quem já estava aqui.
*Como saber que funcionou:* o commit conta que a falha foi reproduzida num venv novo
*antes* da correção, e a correção verificada na mesma versão de Python do runner. Ou seja:
primeiro reproduza, depois corrija.

**`7ea2093` — três defeitos de nó mudo.**
*Sintoma:* nos três casos, um nó que **parece saudável** e não publica nada. MQTT indo
para `0.0.0.0:0` com tópico vazio; WiFi que nunca mais reconecta depois de uma queda; e
mensagens órfãs no flash, recontadas a cada boot.
*Por que ninguém notou:* os três estão **na fronteira com o hardware**, exatamente onde os
testes nativos não chegavam. A lógica pura, bem coberta, saiu correta. O commit é explícito
sobre isso: "o que ficou fora da rede de testes foi o que quebrou".
*Como saber que funcionou:* as duas lógicas novas foram **movidas** para `MelipoCore`,
onde são puras, e ganharam 14 testes nativos — recuo com espera longa e com a volta do
contador de `millis()`, reconstrução com anel dado a volta, anel cheio e estado
inconsistente. Cenários que em hardware exigiriam dias.

A lição comum aos três: **a correção real não foi a linha; foi trazer o caso para onde um
teste alcança.**
</details>

## Critério de pronto

- [ ] `./verificar` termina com `=== tudo verde`
- [ ] Você abriu uma colmeia no navegador e localizou pelo menos um buraco num gráfico
- [ ] Você escreveu as três respostas antes de abrir o gabarito

## Pistas

<details>
<summary>`./verificar` reclama do ambiente virtual</summary>

O script imprime o comando exato. É o mesmo de
[Primeira contribuição](../guia/06-primeira-contribuicao.md#plataforma):

```bash
cd platform
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```
</details>

<details>
<summary>`pio: command not found`</summary>

`~/.local/bin` não está no seu `PATH`. E não use `pip install platformio`: as
distribuições recentes recusam instalação no Python do sistema. Use
`uv tool install platformio` ou `pipx install platformio`.
</details>

<details>
<summary>O dashboard abre mas não tem gráfico nenhum</summary>

Faltou gerar os dados sintéticos, ou o `DATABASE_URL` do terminal do servidor aponta para
um banco diferente do que o simulador populou. Confira que os dois terminais exportaram o
**mesmo** `DATABASE_URL`, e que o `--organizacao` do simulador é a mesma organização do
usuário que você criou.
</details>

## O que levar daqui

**Uma verificação que leva segundos você roda; uma que leva minutos você pula.** É por
isso que quase toda a lógica difícil deste projeto foi empurrada para onde roda no PC.

**A mensagem de commit é o único lugar onde o "porquê" existe.** O diff mostra o quê. Em
seis meses, nem você vai lembrar do resto — e é por isso que o guia cobra o parágrafo do
porquê.

→ Próximo: [Uma mensagem ponta a ponta](02-uma-mensagem-ponta-a-ponta.md)
