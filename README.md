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

**Fases 0 e 1 concluídas.**

A Fase 0 fechou o contrato, verificado nos dois lados: o codec C++ e o ingestor Python
são implementações independentes checadas contra os mesmos vetores dourados.

A Fase 1 entregou a fatia vertical — simulador → broker → ingestor → banco → dashboard
com gráfico ao vivo —, provando a arquitetura inteira sem nenhum hardware ligado.

Próximo passo: Fase 2 (organizações, usuários e perfis) e Fase 3 (firmware do
protótipo).

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
platform/    Flask + TimescaleDB — ingestão, dashboard, alertas, relatórios
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

# 48 h de histórico sintético, com lacunas e falhas de sensor injetadas
cd .. && platform/.venv/bin/python -m simulator --transporte direto --historico 48

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

## Contrato

Antes de mexer em firmware ou em ingestão, leia `contracts/README.md`. A regra que
governa o resto: **toda métrica trafega como inteiro escalado**, e a igualdade byte a
byte entre C++ e Python é verificada no CI.

## Licença e contexto

Projeto do IFPB — Campus João Pessoa, em parceria com o LAHMP/UFPB (FAPESQ nº 72/2025).
