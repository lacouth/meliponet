# Guia do bolsista — MelipoNet

Este guia é para quem vai **contribuir com código** no projeto MelipoNet e vem da
Engenharia Elétrica. Ele assume que você sabe programar em C e conhece
microcontroladores, e **não** assume que você já trabalhou num projeto de software com
mais de uma pessoa, com testes, controle de versão e revisão de código.

Essas práticas não são burocracia acadêmica. Elas existem porque este projeto tem uma
característica incômoda: **o erro aparece tarde e caro**. Um nó com firmware errado já
está lacrado dentro de uma colmeia num meliponário em Puxinanã. Uma série de
temperatura corrompida só se revela quando alguém tenta escrever o artigo, meses
depois. Quase tudo neste repositório existe para empurrar a descoberta do erro para
mais cedo — de preferência para a sua máquina, antes do commit.

## Roteiro de leitura

Leia os quatro primeiros na ordem. Depois siga a trilha do que você vai fazer.

| | Documento | Para quem |
|---|---|---|
| 1 | [O sistema](01-o-sistema.md) — o que estamos construindo e como as peças se ligam | todos |
| 2 | [O contrato](02-o-contrato.md) — a peça que permite hardware e software andarem em paralelo | todos |
| 3 | [Do nó ao gráfico](08-do-no-ao-grafico.md) — o sistema hoje, ponta a ponta: identidade do nó, cadastro, visualização, e o que ainda falta | todos |
| 4 | [Engenharia de software](05-engenharia-de-software.md) — git, ambientes, testes, revisão | todos |
| 5a | [A plataforma Flask](03-a-plataforma-flask.md) | quem mexe em `platform/` |
| 5b | [Primeiros passos com o PlatformIO](09-primeiros-passos-com-o-platformio.md) — prática guiada | quem mexe em `firmware/` e nunca usou PlatformIO |
| 5c | [O firmware](04-o-firmware.md) | quem mexe em `firmware/` |
| 5d | [O hardware](10-o-hardware.md) — peças, ligação e primeira energização | quem monta ou liga um nó |
| 6 | [Primeira contribuição](06-primeira-contribuicao.md) — do clone ao pull request | todos |
| — | [Glossário](07-glossario.md) — consulta rápida | todos |

Fora do guia, mas na mesma estante:
[defeitos conhecidos](../defeitos-conhecidos.md) — o registro dos defeitos que já
encontramos e ainda não corrigimos. Vale ler antes de passar uma tarde depurando um
comportamento estranho, e vale acrescentar uma entrada quando você encontrar um e não
for corrigi-lo na hora.

## Regra que vale mais do que o guia inteiro

**Quando não souber, pergunte antes de adivinhar.** Uma pergunta custa cinco minutos.
Um nó reprogramado em campo custa uma viagem a Campina Grande, e uma série corrompida
pode custar meses de coleta. Ninguém neste projeto vai achar ruim uma pergunta básica.
