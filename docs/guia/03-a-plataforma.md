# 3. A plataforma

Para quem vai mexer em `platform/` — e, mesmo para quem só vai escrever o firmware, para
saber o que acontece com a mensagem depois que ela sai do nó.

## O que é Flask

Flask é uma biblioteca Python para escrever servidores web. O modelo mental básico:

```
navegador pede uma URL  →  Flask acha a função responsável  →  a função devolve HTML
```

Cada função dessas se chama **view**, e a ligação entre URL e função é uma **rota**:

```python
@bp.route("/colmeia/<int:colmeia_id>")   # a rota
@login_required                           # só entra quem está autenticado
def detalhe_da_colmeia(colmeia_id: int):  # a view
    ...
    return render_template("painel/colmeia.html", **contexto)
```

Abrir `http://servidor/colmeia/7` chama `detalhe_da_colmeia(colmeia_id=7)`.

## A estrutura de pastas

```
platform/
├── pyproject.toml              o que o projeto precisa para rodar
├── alembic.ini                 configuração das migrações
│
├── meliponet/                  ← O CÓDIGO
│   ├── __init__.py             criar_app(): monta a aplicação
│   ├── configuracao.py         lê as variáveis de ambiente
│   ├── banco.py                conexão com o banco e as sessões
│   ├── modelos.py              as tabelas, como classes Python
│   ├── modelos_futuros.py      tabelas da Fase 4, criadas mas ainda sem uso
│   ├── cli.py                  comandos de terminal (criar-usuario)
│   │
│   ├── rotas/                  ← AS ROTAS (o que o navegador acessa), um arquivo por assunto
│   │   ├── api.py                 POST /api/v1/telemetria: a porta do nó
│   │   ├── autenticacao.py        entrar e sair
│   │   ├── publico.py             a página inicial, sem login
│   │   ├── painel.py              a lista de colmeias e os gráficos
│   │   ├── cadastros.py           a tela /gerenciar/, que lista tudo
│   │   ├── meliponarios.py        criar e editar meliponário
│   │   ├── colmeias.py            criar e editar colmeia
│   │   ├── nos.py                 vincular e desvincular nó
│   │   ├── formulario.py          ajudantes para ler campos de formulário
│   │   └── permissao.py           ajudantes que respondem 403
│   │
│   ├── servicos/               ← A LÓGICA (sem saber que existe web)
│   │   ├── escopo.py              quem pode ver o quê
│   │   ├── serie.py               as consultas que alimentam os gráficos
│   │   └── vinculos.py            as regras de instalar e retirar um nó
│   │
│   ├── ingestao/               ← A ENTRADA DE DADOS (processo separado)
│   │   ├── telemetria.py          valida a mensagem contra o contrato
│   │   ├── gravacao.py            grava no banco
│   │   └── __main__.py            o consumidor MQTT
│   │
│   ├── templates/              ← O HTML, uma pasta por arquivo de rota
│   │   ├── base.html              o esqueleto comum
│   │   ├── painel/                as telas de rotas/painel.py:
│   │   │   ├── colmeias.html         a lista de colmeias
│   │   │   ├── colmeia.html          a página de uma colmeia
│   │   │   └── _fragmento_da_colmeia.html   o pedaço que se atualiza sozinho
│   │   ├── cadastros/  meliponarios/  colmeias/  nos/  autenticacao/  publico/
│   │   └── ...                    (mesma regra: a pasta tem o nome do arquivo da rota)
│   │
│   └── static/                 ← O QUE O NAVEGADOR BAIXA COMO ESTÁ
│       ├── estilo.css             a aparência de todas as páginas
│       └── graficos.js            desenha os gráficos da página da colmeia
│
├── migrations/                 ← AS MUDANÇAS DE ESTRUTURA DO BANCO
└── tests/                      ← OS TESTES
```

## As camadas, e por que existem

Se você vem de microcontrolador, seu modelo mental provável é um `main.c` que faz tudo.
Aqui a coisa é dividida em camadas, e vale entender a razão — não é organização por
organização.

