# A mensagem de telemetria do MelipoNet

Este diretorio e o acordo entre o **no sensor** (que o aluno programa, seguindo
`../firmware/ROTEIRO.md`) e a **plataforma** (`../platform/`, que recebe e guarda). O
simulador (`../simulator/`) produz mensagens iguais as do no, para que a plataforma possa
ser desenvolvida antes de existir hardware.

| Arquivo | Papel |
|---|---|
| `telemetry.v1.schema.json` | O contrato propriamente dito. E o que o ingestor valida. |
| `mensagem.py` | Monta a mensagem em Python. Usado pelo simulador e pelos testes. |
| `exemplos/*.json` | Mensagens validas, para copiar e para testar com `curl`. |
| `exemplos/invalidas/*` | Mensagens recusadas, cada uma com o `.motivo` ao lado. |

## Para onde a mensagem vai

Por HTTP, que e o caminho do roteiro:

```
POST http://<servidor>:5000/api/v1/telemetria
Content-Type: application/json
```

Por MQTT, que e o caminho de campo (etapa final do roteiro):

```
meliponet/v1/<node_id>/telemetry     telemetria, QoS 1
```

Os dois entregam ao mesmo ingestor. Do ponto de vista da plataforma, nada muda.

## Os campos

| Campo | Tipo | Obrigatorio | O que e |
|---|---|---|---|
| `schema` | texto | sim | Sempre `"meliponet.telemetry.v1"`. |
| `node_id` | texto | sim | 8 digitos hexadecimais **maiusculos**: os 4 ultimos bytes do MAC. |
| `seq` | inteiro | sim | Contador do no, que sobrevive ao reinicio. Lacuna nele = mensagem perdida. |
| `ts` | texto | sim | Instante da medicao, em UTC, terminando em `Z`. |
| `temp_in_c` | numero | — | Temperatura interna, em °C. |
| `temp_out_c` | numero | — | Temperatura externa, em °C. |
| `rh_in_pct` | numero | — | Umidade interna, em %. |
| `rh_out_pct` | numero | — | Umidade externa, em %. |
| `weight_kg` | numero | — | Peso da colmeia, em kg, ja com tara e calibracao. |
| `vbat_v` | numero | — | Tensao da alimentacao, em V. |
| `rssi` | inteiro | — | Sinal do WiFi, em dBm (negativo). |
| `flags` | lista | — | O que o no detectou de errado: veja abaixo. |

Toda mensagem precisa de **pelo menos uma** grandeza da colmeia (temperatura, umidade ou
peso). Uma mensagem so com `vbat_v` e recusada: ela nao mede a colmeia.

Flags possiveis: `sht_in_fault`, `sht_out_fault`, `hx711_fault`, `low_batt`,
`clock_unsynced`, `spooled`.

## As tres regras

1. **Campo ausente e omitido**, nunca enviado como `null` nem como `0`. E assim que "o
   sensor falhou" se distingue de "o sensor leu zero" — e a diferenca entre uma lacuna
   honesta na serie e um dado inventado.
2. **`ts` em UTC, com o `Z` no fim.** Sem fuso a mensagem e recusada: meses depois,
   ninguem sabera de que fuso era o relogio daquele no.
3. **`seq` nao pode repetir nem voltar.** A plataforma usa o par (`node_id`, `seq`) para
   reconhecer reenvio; um contador que reinicia do zero faz a plataforma descartar
   leituras novas achando que ja as tinha.

## Um exemplo, e como testa-lo

```bash
curl -i -X POST http://127.0.0.1:5000/api/v1/telemetria \
  -H 'Content-Type: application/json' \
  --data @contracts/exemplos/02-completa.json
```

Resposta esperada: `201`. Trocando pelo arquivo de `exemplos/invalidas/`, a resposta e
`400` com o motivo — o mesmo motivo que a plataforma guarda na tabela `ingest_rejects`,
porque mensagem recusada nunca some em silencio.

## Mudando o contrato

Campo novo entra como **opcional**, e o schema e os exemplos mudam juntos. Alteracao que
quebre nos ja em campo exige uma `v2`, e ai o ingestor precisa aceitar as duas versoes
durante a transicao — ninguem reprograma todas as placas no mesmo dia.
