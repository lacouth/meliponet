# 1. O sistema

## Três propostas, um sistema

O projeto nasceu de três propostas submetidas a editais diferentes. Elas parecem
projetos separados no papel, mas descrevem **fatias de uma coisa só**:

| Proposta | Edital | Fatia | Pasta |
|---|---|---|---|
| **MelipoSense** | PIBITI | o nó sensor: eletrônica, firmware, rádio, energia | `firmware/` |
| **MelipoNet** | PIBIC | a plataforma web: ingestão, banco, dashboard | `platform/` |
| **Coleta de Dados** | FAPESQ | protocolos, qualidade e curadoria das séries | `curation/`, `docs/` |

Isso importa para você por um motivo prático: **as três fatias se encontram num ponto
só**, o contrato de telemetria em `contracts/`. Se você entender esse ponto, entende
como o trabalho de um bolsista não atropela o do outro.

## O que o sistema faz

Uma colmeia de abelha sem ferrão é um sistema homeostático. A colônia mantém a região
de cria numa faixa térmica estreita — perto de 30 °C nas espécies com favos e invólucro
de cerume — e desvios sinalizam estresse, enfraquecimento ou eventos reprodutivos.

O problema é que ninguém consegue observar isso. O manejo tradicional é abrir a caixa
algumas vezes por ano, o que:

- **altera o que se quer medir** — abrir muda o microclima interno;
- **estressa a colônia**;
- **produz medições pontuais**, que não revelam dinâmica nenhuma.

Entre uma inspeção e outra, o meliponicultor não sabe nada. Enxameação, colapso e
infestação só são percebidos quando já são irreversíveis.

O sistema substitui isso por medição contínua e não invasiva: um nó sensor dentro da
caixa mede temperatura interna e externa, umidade e peso, e envia para uma plataforma
web que mostra, guarda e analisa.

## O caminho de um dado

Vale decorar este caminho. Quase toda pergunta sobre "onde eu mexo?" se responde
localizando o ponto certo nele.

```
1. SENSOR            SHT30 (I²C) e HX711 + célula de carga
                     ↓  o firmware lê e converte em inteiros escalados
2. FIRMWARE          ESP32-C6 monta a mensagem no formato do contrato
                     ↓  WiFi, MQTT, QoS 1
3. BROKER            Mosquitto — a "central telefônica" das mensagens
                     ↓
4. INGESTOR          valida contra o contrato, resolve a colmeia, grava
                     ↓
5. BANCO             PostgreSQL + TimescaleDB
                     ↓
6. PLATAFORMA WEB    Flask consulta e desenha os gráficos
                     ↓
7. MELIPONICULTOR    abre o navegador e vê a colmeia
```

Três observações sobre esse desenho que não são óbvias:

**O ingestor é um programa separado do servidor web.** Parecem a mesma coisa (os dois
são Python, os dois falam com o banco), mas rodam como processos independentes. Se
fossem um só, reiniciar o site para publicar uma correção derrubaria a recepção de
telemetria junto — e cada segundo fora do ar viraria uma lacuna permanente nas séries.

**O passo 2 vai mudar, e nada depois dele muda junto.** Hoje o ESP32 fala WiFi direto
com o broker. Na Fase 5 entra rádio LoRa e um gateway Raspberry Pi, porque meliponário
no semiárido não tem WiFi. Quando isso acontecer, o gateway vai publicar **no mesmo
tópico e no mesmo formato** — e os passos 3 a 7 não sabem da diferença. Essa é a
recompensa de ter um contrato.

**A rede vai cair.** Não "pode cair": vai. O meio rural tem conectividade intermitente,
e o sistema é projetado assumindo isso — o nó guarda as mensagens em memória (o
*spool*) e as reenvia quando a rede volta.

## O mapa do repositório

```
meliponet/
├── contracts/     O CONTRATO. Leia isto antes de mexer em firmware ou ingestão.
│                  Define o formato exato das mensagens e os vetores dourados que
│                  provam que C++ e Python concordam.
│
├── firmware/      C++ para o ESP32-C6, via PlatformIO.
│   ├── src/          o programa principal
│   ├── lib/          as bibliotecas do projeto (sensores, rede, codec)
│   └── test/native/  testes que rodam no PC, sem hardware
│
├── platform/      A plataforma web, em Python/Flask.
│   ├── meliponet/    o código
│   ├── migrations/   as mudanças de estrutura do banco
│   └── tests/        os testes
│
├── simulator/     Gera dados sintéticos como se fosse um nó real.
│                  É o que permite trabalhar na plataforma sem hardware nenhum.
│
├── curation/      Qualidade e curadoria das séries (Edital 17).
├── gateway/       (Fase 5) a ponte LoRa → MQTT no Raspberry Pi.
├── deploy/        Como o sistema sobe no servidor.
└── docs/          Documentação, incluindo este guia.
```

## Por que existe um simulador

Repare que `simulator/` não é um brinquedo nem um teste. É uma peça de projeto, prevista
na proposta do PIBIC.

O problema que ele resolve: a plataforma precisa de dados para ser desenvolvida, e os
dados vêm do hardware, que está sendo construído em paralelo. Sem simulador, a equipe
de software ficaria parada esperando a de hardware — e um atraso na entrega dos nós
viraria um atraso no projeto inteiro.

O simulador emite **exatamente** o mesmo JSON que o firmware emite, usando o mesmo
código canônico. Então tudo o que vem depois — validação, banco, gráficos, alertas —
é exercitado pelo caminho real. E ele injeta falhas de propósito (lacunas, deriva de
sensor, valores absurdos), porque a plataforma precisa ser desenvolvida contra dados
imperfeitos: em campo, os dados serão imperfeitos.

## As fases

| Fase | O que entrega | Situação |
|---|---|---|
| 0 | Contrato e fundação | ✅ pronta |
| 1 | Fatia vertical: simulador → banco → dashboard | ✅ pronta |
| 2 | Usuários, perfis, vínculo histórico nó↔colmeia | ✅ pronta |
| 3 | **Firmware do protótipo**: SHT30 + HX711 + WiFi/MQTT | ⬜ próxima |
| 4 | Dashboard completo, alertas, relatórios, INMET | ⬜ |
| 5 | Bioacústica, LoRa, gateway, energia solar, invólucro | ⬜ |
| 6 | Qualidade e curadoria das séries | ⬜ |

→ Próximo: [O contrato](02-o-contrato.md)
