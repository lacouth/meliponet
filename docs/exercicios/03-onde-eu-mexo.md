# 03. Onde eu mexo?

**Área:** todas · **Tempo:** ~30 min · **Treino**

## Por que este exercício existe

O erro mais comum de quem chega a um projeto com camadas não é escrever a linha errada —
é escrever a linha **certa na camada errada**. O código funciona, os testes passam, e o
custo aparece meses depois: a lógica que ficou dentro de uma view não pode ser chamada
pelo gerador de relatórios; o cálculo que ficou no `main.cpp` não pode ser testado sem
placa.

Este exercício treina a pergunta que resolve isso, e que está em
[Engenharia de software](../guia/05-engenharia-de-software.md#separação-de-responsabilidades):
**do que isso precisa para funcionar?**

- Precisa só de aritmética? É lógica pura — `MelipoCore` no firmware, `services/` na
  plataforma. É onde o teste alcança.
- Precisa do banco? É serviço.
- Precisa da requisição HTTP? É view.
- Precisa do Wire, do WiFi, da NVS? É `MelipoHardware`.

## Antes de começar

Faça o exercício [02](02-uma-mensagem-ponta-a-ponta.md). Tenha à mão a estrutura de pastas
de [A plataforma Flask](../guia/03-a-plataforma-flask.md#a-estrutura-de-pastas) e de
[O firmware](../guia/04-o-firmware.md#a-estrutura).

## Passos

Para cada pedido abaixo, responda **três coisas**, por escrito, antes de abrir o gabarito:

1. **Em que arquivo (ou arquivos) a mudança começa?**
2. **Em que ordem?** — se toca mais de um lado, qual vem primeiro.
3. **Que teste prova que funcionou?** — e onde ele mora.

Não implemente nada. O exercício é de localização.

---

### Pedido 1

> "O sensor de temperatura da cria vai ganhar um irmão: um terceiro SHT30, dentro do
> ninho. Quero ver `brood_temp_c` no gráfico."

<details>
<summary>Resposta</summary>

**Começa no contrato, e não no firmware nem na plataforma.** Esta é a resposta que o
exercício inteiro existe para treinar: mexer primeiro num dos lados garante que o outro
vai discordar.

Ordem:

1. `contracts/telemetry.v1.schema.json` — o campo novo, **opcional** (nunca em `required`;
   há nós em campo que ninguém vai reprogramar no mesmo dia).
2. `contracts/canonical.py` — `FIELD_ORDER` (a posição na ordem canônica) e `DECIMALS`
   (quantas casas, ou seja, qual o fator de escala).
3. `contracts/tools/gen_testdata.py` — pelo menos um caso em `VALID` com o campo, e rodar
   `python3 contracts/tools/gen_testdata.py` para regerar os vetores.
4. Firmware: `Telemetria.h` (o membro, o bit em `Campo::`), `Telemetria.cpp` (a emissão),
   `Escala.h` (a `Metrica` com faixa e casas), `Amostra.h`/`Amostra.cpp` (a leitura nova e
   a flag de falha), e `MelipoHardware/SensoresSht` para o endereço I²C do terceiro sensor.
5. Plataforma: `models.py` (a coluna), **uma migração Alembic**, e
   `ingest/store.py` → `METRIC_FIELDS`.
6. Interface: `services/series.py` → `METRIC_COLUMNS`, e `templates/_panel.html`.

*Teste:* o vetor dourado novo já cobre os dois lados (`pio test` e
`pytest platform/tests/test_contract.py`). Some um teste em `test_amostra.cpp` para a
omissão quando o sensor falha, e um em `test_series.py` se a métrica entrar nos gráficos.

*Armadilha:* esquecer `METRIC_FIELDS` em `store.py` faz a mensagem ser aceita e o campo
ser **silenciosamente descartado** na gravação. Nada quebra; a coluna fica sempre `NULL`.
</details>

---

### Pedido 2

> "Quando o peso cair mais de 2 kg de uma vez, quero um e-mail."

<details>
<summary>Resposta</summary>

Duas peças bem separadas, e a separação é o ponto:

**A regra** — "caiu mais de 2 kg entre duas leituras?" — precisa só de aritmética sobre
uma lista de pontos. É lógica pura: um `services/alerts.py` novo, testável sem banco e sem
servidor, no mesmo espírito de `services/series.py`.

**O envio do e-mail** precisa de rede e de configuração. É outra camada, e não pode morar
junto: um teste da regra não pode depender de um servidor SMTP.

O modelo já está preparado: `AlertRule` e `Alert` existem em `models.py` e hoje não são
lidos por ninguém — está registrado como [D-19](../defeitos-conhecidos.md#d-19). Antes de
criar tabela nova, leia o que já existe.

*Teste:* `test_alerts.py`, alimentando a regra com uma série sintética que tem a queda, e
outra que tem uma queda **lenta** de 2 kg ao longo de um dia (que não deve disparar). O
`sustained_samples` de `AlertRule` existe justamente para que um outlier isolado não vire
notificação.

*Cuidado de domínio:* uma queda abrupta de peso pode ser colheita (normal) ou enxameação
(urgente). O simulador injeta colheitas de propósito em `model.py`,
`step_weight_kg` — a regra tem de distinguir as duas, ou o produtor desliga o alerta na
primeira semana.
</details>

---

### Pedido 3

> "Os gráficos deviam mostrar a média móvel de 3 horas, além da série crua."

<details>
<summary>Resposta</summary>

`services/series.py`. **Não** no template, e **não** em JavaScript no `_panel.html`.

A razão é a mesma de a série já ser reamostrada em Python: o que vive no serviço pode ser
chamado pela página, pelo relatório em PDF, por um script de exportação e por um teste,
sem subir servidor nenhum. Calculando no navegador, só a página teria a média.

*Teste:* `test_series.py`, com uma série de valor constante (a média móvel tem de ser a
mesma constante) e uma com um degrau (a média tem de subir suavizada). E o caso que
importa neste projeto: **o que a média faz com uma lacuna?** Se ela preencher o buraco, a
média desfaz visualmente a perda que `spanGaps` desligado existe para mostrar — decida
isso de propósito e escreva o teste que fixa a decisão.
</details>

---

### Pedido 4

> "Quero mudar o intervalo de amostragem do nó de 5 para 10 minutos, sem recompilar."

<details>
<summary>Resposta</summary>

`firmware/src/main.cpp`: um comando de console novo, exatamente como descrito em
[O firmware](../guia/04-o-firmware.md#acrescentar-um-comando-ao-console) — uma função
pequena e uma linha na tabela `kComandos`.

O valor já mora na NVS (`interval_s`, lido por `Configuracao.cpp`) e já é usado por
`g_agenda.iniciar()` no `setup()`. Ou seja: **o mecanismo existe inteiro; falta só a porta
de entrada.**

E há uma armadilha ali: `platformio.ini` define `-DMELIPO_SAMPLE_INTERVAL_S=300`, que
**nenhum arquivo referencia**. Quem quiser mudar o intervalo provavelmente vai editar esse
flag, recompilar, gravar — e nada muda. Está registrado como
[D-10](../defeitos-conhecidos.md#d-10).

*Teste:* a validação do argumento é pura (`lerNumero` em `LinhaDeComando`) e já tem teste
nativo. A gravação na NVS e o efeito no `Agenda` são verificados na bancada.

Este é o exercício [12](12-comando-intervalo.md).
</details>

---

### Pedido 5

> "Um pesquisador quer baixar todas as séries de todas as colmeias em CSV, de uma vez."

<details>
<summary>Resposta</summary>

Três camadas, uma decisão em cada:

1. **`services/`** — a montagem das linhas. Sem saber o que é HTTP.
2. **`blueprints/dashboard.py`** — a rota, o cabeçalho `Content-Type` e o nome do arquivo.
3. **`services/scope.py`** — o filtro. E aqui está o ponto: o perfil `pesquisador`
   **vê tudo**, então esse pedido é legítimo para ele e seria um vazamento para um
   `meliponicultor`. Passe por `scope.hives_for(current_user)`; nunca por `select(Hive)`.

*Teste:* `test_web.py` — um meliponicultor baixando o CSV recebe só as próprias colmeias;
um pesquisador recebe todas. Sem os dois testes, o filtro pode estar ausente e nada acusa:
o modo de falha do escopo é o silêncio.

*Cuidado:* "todas as séries de todas as colmeias" pode ser muita coisa. Vale uma janela
máxima, ou streaming — mas isso é decisão de projeto, não de camada.

A versão de uma colmeia só é o exercício [14](14-exportar-csv.md).
</details>

---

### Pedido 6

> "O nó devia avisar quando a memória do spool estiver acima de 80%."

<details>
<summary>Resposta</summary>

**A decisão** — "80% de `kCapacidadeDoSpool`, já passou?" — é aritmética pura:
`MelipoCore`, junto de `Spool`. `Spool` já expõe `quantidade()`, `cheio()` e
`descartadas()`.

**O aviso** é que depende de onde ele vai aparecer, e as duas opções têm custos diferentes:

- no `Serial`, para a bancada: trivial, e é o que o comando `estado` já faz;
- na telemetria, para a plataforma ver: aí é **mudança de contrato** — uma flag nova em
  `Flag::` e em `canonical.FLAG_ORDER`, com todo o processo do pedido 1.

Antes de acrescentar uma flag, leia [D-08](../defeitos-conhecidos.md#d-08): a
`Flag::spooled` existe, é serializada e **nunca é ligada**. Uma flag a mais que ninguém
liga é pior do que nenhuma.

*Teste:* `test_spool.cpp`, enchendo até 80% e verificando a transição — o teste já enche o
spool inteiro em milissegundos, sem hardware.
</details>

---

### Pedido 7

> "A página da colmeia demora 4 segundos para abrir quando escolho 30 dias."

<details>
<summary>Resposta</summary>

Antes de mexer em qualquer coisa: **meça**. "Demora" pode ser a consulta, a reamostragem
em Python, o volume de JSON indo para o navegador, ou o Chart.js desenhando milhares de
pontos. São quatro correções diferentes.

O suspeito já está documentado: [D-07](../defeitos-conhecidos.md#d-07) — `db.py` cria os
agregados contínuos `measurements_1h` e `measurements_1d` do TimescaleDB, e
`services/series.py` **sempre** lê a tabela bruta e reamostra em Python. Trinta dias a
cada 5 minutos são quase nove mil linhas por métrica para desenhar algumas centenas de
pixels.

*Onde:* `services/series.py`, escolhendo a fonte pela janela.

*Teste:* os testes de lacuna e de reamostragem que já existem em `test_series.py` **são a
rede de segurança** — o contrato de `series()` não muda, então eles precisam continuar
passando. É o padrão a procurar sempre: uma mudança de desempenho que faz um teste de
comportamento cair não é otimização, é regressão.
</details>

---

### Pedido 8

> "Um nó foi roubado. Quero apagar tudo dele do banco."

<details>
<summary>Resposta</summary>

Este pedido é uma armadilha, e a resposta certa é **fazer uma pergunta antes de escrever
código**: apagar o *nó* ou apagar as *medições*?

- `Measurement.node_id` é **texto**, não uma chave estrangeira. O comentário em
  `models.py` diz por quê: "uma leitura precisa continuar rastreável ao nó mesmo que o
  cadastro dele seja removido". Ou seja, apagar a linha de `nodes` **não** apaga as
  medições, de propósito.
- As medições daquela colmeia são dado científico coletado. Apagá-las abre uma lacuna
  permanente na série — e completude é justamente o que o Edital 17 se compromete a
  reportar.

Quase sempre o que se quer é **marcar o nó como inativo** e encerrar o vínculo
(`NodeAssignment.removed_at`), preservando a série. Se for mesmo para apagar, é uma
decisão de projeto com prestação de contas, não uma rota nova.

*Lição:* nem todo pedido vira código. A regra do guia — **quando não souber, pergunte
antes de adivinhar** — vale também para "o pedido faz sentido?".
</details>

## Critério de pronto

- [ ] Você respondeu os oito antes de abrir os gabaritos
- [ ] Você acertou que o pedido 1 **começa no contrato**
- [ ] Você percebeu que o pedido 8 não é um pedido de código

Errar não é problema — errar e não entender por que é. Se alguma resposta te surpreendeu,
volte ao documento do guia que ela cita antes de seguir.

## O que levar daqui

**"Do que isso precisa para funcionar?" responde quase toda dúvida de camada.** Só
aritmética → onde o teste alcança. Banco → serviço. HTTP → view. Wire/WiFi/NVS →
`MelipoHardware`.

**Mudança que atravessa firmware e plataforma começa no contrato.** Sempre. Começar por um
dos lados garante que o outro vai discordar, e a discordância só aparece em campo.

**Antes de criar, procure.** Nos oito pedidos, quatro já tinham metade da estrutura pronta
no repositório — e três já eram defeitos conhecidos documentados.

→ Próximo: [Mutantes do firmware](04-mutantes-do-firmware.md)
