# 3. A plataforma Flask

Para quem vai mexer em `platform/`.

## O que é Flask

Flask é uma biblioteca Python para escrever servidores web. O modelo mental básico:

```
navegador pede uma URL  →  Flask acha a função responsável  →  a função devolve HTML
```

Cada função dessas se chama **view**, e a ligação entre URL e função é uma **rota**:

```python
@bp.route("/colmeia/<int:hive_id>")     # a rota
@login_required                          # só entra quem está autenticado
def hive_detail(hive_id: int):           # a view
    ...
    return render_template("hive.html", **context)
```

Abrir `http://servidor/colmeia/7` chama `hive_detail(hive_id=7)`.

## A estrutura de pastas

```
platform/
├── pyproject.toml              o que o projeto precisa para rodar
├── alembic.ini                 configuração das migrações
│
├── meliponet/                  ← O CÓDIGO
│   ├── __init__.py             create_app(): monta a aplicação
│   ├── config.py               lê as variáveis de ambiente
│   ├── db.py                   conexão com o banco
│   ├── models.py               as tabelas, como classes Python
│   ├── cli.py                  comandos de terminal (criar-usuario)
│   │
│   ├── blueprints/             ← AS ROTAS (o que o navegador acessa)
│   │   ├── auth.py                login e logout
│   │   ├── dashboard.py           a tela das colmeias e os gráficos
│   │   └── manage.py              cadastros e vínculo nó↔colmeia
│   │
│   ├── services/               ← A LÓGICA (sem saber que existe web)
│   │   ├── scope.py               quem pode ver o quê
│   │   └── series.py              as consultas que alimentam os gráficos
│   │
│   ├── ingest/                 ← A ENTRADA DE DADOS (processo separado)
│   │   ├── telemetry.py           valida a mensagem contra o contrato
│   │   ├── store.py               grava no banco
│   │   └── __main__.py            o consumidor MQTT
│   │
│   └── templates/              ← O HTML
│       ├── base.html              o esqueleto comum
│       ├── index.html             a lista de colmeias
│       ├── hive.html              a página de uma colmeia
│       └── _panel.html            o pedaço que se atualiza sozinho
│
├── migrations/                 ← AS MUDANÇAS DE ESTRUTURA DO BANCO
└── tests/                      ← OS TESTES
```

## As camadas, e por que existem

Se você vem de microcontrolador, seu modelo mental provável é um `main.c` que faz tudo.
Aqui a coisa é dividida em camadas, e vale entender a razão — não é organização por
organização.

```
blueprints/   fala HTTP: recebe requisição, devolve HTML
     ↓
services/     lógica de negócio: não sabe o que é uma requisição
     ↓
models.py     as tabelas
     ↓
banco
```

**A regra: uma camada só chama a de baixo.** `services/` nunca importa `blueprints/`.

O motivo prático fica claro num exemplo. `services/series.py` calcula a série de uma
colmeia. Como ele não sabe o que é HTTP, ele pode ser chamado:

- pela página web,
- pelo gerador de relatórios em PDF,
- por um script de exportação,
- por um teste, sem subir servidor nenhum.

Se a lógica estivesse dentro da view, cada um desses casos precisaria simular uma
requisição HTTP para calcular uma média. É por isso que os testes em `test_series.py`
rodam em milissegundos, sem servidor.

## `models.py` — as tabelas como classes

Em vez de escrever SQL, descrevemos as tabelas como classes Python. A biblioteca que faz
essa tradução (SQLAlchemy) chama-se **ORM**.

```python
class Hive(Base):
    __tablename__ = "hives"

    id: Mapped[int] = mapped_column(primary_key=True)
    apiary_id: Mapped[int] = mapped_column(ForeignKey("apiaries.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    species: Mapped[str | None] = mapped_column(String(120))
```

E as consultas viram Python:

```python
hive = session.scalar(select(Hive).where(Hive.id == 7))
print(hive.name)
```

