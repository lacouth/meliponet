# Guia do MelipoNet

Este guia é para quem vai trabalhar no projeto e vem da Engenharia Elétrica. Ele assume
que você sabe programar em C e conhece microcontroladores, e **não** assume que você já
trabalhou num projeto de software com mais de uma pessoa, com testes, controle de versão
e revisão de código.

Essas práticas não são burocracia acadêmica. Elas existem porque este projeto tem uma
característica incômoda: **o erro aparece tarde e caro**. Um nó com firmware errado já
está lacrado dentro de uma colmeia num meliponário em Puxinanã. Uma série de temperatura
corrompida só se revela quando alguém tenta escrever o artigo, meses depois. Quase tudo
neste repositório existe para empurrar a descoberta do erro para mais cedo — de
preferência para a sua máquina, antes do commit.

## Os seis documentos

| | Documento | Do que trata |
|---|---|---|
| 1 | [O sistema](01-o-sistema.md) | o que estamos construindo e como as peças se ligam |
| 2 | [A mensagem](02-a-mensagem.md) | o acordo entre o nó e a plataforma |
| 3 | [A plataforma](03-a-plataforma.md) | o Flask por dentro: rotas, camadas, banco |
| 4 | [O nó sensor](04-o-no-sensor.md) | as peças, a ligação e o que erra quando erra |
| 5 | [Como trabalhamos](05-como-trabalhamos.md) | git, ambiente, testes, revisão, organização |
| 6 | [Glossário](06-glossario.md) | consulta rápida |

Leia na ordem, mas **não leia tudo antes de começar**: ler não fixa. A ordem de verdade
está na **[trilha](../trilha.md)**, que intercala os documentos com exercícios de fazer —
do ambiente montado ao seu nó publicando no gráfico.

E o roteiro do que você vai programar está em
**[`firmware/ROTEIRO.md`](../../firmware/ROTEIRO.md)**.

Na mesma estante: [defeitos conhecidos](../defeitos-conhecidos.md), o registro do que já
está errado e ainda não foi corrigido. Vale ler antes de passar uma tarde depurando um
comportamento estranho, e vale acrescentar uma entrada quando você encontrar um e não for
corrigi-lo na hora.

## Regra que vale mais do que o guia inteiro

**Quando não souber, pergunte antes de adivinhar.** Uma pergunta custa cinco minutos. Um
nó reprogramado em campo custa uma viagem a Campina Grande, e uma série corrompida pode
custar meses de coleta. Ninguém neste projeto vai achar ruim uma pergunta básica.
