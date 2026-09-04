# 5. Engenharia de software

O que muda quando o código deixa de ser seu e passa a ser da equipe. Nada aqui é
específico do MelipoNet — mas todos os exemplos são.

## Git: o histórico é o produto

Git guarda o histórico do projeto. Não é backup: é a possibilidade de responder "quando
isso mudou, por quê, e o que mais mudou junto".

### Os quatro comandos do dia a dia

```bash
git status            # o que mudou desde o último commit
git diff              # exatamente o que mudou, linha a linha
git add <arquivo>     # marca o que vai no próximo commit
git commit            # registra
```

### Sempre trabalhe numa branch

```bash
git switch -c firmware/leitura-sht30    # cria e entra
# ... trabalha, commita ...
git push -u origin firmware/leitura-sht30
```

Uma **branch** é uma linha de trabalho paralela. Você mexe nela sem afetar a `main`, que
é a versão que sempre funciona. Quando terminar, abre um **pull request** — um pedido
para juntar seu trabalho à `main`, que outra pessoa revisa antes.

Nomes: `firmware/...`, `plataforma/...`, `docs/...`.

### Commits

Um commit é uma unidade lógica de mudança. Não é "fim do dia".

- ✅ "Adiciona leitura do SHT30 externo com detecção de sensor ausente"
- ❌ "ajustes"
- ❌ "wip"
- ❌ um commit com o driver do SHT30, uma correção de CSS e um `print` de depuração

A mensagem tem duas partes:

```
Uma linha dizendo O QUE mudou

E um parágrafo dizendo POR QUÊ. O "o quê" o diff já mostra; o "por quê"
só existe na sua cabeça, e daqui a seis meses não vai mais estar lá.
```

Escreva o "por quê" pensando em você mesmo em dezembro tentando lembrar por que aquela
linha existe.

### O que nunca vai para o repositório

| Não commitar | Por quê |
|---|---|
| senhas, tokens, credenciais de WiFi | vazam para sempre — o histórico do git não esquece |
| `.venv/`, `.pio/`, `__pycache__/` | são gerados; cada máquina tem os seus |
| `*.sqlite3` | banco local, muda a cada execução |
| binários compilados | idem |

O `.gitignore` já cuida disso. Se `git status` mostrar algo dessa lista, avise em vez de
commitar.

**Se você commitar uma senha por engano, avise imediatamente.** Apagar num commit
seguinte não resolve: ela continua no histórico. A senha precisa ser trocada.

## Ambiente virtual: por que não `pip install` direto

```bash
python3 -m venv .venv                 # cria um Python isolado para este projeto
.venv/bin/pip install -e ".[dev]"     # instala as dependências dentro dele
```

Sem isso, todos os projetos da sua máquina dividem as mesmas bibliotecas. Instalar algo
para o MelipoNet quebra o trabalho da disciplina de Sinais, e vice-versa. E na hora de
descobrir de que o projeto realmente depende, ninguém sabe.

`pyproject.toml` declara as dependências com versão. É o equivalente ao `lib_deps` do
`platformio.ini`.

## Testes

Provavelmente sua experiência de teste é `printf` e olhar o monitor serial. Um teste
automatizado é a mesma ideia, com duas diferenças: a verificação é feita pelo
computador, e ele roda de novo sozinho para sempre.

```python
def test_reenvio_do_spool_e_idempotente(scenario):
    with session_scope() as session:
        primeiro = store(session, decode(message(7)))
    with session_scope() as session:
        de_novo = store(session, decode(message(7)))

    assert primeiro.stored
    assert de_novo.duplicate
```

### Por que aqui os testes valem mais do que a média

Repita para si: **o erro aparece tarde e caro neste projeto**. Um nó com firmware errado
está lacrado numa colmeia a 130 km. Uma série corrompida só se revela quando alguém vai
escrever o artigo.

O teste é o que traz a descoberta do erro para a sua máquina, antes do commit.

### O que testar

Teste o comportamento que você teria medo de quebrar. Alguns exemplos reais deste
repositório, e o que cada um protege:

| Teste | O que ele impede |
|---|---|
| vetores dourados | firmware e plataforma divergirem sem ninguém notar |
| reenvio idempotente | a série ganhar pontos duplicados a cada reconexão |
| lacuna vira `null` | o gráfico desenhar uma reta por cima de dados perdidos |
| escopo por organização | um meliponicultor ver as colmeias de outro |
| nó remanejado | a série da colmeia antiga migrar para a nova |

