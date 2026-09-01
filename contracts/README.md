# Contrato de telemetria MelipoNet

Este diretório é a **fonte da verdade** compartilhada entre o firmware C++
(`firmware/`), o simulador (`simulator/`), o ingestor da plataforma
(`platform/meliponet/ingest/`) e, a partir da Fase 5, o gateway LoRa (`gateway/`).

As três propostas do projeto listam o acordo do contrato de API como pré-requisito
(metas M1/M2 dos editais 11, 12 e 17/2026). Ele é o artefato que permite às equipes de
hardware e de software trabalharem em paralelo.

## Arquivos

| Arquivo | Papel |
|---|---|
| `telemetry.v1.schema.json` | JSON Schema da mensagem MQTT. O que o ingestor valida. |
| `canonical.py` | Regras de serialização canônica, em Python. |
| `tools/gen_testdata.py` | Gera os vetores dourados a partir dos casos declarados nele. |
| `testdata/telemetry_*.json` | Mensagens válidas na forma canônica. |
| `testdata/invalid/*` | Payloads que devem ser rejeitados, com o motivo esperado. |
| `testdata/vectors.h` | Os mesmos casos válidos como C++, para o teste nativo. |

## Tópico MQTT

```
meliponet/v1/<node_id>/telemetry     telemetria (QoS 1)
meliponet/v1/<node_id>/status        Last Will, para detecção de nó mudo
```

No protótipo (Fase 3) quem publica é o próprio ESP32-C6 por WiFi. Na Fase 5 quem
publica é o gateway Raspberry Pi, **no mesmo tópico e no mesmo formato** — do broker
para dentro, nada muda.

## A regra que governa tudo: métricas são inteiros escalados

Temperatura trafega em centésimos de grau, peso em gramas, umidade em centésimos de
ponto percentual. A serialização apenas insere a vírgula decimal no inteiro.

Isso não é preciosismo. A alternativa — cada lado formatar um `float` com `%.2f` — não
é reproduzível entre plataformas: a `printf` da newlib do ESP32 não arredonda igual à
glibc do PC, o ESP32 calcula em `float` de 32 bits onde o Python usa `double`, e
empates como 30.125 caem para lados diferentes. Com inteiros escalados o
arredondamento acontece **uma vez**, na camada de sensores, e vira parte da medição em
vez de um detalhe do encoder. É também exatamente o que o quadro binário LoRa da Fase 5
vai carregar, de modo que os dois transportes rendem valores idênticos.

A regra de arredondamento float → inteiro é `ROUND_HALF_UP` sobre o valor binário
exato (`canonical.quantize`).

## Demais regras canônicas

1. JSON compacto, sem espaços.
2. Ordem de chaves fixa e lógica (`canonical.FIELD_ORDER`), não alfabética.
3. Campo ausente é **omitido**, nunca emitido como `null` nem como zero — é assim que
   "sensor com falha" se distingue de "sensor leu zero".
4. Casas decimais fixas: 12,5 kg sai como `12.500`.
5. Flags em ordem canônica (`canonical.FLAG_ORDER`), independente da ordem de detecção.

## Como isso é garantido

Duas implementações independentes, em linguagens diferentes, verificadas contra os
mesmos arquivos:

```bash
pio test -e native -d firmware       # o codec C++ reproduz os vetores byte a byte
pytest platform/tests/test_contract.py   # o ingestor lê os mesmos vetores
python3 contracts/tools/gen_testdata.py --check   # os vetores estão atualizados
```

Enquanto os três passarem, firmware e plataforma não podem ter divergido. Sem isso, a
divergência só apareceria em campo, com o nó já instalado na colmeia.

## Alterando o contrato

1. Edite os casos em `tools/gen_testdata.py` e/ou o schema.
2. Rode `python3 contracts/tools/gen_testdata.py`.
3. Rode os testes dos dois lados.
4. **Campo novo entra como opcional.** Foi assim que o protótipo (sem bioacústica) e o
   nó completo da Fase 5 (com `sound_rms` e `sound_bands`) couberam na mesma versão do
   contrato. Só mude para `v2` em alteração incompatível — e aí o ingestor precisa
   aceitar as duas versões durante a transição, porque há nós em campo que ninguém vai
   reprogramar no mesmo dia.