### Duas decisões do nosso modelo que você precisa entender

**Métricas são anuláveis (`float | None`).** Já explicado no contrato: sensor que falhou
não produz zero, produz nada.

**O vínculo nó↔colmeia é histórico, não um campo.** Este é o ponto mais sutil do
modelo. Um nó é remanejado entre colmeias em campo: sai de uma caixa que colapsou, entra
em outra. Se o vínculo fosse uma coluna em `nodes`, remanejar **reescreveria o passado**
— toda a série histórica da colmeia antiga passaria a ser atribuída à nova.

Por isso existe `NodeAssignment`, com `installed_at` e `removed_at`. A colmeia de uma
medição é resolvida pelo **instante da medição**:

```python
def resolve_hive(session, node, when):
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
# depois de mudar models.py, gere a migração
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
{% for row in overview %}
  <tr>
    <td>{{ row.hive.name }}</td>
    <td>{{ row.latest.temp_in_c | num(1, ' °C') }}</td>
  </tr>
{% endfor %}
```

- `{{ ... }}` insere um valor
- `{% ... %}` é lógica (`if`, `for`)
- `| num(1, ' °C')` é um **filtro**: formata o valor

`base.html` é o esqueleto (cabeçalho, CSS, navegação) e as outras páginas o estendem com
`{% extends "base.html" %}`.

### Uma armadilha que já nos pegou

Este erro vai aparecer para você mais cedo ou mais tarde:

```
DetachedInstanceError: Parent instance <Hive> is not bound to a Session
```

O que acontece: o ORM carrega objetos **preguiçosamente**. `hive.apiary` só vai ao banco
no momento em que você usa. Se isso acontece no template, a sessão do banco já fechou, e
não há como buscar.

A correção é pedir a relação junto na consulta:

```python
hive = session.scalar(
    select(Hive).options(joinedload(Hive.apiary)).where(Hive.id == hive_id)
)
```

**Regra:** toda relação que a view entrega ao template precisa vir carregada da consulta.

## `services/scope.py` — quem vê o quê

Três perfis: `meliponicultor` vê só a própria organização, `pesquisador` vê tudo mas não
edita, `admin` vê tudo e edita.

A regra vive num arquivo só. O motivo é o modo de falha: **uma consulta que esquece o
filtro não quebra**. Não levanta erro, não aparece em teste de rota que só cheque o
status HTTP. Ela apenas mostra a um meliponicultor as colmeias de outro. Concentrando a
regra num lugar, esquecer fica difícil.

```python
# ✅ certo
hives = session.scalars(scope.hives_for(current_user))

# ❌ errado — vê tudo, sem reclamar
hives = session.scalars(select(Hive))
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
só protege quem a chama**. Hoje as duas rotas usam `can_manage_node`, e o nó recebe a
organização da colmeia.

E há uma segunda lição, sobre teste: nenhum teste exercitava o perfil `admin` — as
fixtures nasciam meliponicultor. Um conjunto de testes que nunca constrói um dos casos
não cobre aquele caso, por mais linhas que tenha.

## `ingest/` — por que é um processo separado

`ingest/__main__.py` roda como um programa próprio, não dentro do servidor web. Ele:

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
.venv/bin/python -m flask --app "meliponet:create_app" criar-usuario \
  --email voce@exemplo.br --nome "Seu Nome" --organizacao "Teste" --perfil admin

cd .. && platform/.venv/bin/python -m simulator --transporte direto --historico 48 \
  --organizacao "Teste"

cd platform && .venv/bin/python -m flask --app "meliponet:create_app" run
```

Em desenvolvimento roda SQLite (um arquivo, zero infraestrutura); em produção,
PostgreSQL + TimescaleDB. O código é o mesmo — o Timescale acrescenta desempenho de
série temporal, não muda a semântica.

→ Próximo: [Primeira contribuição](06-primeira-contribuicao.md)
