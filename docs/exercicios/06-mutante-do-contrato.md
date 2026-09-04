# 06. O mutante do contrato

**Área:** contrato · **Tempo:** ~30 min · **Treino** — nada aqui é commitado

## Por que este exercício existe

[O contrato](../guia/02-o-contrato.md#o-modo-de-falha-dos-vetores-dourados) faz um aviso
que é fácil ler e difícil sentir:

> Se alguém muda o contrato e roda o gerador sem pensar, os vetores passam a descrever o
> comportamento **novo**, os dois testes voltam a passar, e o bug foi abençoado. O vetor
> virou cúmplice em vez de juiz.

Este exercício faz você viver isso: quebrar o contrato, ver os verificadores acusarem,
"consertar" da forma errada — regerando —, ver tudo ficar verde de novo, e descobrir o que
ainda sobra de pé.

## Antes de começar

- Exercício [02](02-uma-mensagem-ponta-a-ponta.md) feito.
- `./verificar` verde agora.

**Mutante nunca é commitado.** Neste exercício você vai mexer em `contracts/canonical.py`
**e** regerar arquivos em `contracts/testdata/`. No fim:

```bash
git restore contracts/
git status            # tem de ficar limpo
```

## A mutação

**Arquivo:** `contracts/canonical.py`, tupla `FIELD_ORDER`. Troque a ordem de dois campos:

```python
# antes
    "vbat_v",
    "rssi",

# depois
    "rssi",
    "vbat_v",
```

Nenhum valor mudou. Nenhum campo entrou ou saiu. Só a ordem em que eles aparecem no JSON.

> **Antes de rodar qualquer coisa:** isso é um bug? Um JSON com as chaves em outra ordem
> ainda é o mesmo JSON, do ponto de vista de qualquer parser. Escreva sua resposta.

## Passo 1 — os verificadores, um por um

Rode os três separadamente, nesta ordem, e anote o resultado de cada um:

```bash
python3 contracts/tools/gen_testdata.py --check
platform/.venv/bin/pytest platform/tests -q
pio test -e native -d firmware
```

<details>
<summary>O que acontece</summary>

**1. `gen_testdata.py --check` falha**, listando cinco arquivos desatualizados:

```
vetores dourados desatualizados:
  testdata/telemetry_01_nominal.json
  testdata/telemetry_02_arredondamento.json
  testdata/telemetry_03_sht_externo_ausente.json
  testdata/telemetry_07_no_completo_lora.json
  testdata/vectors.h
rode: python3 contracts/tools/gen_testdata.py
```

(Os casos 04, 05 e 06 não aparecem porque nenhum deles tem `rssi` **e** `vbat_v` ao mesmo
tempo — sem os dois campos, a ordem entre eles não muda nada. Repare que a cobertura dos
vetores não é uniforme.)

**2. O `pytest` falha** em quatro casos de `test_contract.py::test_vetor_esta_na_forma_canonica`
— os mesmos quatro. O lado Python detecta que o `canonical.py` e os vetores gravados não
concordam mais.

**3. O `pio test` passa**, com os 63 verdes. E isso faz sentido: o `vectors.h` no disco
ainda é o antigo, e o codec C++ ainda reproduz o antigo. **Os dois lados só divergem
quando alguém atualiza um deles.**
</details>

## Passo 2 — o "conserto" errado

O `--check` até sugeriu o comando. Faça o que ele diz, sem pensar — é exatamente o erro
que o exercício quer que você cometa:

```bash
python3 contracts/tools/gen_testdata.py
```

Agora rode os três de novo.

<details>
<summary>O que acontece</summary>

**1. `--check` passa.** Os vetores estão atualizados.

**2. O `pytest` passa.** Os 76 verdes de volta.

Pare aqui e olhe para o que aconteceu: **o contrato mudou e dois dos três verificadores
estão verdes.** Se o repositório tivesse só esses dois, você commitaria a mudança agora,
o CI aprovaria, e o vetor teria virado cúmplice — exatamente o que o guia avisa.

**3. O `pio test` falha — e nem chega a rodar:**

```
error: designator order for field 'meliponet::Telemetria::vbat_v' does not
match declaration order in 'meliponet::Telemetria'
```

**O compilador C++ pegou.** O `vectors.h` gerado usa *designated initializers*
(`.rssi = -58, .vbat_v = 400`), e o C++20 exige que eles apareçam **na mesma ordem em que
os membros foram declarados** na `struct`. Como `Telemetria.h` declara `vbat_v` antes de
`rssi`, o cabeçalho gerado ficou fora de ordem e o build quebrou.

Ou seja: existe um terceiro verificador que ninguém escreveu de propósito, e ele é o
compilador. A ordem canônica do contrato e a ordem dos membros da `struct` C++ estão
amarradas uma na outra.
</details>

## Passo 3 — reverter e responder

```bash
git restore contracts/
git status
./verificar
```

Agora responda, por escrito:

> **Pergunta 1.** Trocar a ordem das chaves era um bug? Sua resposta mudou desde o começo?
>
> **Pergunta 2.** Por que o `--check` existe, se o `pytest` já pegava a divergência?
>
> **Pergunta 3.** Suponha que a mutação tivesse sido em `DECIMALS`, mudando `weight_kg` de
> 3 para 2 casas. O compilador teria pegado depois de regerar?

<details>
<summary>Respostas</summary>

**1.** Sim, e por uma razão que não é técnica: o contrato **define** a forma canônica. Um
JSON com as chaves em outra ordem é o mesmo objeto para um parser, mas não é a mesma
sequência de bytes — e a verificação entre C++ e Python é byte a byte, de propósito. Sem
uma ordem fixa, as duas implementações precisariam concordar sobre ordenação de chaves, o
que é mais uma oportunidade de divergir sem ninguém errar.

Repare que a mudança não é *errada*: ela é **incompatível**. Fazê-la de propósito exigiria
combinar com a outra ponta, como manda
[Como mudar o contrato](../guia/02-o-contrato.md#como-mudar-o-contrato).

**2.** Porque eles pegam coisas diferentes. O `pytest` compara os vetores gravados com o
`canonical.py` — e para de acusar assim que alguém regenera. O `--check` **falha em vez de
regravar em silêncio**, o que força a regeração a ser uma decisão explícita, com o diff
aparecendo no commit. É a diferença entre um verificador e um corretor automático: um
corretor automático teria "consertado" o bug para você.

E é por isso que a revisão de um PR que mexe em vetores dourados tem de ler o diff dos
`.json` **com o mesmo cuidado de um diff de código**. É isso que eles são.

**3.** **Não.** `DECIMALS` não altera a ordem dos campos, só o número de casas — o
`vectors.h` continuaria com os inicializadores na ordem certa e compilaria. Depois de
regerar, os três verificadores ficariam verdes, com o contrato dizendo agora que o peso
trafega em centésimos de quilo em vez de gramas.

O que sobraria de proteção? Nada automático. Sobraria a revisão humana, olhando um diff em
que `"weight_kg":12.483` virou `"weight_kg":12.48` — e é exatamente por isso que a regra do
projeto é conversar com a outra ponta **antes**, e não depois.

Foi sorte o compilador ter pegado a mutação deste exercício. **Não conte com sorte.**
</details>

## Critério de pronto

- [ ] Você anotou o resultado dos três verificadores antes e depois de regerar
- [ ] Você viu, com os próprios olhos, dois verificadores verdes com o contrato quebrado
- [ ] `git status` limpo e `./verificar` verde
- [ ] Você respondeu a pergunta 3 antes de abrir o gabarito

## Pistas

<details>
<summary>`git restore contracts/` não limpou tudo</summary>

`git status` mostra o que sobrou. Se aparecer algum arquivo novo em `testdata/` como
não rastreado (`??`), apague-o à mão — o `restore` só desfaz mudanças em arquivos que o git
já conhecia.
</details>

<details>
<summary>Quero ver o JSON antes e depois</summary>

Antes de regerar, guarde uma cópia fora do repositório:

```bash
cp contracts/testdata/telemetry_01_nominal.json /tmp/antes.json
python3 contracts/tools/gen_testdata.py
diff /tmp/antes.json contracts/testdata/telemetry_01_nominal.json
```
</details>

## O que levar daqui

**Um vetor dourado é código.** Ele é lido, revisado e discutido como código — porque um
vetor regerado sem pensar abençoa o bug em vez de acusá-lo.

**`--check` falha em vez de corrigir, e isso é uma escolha de projeto.** Ferramenta que
conserta sozinha esconde a decisão; ferramenta que reclama obriga alguém a tomá-la.

**Verificação automática tem borda.** Duas das três verificações aprovaram um contrato
quebrado. A terceira foi coincidência. O que fecha a lacuna não é mais um script: é
conversar com a outra ponta antes de mudar o contrato.

→ Próximo: [O mutante que ninguém pega](07-o-mutante-que-ninguem-pega.md)
