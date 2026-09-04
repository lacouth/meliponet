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

A **Fase 3** entregou o firmware do protótipo: dois SHT30, célula de carga via HX711,
WiFi com NTP, MQTT com Last Will e spool em LittleFS. Toda a lógica que não depende de
sensor — escala, montagem da mensagem, calibração, agendamento, fila do spool — é
testada no PC, sem placa. **Falta a verificação em hardware real.**

Próximo passo: Fase 4 (dashboard completo, alertas, relatórios, INMET).

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
./verificar          # tudo: contrato, ruff, pytest e os testes nativos do firmware
```

Restringe com um argumento: `./verificar plataforma`, `firmware`, `contrato`, ou `alvo`
(compila para o ESP32-C6, sem precisar de placa). São as mesmas verificações do CI. Ou, só
a plataforma:

```bash
cd platform && .venv/bin/pytest
```

### Firmware

Testes no PC, sem hardware — cobrem o codec, a escala, a montagem da mensagem, a
calibração da célula, o agendamento e o spool:

```bash
uv tool install platformio      # ou: pipx install platformio
pio test -e native -d firmware
```

> `pip install platformio` falha em distribuições com PEP 668 (Arch, Debian 12+,
> Ubuntu 24.04+), que bloqueiam instalação no Python do sistema. `uv tool` e `pipx`
> instalam a ferramenta isolada, sem sudo. No Arch há também
> `sudo pacman -S platformio-core`.

Na placa:

```bash
pio run -e esp32c6 -d firmware -t upload -t monitor
```

Credenciais **não** vão no código: são gravadas na NVS pelo console serial. Para
verificar a eletrônica na bancada não é preciso nada disso — `ler` funciona sem WiFi,
sem broker e sem plataforma, e mostra cada grandeza em unidade física e no inteiro
escalado que iria para a mensagem.

```
wifi <ssid> <senha>     grava as credenciais de WiFi
broker <host> [porta]   grava o endereço do broker MQTT
mqtt <usuario> <senha>  grava as credenciais do broker (sem argumentos, apaga)
tara                    tara a célula com a colmeia vazia
calibrar <kg>           calibra com uma massa-padrão conhecida
ler [n]                 lê os sensores agora, sem rede e sem publicar
sondar                  redetecta os sensores, sem reiniciar
estado                  mostra sensores, conexões, calibração e spool
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

E faça a **[trilha de exercícios](docs/guia/11-trilha-de-exercicios.md)**: quinze
exercícios em `docs/exercicios/`, do ambiente montado ao primeiro pull request, cada um com
um critério de pronto que o próprio aluno confere — a saída de `./verificar`, um teste que
precisa falhar antes e passar depois, ou uma resposta dobrável para comparar. Foi escrita
para quem vai aprender sozinho, sem alguém do lado para corrigir.

Antes de depurar qualquer comportamento estranho, confira
**[`docs/defeitos-conhecidos.md`](docs/defeitos-conhecidos.md)**: é o registro dos
defeitos que a equipe já conhece e ainda não corrigiu, com o sintoma de cada um. Vários
deles se manifestam de forma que parece outra coisa.

## Contrato

Antes de mexer em firmware ou em ingestão, leia `contracts/README.md`. A regra que
governa o resto: **toda métrica trafega como inteiro escalado**, e a igualdade byte a
byte entre C++ e Python é verificada no CI.

## Licença e contexto

Projeto do IFPB — Campus João Pessoa, em parceria com o LAHMP/UFPB (FAPESQ nº 72/2025).
