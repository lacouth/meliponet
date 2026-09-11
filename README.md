# MelipoNet

Monitoramento remoto de colmeias de abelhas nativas sem ferrão (Meliponini) na Paraíba.

O projeto tem duas metades. A **plataforma web** já funciona: recebe telemetria, guarda,
mostra o gráfico, controla quem vê o quê. O **nó sensor** é o exercício: quem chega ao
projeto escreve o firmware do zero, seguindo um roteiro de etapas verificáveis, e usa a
plataforma como corretor — enquanto a mensagem não estiver certa, o ponto não aparece na
tela.

## Estrutura

```
contracts/   a mensagem: schema, exemplos e a montagem em Python
firmware/    ROTEIRO.md — o que o nó precisa fazer. O código é do aluno.
platform/    Flask + SQLite/TimescaleDB — ingestão, painel, cadastros, perfis
simulator/   gerador de dados sintéticos, para desenvolver sem hardware
docs/        a trilha, o guia e o registro de defeitos conhecidos
deploy/      docker compose, Mosquitto, Caddy — operação, fora da trilha
```

## Para quem está começando

Comece pela **[trilha](docs/trilha.md)**: nove exercícios curtos e o
**[roteiro do nó sensor](firmware/ROTEIRO.md)**, cada um com critério de pronto que você
confere sozinho — a saída de um comando, um teste que precisa falhar antes e passar
depois, ou uma resposta dobrável para comparar.

O **[guia](docs/guia/README.md)** é a leitura de apoio: o sistema, a mensagem, a
plataforma por dentro, o nó sensor e as práticas de engenharia de software que o projeto
usa e por quê.

Antes de depurar qualquer comportamento estranho, confira
**[docs/defeitos-conhecidos.md](docs/defeitos-conhecidos.md)**: é o registro dos defeitos
que a equipe já conhece e ainda não corrigiu, com o sintoma de cada um. Vários deles se
manifestam de forma que parece outra coisa.

## Como rodar

Precisa de git e Python 3.11+. Roda contra SQLite, sem infraestrutura nenhuma:

```bash
cd platform
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
export DATABASE_URL="sqlite:///$PWD/../meliponet-dev.sqlite3"

# esquema do banco
.venv/bin/python -m alembic upgrade head

# primeiro usuário (a interface exige login, e criar conta exige estar logado —
# a conta inicial só pode nascer do terminal do servidor)
.venv/bin/python -m flask --app "meliponet:create_app" criar-usuario \
  --email voce@exemplo.br --nome "Seu Nome" --organizacao "Seu Meliponário" --perfil admin

# 48 h de histórico sintético, com lacunas e falhas de sensor injetadas
cd .. && platform/.venv/bin/python -m simulator --transporte direto --historico 48 \
  --organizacao "Seu Meliponário"

# servidor em http://127.0.0.1:5000
cd platform && .venv/bin/python -m flask --app "meliponet:create_app" run
```

Para ver o painel se atualizando sozinho, deixe o simulador emitindo em paralelo:

```bash
platform/.venv/bin/python -m simulator --transporte direto --historico 0 --tempo-real
```

## Como um nó entrega a leitura

Pelo caminho curto, HTTP — o do roteiro:

```bash
curl -i -X POST http://127.0.0.1:5000/api/v1/telemetria \
  -H 'Content-Type: application/json' \
  --data @contracts/exemplos/02-completa.json
```

`201` gravou, `200` já tinha essa `seq`, `400` traz o motivo em português. Pelo caminho de
campo, MQTT, o nó publica em `meliponet/v1/<node_id>/telemetry` com QoS 1, e o ingestor
(um processo separado do servidor web) grava. Os dois caminhos passam pelo mesmo código de
validação e persistência.

O formato da mensagem está em [`contracts/README.md`](contracts/README.md), com exemplos
prontos em `contracts/exemplos/`.

## Testes

```bash
./verificar          # ruff e pytest — as mesmas verificações do CI
```

## Perfis de acesso

| Perfil | Vê | Edita cadastros |
|---|---|---|
| `meliponicultor` | apenas a própria organização | sim |
| `pesquisador` | todas as organizações | não |
| `admin` | todas as organizações | sim |

O isolamento vive num helper único, `meliponet/services/scope.py`. A razão é o modo de
falha: uma consulta que esquece o filtro não quebra nem levanta erro — ela apenas mostra a
um meliponicultor as colmeias de outro.

## Pilha completa

```bash
cp deploy/.env.example deploy/.env   # preencha as senhas
docker compose -f deploy/docker-compose.yml up -d
```

Sobe TimescaleDB, Mosquitto, o ingestor, o Flask sob gunicorn e o Caddy. Não é necessário
para nada da trilha.

## Licença e contexto

Projeto do **GTEMA/IFPB** — Campus João Pessoa, em parceria com o **LAHMP/UFPB**
(FAPESQ nº 72/2025). As propostas submetidas aos editais ficam em `propostas/`, fora do
controle de versão.

O firmware C++ preservado na tag `firmware-referencia-v1`.
