# S — os sensores simulados

**Tempo:** ~4 h · voltar ao [índice](../ROTEIRO.md)

**Para quem ainda não tem os sensores.** Você tem a placa, o nó já entra na rede e sabe
que horas são (E1 a E3), mas os dois SHT30 e o HX711 ainda não chegaram. Sem eles, E4 não
tem o que ler, e sem leitura a plataforma recusa a mensagem.

Nesta etapa o nó **inventa** as leituras: temperatura, umidade e peso com a cara de uma
colmeia de verdade. Com elas você segue para E5 e E6, vê o seu ponto no gráfico e faz o
nó completo de E8 — tudo sem sensor nenhum. Quando o hardware chegar, você faz E4 e E7, e
o resto do seu programa não muda.

E mesmo depois disso a simulação continua útil. Ela é o jeito de testar a mensagem num nó
sem sensores ligados, e o único jeito de fazer um sensor falhar quando **você** quer.

> **O conceito: trocar uma peça sem mexer no resto.**
> Todo o seu nó depende de uma coisa só vinda dos sensores: **a leitura** — cinco números
> e, para cada sensor, se ele respondeu. Se existir **uma única função** cujo trabalho é
> preencher essa leitura, quem está do outro lado dela — a montagem do JSON, o envio, o
> laço de cinco minutos — não precisa saber de onde os números vieram. A função pode ler
> o SHT30 ou pode inventar; o resto do programa é o mesmo.
>
> Uma peça que ocupa o lugar de outra para que o resto possa funcionar sem ela chama-se
> **dublê**. A plataforma usa a mesma ideia do outro lado: o
> [`simulator/`](../../simulator/) é um dublê do seu nó, e foi com ele que a plataforma
> inteira foi escrita antes de existir nó nenhum. Verbete no
> [glossário](../../docs/guia/06-glossario.md).

---

## S.1 — a leitura tem um formato

Defina, no seu programa, **o formato da leitura**: um lugar com as cinco medidas —
temperatura interna, temperatura externa, umidade interna, umidade externa e peso — e, para
cada um dos três sensores (SHT30 interno, SHT30 externo, HX711), a marca de que ele
respondeu ou não.

Depois escreva **uma função** que preenche essa leitura. Nesta primeira versão ela devolve
sempre os mesmos números, fixos: uma colmeia parada no tempo.

**Pronto quando:** o serial imprime, a cada 10 segundos, os cinco valores rotulados e o
estado de cada sensor — algo como:

```
interna 30.0 C  68.0 %   | externa 33.0 C  45.0 %   | peso 12.000 kg
sht_in: ok   sht_out: ok   hx711: ok
```

Repare onde está o `Serial.print`: **fora** da função de leitura. Ela só preenche; quem
imprime é quem a chamou. Essa separação é o que faz a troca do passo S.4 ser possível.

---

## S.2 — números que parecem de colmeia

Números fixos provam que o encanamento funciona, e mais nada: um gráfico com uma linha
reta não mostra se o eixo está certo, se a lacuna aparece, se o diferencial faz sentido.
Faça a função inventar números **com a forma** dos reais:

| Medida | Comportamento |
|---|---|
| temperatura interna | perto de 30 °C, variando pouco — a colônia controla a região de cria |
| temperatura externa | segue a hora do dia: mínima de madrugada, máxima no meio da tarde, com amplitude bem maior que a interna |
| umidade interna | perto de 70 %, variando pouco |
| umidade externa | o contrário da temperatura externa: mais alta de madrugada, mais baixa à tarde |
| peso | perto de 12 kg, mudando devagar — alguns gramas por leitura, nunca saltos |

A hora do dia você já tem desde E3. E um pouco de sorteio em cima de cada valor faz a
série parecer medida, e não calculada.

**Não precisa inventar a física.** O simulador da plataforma faz exatamente isso, em
Python, em [`simulator/model.py`](../../simulator/model.py): leia as funções
`outside_temp_c`, `inside_temp_c` e `step_weight_kg` e traduza **a ideia** para o seu
nó. Ler um programa numa linguagem e reescrever a lógica em outra é um exercício por si
só — copiar as fórmulas sem entendê-las não é.

> **Como conferir algo que depende da hora sem esperar um dia inteiro.** Escreva a conta
> da temperatura externa como uma função que **recebe a hora** em vez de consultá-la
> sozinha. Assim você pode chamá-la com 0, 1, 2 ... 23 e ver o dia inteiro em um segundo.
> É a mesma ideia do conceito desta etapa, em escala menor: o que a função precisa vem de
> fora, e quem chama decide se é o relógio de verdade ou um número de teste.

**Pronto quando:**

1. O nó imprime uma tabela das 24 horas com a temperatura externa calculada para cada
   uma, e ela é **mais baixa de madrugada e mais alta à tarde**, com diferença de vários
   graus entre as duas.
2. Dez leituras seguidas, no laço normal, ficam dentro destas faixas:

| Medida | Faixa |
|---|---|
| temperatura interna | entre 28 e 32 °C |
| umidade | entre 0 e 100 % — umidade acima de 100 é impossível, e a plataforma recusa |
| peso | sem salto maior que 50 g de uma leitura para a seguinte |

As faixas que a plataforma aceita estão escritas no contrato,
[`../../contracts/telemetry.v1.schema.json`](../../contracts/telemetry.v1.schema.json) —
procure `minimum` e `maximum`. Um simulador que sai delas vai gerar `400` em E5, e é
melhor descobrir aqui.