```
rotas/       fala HTTP: recebe requisição, devolve HTML
     ↓
servicos/    lógica de negócio: não sabe o que é uma requisição
     ↓
modelos.py   as tabelas
     ↓
banco
```

**A regra: uma camada só chama a de baixo.** `servicos/` nunca importa `rotas/`.

O motivo prático fica claro num exemplo. `servicos/serie.py` calcula a série de uma
colmeia. Como ele não sabe o que é HTTP, ele pode ser chamado:

- pela página web,
- pelo gerador de relatórios em PDF,
- por um script de exportação,
- por um teste, sem subir servidor nenhum.

Se a lógica estivesse dentro da view, cada um desses casos precisaria simular uma
requisição HTTP para calcular uma média. É por isso que os testes em `test_serie.py`
rodam em milissegundos, sem servidor.

## `modelos.py` — as tabelas como classes

Em vez de escrever SQL, descrevemos as tabelas como classes Python. A biblioteca que faz
essa tradução (SQLAlchemy) chama-se **ORM**.

```python
class Colmeia(Base):
    __tablename__ = "hives"

    id: Mapped[int] = mapped_column(primary_key=True)
    apiary_id: Mapped[int] = mapped_column(ForeignKey("apiaries.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    species: Mapped[str | None] = mapped_column(String(120))
```

E as consultas viram Python:

```python
hive = session.scalar(select(Colmeia).where(Colmeia.id == 7))
print(hive.name)
```

### Duas decisões do nosso modelo que você precisa entender

**Métricas são anuláveis (`float | None`).** Já explicado no contrato: sensor que falhou
não produz zero, produz nada.

**O vínculo nó↔colmeia é histórico, não um campo.** Este é o ponto mais sutil do
modelo. Um nó é remanejado entre colmeias em campo: sai de uma caixa que colapsou, entra
em outra. Se o vínculo fosse uma coluna em `nodes`, remanejar **reescreveria o passado**
— toda a série histórica da colmeia antiga passaria a ser atribuída à nova.

Por isso existe `Vinculo`, com `installed_at` e `removed_at`. A colmeia de uma
medição é resolvida pelo **instante da medição**:

```python
def colmeia_no_instante(session, node, when):
    # "em que colmeia este nó estava em `when`?" — não "onde ele está hoje"
```

Isso também resolve o spool: uma mensagem represada por dias pousa na colmeia em que o
nó estava **quando mediu**.

## `migrations/` — mudando a estrutura do banco

O banco de desenvolvimento você apaga e refaz à vontade. O de produção tem meses de
séries coletadas em campo — apagar não é opção.

Uma **migração** é um script que transforma a estrutura do banco de uma versão para a
seguinte, preservando os dados. A ferramenta é o Alembic.

```bash
# depois de mudar modelos.py, gere a migração
python -m alembic revision --autogenerate -m "adiciona coluna X"

# LEIA o arquivo gerado em migrations/versions/ antes de aplicar
python -m alembic upgrade head
```

Duas regras:

**Leia sempre a migração gerada.** O autogenerate é bom, não é perfeito — ele às vezes
interpreta um `rename` como "apaga a coluna velha, cria uma nova", o que descarta os
dados.

**Nunca edite uma migração já aplicada em produção.** Ela é o registro do que foi de
fato executado naquele banco. Precisa mudar? Crie outra.

## `templates/` — o HTML

Templates são HTML com buracos preenchidos pelo Python. A linguagem é o Jinja:

```html
{% for linha in visao_geral %}
  <tr>
    <td>{{ linha.colmeia.name }}</td>
    <td>{{ linha.ultima.temp_in_c | numero(1, ' °C') }}</td>
  </tr>
{% endfor %}
```

- `{{ ... }}` insere um valor
- `{% ... %}` é lógica (`if`, `for`)
- `| numero(1, ' °C')` é um **filtro**: formata o valor

