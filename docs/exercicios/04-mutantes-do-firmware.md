# 04. Mutantes do firmware

**Área:** firmware · **Tempo:** ~45 min · **Treino** — nada aqui é commitado

## Por que este exercício existe

`pio test` diz "63 succeeded". Isso é um número, e um número não ensina nada.

Cada um daqueles testes é uma **afirmação sobre o sistema** que alguém escreveu depois de
levar um susto. A forma mais rápida de descobrir quais afirmações são essas é quebrar o
código de propósito e ver quem grita.

A técnica tem nome — *teste de mutação* — e é o que responde à pergunta que o guia deixa
no ar em [Primeiros passos com o PlatformIO](../guia/09-primeiros-passos-com-o-platformio.md#a-parte-que-ensina-de-verdade):
um teste verde prova alguma coisa?

## Antes de começar

- Exercício [02](02-uma-mensagem-ponta-a-ponta.md) feito.
- `pio test -e native -d firmware` verde agora.

### A regra que não se quebra

**Mutante nunca é commitado.** Depois de cada mutação:

```bash
git restore <arquivo>
git status            # tem de ficar limpo
```

Se você fechar o computador com um mutante aplicado, na segunda-feira vai passar uma hora
depurando um bug que você mesmo plantou.

## Como fazer cada mutação

Para cada uma, nesta ordem — e a ordem é o exercício:

1. **Preveja.** Escreva, antes de rodar, quantos testes vão falhar e quais.
2. Aplique a mutação.
3. `pio test -e native -d firmware`
4. **Compare** com a sua previsão. O interessante não é acertar: é entender a diferença.
5. `git restore` e confira o `git status`.

---

## Mutação A — arredondar vira cortar

**Arquivo:** `firmware/lib/MelipoCore/Escala.cpp`, função `escalar()`.

```cpp
// antes
return {static_cast<int32_t>(llround(produto)), true};

// depois
return {static_cast<int32_t>(produto), true};
```

É exatamente a implementação "óbvia" que a prática do PlatformIO já tinha mostrado ser
diferente. Escreva sua previsão e rode.

<details>
<summary>O que acontece</summary>

**Dois** testes falham, em arquivos diferentes:

```
test_escala.cpp:26: test_vetores_de_escala: Expected 3013 Was 3012. temp_in_c   [FAILED]
test_amostra.cpp:146: test_mensagem_montada_serializa: ... "temp_out_c":34.79 ... [FAILED]
```

O primeiro era esperado: 30,125 é o empate, e cortar dá 3012 em vez de 3013.

**O segundo é a lição de verdade.** Olhe o que ele acusa: `temp_out_c` saiu `34.79` em vez
de `34.80` — e 34,8 não é caso de empate nenhum. Por quê?

Porque **34,8 não é exatamente representável em binário**. O `double` mais próximo é um
tiquinho *abaixo* de 34,8, então `34.8 * 100` dá algo como `3479,9999999999995`. Arredondar
dá 3480; cortar dá 3479.

Ou seja: a diferença entre arredondar e cortar **não atinge só os empates**. Ela atinge
uma fatia enorme dos valores comuns, de forma imprevisível — o pior tipo de bug, porque
funciona quase sempre.

Repare também em *quem* pegou: um teste de escala e um teste de montagem de mensagem. A
suíte defende a mesma regra de dois ângulos.
</details>

---

## Mutação B — sensor com falha vira zero

**Arquivo:** `firmware/lib/MelipoCore/Amostra.cpp`, função `atribuir()`.

```cpp
// antes
  if (!leitura.valida) {
    return false;
  }

// depois
  if (!leitura.valida) {
    destino = 0;
    presentes |= campo;
    return true;
  }
```

Você acabou de quebrar **a regra mais importante do projeto inteiro**: "ausente não é
zero". Quantos testes acha que a defendem?

<details>
<summary>O que acontece</summary>

**Três** testes falham, todos em `test_amostra.cpp`:

```
test_sensor_externo_ausente_omite_campos_e_liga_flag   [FAILED]
test_meia_leitura_do_sht_liga_a_flag                   [FAILED]
test_celula_de_carga_desconectada                      [FAILED]
```

Vale abrir os três e ler os comentários. O de baixo diz, em uma frase, por que isso
importa mais do que parece:

> Um HX711 desconectado não pode virar "a colmeia pesa 0 kg" — isso dispararia o alerta de
> queda abrupta de peso e mandaria o meliponicultor ao meliponário à toa.

Note que a mutação **não trava nada**. O nó continua publicando, o JSON continua válido, o
ingestor aceita, o banco grava, o gráfico desenha. Só que a série está mentindo. É esse o
modo de falha que três testes separados existem para pegar.
</details>

---

## Mutação C — meia leitura do SHT30 passa

**Arquivo:** `firmware/lib/MelipoCore/Amostra.cpp`, em `montarTelemetria`.

```cpp
// antes
  if (!temp_int_ok || !ur_int_ok) {

// depois
  if (!temp_int_ok) {
```

Um SHT30 mede temperatura **e** umidade no mesmo chip. Esta mutação diz: se a temperatura
veio, está tudo bem, mesmo que a umidade não tenha vindo.

<details>
<summary>O que acontece</summary>

**Um** teste falha:

```
test_amostra.cpp:78: test_meia_leitura_do_sht_liga_a_flag: Expected TRUE Was FALSE  [FAILED]
```

Um teste só — e esse é o ponto. Compare com a mutação B, defendida por três. Aqui a
afirmação é mais estreita, e **um único teste é toda a rede de segurança**. Se alguém
apagasse esse teste por achá-lo redundante, a regra ficaria descoberta e nada acusaria.

A regra em si: meia leitura significa chip com problema, e o campo que veio também é
descartado por não ser confiável sozinho. É uma decisão de projeto — e é justamente o tipo
de decisão que, sem teste, alguém "simplifica" seis meses depois.
</details>

---

## Critério de pronto

- [ ] Você escreveu a previsão **antes** de rodar, nas três mutações
- [ ] Você entendeu por que a mutação A derruba um teste que fala de `34.80`
- [ ] `git status` está limpo — nenhum mutante sobreviveu
- [ ] `pio test -e native -d firmware` está verde de novo

## Pistas

<details>
<summary>Depois da mutação, `pio test` reclama de compilação</summary>

Você provavelmente colou o trecho no lugar errado, ou deixou uma chave sobrando. Rode
`git diff` para ver exatamente o que mudou — se o diff tiver mais do que as linhas
previstas, `git restore` e comece de novo.
</details>

<details>
<summary>Nenhum teste falhou e eu esperava que falhasse</summary>

Confira duas coisas: se o arquivo foi mesmo salvo (`git diff` mostra a mudança?) e se você
está lendo a saída certa — `pio test` imprime muita coisa; procure a linha do `SUMMARY`.

E se a mudança está aplicada e nada falhou mesmo, **você encontrou um buraco na suíte**.
Isso é o assunto do exercício [07](07-o-mutante-que-ninguem-pega.md).
</details>

## O que levar daqui

**A suíte não é um número: é uma lista de afirmações.** Três mutações, três respostas
diferentes — dois testes, três testes, um teste. Quanto mais estreita a defesa, mais frágil
a regra.

**Erro de arredondamento não fica nos empates.** A mutação A quebra `34.8`, um valor
banal, porque binário não representa decimal exatamente. Foi por isso que o contrato
escolheu trafegar inteiros.

**Nenhuma das três mutações trava nada.** Todas produzem um sistema que roda, publica e
desenha gráficos — com dados errados. É contra isso que os testes existem.

→ Próximo: [Mutantes da plataforma](05-mutantes-da-plataforma.md)
