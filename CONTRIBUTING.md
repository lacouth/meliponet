# Como contribuir

Este arquivo é o atalho. O caminho completo, com o porquê de cada passo, está em
[docs/guia/05-como-trabalhamos.md](docs/guia/05-como-trabalhamos.md), e vale a pena ler
antes do primeiro pull request.

## Preparar a máquina

    git clone https://github.com/lacouth/meliponet.git
    cd meliponet

    cd platform
    python3 -m venv .venv
    .venv/bin/pip install -e ".[dev]"
    cd ..

É só isso: git e Python 3.11+. O firmware do nó é escrito com a ferramenta que você
preferir, fora deste repositório — ver [firmware/ROTEIRO.md](firmware/ROTEIRO.md).

## O ciclo

    git switch -c minha-branch
    # mexa, e escreva o teste
    ./verificar
    git commit -am "área: o que mudou"
    git push -u origin minha-branch

`./verificar` roda as mesmas duas verificações que o CI roda a cada push: o `ruff` e o
`pytest`. Se faltar alguma ferramenta, ele diz qual e como instalar. Rode antes de **cada**
commit.

Depois abra o pull request. O modelo pede três blocos — o que muda, por quê, como
verifiquei — porque são as três perguntas que qualquer revisor faria.

## O que é bom saber antes

- **O código é escrito em português**, e para quem vem do Arduino. A exceção são os nomes
  que aparecem no contrato JSON, que ficam letra por letra como o contrato os escreve. As
  regras estão em [CLAUDE.md](CLAUDE.md).
- **O firmware do nó não mora aqui.** Ele é exercício, e o roteiro está em
  [firmware/ROTEIRO.md](firmware/ROTEIRO.md).
- **Commits pequenos e verdes**, um assunto por commit.

## Por onde começar

- [A trilha](docs/trilha.md) — oito exercícios e o roteiro do nó, cada um com critério de
  pronto que você confere sozinho.
- [Defeitos conhecidos](docs/defeitos-conhecidos.md) — o que está errado e ainda não foi
  corrigido.
- [Como trabalhamos](docs/guia/05-como-trabalhamos.md) — git, testes, revisão, e o quadro
  de tarefas.

## Quando travar

Pergunte. Trinta minutos travado já é motivo suficiente, e ninguém neste projeto vai achar
ruim uma pergunta básica — está escrito no [guia](docs/guia/README.md) e é para valer.