`base.html` é o esqueleto (cabeçalho, navegação) e as outras páginas o estendem com
`{% extends "base.html" %}`. A aparência mora em `static/estilo.css`, e o JavaScript dos
gráficos em `static/graficos.js`: o template fica só com HTML.

**Para achar o template de uma tela**, olhe o `render_template` da rota: o nome da pasta é
o nome do arquivo da rota. `rotas/nos.py` desenha `templates/nos/vincular.html`.

**Nome errado no template é erro, não silêncio.** Por padrão o Jinja trata uma variável
que não existe como vazia — o pedaço da tela simplesmente some. Aqui o `criar_app` liga o
modo estrito (`StrictUndefined`), e um nome errado vira `UndefinedError` na hora: o teste
que abre a página quebra. Foi assim que descobrimos, tarde, que as flags de qualidade
tinham sumido do painel numa tradução.

### A sessão do banco dura a requisição inteira

O template renderiza **depois** que a view retorna. Isso importa porque o ORM carrega
objetos **preguiçosamente**: `hive.apiary` só vai ao banco no momento em que alguém usa o
atributo — e esse momento, no caso de um template, é depois da view.

Por isso a sessão está amarrada à requisição, e não à view:

```python
@bp.route("/colmeia/<int:colmeia_id>")
@login_required
def detalhe_da_colmeia(colmeia_id: int):
    session = sessao_do_request()          # abre na primeira chamada da requisição
    ...
```

Quem fecha é o Flask, no fim da requisição, seguindo uma regra só:
**requisição que terminou bem grava; qualquer outra coisa desfaz.** Uma resposta 4xx ou
5xx não commita, mesmo que a view já tivesse mexido em algum objeto antes de desistir. O
mecanismo está em `banco.py`, em `registrar_sessao_por_request`.

Com a sessão aberta, o template escreve `{{ colmeia.apiary.name }}` sem cerimônia.

**O que isso não dispensa.** Você ainda vai ver `selectinload` nas consultas de listagem:

```python
apiaries = list(
    session.scalars(
        escopo.meliponarios_visiveis(current_user)
        .options(selectinload(Meliponario.hives))
        .order_by(Meliponario.name)
    )
)
```

Mas agora ele está ali por **desempenho**, não por correção: sem ele, cada meliponário da
lista dispararia uma consulta própria para buscar as colmeias — o clássico **N+1**. Uma
tela com 20 meliponários faria 21 consultas em vez de 2.

Essa distinção vale guardar, porque as duas coisas se pareciam antes e são diferentes:
carregamento adiantado por correção você não precisa mais fazer; por desempenho, precisa
quando estiver percorrendo uma lista.

### Quem não tem requisição

O ingestor MQTT, o `cli.py` e os testes não têm requisição nenhuma, e continuam abrindo a
sessão na mão:

```python
with abrir_sessao() as session:
    gravar(session, decodificar(mensagem))
```

Há uma exceção que vale entender, em `rotas/api.py`: a rota HTTP de telemetria
**também** usa `abrir_sessao()`, mesmo sendo uma rota. O motivo é que ela grava a recusa
de uma mensagem inválida e **responde 400** — e a regra da sessão por requisição desfaria
justamente o registro que serve para depurar.

## `servicos/escopo.py` — quem vê o quê

Três perfis: `meliponicultor` vê só a própria organização, `pesquisador` vê tudo mas não
edita, `admin` vê tudo e edita.

A regra vive num arquivo só. O motivo é o modo de falha: **uma consulta que esquece o
filtro não quebra**. Não levanta erro, não aparece em teste de rota que só cheque o
status HTTP. Ela apenas mostra a um meliponicultor as colmeias de outro. Concentrando a
regra num lugar, esquecer fica difícil.

```python
# ✅ certo
hives = session.scalars(escopo.colmeias_visiveis(current_user))

# ❌ errado — vê tudo, sem reclamar
hives = session.scalars(select(Colmeia))
```

