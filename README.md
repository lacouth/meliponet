# MelipoNet

Monitoramento remoto de colmeias de abelhas nativas sem ferrão (Meliponini) na Paraíba.

O repositório implementa três propostas submetidas a editais do IFPB, que descrevem
fatias complementares de um mesmo sistema. Os PDFs das propostas não são versionados —
ficam em `propostas/`, na máquina de quem trabalha no projeto.

| Proposta | Edital | Fatia neste repositório |
|---|---|---|
| **MelipoSense** | 12/2026 PIBITI | `firmware/`, `gateway/` — nó sensor e telemetria |
| **MelipoNet** | 11/2026 PIBIC | `platform/`, `simulator/` — plataforma web |
| **Coleta de Dados** | 17/2026 FAPESQ | `curation/`, `docs/` — protocolo, qualidade e curadoria |

Costurando as três: `contracts/`, o contrato de telemetria que hardware e software
acordam antes de escrever código — pré-requisito explícito nas metas M1/M2 dos três
editais.

## Estado atual

**Fases 0, 1 e 2 concluídas.**

A **Fase 0** fechou o contrato, verificado nos dois lados: o codec C++ e o ingestor
Python são implementações independentes checadas contra os mesmos vetores dourados.

A **Fase 1** entregou a fatia vertical — simulador → broker → ingestor → banco →
dashboard com gráfico ao vivo —, provando a arquitetura inteira sem hardware ligado.

A **Fase 2** trouxe autenticação, os três perfis, o isolamento por organização e o
vínculo histórico nó↔colmeia, com migrações Alembic.

Próximo passo: Fase 3, o firmware do protótipo (SHT30 + HX711 + WiFi/MQTT).

## Recorte do primeiro protótipo

Temperatura, umidade e peso, publicados **direto do ESP32-C6 para o broker MQTT via
WiFi**. Sem LoRa, sem gateway, sem bioacústica e sem subsistema solar — tudo isso entra
na Fase 5, reaproveitando o mesmo contrato. O caminho até um nó real gravando no banco
fica curto, e sensores, calibração e plataforma são validados antes de entrar a
complexidade de rádio e energia.

## Estrutura

```
contracts/   contrato de telemetria: schema, regras canônicas, vetores dourados
firmware/    C++ / PlatformIO — ESP32-C6, SHT30 ×2, HX711, WiFi + MQTT
platform/    Flask + TimescaleDB — autenticação, ingestão, dashboard, cadastros
simulator/   gerador de dados sintéticos conforme o contrato
curation/    qualidade e curadoria das séries (Edital 17)
gateway/     (Fase 5) bridge LoRa → MQTT no Raspberry Pi 5
deploy/      docker compose, Mosquitto, Caddy
docs/        arquitetura, protocolo de instrumentação, ADRs
```

## Como rodar

### Local, sem infraestrutura

Roda contra SQLite e entrega telemetria direto ao pipeline de ingestão, sem broker.
É o caminho mais curto para ver a plataforma funcionando:

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

O modo `--transporte direto` exercita o mesmo código de validação e persistência que o
MQTT, menos o transporte. O que ele **não** cobre é a reentrega do broker e o
comportamento sob reconexão — para isso, use a pilha completa abaixo.

### Testes

```bash
cd platform && .venv/bin/pytest
```

Firmware (testes no PC, sem hardware):

```bash
pip install platformio
pio test -e native -d firmware
```

Pilha completa:

```bash
cp deploy/.env.example deploy/.env   # preencha as senhas
docker compose -f deploy/docker-compose.yml up -d
```

## Perfis de acesso

| Perfil | Vê | Edita cadastros |
|---|---|---|
| `meliponicultor` | apenas a própria organização | sim |
| `pesquisador` | todas as organizações | não |
| `admin` | todas as organizações | sim |

O isolamento vive num helper único, `meliponet/services/scope.py`. A razão é o modo de
falha: uma consulta que esquece o filtro não quebra nem levanta erro — ela apenas
mostra a um meliponicultor as colmeias de outro.

## Para quem vai contribuir

Comece por **[`docs/guia/`](docs/guia/README.md)** — um guia de onboarding escrito para
estudantes de Engenharia Elétrica que vão trabalhar no projeto: o contrato, a estrutura
da plataforma Flask, a do firmware, e as práticas de engenharia de software (git,
ambientes, testes, revisão) que o projeto usa e por quê.

## Contrato

Antes de mexer em firmware ou em ingestão, leia `contracts/README.md`. A regra que
governa o resto: **toda métrica trafega como inteiro escalado**, e a igualdade byte a
byte entre C++ e Python é verificada no CI.

## Licença e contexto

Projeto do IFPB — Campus João Pessoa, em parceria com o LAHMP/UFPB (FAPESQ nº 72/2025).
