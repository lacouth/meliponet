# Como contribuir

Este arquivo é o atalho. O caminho completo, com o porquê de cada passo, está em
[docs/guia/06-primeira-contribuicao.md](docs/guia/06-primeira-contribuicao.md), e vale a
pena ler antes do primeiro pull request.

## Preparar a máquina

    git clone https://github.com/lacouth/meliponet.git
    cd meliponet

    cd platform
    python3 -m venv .venv
    .venv/bin/pip install -e ".[dev]"
    cd ..

    uv tool install platformio      # ou: pipx install platformio

Não use `pip install platformio`: as distribuições recentes recusam a instalação no Python
do sistema (PEP 668).

## O ciclo

    git switch -c minha-branch
    # mexa, e escreva o teste
    ./verificar
    git commit -am "área: o que mudou"
    git push -u origin minha-branch

`./verificar` roda as mesmas quatro verificações que o CI roda a cada push: o contrato, o
`ruff`, o `pytest` e os testes nativos do firmware. Se faltar alguma ferramenta, ele diz
qual e como instalar. Rode antes de **cada** commit.

Depois abra o pull request. O modelo pede três blocos — o que muda, por quê, como
verifiquei — porque são as três perguntas que qualquer revisor faria.

## O que é bom saber antes

- **O código é escrito em português**, e para quem vem do Arduino. A exceção são os nomes
  que aparecem no contrato JSON, que ficam letra por letra como o contrato os escreve. As
  regras estão em [CLAUDE.md](CLAUDE.md).
- **`contracts/testdata/` é gerado**, não editado à mão.
- **Commits pequenos e verdes**, um assunto por commit.

## Por onde começar

- [A trilha de exercícios](docs/guia/11-trilha-de-exercicios.md) — quinze exercícios com
  critério de pronto que você confere sozinho.
- [Defeitos conhecidos](docs/defeitos-conhecidos.md) — o que está errado e ainda não foi
  corrigido.
- [Como nós nos organizamos](docs/guia/12-como-nos-organizamos.md) — o quadro de tarefas,
  as frentes e a cadência.

## Quando travar

Pergunte. Trinta minutos travado já é motivo suficiente, e ninguém neste projeto vai achar
ruim uma pergunta básica — está escrito no [guia](docs/guia/README.md) e é para valer.
