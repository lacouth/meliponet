# 03. Onde eu mexo?

**Tempo:** ~30 min · **Treino**

## Por que este exercício existe

O erro mais comum de quem chega a um projeto com camadas não é escrever a linha errada —
é escrever a linha **certa na camada errada**. O código funciona, os testes passam, e o
custo aparece meses depois: a lógica que ficou dentro de uma view não pode ser chamada
pelo gerador de relatórios; o cálculo que ficou no laço principal do firmware não pode ser
conferido sem placa.

Este exercício treina a pergunta que resolve isso:
**do que isso precisa para funcionar?**

- Precisa só de aritmética? É lógica pura — `services/` na plataforma, e no seu nó uma
  função que não fala com sensor nenhum. É onde a conferência é fácil.
- Precisa do banco? É serviço.
- Precisa da requisição HTTP? É view.
- Precisa do Wire, do WiFi, da NVS? É a camada de hardware do seu firmware.

## Antes de começar

Faça o exercício [02](02-uma-mensagem-ate-o-grafico.md). Tenha à mão a estrutura de pastas
de [A plataforma](../guia/03-a-plataforma.md#a-estrutura-de-pastas).

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
vai discordar — e a discordância só aparece quando o nó já está na colmeia.

Ordem:

1. `contracts/telemetry.v1.schema.json` — o campo novo, **opcional** (nunca em `required`;
   há nós em campo que ninguém vai reprogramar no mesmo dia).
2. `contracts/mensagem.py` — `ORDEM_DOS_CAMPOS` e `CASAS_DECIMAIS`.
3. `contracts/exemplos/` — um exemplo com o campo, que os testes passam a exigir que a
   plataforma aceite.
4. Plataforma: `models.py` (a coluna), **uma migração Alembic**, e
   `ingest/store.py` → `METRIC_FIELDS`.
5. Interface: `services/series.py` → `METRIC_COLUMNS`, e `templates/_panel.html`.
6. Só então o firmware: o terceiro endereço I²C, a leitura, o campo na mensagem e a flag
   de falha correspondente.

*Teste:* `test_contract.py` já cobre o exemplo novo dos dois lados. Some um teste em
`test_series.py` se a métrica entrar nos gráficos.

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
outra que tem uma queda **lenta** de 2 kg ao longo de um dia (que não deve disparar).

*Cuidado de domínio:* uma queda abrupta de peso pode ser colheita (normal) ou enxameação
(urgente). O simulador injeta colheitas de propósito em `model.py` — a regra tem de
distinguir as duas, ou o produtor desliga o alerta na primeira semana.
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
média desfaz visualmente a perda que o gráfico existe para mostrar — decida isso de
propósito e escreva o teste que fixa a decisão.
</details>

---

### Pedido 4

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

A versão de uma colmeia só é o exercício [07](07-exportar-csv.md).
</details>

---

### Pedido 5

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

### Pedido 6

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
  permanente na série — e completude é justamente o que o projeto se compromete a medir.

Quase sempre o que se quer é **marcar o nó como inativo** e encerrar o vínculo
(`NodeAssignment.removed_at`), preservando a série. Se for mesmo para apagar, é uma
decisão de projeto com prestação de contas, não uma rota nova.

*Lição:* nem todo pedido vira código. A regra do guia — **quando não souber, pergunte
antes de adivinhar** — vale também para "o pedido faz sentido?".
</details>

## Critério de pronto

- [ ] Você respondeu os seis antes de abrir os gabaritos
- [ ] Você acertou que o pedido 1 **começa no contrato**
- [ ] Você percebeu que o pedido 6 não é um pedido de código

Errar não é problema — errar e não entender por que é. Se alguma resposta te surpreendeu,
volte ao documento do guia que ela cita antes de seguir.

## O que levar daqui

**"Do que isso precisa para funcionar?" responde quase toda dúvida de camada.** Só
aritmética → onde a conferência é fácil. Banco → serviço. HTTP → view. Wire/WiFi/NVS →
a camada de hardware do seu firmware.

**Mudança que atravessa o nó e a plataforma começa no contrato.** Sempre. Começar por um
dos lados garante que o outro vai discordar, e a discordância só aparece em campo.

**Antes de criar, procure.** Nos seis pedidos, metade já tinha estrutura pronta no
repositório — e dois já eram defeitos conhecidos documentados.

→ Próximo: [Mutantes da plataforma](04-mutantes-da-plataforma.md)
