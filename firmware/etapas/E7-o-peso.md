# E7 — o peso

**Tempo:** ~6 h · voltar ao [índice](../ROTEIRO.md)

O peso é a medida mais valiosa que este nó produz — é ela que mostra a colmeia ganhando
reserva na florada e gastando na estiagem — e é também a única que **não dá para conferir
lendo o número**. Temperatura errada você percebe (uma colmeia não está a 60 °C). Peso
errado parece peso.

Por isso esta etapa é a mais fatiada do roteiro: seis passos, cada um provando uma coisa
só. Pular direto para "calibrar" é a forma mais rápida de passar dois dias calibrando um
problema de solda.

> **O conceito: a célula de carga não mede quilos.**
> Ela é um pedaço de metal que se deforma sob peso, com extensômetros colados que mudam de
> resistência ao deformar. O que sai dali é uma variação de tensão minúscula — milivolts.
> O HX711 é o conversor que amplifica isso e entrega ao nó um **número inteiro grande e
> sem unidade**, que este roteiro chama de **contagem bruta**. Esse número não é quilo, não
> é grama, não é nada: é "o quanto a célula está deformada", numa escala arbitrária que
> depende da célula, do módulo e de como você montou. Transformá-lo em quilos é o seu
> trabalho, e é o assunto de E7.3 e E7.4.

---

## E7.1 — a contagem bruta se move

Leia o HX711 e imprima a **contagem bruta**, sem converter nada. Aperte a plataforma com a
mão.

**Pronto quando:** o número se move de forma consistente enquanto você aperta, e volta para
perto de onde estava quando você solta.

**Se ele não se move, pare.** Nenhuma calibração conserta um sinal que não existe: o
problema é elétrico — ligação, solda, ou o próprio módulo. [O nó
sensor](../../docs/guia/04-o-no-sensor.md) tem a ordem segura de energização, e vale
relê-la: **alimentar o HX711 em 5 V queima o GPIO** da placa, que é 3,3 V.

---

## E7.2 — o número para de tremer

Você vai notar que a contagem bruta oscila mesmo com nada em cima. Leia N vezes seguidas e
imprima a média.

> **O conceito: ruído, e por que a média resolve.**
> Cada leitura traz um erro aleatório — interferência elétrica, vibração, variação da
> alimentação. Aleatório quer dizer que às vezes o erro é para cima e às vezes para baixo,
> e por isso ele tende a se cancelar quando você tira a média de várias leituras. O que a
> média **não** corrige é erro sistemático: se o valor está deslocado sempre para o mesmo
> lado, tirar a média de mil leituras devolve o mesmo valor deslocado, só que com mais
> confiança. O deslocamento constante é assunto da tara, no passo seguinte.

**Pronto quando:** com nada sobre a plataforma, leituras sucessivas da média variam bem
menos que leituras individuais. Anote quantas leituras você precisou — esse N vai para E8,
onde cada leitura custa tempo e bateria.

---

## E7.3 — a tara

Com a colmeia montada e **vazia**, leia a média e guarde esse valor. Ele é a **tara**: a
contagem que corresponde a "zero quilos de mel e abelhas".

> **O conceito: tara e fator de calibração são duas coisas diferentes.**
> A conta que transforma contagem em quilos tem duas incógnitas:
>
>     peso_kg = (contagem_media - tara) / fator
>
> A **tara** é o deslocamento: quanto a célula já acusa por causa do peso da própria caixa,
> da madeira, dos parafusos. Ela muda quando você monta a colmeia de outro jeito, e não
> tem nada a ver com a sensibilidade do sensor.
>
> O **fator** é a escala: quantas contagens correspondem a um quilo. Ele é uma propriedade
> daquela célula com aquele módulo, e não muda quando você troca o que está em cima.
>
> Misturar as duas é o erro clássico desta etapa: recalibrar quando o que mudou foi só a
> caixa, ou tarar de novo esperando corrigir uma escala errada.

**Pronto quando:** com a colmeia vazia sobre a célula, `contagem_media - tara` dá algo
muito próximo de zero.

---

## E7.4 — o fator de calibração

Ponha uma massa **conhecida** sobre a plataforma — um objeto que você pesou numa balança
confiável. Leia a média de novo e calcule o fator.

