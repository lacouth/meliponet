# E9 e E10 — as etapas opcionais

**Tempo:** ~8 h no total · voltar ao [índice](../ROTEIRO.md)

As duas são **opcionais** no sentido de que o nó de E8 já é um nó que funciona e cujos
dados valem. Mas as duas são o que separa um nó de bancada de um nó que fica meses numa
colmeia sem ninguém por perto.

---

## E9 — sobreviver à queda da rede

**Tempo:** ~4 h

> **O conceito: spool é a memória de curto prazo do nó.**
> A rede vai cair. Vai cair porque o roteiro do apiário reiniciou, porque o servidor
> estava sendo atualizado, porque choveu. Sem nenhuma providência, cada envio que falha é
> uma leitura perdida para sempre — e o buraco na série não distingue "a rede caiu" de "a
> colmeia parou de ser interessante".
>
> **Spool** é o buffer local onde o nó guarda o que não conseguiu entregar, para drenar
> quando a rede voltar. O que faz isso funcionar é uma decisão da plataforma que você já
> viu em E8.2: reenviar algo que ela já tem responde `200`, não erro. O nó pode reenviar
> sem medo, e apagar a cópia local tanto no `201` quanto no `200`. Verbete no
> [glossário](../../docs/guia/06-glossario.md).

### E9.1 — guardar o que falhou

Quando o envio falha, guarde a leitura (em memória ou no sistema de arquivos) em vez de
descartá-la.

**Pronto quando:** com o WiFi desligado, o nó continua medindo, e o serial mostra a
contagem de leituras guardadas subindo a cada cinco minutos.

### E9.2 — drenar quando a rede voltar

Ao reconectar, envie o que está guardado, com a flag `spooled`, e apague cada leitura
entregue.

**Pronto quando:** você desliga o WiFi por 15 minutos, liga de volta, e as três leituras do
período aparecem no gráfico — **no horário em que foram medidas**, não no horário em que
chegaram.

> **Este é o ponto do exercício inteiro.** O `ts` viaja junto da leitura desde E3
> justamente para isso: é o horário da medição, não o do envio. Um nó que carimbasse a hora
> na entrega transformaria toda queda de rede numa distorção da série — quinze minutos de
> dados empilhados no mesmo instante.

### E9.3 — o que fazer quando encher

Decida quantas leituras cabem e o que acontece quando o espaço acaba: descartar a mais
antiga, parar de guardar, ou outra coisa. Escreva a decisão e o porquê no seu caderno de
bancada.

**Pronto quando:** com o WiFi desligado além do limite que você escolheu, o nó **continua
rodando** — não trava, não reinicia, não enche a memória. E, quando a rede volta, entrega
o que ainda tem.

> **Não existe resposta certa aqui, existe resposta escrita.** Descartar a mais antiga
> preserva o dado recente (bom para alerta); descartar a mais nova preserva a série contínua
> (bom para análise). As duas são defensáveis; a que não é defensável é a que ninguém
> decidiu, porque aí o comportamento vira o que a memória acabou fazendo.

### Pistas — E9

<details>
<summary>O nó reinicia sozinho depois de alguns minutos sem rede</summary>

Memória. Guardar em RAM é o caminho mais simples e o que estoura primeiro — um teto
explícito de leituras (E9.3) é o que impede o reinício, e um reinício apaga o spool
inteiro, que é o pior desfecho possível.
</details>

<details>
<summary>As leituras drenadas aparecem todas no mesmo instante do gráfico</summary>

Você está gerando o `ts` na hora do envio. Ele precisa ser gravado junto da leitura, no
momento da medição, e viajar com ela.
</details>

<details>
<summary>A mesma leitura aparece várias vezes</summary>

Você não está apagando a cópia local depois da entrega — provavelmente porque só apaga no
`201` e o reenvio devolve `200`. Os dois são sucesso. (A plataforma não duplica nada, mas
o seu spool nunca esvazia.)
</details>

---

## E10 — MQTT, o caminho de campo

**Tempo:** ~4 h

Troque o POST por uma publicação MQTT no tópico
`meliponet/v1/<node_id>/telemetry`, com QoS 1.

> **O conceito: por que um broker no meio.**
> No HTTP, o nó fala direto com o servidor: se o servidor está reiniciando naquele
> instante, a mensagem não tem para onde ir e vira problema do nó resolver. O MQTT põe um
> intermediário — o **broker** — que recebe a publicação e a guarda até o consumidor pegar.
> O nó entrega e segue a vida; o servidor pode reiniciar, atualizar, ficar fora por dez
> minutos, e nada se perde.
>
> **QoS 1** é o nível de garantia: o broker confirma o recebimento, e o nó repete até ser
> confirmado. O preço é que uma mensagem pode chegar duas vezes — e é aqui que a decisão da
> `seq` paga de novo: uma duplicata é reconhecida como reenvio e responde `200`. O contrato
> foi desenhado para tolerar isso.

### E10.1 — publicar qualquer coisa

Publique uma mensagem de teste no broker e veja-a chegar, assinando o tópico de outro
computador.

**Pronto quando:** o que você publicou aparece do outro lado. Ainda sem a plataforma no
caminho: primeiro o transporte, depois o conteúdo.

### E10.2 — a mensagem de verdade, sem mudar uma vírgula

Publique a mesma mensagem de E8, no tópico certo, com QoS 1.

**Pronto quando:** com o ingestor MQTT rodando, o gráfico continua ganhando pontos — e
você **não mudou nada na mensagem**. Se precisou mudar, o que mudou pertencia ao
transporte e estava no lugar errado.

### E10.3 — o servidor pode cair

Com o nó publicando, derrube a plataforma por alguns minutos e levante-a de novo.

**Pronto quando:** as leituras do período aparecem assim que o ingestor volta, e o nó nem
soube que houve problema. É a diferença que justifica o MQTT existir.

### Pistas — E10

<details>
<summary>Publica e nada chega</summary>

Assine o tópico de outro computador e publique à mão por lá primeiro. Isso separa "o meu
nó publica errado" de "o broker não está onde eu acho". Confira também a grafia do tópico:
o `<node_id>` é o seu, em maiúsculas, como no contrato.
</details>

<details>
<summary>Chega no broker e não aparece no gráfico</summary>

O broker recebeu e o ingestor não consumiu. Olhe o log do ingestor e a tabela
`ingest_rejects` — se a mensagem foi recusada, o motivo está lá, do mesmo jeito que no
HTTP. O exercício
[02](../../docs/exercicios/02-uma-mensagem-ate-o-grafico.md) ensina a consulta.
</details>

<details>
<summary>A mesma leitura aparece duas vezes no broker</summary>

Comportamento normal de QoS 1, e é por isso que o contrato tem `seq`. A plataforma
responde `200` à segunda e não duplica nada.
</details>

---

## O que levar daqui

**Transporte e conteúdo são coisas separadas.** A mesma mensagem viaja por HTTP em E6 e
por MQTT em E10 sem mudar um byte. É o que permite ao projeto trocar o caminho — LoRa, um
gateway, o que vier — sem mexer no nó nem na plataforma.

**Perder dado é uma decisão.** E9.3 força você a escolher o que perder quando não couber
tudo. Sistemas que não escolhem também perdem, só que sem ninguém saber o quê.

---

## Depois de E10

O nó está pronto para ficar na colmeia. O que fica para outras pessoas, ou para você mais
adiante: rádio LoRa e gateway para apiários sem WiFi, microfone para bioacústica, painel
solar com *deep sleep*, e o invólucro impresso.
