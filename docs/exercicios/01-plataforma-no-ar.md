# 01. A plataforma no ar

**Tempo:** ~45 min · **Treino**

## Por que este exercício existe

Duas coisas precisam estar no lugar antes de qualquer outra: o ambiente montado e o
hábito de olhar o histórico.

O ambiente é óbvio. O histórico não: a maior parte do que este projeto sabe não está no
código — está nas mensagens de commit, que explicam por que uma linha tem a forma
esquisita que tem. Quem só lê o código conclui que várias decisões são arbitrárias, e a
primeira coisa que faz é "simplificar" alguma delas.

## Antes de começar

Monte o ambiente conforme
[Como trabalhamos](../guia/05-como-trabalhamos.md#preparando-a-máquina). Precisa de git e
Python 3.11+, e mais nada.

## Passos

### 1. As verificações, de uma vez

Na raiz do repositório:

```bash
./verificar
```

Você deve ver duas etapas anunciadas — `ruff` e `pytest` — e, no fim, `=== tudo verde`.

Se faltar alguma ferramenta, o script diz qual e como instalar. Se algum teste falhar numa
`main` recém-clonada, **isso é uma notícia** — avise, porque a `main` deveria estar sempre
verde.

Repare no que acabou de acontecer: sem placa nenhuma ligada, você verificou o formato da
mensagem, a gravação idempotente do reenvio, o isolamento por organização e o vínculo
histórico nó↔colmeia. Em poucos segundos.

### 2. Veja o sistema rodando

São quatro comandos, e cada um tem uma saída que você confere antes de passar ao próximo.
A mesma sequência está em
[Vendo o sistema rodar](../guia/05-como-trabalhamos.md#vendo-o-sistema-rodar).

> **O que é `DATABASE_URL`, e por que ela vem primeiro.**
> A plataforma não decide sozinha em qual banco mexer: ela lê essa variável de ambiente.
> Isso permite que a mesma plataforma rode sobre um arquivo SQLite na sua máquina e sobre
> um PostgreSQL no servidor, sem trocar uma linha de código.
>
> A armadilha é que uma variável de ambiente **vale só no terminal onde você a exportou**.
> Abriu um segundo terminal, precisa exportar de novo — e se esquecer, aquele terminal vai
> criar um banco vazio novo em vez de usar o seu. É a causa mais comum de "o servidor não
> acha os dados que eu acabei de gerar".

#### 2.1 — aponte para o banco

```bash
cd platform
export DATABASE_URL="sqlite:///$PWD/../meliponet-dev.sqlite3"
echo $DATABASE_URL
```

**Confira:** o `echo` imprime um caminho absoluto terminando em `meliponet-dev.sqlite3`.
Se imprimiu linha vazia, o `export` não pegou.

#### 2.2 — crie o banco

```bash
.venv/bin/python -m alembic upgrade head
```

**Confira:** a última linha é `Running upgrade  -> c5015ea6a1fa, esquema inicial`, e o
arquivo `meliponet-dev.sqlite3` passa a existir na raiz do repositório.

> **O que acabou de acontecer.** As tabelas não são criadas pelo código que as descreve —
> são criadas por **migrações**, arquivos versionados que registram cada mudança de
> estrutura em ordem. É o que permite ao banco do servidor, cheio de dados reais, receber
> uma coluna nova sem ser recriado do zero. [A
> plataforma](../guia/03-a-plataforma.md) explica o mecanismo; você vai voltar a ele no
> exercício [03](03-onde-eu-mexo.md).

#### 2.3 — crie o seu usuário

```bash
.venv/bin/python -m flask --app "meliponet:create_app" criar-usuario \
  --email voce@exemplo.br --nome "Seu Nome" --organizacao "Teste" --perfil admin
```

Ele pede a senha e a confirmação. Anote as duas coisas: o e-mail e a senha são como você
vai entrar no painel.

**Confira:** saem duas linhas —

```
Organização criada: Teste
Usuário voce@exemplo.br criado como Administrador em Teste.
```

#### 2.4 — gere 48 h de dados

```bash
cd .. && platform/.venv/bin/python -m simulator --transporte direto --historico 48 \
  --organizacao "Teste"
```

**Confira:** a última linha diz quantas medições e quantas lacunas foram criadas —
algo como `historico pronto: 2212 medições, 96 lacunas injetadas`. Os números variam a
cada execução; o que importa é que as duas contagens são maiores que zero.

As **lacunas são de propósito**: o simulador finge que a rede caiu, para que você veja um
gráfico com buraco antes de ver um gráfico perfeito. Colmeia real produz série com buraco.

#### 2.5 — suba o servidor

```bash
cd platform && .venv/bin/python -m flask --app "meliponet:create_app" run
```

**Confira:** ele imprime `Running on http://127.0.0.1:5000`. Deixe este terminal ocupado —
o servidor fica rodando nele. Daqui em diante, trabalhe em **outro** terminal (e lembre do
`export` da variável, se for mexer no banco por lá).

#### 2.6 — explore dez minutos

Abra `http://127.0.0.1:5000` e entre com o e-mail e a senha de 2.3:

- abra uma colmeia e alterne 24 h / 7 dias / 30 dias;
- **procure os buracos nos gráficos** — são as lacunas de 2.4. Repare que o gráfico
  **mostra** o buraco em vez de ligar os pontos vizinhos: esconder a perda seria mentir
  sobre a completude dos dados;
- veja a linha tracejada do diferencial térmico;
- vá em **Cadastros** e olhe a tela de vínculo nó↔colmeia. É por ela que uma leitura
  passa a aparecer no gráfico de uma colmeia.

### 3. Leia três commits

O `--stat` mostra quais arquivos cada commit tocou. Leia a mensagem **inteira** dos três:

```bash
git log -1 --stat 6507c76    # plataforma: declara o pacote, consertando o CI
git log -1 --stat 1f492bf    # plataforma: o administrador volta a administrar tudo
git log -1 --stat b4cc633    # simulador: o meliponario e procurado dentro da organizacao
```

Para cada um, responda por escrito (num rascunho seu, não num arquivo do repositório):

1. **Qual era o sintoma no mundo?** Não o que estava errado no código — o que a pessoa que
   usava o sistema via acontecer.
2. **Por que ninguém tinha notado antes?**
3. **Como saber que a correção funcionou?**

<details>
<summary>Respostas — abra depois de escrever as suas</summary>

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

**`1f492bf` — o administrador levando 403.**
*Sintoma:* o administrador via na tela os nós de todas as organizações, com os botões
"Remanejar" e "Desvincular" desenhados, e **levava 403 ao clicar**. Junto ia um defeito
mais silencioso: ao vincular, o nó recebia a organização de *quem estava logado*, de modo
que um admin adotando um nó para a colmeia de outra organização levava o nó consigo — e o
dono legítimo deixava de enxergar o próprio nó, sem erro nenhum na tela.
*Por que ninguém notou:* nenhum teste exercitava o perfil `admin`; as fixtures nasciam
meliponicultor. Um conjunto de testes que nunca constrói um dos casos não cobre aquele
caso, por mais linhas que tenha.
*Como saber que funcionou:* as duas rotas passaram a perguntar ao `services/scope.py` em
vez de comparar `organization_id` na mão, e o teste do nó alheio continua exigindo 403 —
que é o que garante que a correção não virou buraco de segurança.

**`b4cc633` — o meliponário homônimo.**
*Sintoma:* rodar o simulador com `--organizacao` apontando para outra organização
pendurava as colmeias novas no meliponário homônimo da primeira, **em silêncio**. Quem
esperava ver dados numa organização via o painel vazio, e os dados estavam noutro lugar.
*Por que ninguém notou:* com uma organização só, a busca pelo nome sempre acerta. O
defeito só existe a partir da segunda.
*Como saber que funcionou:* o `seed` passou a procurar o meliponário **dentro da
organização**, e há teste para isso — é o mesmo motivo pelo qual as fixtures dos testes
têm duas organizações desde a base.

A lição comum aos três: **um caso que nenhum teste constrói é um caso que ninguém
cobre.**
</details>

## Critério de pronto

- [ ] `./verificar` termina com `=== tudo verde`
- [ ] Cada um dos cinco comandos do passo 2 deu a saída que o exercício descreve
- [ ] Você entrou no painel com o usuário que criou
- [ ] Você abriu uma colmeia no navegador e localizou pelo menos um buraco num gráfico
- [ ] Você escreveu as três respostas antes de abrir o gabarito

## Pistas

<details>
<summary>`./verificar` reclama do ambiente virtual</summary>

O script imprime o comando exato:

```bash
cd platform
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```
</details>

<details>
<summary>O painel abre mas não tem gráfico nenhum</summary>

Faltou gerar os dados sintéticos, ou o `DATABASE_URL` do terminal do servidor aponta para
um banco diferente do que o simulador populou. Confira que os dois terminais exportaram o
**mesmo** `DATABASE_URL`, e que o `--organizacao` do simulador é a mesma organização do
usuário que você criou.
</details>

## O que levar daqui

**Uma verificação que leva segundos você roda; uma que leva minutos você pula.** É por
isso que quase toda a lógica difícil deste projeto foi empurrada para onde roda no PC, sem
hardware.

**A mensagem de commit é o único lugar onde o "porquê" existe.** O diff mostra o quê. Em
seis meses, nem você vai lembrar do resto — e é por isso que o guia cobra o parágrafo do
porquê.

→ Próximo: [Uma mensagem até o gráfico](02-uma-mensagem-ate-o-grafico.md)
