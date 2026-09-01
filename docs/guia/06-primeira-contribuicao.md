# 6. Primeira contribuição

Um roteiro do zero até um pull request. Faça uma vez inteiro, mesmo que a mudança seja
pequena — o objetivo é passar por todas as etapas antes de precisar delas com pressa.

## Preparando a máquina

Você precisa de: **git**, **Python 3.11+** e, se for mexer em firmware,
**PlatformIO**.

```bash
git clone https://github.com/lacouth/meliponet.git
cd meliponet
```

### Plataforma

```bash
cd platform
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest                    # tudo verde? ambiente ok
```

### Firmware

```bash
uv tool install platformio          # ou: pipx install platformio
pio test -e native -d firmware      # roda no PC, não precisa de placa
```

Se `pio` não for encontrado depois de instalar, confira que `~/.local/bin` está no
seu `PATH`.

> **Por que não `pip install platformio`.** As distribuições recentes (Arch, Debian
> 12+, Ubuntu 24.04+) marcam o Python do sistema como *externally managed* (PEP 668) e
> recusam a instalação, para que um `pip install` não quebre pacotes do sistema. É a
> mesma razão pela qual a plataforma usa ambiente virtual. `uv tool` e `pipx` instalam
> cada ferramenta num ambiente isolado próprio, o que resolve o problema sem sudo.

**Para gravar na placa** (só quando você tiver hardware em mãos), o Linux precisa das
regras de acesso à porta USB, senão o `upload` falha por permissão:

```bash
sudo pacman -S platformio-core-udev     # Arch
# outras distribuições: veja docs.platformio.org/en/latest/core/installation/udev-rules.html
```

## Vendo o sistema rodar

Antes de mexer, veja funcionando. Isso dá o modelo mental que nenhum documento dá.

```bash
cd platform
export DATABASE_URL="sqlite:///$PWD/../meliponet-dev.sqlite3"

# 1. cria o banco
.venv/bin/python -m alembic upgrade head

# 2. cria seu usuário
.venv/bin/python -m flask --app "meliponet:create_app" criar-usuario \
  --email voce@exemplo.br --nome "Seu Nome" --organizacao "Teste" --perfil admin

# 3. gera 48 h de dados sintéticos, com falhas injetadas
cd .. && platform/.venv/bin/python -m simulator --transporte direto --historico 48 \
  --organizacao "Teste"

# 4. sobe o servidor
cd platform && .venv/bin/python -m flask --app "meliponet:create_app" run
```

Abra `http://127.0.0.1:5000` e entre.

Para ver o painel se atualizando sozinho, deixe o simulador emitindo em outro terminal:

```bash
platform/.venv/bin/python -m simulator --transporte direto --historico 0 \
  --tempo-real --organizacao "Teste"
```

### Explore antes de codar

Vale gastar meia hora aqui:

- Abra uma colmeia e alterne as janelas de 24 h / 7 dias / 30 dias.
- Procure os **buracos** nos gráficos. São as lacunas que o simulador injeta de
  propósito. O gráfico mostra o buraco em vez de ligar os pontos vizinhos — porque
  esconder a perda seria mentir sobre a completude.
- Vá em **Cadastros** e olhe a tela de vínculo nó↔colmeia.
- No terminal, veja o banco por dentro:

```bash
sqlite3 meliponet-dev.sqlite3 "SELECT time, temp_in_c, temp_out_c, weight_kg
                               FROM measurements ORDER BY time DESC LIMIT 5;"
```

## O ciclo de trabalho

### 1. Branch

```bash
git switch main && git pull
git switch -c plataforma/exportar-csv
```

### 2. Mexa

Antes de escrever, ache onde a coisa já é feita de forma parecida. Copiar o padrão
existente vale mais do que inventar um novo — e se o padrão existente estiver ruim,
esse é um bom assunto para o PR.

### 3. Escreva o teste

Se corrigiu um bug: escreva o teste que pega aquele bug. Rode antes da correção para ver
falhar — um teste que passa mesmo com o bug presente não testa nada.

### 4. Verifique tudo

```bash
cd platform && .venv/bin/pytest
cd .. && platform/.venv/bin/python -m ruff check platform contracts simulator
pio test -e native -d firmware                      # se mexeu no firmware
python3 contracts/tools/gen_testdata.py --check     # se mexeu no contrato
```

### 5. Commit

```bash
git status          # confira que não entrou senha, .venv, banco
git diff            # releia o que você mesmo escreveu
git add -p          # adiciona por pedaço, revisando cada um
git commit
```

O `git add -p` te obriga a olhar cada trecho antes de commitar. É a forma mais barata de
pegar um `print` de depuração esquecido.

### 6. Pull request

```bash
git push -u origin plataforma/exportar-csv
```

Na descrição, responda: **o que muda**, **por que**, e **como você verificou**.

Espere o CI ficar verde e peça revisão.

## Tarefas boas para começar

Escolhidas por serem pequenas, reais e por te fazerem passar pelo caminho inteiro.

**Plataforma**

- Acrescentar a janela de 90 dias no dashboard (`services/series.py`, `WINDOWS`).
- Mostrar o RSSI num card da página da colmeia.
- Exportar as medições de uma colmeia em CSV.
- Melhorar a página de erro 404.

**Firmware**

- Implementar `ShtPair` lendo os dois SHT30 (0x44 e 0x45), com teste nativo da conversão
  para inteiro escalado.
- Implementar a rotina de calibração do HX711 por comando serial.
- Escrever o teste nativo do `Spool` (grava, reinicia, drena na ordem certa).

**Contrato e documentação**

- Acrescentar um vetor dourado para um caso de borda ainda não coberto.
- Corrigir qualquer coisa errada neste guia. Se você tropeçou em algo, a próxima pessoa
  também vai.

## Quando travar

Antes de pedir ajuda, junte:

1. **o comando exato** que você rodou;
2. **a mensagem de erro inteira** (não um pedaço);
3. **o que você já tentou**.

Isso faz a diferença entre uma resposta em cinco minutos e uma conversa de meia hora
para descobrir o que aconteceu. E não fique travado sozinho por horas — perguntar cedo é
o comportamento certo, não o oposto.

→ Consulta rápida: [Glossário](07-glossario.md)
