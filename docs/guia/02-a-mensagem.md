# 2. A mensagem

Tudo neste projeto se encontra num ponto só: **a mensagem que o nó envia**. Ela é o
acordo entre quem escreve o firmware e quem escreve a plataforma — e é por existir esse
acordo que os dois lados podem ser escritos ao mesmo tempo, por pessoas diferentes, sem
que um fique esperando o outro.

O acordo está em [`contracts/`](../../contracts/README.md): o schema (`telemetry.v1.schema.json`)
diz o que é aceito, e `exemplos/` mostra mensagens prontas.

## Um exemplo

```json
{
  "schema": "meliponet.telemetry.v1",
  "node_id": "A4C1380F",
  "seq": 10432,
  "ts": "2027-03-14T12:10:00Z",
  "temp_in_c": 30.12,
  "temp_out_c": 34.8,
  "rh_in_pct": 68.4,
  "rh_out_pct": 41.2,
  "weight_kg": 12.483,
  "vbat_v": 3.92,
  "rssi": -58
}
```

Quatro campos são obrigatórios (`schema`, `node_id`, `seq`, `ts`) e é preciso haver **ao
menos uma** grandeza da colmeia — temperatura, umidade ou peso. Uma mensagem só com a
tensão da bateria é recusada: ela não mede a colmeia.

## As três regras, e por que elas existem

### Campo ausente é omitido, nunca zero

Se o SHT30 externo não respondeu, `temp_out_c` simplesmente não entra na mensagem, e o nó
acende a flag `sht_out_fault`.

A tentação é mandar `0`. Não faça: zero é uma temperatura possível. Quem for analisar a
série daqui a um ano não terá como distinguir "estava fazendo 0 °C" de "o sensor estava
quebrado" — e a média do mês sairá errada sem que nada acuse. Uma lacuna honesta é
informação; um zero inventado é dado corrompido.

### `ts` é o horário da medição, em UTC

O nó carimba o horário em que **mediu**, não em que conseguiu enviar. A diferença aparece
sempre que uma mensagem fica guardada durante uma queda de rede: ela chega horas depois, e
precisa pousar no gráfico na hora certa.

Sempre em UTC, com o `Z` no fim. Sem fuso a mensagem é recusada, porque meses depois
ninguém saberá de que fuso era o relógio daquele nó — e uma série com dois fusos
misturados não tem conserto.

### `seq` é do nó, e não pode voltar

A plataforma reconhece reenvio pelo par (`node_id`, `seq`). É isso que faz o nó poder
reenviar tudo o que guardou durante uma queda sem duplicar nada no banco.

A consequência para quem escreve o firmware: **`seq` precisa sobreviver ao reinício**. Um
contador que volta ao zero faz a plataforma descartar leituras novas achando que já as
tinha — e o sintoma é o pior possível, um gráfico que simplesmente para de crescer sem
nenhum erro em lugar nenhum.

## Onde a mensagem é conferida

Na fronteira, e só ali: `platform/meliponet/ingest/telemetry.py`. Tudo que chega vem de um
nó em campo e não é confiável — pode estar truncado por um buffer pequeno, vir de um
firmware antigo ou trazer um valor fisicamente impossível.

Uma mensagem recusada **nunca some em silêncio**: o motivo é guardado na tabela
`ingest_rejects`, junto com o pedaço do payload. Isso é o que permite descobrir, depois,
que o nó daquela colmeia estava mandando um JSON cortado ao meio — em vez de concluir que
"a colmeia parou de mandar dados".

Vale distinguir duas coisas que parecem a mesma:

- **Validação sintática** (o que o ingestor faz): a mensagem obedece ao contrato? Se não,
  é recusada com um motivo.
- **Validação semântica** (ainda por fazer): esta leitura faz sentido diante do histórico
  daquela colmeia? Uma leitura suspeita é gravada **com flag**, não recusada — quem
  descarta o que parece estranho perde justamente o evento raro.

## Mudando a mensagem

Campo novo entra como **opcional**, e o schema e os exemplos mudam juntos. Alteração que
quebre nós já instalados exige uma `v2`, e aí o ingestor precisa aceitar as duas versões
durante a transição: ninguém reprograma todas as placas no mesmo dia.

→ Próximo: [A plataforma](03-a-plataforma.md)
