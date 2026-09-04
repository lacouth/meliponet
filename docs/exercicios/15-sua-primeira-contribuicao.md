# 15. Sua primeira contribuição

**Área:** você escolhe · **Contribuição** · **Sem gabarito**

## Por que este exercício existe

Os catorze anteriores tinham resposta em algum lugar — dobrada no fim da página, ou num
teste que dizia se você chegou lá. Este não tem.

É de propósito. A partir daqui, o que decide se o trabalho está bom é a revisão de outra
pessoa, e o que você precisa ter aprendido é **como chegar até ela**: um problema escolhido
com critério, um teste que prova a correção, um registro atualizado e uma descrição que
alguém consiga revisar sem te perguntar nada.

## Passo 1 — escolha

Abra [docs/defeitos-conhecidos.md](../defeitos-conhecidos.md) e leia a tabela de abertos
inteira. Escolha **um** — e combine com o orientador antes de começar, para não duplicar
trabalho.

Como escolher:

| Se você… | Olhe para |
|---|---|
| quer algo pequeno e fechado | [D-16](../defeitos-conhecidos.md#d-16) (CSRF), [D-18](../defeitos-conhecidos.md#d-18) (organização no cadastro) |
| quer algo com consequência visível | [D-02](../defeitos-conhecidos.md#d-02) (medições órfãs), [D-17](../defeitos-conhecidos.md#d-17) (vínculo não editável) |
| quer mexer em firmware | [D-05](../defeitos-conhecidos.md#d-05) (re-sondagem periódica), [D-08](../defeitos-conhecidos.md#d-08) (`Flag::spooled`) |
| quer decidir em vez de codar | [D-08](../defeitos-conhecidos.md#d-08) — a correção pode ser **apagar código**, e defender isso é a entrega |
| quer algo grande | [D-01](../defeitos-conhecidos.md#d-01) (QoS 1 de verdade) — combine antes, é uma troca de biblioteca |

Se você tropeçou em algo que não está na lista, isso também vale — e **acrescentar a
entrada** já é uma contribuição, mesmo que você não corrija agora.

## Passo 2 — antes de escrever código

Três perguntas. Se você não souber responder alguma, pergunte antes de começar.

1. **Qual é o sintoma no mundo?** O que a pessoa que usa o sistema vê acontecer. Se você só
   consegue descrever o que está errado no código, ainda não entendeu o defeito.
2. **Como eu reproduzo?** Um comando, um teste, um clique. Sem reprodução, não há como
   saber que a correção funcionou — só que o código mudou.
3. **O que mais depende disso?** Rode `grep` pelo nome da função. Uma correção que conserta
   uma chamada e quebra outra é uma regressão com boa intenção.

## Passo 3 — o ciclo

Já é o de [Primeira contribuição](../guia/06-primeira-contribuicao.md#o-ciclo-de-trabalho).
O que a trilha acrescenta é a ênfase no primeiro item:

1. **Branch** a partir da `main` atualizada.
2. **O teste que pega o defeito** — e rode-o **antes** da correção, para vê-lo falhar. Você
   já viu, no exercício [07](07-o-mutante-que-ninguem-pega.md), que um teste que nunca
   falhou é uma suposição.
3. **A correção**, a menor que resolve.
4. **`./verificar`** — o novo passa e nenhum antigo quebrou.
5. **O registro**: sai dos abertos, entra em Resolvidos, no **mesmo commit**.
6. **Commit**: o quê numa linha, o porquê num parágrafo. `git add -p` para reler cada
   trecho.
7. **PR**: o que muda, por quê, como você verificou.

### Se o defeito não tiver como ser testado

Acontece — [D-04](../defeitos-conhecidos.md#resolvidos) foi assim: o comando vivia num
arquivo que depende do Arduino, e a chamada que faltava era para um objeto que só existe
com hardware.

Nesse caso, **diga isso no commit**, e diga como a verificação foi feita na bancada. É o
que aquele commit fez. Silenciar a ausência de teste é pior do que admiti-la — quem ler
depois vai supor que existe cobertura.

E vale a pergunta seguinte: **dá para mover a lógica para onde um teste alcança?** Foi o
que o commit `7ea2093` fez com o recuo e a fila do spool — a correção real não foi a linha,
foi trazer o caso para `MelipoCore`.

## Passo 4 — a descrição do PR

Três blocos. Sem enfeite.

**O que muda.** Uma ou duas frases.

**Por quê.** O sintoma no mundo, não a linha errada. *"Quem executa o comando acredita ter
revogado o acesso e não revogou"* é melhor do que *"faltava checar `is_active`"*.

**Como verifiquei.** O teste que você viu falhar, e o que ele afirma. Se houve verificação
manual, quais passos.

E, se for o caso: **o que ficou de fora.** Um PR que resolve metade e diz qual metade é
melhor do que um que resolve metade em silêncio.

## Passo 5 — a revisão

Espere o CI ficar verde antes de pedir revisão: **PR com CI vermelho não é revisado.**

Quando os comentários chegarem, lembre que a revisão é sobre o código, não sobre você — e
que ela é, segundo o guia, *"a forma mais barata de achar erro, e a forma mais rápida de
aprender o que os outros sabem"*.

Duas coisas úteis de fazer como autor:

- **Se você mexeu em algo que não entendeu bem, diga na descrição.** Economiza o tempo de
  todo mundo, e é o oposto de fraqueza: é o que permite ao revisor olhar no lugar certo.
- **Discordar é legítimo**, desde que com argumento. Um revisor que sugere algo pior deve
  ser respondido, não obedecido. O exemplo está no próprio registro: a correção sugerida
  para [D-08](../defeitos-conhecidos.md#d-08) pode muito bem ser apagar a flag, e defender
  isso é uma resposta melhor do que implementá-la.

## Critério de pronto

- [ ] O defeito foi combinado com o orientador antes de você começar
- [ ] Você reproduziu o defeito **antes** de corrigi-lo
- [ ] O teste falhou antes da correção — ou você explicou no commit por que não há teste
- [ ] `./verificar` verde
- [ ] O registro de defeitos foi atualizado no mesmo commit
- [ ] A descrição do PR responde: o que muda, por quê, como verifiquei
- [ ] O CI está verde **antes** de você pedir revisão

## Depois

Terminada a trilha, o repositório passa a ser o guia. Duas coisas que continuam valendo:

**Acrescente ao registro o que você encontrar e não for corrigir.** Custa três minutos e
poupa um dia de outra pessoa. É a mesma razão pela qual o registro existe.

**Corrija o que estiver errado nesta trilha.** Se você tropeçou em alguma instrução, em
alguma conta, ou numa resposta que não bate mais com o código, a próxima pessoa vai
tropeçar no mesmo lugar. Um dos exercícios já te fez encontrar um número errado no registro
de defeitos — documentação é código que ninguém executa.

E a regra que vale mais do que o guia inteiro: **quando não souber, pergunte antes de
adivinhar.** Uma pergunta custa cinco minutos. Um nó reprogramado em campo custa uma viagem
a Campina Grande.

→ Volta ao começo: [Trilha de exercícios](../guia/11-trilha-de-exercicios.md) ·
[Glossário](../guia/07-glossario.md)
