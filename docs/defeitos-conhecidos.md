# Defeitos conhecidos

Registro dos defeitos que a equipe **já conhece e ainda não corrigiu**. Existe porque a
alternativa é pior: um defeito conhecido que só vive na memória de quem o encontrou
reaparece meses depois como se fosse novo, e quem o reencontra gasta o mesmo dia de
depuração de novo. Pior ainda quando a documentação descreve o comportamento pretendido
e o código faz outra coisa — aí o defeito não é só um bug, é uma armadilha.

Um item aqui não é vergonha nem pendência atrasada. É uma decisão consciente de não
corrigir agora, escrita para que a próxima pessoa não tropece.

## Como usar

- **Ao encontrar um defeito que você não vai corrigir agora**, acrescente uma entrada.
  Custa três minutos e vale um dia de trabalho de outra pessoa.
- **Toda entrada diz como o defeito aparece no mundo**, não só o que está errado no
  código. "Buffer pequeno" não ajuda ninguém; "o nó para de publicar e nada no serial
  explica" ajuda.
- **Ao corrigir**, remova a entrada da tabela de abertos **no mesmo commit da correção**
  e acrescente uma linha em [Resolvidos](#resolvidos). Uma lista que não encolhe deixa
  de ser lida.
- **Ao corrigir, escreva o teste que pega o defeito** e rode-o antes da correção, para
  ver falhar. Vários itens aqui só são detectáveis em campo hoje — mudar isso é parte da
  correção.
- Os identificadores (`D-01`, …) são estáveis: nunca reaproveite o número de um item
  removido, para que uma referência antiga num commit ou numa conversa continue fazendo
  sentido.

## Abertos

| # | Gravidade | Onde | Defeito |
|---|---|---|---|
| [D-01](#d-01) | alta | firmware | A telemetria é publicada em QoS 0, não em QoS 1 |
| [D-02](#d-02) | alta | plataforma | Medições anteriores ao vínculo ficam órfãs para sempre |
| [D-03](#d-03) | média | firmware | O buffer do MQTT não tem folga para cabeçalho e tópico |
| [D-04](#d-04) | média | firmware | `tara` só passa a valer depois de reiniciar |
| [D-05](#d-05) | média | firmware | A presença dos sensores é decidida no boot e nunca revista |
| [D-06](#d-06) | média | plataforma | O Last Will é publicado e ninguém o assina |
| [D-07](#d-07) | baixa | plataforma | Os agregados contínuos são criados e nunca consultados |
| [D-08](#d-08) | baixa | firmware | `Flag::spooled` é código morto |
| [D-09](#d-09) | baixa | contrato | `canonical.py` aponta para um caminho que não existe mais |
| [D-10](#d-10) | baixa | firmware | `MELIPO_SAMPLE_INTERVAL_S` é um flag de compilação sem uso |

---

### D-01

**A telemetria é publicada em QoS 0, não em QoS 1.**

*Onde:* `firmware/lib/MelipoHardware/MqttPublisher.cpp`, `MqttPublisher::publish`.

*Sintoma:* enquanto o ingestor estiver fora do ar — um deploy da plataforma, um reinício
do contêiner —, as mensagens publicadas nesse intervalo se perdem. Aparecem como lacuna
na série, sem que nada acuse: o nó publicou, o broker aceitou, e ninguém guardou.

*Por que acontece:* a biblioteca `PubSubClient` só implementa QoS 0 na publicação. Como
o QoS efetivo de uma entrega é o menor entre o da publicação e o da assinatura, o
`clean_session=False` do ingestor e o `persistence true` do Mosquitto **não protegem
nada hoje**. O spool do nó cobre o trecho nó→broker; o trecho broker→ingestor está
descoberto.

*Agravante:* vários documentos afirmam QoS 1 — `contracts/README.md`, o cabeçalho de
`MqttPublisher.h`, o comentário do `deploy/mosquitto.conf`. Quem ler acredita estar
protegido.

*Como corrigir:* trocar a biblioteca. A `esp-mqtt`, do próprio ESP-IDF, publica em
QoS 1 e está disponível sob o Arduino core 3.x. Mexe na única parte do firmware que os
testes nativos não cobrem, então planeje a verificação em bancada: derrube o ingestor,
publique, suba o ingestor, confira se a mensagem chegou.

---

### D-02

**Medições anteriores ao vínculo ficam órfãs para sempre.**

*Onde:* `platform/meliponet/ingest/store.py`, `store()`.

*Sintoma:* liga-se o nó em campo antes de vinculá-lo a uma colmeia na interface. As
leituras desse período existem no banco, mas o gráfico da colmeia começa só a partir do
vínculo. Nada quebra, nada avisa; o gráfico só começa mais tarde do que se esperava.

*Por que acontece:* o `hive_id` é carimbado na linha da medição no instante da ingestão,
por `resolve_hive()`. Sem vínculo naquele instante, a coluna fica `NULL` — e vincular
depois não reprocessa o passado. A interface promete o contrário: o texto de "Nós
aguardando vínculo" diz que as leituras "passam a aparecer nos gráficos assim que o
vínculo existir", o que só vale para o que chegar depois.

*Contorno hoje:* vincule antes de deixar o nó publicando. Está documentado em
[docs/guia/08-do-no-ao-grafico.md](guia/08-do-no-ao-grafico.md).

*Como corrigir:* ao criar um `NodeAssignment`, reatribuir as medições daquele nó que
caem dentro do período e ainda estão com `hive_id IS NULL`. São poucas linhas em
`manage.assign_node`, e o teste é direto: ingerir duas medições, vincular, conferir que
as duas aparecem em `series()`. Corrigir o texto da interface faz parte da correção.

---

### D-03

**O buffer do MQTT não tem folga para o cabeçalho e o tópico.**

*Onde:* `firmware/lib/MelipoHardware/MqttPublisher.cpp`, `kBufferSize = 512`, contra
`kMaxTelemetryJson = 512` em `TelemetryCodec.h`.

*Sintoma:* uma mensagem que ocupe o tamanho máximo previsto pelo codec é recusada pelo
`PubSubClient` sem sair da placa. Ela vai para o spool, é drenada, é recusada de novo — e
**trava a cabeça da fila para sempre**, bloqueando todas as mensagens atrás dela. O nó
fica mudo com o spool cheio.

*Por que acontece:* o buffer do `PubSubClient` precisa acomodar o cabeçalho MQTT e o
tópico além do payload. O tópico `meliponet/v1/XXXXXXXX/telemetry` tem 30 bytes, e o
cabeçalho, uns 7 — o teto real do payload fica perto de 475 bytes, não 512.

*Por que ainda não mordeu:* a mensagem do protótipo tem cerca de 350 bytes. A margem
existe, mas some quando a Fase 5 acrescentar `sound_bands`.

*Como corrigir:* dimensionar `kBufferSize` como `kMaxTelemetryJson` mais a folga do
cabeçalho e do tópico, com um `static_assert` que quebre o build se as duas constantes
voltarem a se aproximar. E, independentemente disso, `drainSpool` deveria descartar (com
contador) uma mensagem recusada mais de N vezes, em vez de tentar a mesma para sempre.

---

### D-04

**`tara` só passa a valer depois de reiniciar.**

*Onde:* `firmware/src/main.cpp`, comando `tara` em `handleSerial()`.

*Sintoma:* quem tara a célula e mede em seguida vê o peso calculado com o zero **antigo**.
Reiniciar a placa resolve, e é fácil concluir que a tara "não pegou" e refazer o
procedimento várias vezes.

*Por que acontece:* o comando grava o novo `offset` em `g_config` e na NVS, mas não
chama `g_load_cell.setCalibration()`. O objeto da célula segue com a calibração que
recebeu no boot. O comando `calibrar` faz a chamada; o `tara` não.

*Como corrigir:* uma linha — `g_load_cell.setCalibration(g_config.calibration);` depois
de atualizar o offset, como o `calibrar` já faz.

---

### D-05

**A presença dos sensores é decidida no boot e nunca revista.**

*Onde:* `firmware/lib/MelipoHardware/ShtPair.cpp` (`begin()`) e `LoadCell`.

*Sintoma:* um sensor com mau contato no instante do boot fica marcado como ausente até
alguém reiniciar a placa, mesmo que o contato volte um minuto depois. As leituras dele
saem omitidas com a flag de falha por dias, e o `estado` continua dizendo `ausente` com
o sensor funcionando. O inverso também vale: um sensor que se solta depois do boot
continua marcado como presente.

*Contorno hoje:* o comando serial `sondar` refaz a detecção sem reiniciar. Resolve na
bancada, onde alguém está na frente da placa; não resolve em campo, que é onde o defeito
importa.

*Como corrigir:* tentar reconectar periodicamente — a cada N amostras, ou sempre que uma
leitura falhar —, em vez de confiar num teste feito uma vez. A lógica de quando
re-sondar é pura e cabe em `MelipoCore`, com teste nativo.

---

### D-06

**O Last Will é publicado e ninguém o assina.**

*Onde:* o nó publica em `meliponet/v1/<node_id>/status`
(`firmware/lib/MelipoHardware/MqttPublisher.cpp`); nada em
`platform/meliponet/ingest/` assina esse tópico.

*Sintoma:* um nó que morre em campo não gera aviso nenhum. "O nó parou de enviar" segue
indistinguível de "ainda não chegou a hora de enviar", que é exatamente o problema que o
Last Will existe para resolver.

*Como corrigir:* assinar `meliponet/v1/+/status` no ingestor e registrar a transição em
`nodes`. O alerta de nó mudo em si é da Fase 4, mas guardar a transição pode ser feito
antes e barato.

---

### D-07

**Os agregados contínuos são criados e nunca consultados.**

*Onde:* `platform/meliponet/db.py` cria `measurements_1h` e `measurements_1d`;
`platform/meliponet/services/series.py` sempre lê a tabela bruta e reamostra em Python.

*Sintoma:* nenhum hoje — funciona e responde rápido com meses de dados de poucas
colmeias. Vira problema com dezenas de nós e anos de série, e vira problema de uma vez,
não gradualmente.

*Como corrigir:* escolher a fonte pela janela — bruto para 24 h, `measurements_1h` para
7 e 30 dias. O contrato de `series()` não muda; os testes existentes de lacuna e de
reamostragem continuam valendo e são a rede de segurança da mudança.

---

### D-08

**`Flag::spooled` é código morto.**

*Onde:* `firmware/lib/MelipoCore/Sample.cpp` liga a flag quando
`SampleContext::from_spool` é verdadeiro, mas `firmware/src/main.cpp` nunca define esse
campo.

*Sintoma:* nenhuma mensagem reenviada do spool chega marcada como tal. Perde-se a
distinção entre "medição que chegou na hora" e "medição represada por horas", que é
justamente um dos indicadores de qualidade que o Edital 17 promete reportar.

*Por que acontece:* o spool guarda a mensagem **já serializada**, então no momento do
reenvio não há mais um `SampleContext` para marcar. A flag teria de ser decidida na
montagem, quando ainda não se sabe se a mensagem vai ou não para o spool.

*Como corrigir:* decidir o que a flag significa antes de implementá-la. Uma saída é
marcar no reenvio, reescrevendo o campo `flags` da mensagem guardada — o que exige que o
spool saiba um pouco do formato. A outra é remover a flag e derivar o atraso na
plataforma, comparando `ts` com `received_at`, que já estão os dois no banco. **A segunda
é provavelmente a certa**, e aí a correção é apagar código.

---

### D-09

**`canonical.py` aponta para um caminho que não existe mais.**

*Onde:* `contracts/canonical.py`, no docstring do módulo: cita
`firmware/lib/MelipoNet/TelemetryCodec`. A pasta hoje é `firmware/lib/MelipoCore/`.

*Sintoma:* quem seguir a referência não encontra o arquivo. É o menor item desta lista,
e está aqui porque o `canonical.py` é a primeira coisa que alguém lê ao mexer no
contrato — mandar essa pessoa para um caminho inexistente na primeira página é um começo
ruim.

*Como corrigir:* trocar o caminho.

---

### D-10

**`MELIPO_SAMPLE_INTERVAL_S` é um flag de compilação sem uso.**

*Onde:* `firmware/platformio.ini`, `-DMELIPO_SAMPLE_INTERVAL_S=300`. Nenhum arquivo do
firmware o referencia.

*Sintoma:* quem quiser mudar o intervalo de amostragem provavelmente vai editar esse
flag, recompilar, gravar — e o nó continuará amostrando a cada 5 minutos, porque o valor
real vem da NVS (`interval_s`, lido em `Config.cpp`). Um flag que parece configurar algo
e não configura é pior do que nenhum.

*Como corrigir:* remover o flag. Se um padrão de compilação for desejável no futuro, ele
deve ser o valor usado pelo `loadConfig()` quando a chave da NVS está ausente, não uma
constante paralela.

---

## Resolvidos

| # | Defeito | Corrigido em |
|---|---|---|
| D-11 | O CI da plataforma quebrado desde a Fase 2: `pip install -e platform[dev]` falhava com "Multiple top-level packages discovered in a flat-layout", porque `pyproject.toml` não declarava o que empacotar e o Alembic trouxe `migrations/` para o lado de `meliponet/`. Passou despercebido por doze commits porque um ambiente virtual criado antes de `migrations/` existir continua funcionando — só instalação limpa falha | 2026-09-02 — `[tool.setuptools.packages.find]` em `platform/pyproject.toml` |
| D-00 | Sem comando serial para as credenciais do broker MQTT: um nó de campo não conseguia autenticar num broker com `allow_anonymous false`, e a única saída era liberar acesso anônimo no broker | 2026-09-02 — comandos `mqtt <usuario> <senha>` e `broker <host> [porta]` |