---

## S.3 — o sensor falha quando você manda

Um sensor de verdade falha: o cabo solta, a umidade entra, o barramento trava. O seu nó
precisa saber dizer "ausente" — e é aqui que a simulação faz o que o hardware não faz:
**falhar na hora em que você pede**, quantas vezes quiser.

Faça o nó aceitar comandos pelo monitor serial para desligar e religar cada sensor
simulado. Por exemplo, `falha externo` e `volta externo` — os nomes são seus.

**Pronto quando:**

1. Depois de `falha externo`, a leitura seguinte imprime **"ausente"** para o sensor
   externo — **não zero** — e continua lendo o interno e o peso normalmente.
2. Depois de `volta externo`, os números do sensor externo voltam.
3. O mesmo funciona para o sensor interno e para o peso.

> **Zero não é ausente.** Zero é uma temperatura possível, e um peso possível. Se o sensor
> ausente virar `0.0`, quem ler a série daqui a um ano vai ver uma colmeia a 0 °C, não um
> sensor quebrado. Este passo é o E4.4 sem precisar desligar um fio — e é ele que você vai
> usar em E5.2 para fazer o campo sumir da mensagem e a flag aparecer.

---

## S.4 — a chave

Os sensores vão chegar. Quando chegarem, você vai escrever a leitura de verdade (E4 e E7)
— e **não vai apagar a simulada**. As duas ficam no programa, e uma **única chave** no
código escolhe qual delas o nó usa.

Por enquanto a leitura de verdade ainda não existe. Então, na posição "real", faça ela
devolver **os três sensores ausentes** — é exatamente o que um nó sem sensor ligado
reportaria.

**Pronto quando:**

1. Com a chave em "real", o programa compila, roda, e imprime os três sensores como
   ausentes, sem travar e sem imprimir zero.
2. Com a chave de volta em "simulado", os números voltam.
3. Procurando no seu código, **nenhuma linha fora da função de leitura** menciona a
   simulação. A montagem da mensagem, o envio e o laço não sabem que ela existe.

O item 3 é o que importa. Se a função que monta o JSON tiver um `if` perguntando se a
leitura é simulada, a troca de peça não está funcionando — está só escondida.

> **Guarde para E5.3.** Quando você chegar lá e mandar a primeira mensagem à mão, mande
> também uma montada com a chave em "real". Sem nenhuma medida, a plataforma responde
> `400 mensagem sem nenhuma metrica de colmeia`: ela não aceita uma leitura vazia. É a
> prova de que o "tudo ausente" chega do jeito certo — como ausência, e não como zeros.

---

## Para onde mandar dados inventados

**Só para a plataforma que roda no seu computador** — a do
[exercício 01](../../docs/exercicios/01-plataforma-no-ar.md). **Nunca** para o servidor
de campo.

A mensagem não tem como dizer que foi inventada: para a plataforma, uma temperatura
simulada é uma temperatura. Uma série de mentira gravada no banco de verdade fica
indistinguível das reais, e quem for escrever o artigo não tem como separá-las.

---

## Pistas

<details>
<summary>Os números "sorteados" são sempre os mesmos a cada vez que a placa liga</summary>

O sorteio do computador é uma conta, não um dado jogado: ele parte de um valor inicial (a
**semente**) e, com a mesma semente, produz sempre a mesma sequência. Para variar de uma
ligada para outra, a semente precisa vir de algo que muda — o ESP32 tem um gerador de
números aleatórios em hardware que serve para isso.
</details>

<details>
<summary>A temperatura externa fica travada num valor esquisito logo depois de ligar</summary>

A hora do dia vem do NTP (E3), e o relógio da placa começa errado até sincronizar. Se a
primeira leitura acontece antes disso, a conta usa uma hora de 1970. Espere o relógio
sincronizar antes da primeira leitura — ou trate "relógio ainda não sincronizado" como o
E3 ensinou.
</details>

<details>
<summary>Sai <code>nan</code> no lugar de um número</summary>

Alguma conta dividiu por zero ou tirou raiz de negativo — quase sempre na hora de
transformar a hora do dia num ângulo para o seno. Imprima os valores intermediários da
conta, um por linha, e veja qual deles já sai errado.
</details>

<details>
<summary>O peso sobe sem parar, e depois de um dia está em 40 kg</summary>

Somar um pouquinho a cada leitura, para sempre, dá um número que cresce para sempre.
Colmeia de verdade ganha peso de dia e perde à noite. Dê ao peso simulado um limite, ou
faça-o subir e descer com a hora, como a temperatura.
</details>

<details>
<summary>O comando pelo serial não faz nada</summary>

Confira o que chega: imprima cada caractere recebido, com o código numérico dele. O
monitor serial costuma mandar um fim de linha junto com o texto — e `"falha externo\n"`
não é igual a `"falha externo"`.
</details>

---

## O que levar daqui

**A função de leitura é a fronteira entre o nó e o mundo.** Tudo que vem depois dela —
mensagem, envio, laço, `seq` — funciona igual com sensor de verdade ou de mentira. É isso
que deixa você fazer o resto do roteiro antes do hardware chegar.

**Um teste bom provoca a falha em vez de esperar por ela.** Desligar um fio com o
programa rodando testa a falha uma vez; um comando no serial a testa sempre que você
quiser.

→ Próximo: [E5 — a mensagem existe](E4-E6-a-primeira-mensagem.md#e5--a-mensagem-existe)