Repare que **cada um desses foi escrito depois de um bug real**. É o padrão normal:
achou um bug, escreva o teste que o pega, depois corrija.

### Rodando

```bash
cd platform && .venv/bin/pytest        # plataforma
pio test -e native -d firmware         # firmware, no PC
```

Ou, da raiz, `./verificar` — que roda os dois mais o `ruff` e a checagem dos vetores
dourados, exatamente como o CI.

### Descobrindo o que cada teste protege

Uma suíte verde é um número, e número não ensina nada. A forma mais rápida de descobrir o
que aqueles testes afirmam é **quebrar o código de propósito e ver quem reclama** — é o
assunto do bloco de mutantes da [trilha de exercícios](11-trilha-de-exercicios.md).

Ele também mostra o outro lado: mutações que **nenhum** teste pega. Elas existem, são
defeitos de verdade, e encontrá-las é uma das contribuições mais úteis que alguém novo
pode fazer aqui.

## Integração contínua

Todo push dispara o GitHub Actions, que roda os mesmos comandos numa máquina limpa.
Isso pega a categoria de bug mais irritante que existe: o que funciona na sua máquina
porque você tem algo instalado que ninguém mais tem.

Três verificações:

| Job | O que garante |
|---|---|
| `contrato` | os vetores dourados estão atualizados |
| `plataforma` | `ruff` e `pytest` passam |
| `firmware` | o codec C++ reproduz os vetores |

**PR com CI vermelho não é revisado.** Corrija antes de pedir revisão.

## Revisão de código

Todo código entra na `main` por pull request revisado. Não é desconfiança — é a forma
mais barata de achar erro, e a forma mais rápida de aprender o que os outros sabem.

**Como autor:** PR pequeno. Explique o *porquê* na descrição. Se você mexeu em algo que
não entendeu bem, diga isso — economiza tempo de todo mundo.

**Como revisor:** pergunte em vez de acusar ("o que acontece se o sensor não responder
aqui?" em vez de "isso está errado"). Distinga o obrigatório do opinativo. E aprove
quando estiver bom — PR parado é trabalho parado.

## Ler um erro

Python imprime um *traceback*. **Leia de baixo para cima**: a última linha é o erro, e
as de cima mostram o caminho até ele.

```
sqlalchemy.orm.exc.DetachedInstanceError: Parent instance <Hive> is not bound
to a Session; lazy load operation of attribute 'apiary' cannot proceed
```

Isso diz tudo: um objeto `Hive`, a relação `apiary`, fora de uma sessão. A causa é a
armadilha de lazy loading descrita em [A plataforma Flask](03-a-plataforma-flask.md).

Se a mensagem não fizer sentido, **cole ela inteira** ao pedir ajuda. A metade que você
cortaria costuma ser a que contém a resposta.

## Comentários

Comente o **porquê**, não o **o quê**. O código já diz o quê.

```python
# ❌ inútil
# incrementa o contador
counter += 1

# ✅ útil
# A seq avança mesmo nas leituras puladas: é assim que o nó real se comporta,
# e é o que torna a perda contável do lado da plataforma.
```

Se um trecho precisa de comentário para ser entendido, considere primeiro se ele não
poderia ser mais claro. Mas quando a razão é uma decisão de projeto, uma armadilha da
plataforma ou algo aprendido em campo, **escreva**. É informação que não está em lugar
nenhum além da sua cabeça.

## Separação de responsabilidades

O princípio por trás das camadas na plataforma e da divisão lógica/hardware no firmware
é o mesmo: **cada peça faz uma coisa e depende do mínimo possível**.

Não é estética. É o que permite:

- testar a lógica sem hardware e sem servidor;
- trocar WiFi por LoRa sem tocar em nada depois do broker;
- duas pessoas trabalharem ao mesmo tempo sem colidir.

Quando não souber onde pôr um código, pergunte: **do que isso precisa para funcionar?**
Se precisa só de aritmética, é lógica pura — ponha onde possa ser testado. Se precisa do
banco, é serviço. Se precisa da requisição HTTP, é view.

→ Próximo: [Primeira contribuição](06-primeira-contribuicao.md)