E repare que colmeia alheia responde **404, não 403**. Um 403 confirmaria que aquele id
existe, e enumerar ids é justamente o ataque que a rota impede.

**O que aconteceu quando alguém contornou o helper.** Duas rotas de vínculo comparavam
`node.organization_id` com o do usuário diretamente, em vez de perguntar ao escopo. A
comparação estava certa para o meliponicultor e nunca acompanhou os perfis que veem
tudo: o administrador via na tela os nós de todas as organizações, com os botões
desenhados, e levava **403 ao clicar**. Junto ia um defeito mais silencioso — o vínculo
carimbava no nó a organização de quem estava logado, e um admin que adotasse um nó para
a colmeia de outra organização levava o nó consigo, deixando o dono legítimo sem
enxergar o próprio nó. É a mesma lição do arquivo, do outro lado: **a regra concentrada
só protege quem a chama**. Hoje as duas rotas usam `pode_gerenciar_no`, e o nó recebe a
organização da colmeia — regra que mora em `servicos/vinculos.py`, na função `vincular`,
e é testada sem servidor nenhum em `test_vinculos.py`. A rota só lê o formulário,
confere a permissão e chama o serviço.

E há uma segunda lição, sobre teste: nenhum teste exercitava o perfil `admin` — as
fixtures nasciam meliponicultor. Um conjunto de testes que nunca constrói um dos casos
não cobre aquele caso, por mais linhas que tenha.

## As duas portas por onde a telemetria entra

O nó pode entregar a leitura de dois jeitos, e os dois terminam nas mesmas duas funções
(`ingestao.telemetria.decodificar` valida, `ingestao.gravacao.gravar` grava). Não existe uma segunda
implementação da ingestão — se existisse, os dois caminhos divergiriam, e o nó que
trocasse de transporte veria a plataforma se comportar de outro jeito.

**`rotas/api.py` — `POST /api/v1/telemetria`.** É a porta que o aluno usa enquanto
escreve o firmware: nenhuma peça a mais para instalar, e a resposta HTTP diz na hora o
que estava errado (`201` gravou, `200` já tinha, `400` com o motivo). O token de ingestão
é opcional: sem `TOKEN_INGESTAO` no ambiente a rota aceita qualquer POST, o que permite
testar com `curl` sem configurar nada.

**`ingestao/__main__.py` — o consumidor MQTT.** É a porta de campo, e roda como um programa
próprio, não dentro do servidor web. Ele:

1. conecta no broker MQTT e assina `meliponet/v1/+/telemetry`;
2. para cada mensagem, valida contra o contrato;
3. resolve a colmeia e grava;
4. mensagem inválida vira uma linha em `ingest_rejects` **com o motivo**.

A separação é deliberada. Se fossem o mesmo processo, reiniciar o site para publicar
uma correção derrubaria a recepção junto, e cada segundo fora do ar viraria uma lacuna
permanente. Separados, o broker guarda as mensagens (QoS 1 + sessão persistente) e
entrega quando o ingestor volta.

E note o passo 4: **recusa nunca é silenciosa**. O Edital 17 se compromete a reportar a
proporção de leituras descartadas, o que só é possível se o descarte for registrado.

## Rodando

```bash
cd platform
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
export DATABASE_URL="sqlite:///$PWD/../meliponet-dev.sqlite3"

.venv/bin/python -m alembic upgrade head
.venv/bin/python -m flask --app "meliponet:criar_app" criar-usuario \
  --email voce@exemplo.br --nome "Seu Nome" --organizacao "Teste" --perfil admin

cd .. && platform/.venv/bin/python -m simulator --transporte direto --historico 48 \
  --organizacao "Teste"

cd platform && .venv/bin/python -m flask --app "meliponet:criar_app" run
```

Em desenvolvimento roda SQLite (um arquivo, zero infraestrutura); em produção,
PostgreSQL + TimescaleDB. O código é o mesmo — o Timescale acrescenta desempenho de
série temporal, não muda a semântica.

→ Próximo: [O nó sensor](04-o-no-sensor.md)
