# 7. Glossário

## Do projeto

**Contrato** — a especificação do formato das mensagens de telemetria, em `contracts/`.
A fonte da verdade compartilhada entre firmware e plataforma.

**Vetor dourado** *(golden vector)* — par entrada→saída conhecidamente correto,
congelado num arquivo, contra o qual as duas implementações se verificam. Ver
[O contrato](02-o-contrato.md).

**Inteiro escalado** — a forma como as métricas trafegam: temperatura em centésimos de
grau, peso em gramas. Evita que o arredondamento de `float` difira entre ESP32 e PC.

**`seq`** — contador monotônico por nó, guardado na NVS. Permite detectar quantas
mensagens se perderam contando os saltos.

**Spool** — buffer local onde o nó guarda mensagens enquanto a rede está fora, drenado
ao reconectar.

**Lacuna** *(gap)* — mensagem que nunca chegou. Aparece como salto na `seq` e como
buraco no gráfico.

**Completude** — proporção de mensagens recebidas sobre as esperadas. Um dos indicadores
que o Edital 17 se compromete a reportar.

**Diferencial térmico** — temperatura interna menos externa. Estimativa do esforço
termorregulatório da colônia.

**Nó** *(node)* — um dispositivo MelipoSense instalado numa colmeia.

**Vínculo** (`NodeAssignment`) — o período em que um nó esteve numa colmeia, com
`installed_at` e `removed_at`. A colmeia de uma medição é resolvida pelo instante da
medição, não pelo estado atual.

**Ingestor** — o processo que consome do broker MQTT, valida e grava no banco. Separado
do servidor web.

**Simulador** — gerador de dados sintéticos que emite o mesmo formato que o firmware.
Desacopla o desenvolvimento da plataforma da entrega do hardware.

## Software

**API** — a interface pela qual um programa é usado por outro.

**Blueprint** — no Flask, um grupo de rotas relacionadas. Ex.: `dashboard.py`.

**Branch** — linha de trabalho paralela no git.

**CI** *(integração contínua)* — as verificações automáticas a cada push.

**Commit** — um registro de mudança no histórico do git.

**Endpoint** — uma URL que o servidor atende.

**Idempotente** — operação que, repetida, tem o mesmo efeito de uma vez só. Nosso
armazenamento de medições é idempotente: reenviar a mesma `seq` não duplica a linha.

**Lazy loading** — o ORM só busca uma relação no banco quando ela é usada. Causa o
`DetachedInstanceError` quando o uso acontece depois de a sessão fechar.

**Migração** — script que transforma a estrutura do banco de uma versão para outra
preservando os dados.

**Mock / stub** — objeto falso que substitui uma dependência real num teste.

**ORM** — biblioteca que mapeia tabelas do banco para classes da linguagem. Usamos
SQLAlchemy.

**Pull request (PR)** — pedido para juntar uma branch à `main`, revisado antes.

**Refatorar** — mudar a estrutura do código sem mudar o comportamento.

**Regressão** — algo que funcionava e parou de funcionar.

**Rota** — a ligação entre uma URL e a função que a atende.

**Template** — HTML com buracos preenchidos pelo Python. Usamos Jinja.

**Traceback** — o rastro de chamadas que Python imprime num erro. Leia de baixo para
cima.

**View** — a função que atende uma rota.

## Protocolos e infraestrutura

**Broker** — o servidor MQTT (Mosquitto) por onde passam as mensagens.

**Docker / Compose** — forma de empacotar e subir os serviços (banco, broker, web,
ingestor) de modo idêntico em qualquer máquina.

**HTMX** — biblioteca que permite atualizar um pedaço da página sem escrever JavaScript.

**MQTT** — protocolo leve de mensageria, publish/subscribe. Padrão em IoT porque tolera
conectividade intermitente.

**NTP** — protocolo de sincronização de relógio pela rede.

**NVS** — memória não-volátil do ESP32, onde ficam credenciais, calibração e `seq`.

**QoS 1** — nível de garantia do MQTT: a mensagem chega **ao menos uma vez**. Pode
chegar duplicada — por isso a gravação é idempotente.

**Retenção / downsampling** — descartar ou agregar dados antigos para o banco não
crescer sem limite.

**TimescaleDB** — extensão do PostgreSQL para séries temporais.

**Tópico** *(topic)* — o "endereço" de uma mensagem MQTT. O nosso:
`meliponet/v1/<node_id>/telemetry`.

**UTC** — fuso de referência. Tudo é gravado em UTC; a conversão para o horário da
Paraíba acontece só na exibição.

## Hardware

**ESP32-C6** — o microcontrolador do nó.

**HX711** — conversor analógico-digital para célula de carga.

**I²C** — barramento serial de dois fios. Os dois SHT30 compartilham um, distinguidos
pelos endereços 0x44 e 0x45.

**INMP441** — microfone MEMS digital (Fase 5).

**LoRa** — modulação de rádio de longo alcance e baixo consumo (Fase 5).

**PlatformIO** — a ferramenta de build do firmware.

**SHT30** — sensor de temperatura e umidade.

**Deep sleep** — modo de baixíssimo consumo do ESP32 (Fase 5).