**Pronto quando:** aplicando a conta acima, o nó imprime o peso dessa massa conhecida com
erro menor que 20 g.

---

## E7.5 — a conferência com massa diferente

Tire a massa da calibração e ponha **outra**, de valor conhecido e diferente.

**Pronto quando:** o valor lido bate com o real, também dentro de 20 g.

> **Por que este passo existe.** Conferir com a mesma massa que você usou para calibrar não
> prova nada: a conta foi montada para acertar exatamente aquele ponto, e vai acertá-lo
> mesmo que a escala inteira esteja errada. Só uma segunda massa mostra se a relação entre
> contagem e quilo é linear de verdade. É o mesmo raciocínio de um teste que só confere a
> entrada com que foi escrito.

---

## E7.6 — tara e fator sobrevivem ao reset

Guarde os dois valores na NVS e leia-os na inicialização.

> **O conceito: NVS é a gaveta que sobrevive ao desligamento.**
> A RAM da placa se apaga inteira a cada reset e a cada queda de energia. A NVS (*non-volatile
> storage*) é uma área da memória flash reservada para dados que precisam continuar lá:
> credenciais de rede, calibração, e a `seq` de E8. Ela funciona como um caderninho de
> pares chave-valor — você grava sob um nome e depois lê por esse nome.
>
> **As chaves ficam escritas letra por letra como o projeto as define** (`"cal_offset"`,
> `"ssid"`, `"wifi_pw"`). Trocar o nome de uma chave não dá erro: a placa simplesmente não
> acha o valor antigo e volta ao padrão — uma placa calibrada perde a calibração em
> silêncio, e você só descobre pelo peso errado semanas depois. Verbete no
> [glossário](../../docs/guia/06-glossario.md).

**Pronto quando:** você calibra, desliga a placa da tomada, liga de novo, põe a massa
conhecida e o valor continua certo — sem recalibrar nada.

---

## Pistas

<details>
<summary>A contagem bruta não se move ao apertar</summary>

Problema elétrico, nunca de código. Na ordem: confira a alimentação do módulo (3,3 V, não
5 V), o GND comum, e os quatro fios da célula — dois pares, e inverter um par inverte o
sinal (o peso "diminui" ao apertar), enquanto trocar os pares entre si produz leitura sem
sentido nenhum.
</details>

<details>
<summary>A contagem bruta muda ao apertar, mas o peso sai negativo</summary>

Fios da célula invertidos, ou sinal do fator trocado. Não conserte com um valor absoluto:
ache o que está invertido, porque o valor absoluto vai esconder também os casos legítimos
em que o peso cai (enxame saindo, colheita).
</details>

<details>
<summary>O peso derrapa ao longo do dia, sem nada mudar em cima</summary>

Célula de carga tem deriva térmica, e a caixa esquenta ao sol. Não é defeito do seu código
— é um limite conhecido da medição. Registre-o no seu caderno de bancada: quem for
interpretar a série precisa saber que uma variação de dezenas de gramas ao longo do dia
pode ser térmica.
</details>

<details>
<summary>O valor pula de vez em quando para um número absurdo</summary>

Leitura feita enquanto o HX711 ainda não tinha valor novo pronto. O módulo tem uma taxa
própria; ler mais rápido que ela devolve lixo. E lixo entra na média e a estraga — vale
descartar os extremos antes de mediar.
</details>

<details>
<summary>Depois do reset o peso volta errado</summary>

Ou os valores não estão sendo gravados, ou estão sendo lidos com chave diferente da que
foi gravada. Imprima a tara e o fator logo na inicialização: se saírem no valor padrão, é
a NVS que não devolveu nada.
</details>

---

## O que levar daqui

**Prove o sinal antes de converter o sinal.** Os dois primeiros passos não produzem nenhum
quilo, e são os que separam "problema de montagem" de "problema de conta". Sem eles, todo
defeito parece de calibração.

**Confira com uma massa diferente da que calibrou.** Verificar com o dado que gerou a
resposta é um jeito confortável de não descobrir nada.

→ Próximo: [E8 — o nó vira um nó](E8-o-no-completo.md)
