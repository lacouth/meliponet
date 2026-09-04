# 09. Desativar usuário encerra a sessão

**Área:** plataforma · **Tempo:** ~2 h · **Contribuição** — corrige [D-15](../defeitos-conhecidos.md#d-15)

> **Combine antes de começar.** Este exercício corrige um defeito real e vira um PR. Só uma
> pessoa deve fazê-lo.

## Por que este exercício existe

É o primeiro defeito de verdade da trilha, e ele foi escolhido por uma razão específica: é
uma falha de segurança **que dá a impressão contrária**.

Alguém sai do projeto. O orientador marca `is_active = false` no banco e acredita ter
revogado o acesso. Não revogou: quem já estava logado continua navegando, e o cookie
permanente faz isso durar. Ninguém recebe erro, nada aparece no log, e a pessoa que
executou o comando não tem como saber que ele não fez efeito.

Compare com um defeito barulhento — um nó que para de publicar. Esse alguém nota. Este,
não.

## Antes de começar

- Exercício [08](08-uma-janela-nova.md) feito.
- Leia [D-15](../defeitos-conhecidos.md#d-15) inteiro.
- Leia `platform/meliponet/blueprints/auth.py` e a função `load_user` em
  `platform/meliponet/__init__.py`.

```bash
git switch main && git pull
git switch -c plataforma/desativar-encerra-sessao
```

## Entenda antes de corrigir

Responda, lendo o código:

> **Pergunta 1.** `auth.login` já verifica `user.is_active`. Por que isso não basta?
>
> **Pergunta 2.** Por onde passa **toda** requisição autenticada?
>
> **Pergunta 3.** O login é feito com `remember=True`. O que isso muda na gravidade?

<details>
<summary>Respostas</summary>

**1.** Porque a verificação acontece **uma vez**, no momento de entrar. Quem já entrou não
passa por ela de novo. Desativar alguém logado não tem efeito nenhum sobre a sessão em
curso.

**2.** Pelo `user_loader` — a função `load_user` em `meliponet/__init__.py`. É o Flask-Login
chamando, a cada requisição, "quem é o usuário deste cookie?". Ela hoje devolve o usuário
sem olhar `is_active`.

Esse é o ponto de estrangulamento, e é por isso que a correção cabe ali: é o único lugar
por onde tudo passa. É o mesmo raciocínio de `services/scope.py` — concentrar a regra onde
não dá para esquecê-la.

**3.** `remember=True` grava um cookie permanente. Sem ele, a sessão morreria ao fechar o
navegador e o problema teria prazo de validade. Com ele, o acesso do desativado dura
semanas.
</details>

## Passos

### 1. O teste, primeiro — e ele precisa falhar

Em `platform/tests/test_web.py`. O teste tem de reproduzir a história do defeito, nesta
ordem:

1. criar um usuário e autenticá-lo (a fixture `login` já faz isso);
2. confirmar que ele **acessa** uma página protegida;
3. marcar `is_active = False` no banco, como faria o orientador;
4. afirmar que a próxima requisição **não** é mais atendida.

Sobre o passo 4: uma página protegida por `@login_required` responde `302` para o
`/entrar` quando não há usuário autenticado — é o que
`test_paginas_exigem_login` já verifica. Use o mesmo critério.

```bash
platform/.venv/bin/pytest platform/tests/test_web.py -q
```

Ele **tem** de falhar agora. Se passar, ele não está reproduzindo o defeito — reveja o
passo 2 (o usuário estava mesmo logado?) e o passo 3 (a mudança foi mesmo persistida?).

### 2. Corrija

No `user_loader`. A correção é curta.

Um cuidado: `load_user` devolve `None` para "não há usuário válido neste cookie" — é assim
que o Flask-Login entende que ninguém está autenticado.

### 3. Verifique tudo

```bash
./verificar plataforma
```

O teste novo passa **e** os que já existiam continuam verdes. O segundo é tão importante
quanto o primeiro: uma correção que quebra o login de todo mundo não é uma correção.

### 4. Feche o registro do defeito

Isto faz parte do commit, e não de um "depois" — é o que
[o registro de defeitos](../defeitos-conhecidos.md#como-usar) manda:

- remova a linha **D-15** da tabela de abertos;
- remova a seção `### D-15`;
- acrescente uma linha em **Resolvidos**, com a data e o que foi feito.

E não reaproveite o número: `D-15` está aposentado, para que uma referência antiga num
commit ou numa conversa continue fazendo sentido.

### 5. Commit e PR

```bash
git status
git diff
git add -p
git commit
git push -u origin plataforma/desativar-encerra-sessao
```

A mensagem precisa contar **o sintoma no mundo** — "quem executou o comando acredita ter
revogado o acesso e não revogou" —, não só o que mudou no código. Releia as mensagens dos
commits do exercício [01](01-tudo-verde.md) como modelo.

Na descrição do PR: o que muda, por quê, e como você verificou (o teste falhando antes).

## Critério de pronto

- [ ] O teste falhou antes da correção — você viu a falha
- [ ] `./verificar` verde
- [ ] D-15 saiu da tabela de abertos e entrou em Resolvidos, **no mesmo commit**
- [ ] A mensagem do commit descreve o sintoma, não só a mudança

## Pistas

<details>
<summary>Meu teste passa antes da correção</summary>

O suspeito mais provável é o passo 3: a mudança no banco não foi persistida, ou foi feita
num objeto de outra sessão. Use `session_scope()` e busque o usuário pelo e-mail dentro
dele — como fazem os outros testes de `test_web.py`.

Confirme também o passo 2: um `assert client.get("/colmeias").status_code == 200` antes de
desativar prova que o login pegou. Sem essa âncora, um teste que "passa" pode estar só
verificando que ninguém nunca entrou.
</details>

<details>
<summary>Corrigi e agora vários testes falham</summary>

Cuidado com a ordem das checagens dentro do `load_user`: se você tentar ler
`user.organization.name` antes de decidir devolver `None`, um usuário inativo pode estourar
em vez de simplesmente não autenticar. Devolva `None` cedo.

E confira que você não inverteu a condição — `is_active` verdadeiro é o caso normal.
</details>

<details>
<summary>Vale a pena testar também que o desativado não consegue entrar de novo?</summary>

Já existe: `auth.login` verifica `is_active` e há teste para o login. O buraco era só a
sessão já aberta. Mas se você quiser deixar isso explícito com um teste, não custa nada e
documenta a regra inteira num lugar só.
</details>

## O que levar daqui

**Verificação feita uma vez não é verificação contínua.** A pergunta que resolve essa
classe inteira de bug é "por onde passa toda requisição?" — e a resposta é onde a regra
deve morar.

**A pior falha de segurança é a que dá a impressão contrária.** Um acesso negado por engano
alguém reclama. Um acesso concedido por engano ninguém reclama.

**Corrigir inclui fechar o registro.** Uma lista de defeitos que só cresce deixa de ser
lida — e aí volta a ser mais barato redescobrir cada defeito do que consultá-la.

→ Próximo: [Um vetor dourado novo](10-um-vetor-dourado-novo.md)
