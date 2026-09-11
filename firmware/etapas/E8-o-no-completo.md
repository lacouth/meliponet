# E8 — o nó vira um nó

**Tempo:** ~5 h · voltar ao [índice](../ROTEIRO.md)

Até aqui você tem peças que funcionam quando você está olhando. Nesta etapa elas viram um
equipamento: um laço que mede e envia sozinho, com um contador que sobrevive a
desligamentos e uma medida da própria bateria.

O critério final não é uma leitura certa — é **uma hora seguida** de leituras certas, sem
ninguém por perto.

---

## E8.1 — o laço de cinco minutos

Junte o que já funciona num laço: mede, monta a mensagem, envia, espera cinco minutos,
repete.

**Pronto quando:** o gráfico do painel ganha três pontos seguidos, espaçados de cinco
minutos.

> **Cuidado com o jeito de esperar.** Enquanto o nó espera, ele não pode ficar preso de um
> jeito que impeça o rádio de trabalhar, nem perder a conta do tempo por causa de um envio
> que demorou. Se a medição levou 8 s, a espera até o próximo ciclo é de 4 min 52 s, não de
> 5 min — senão o intervalo real vai derrapando a cada ciclo.

---

## E8.2 — a `seq` sobrevive ao reset

Incremente a `seq` a cada leitura e guarde-a na NVS.

> **O conceito: `seq` é como a plataforma reconhece reenvio.**
> A plataforma identifica cada leitura pelo par (`node_id`, `seq`). Quando chega uma `seq`
> que ela já tem daquele nó, ela responde `200` em vez de gravar de novo — e isso é
> **sucesso**, não erro: é o que permite ao nó reenviar tranquilamente o que guardou
> durante uma queda de rede, sem precisar saber o que a plataforma já recebeu.
>
> A consequência é que um contador que **volta ao zero** é um desastre silencioso: o nó
> passa a mandar `seq` que a plataforma já viu, ela responde `200` a todas, e as leituras
> novas são descartadas achando que são repetidas. O gráfico simplesmente congela, sem
> nenhum erro em lugar nenhum. É por isso que a `seq` mora na NVS (E7.6) e não na RAM.
>
> Ela também mede o que se perdeu: um salto de 1042 para 1051 diz que nove leituras não
> chegaram. Verbete no [glossário](../../docs/guia/06-glossario.md).

**Pronto quando:** você desliga a placa da tomada, liga de volta, e a primeira `seq`
enviada é a seguinte à última de antes — não zero. Confirme pela resposta: tem de ser
`201`, e não `200`.

---

## E8.3 — a tensão da bateria

Meça a tensão da célula 18650 pelo divisor e mande em `vbat_v`.

> **O conceito: o divisor resistivo, e por que a leitura é metade.**
> A célula 18650 chega a 4,2 V cheia, e a entrada analógica da placa não tolera mais que
> 3,3 V. Dois resistores iguais em série entre a bateria e o GND resolvem: o ponto no meio
> deles fica em **exatamente metade** da tensão da bateria, dentro da faixa segura. Por
> isso o valor lido precisa ser **multiplicado por dois** para virar a tensão real — e
> esquecer essa multiplicação produz uma bateria que parece permanentemente descarregada.

**Pronto quando:** o `vbat_v` que o nó imprime bate com o que um multímetro mede nos
terminais da bateria, dentro de 0,1 V.

> **Não confie na conta sozinha.** O conversor analógico do ESP32 não é calibrado de
> fábrica para precisão, e os resistores têm tolerância. A conferência com multímetro é
> parte do passo, não um extra — é o que [O nó
> sensor](../../docs/guia/04-o-no-sensor.md) chama de medida que precisa de conferência
> externa.

---

## E8.4 — a flag `low_batt`

Acenda a flag `low_batt` quando `vbat_v` ficar abaixo de **3,50 V**.

**Pronto quando:** alimentando o divisor por uma fonte ajustável (ou com uma bateria
realmente descarregada), a flag aparece na mensagem abaixo do limiar e some acima dele.

> **Por que uma flag e não um limiar na plataforma.** Quem sabe que a leitura foi feita com
> a bateria fraca é o nó, no instante da medição. A plataforma recebe um número já
> arredondado e pode nem ter recebido as leituras do período crítico. A flag viaja junto do
> dado que ela descreve — e continua junto dele daqui a cinco anos, quando ninguém mais
> lembrar do limiar.

---

## E8.5 — uma hora sozinho

Deixe o nó rodando por uma hora, sem mexer.

**Pronto quando:** o gráfico tem doze pontos, espaçados de cinco minutos, sem buraco. E,
ao fim, você desliga e religa a placa e o ponto seguinte continua a série — com `201`.

Este é o critério de pronto da etapa inteira, e o primeiro que você não consegue conferir
olhando: precisa deixar rodando e voltar depois.

---

## Pistas

<details>
<summary>O gráfico ganha pontos e depois para</summary>

Três hipóteses, na ordem de frequência: a `seq` parou de incrementar (confira se as
respostas viraram `200`); o programa reiniciou por watchdog no meio de um envio; ou a
memória foi acabando a cada ciclo — um vazamento que só aparece depois de dezenas de
iterações, que é justamente o que E8.5 procura.
</details>

<details>
<summary>Os pontos aparecem, mas espaçados de 5 min e uns segundos, cada vez mais</summary>

A espera está sendo contada depois do trabalho, e não a partir do início do ciclo. Some o
tempo gasto medindo e enviando e desconte-o da espera.
</details>

<details>
<summary>Depois do reset, resposta <code>200</code> para tudo</summary>

A `seq` voltou ao zero: ou não foi gravada na NVS, ou está sendo lida com chave diferente
da gravada. Imprima a `seq` lida logo na inicialização, antes do primeiro envio.
</details>

<details>
<summary>O <code>vbat_v</code> sai sempre em torno de 2,0 V com a bateria cheia</summary>

Faltou multiplicar por dois: você está mandando a tensão do ponto médio do divisor, não a
da bateria.
</details>

<details>
<summary>O <code>vbat_v</code> oscila muito entre leituras</summary>

O conversor analógico é ruidoso, e o rádio transmitindo puxa corrente e derruba a tensão
momentaneamente. Vale a mesma solução de E7.2 — média de várias leituras — e medir num
instante em que o rádio não esteja transmitindo.
</details>

<details>
<summary>Alguma leitura some, de vez em quando</summary>

É o comportamento esperado enquanto E9 não existir: sem spool, uma falha de envio perde
aquela leitura para sempre. A `seq` permite provar que foi isso: procure o salto na série.
</details>

---

## O que levar daqui

**O que não sobrevive ao reset não existe.** Calibração, tara e `seq` são estado de
equipamento, não de programa. O reset acontece — por queda de energia, por watchdog, por
alguém esbarrando no cabo.

**Defeito que só aparece com o tempo só aparece com o tempo.** Vazamento de memória,
deriva do intervalo e `seq` mal guardada passam ilesos por qualquer teste de dois minutos.
Por isso o critério de E8.5 é uma hora.

→ Próximo: [E9 e E10 — as etapas opcionais](E9-E10-opcionais.md)
