# Defeitos conhecidos

Registro dos defeitos que a equipe **já conhece e ainda não corrigiu**. Existe porque a
alternativa é pior: um defeito conhecido que só vive na memória de quem o encontrou
reaparece meses depois como se fosse novo, e quem o reencontra gasta o mesmo dia de
depuração de novo. Pior ainda quando a documentação descreve o comportamento pretendido
e o código faz outra coisa — aí o defeito não é só um bug, é uma armadilha.

Um item aqui não é vergonha nem pendência atrasada. É uma decisão consciente de não
corrigir agora, escrita para que a próxima pessoa não tropece.

## Como usar

- **Ao encontrar um defeito que você não vai corrigir agora**, acrescente uma entrada.
  Custa três minutos e vale um dia de trabalho de outra pessoa.
- **Toda entrada diz como o defeito aparece no mundo**, não só o que está errado no
  código. "Buffer pequeno" não ajuda ninguém; "o nó para de publicar e nada no serial
  explica" ajuda.
- **Ao corrigir**, remova a entrada da tabela de abertos **no mesmo commit da correção**
  e acrescente uma linha em [Resolvidos](#resolvidos). Uma lista que não encolhe deixa
  de ser lida.
- **Ao corrigir, escreva o teste que pega o defeito** e rode-o antes da correção, para
  ver falhar. Vários itens aqui só são detectáveis em campo hoje — mudar isso é parte da
  correção.
- Os identificadores (`D-01`, …) são estáveis: nunca reaproveite o número de um item
  removido, para que uma referência antiga num commit ou numa conversa continue fazendo
  sentido.

## Abertos

| # | Gravidade | Onde | Defeito |
|---|---|---|---|
| [D-02](#d-02) | alta | plataforma | Medições anteriores ao vínculo ficam órfãs para sempre |
| [D-13](#d-13) | alta | plataforma | O registro fotográfico do vínculo não tem como ser anexado |
| [D-06](#d-06) | média | plataforma | O Last Will é publicado e ninguém o assina |
| [D-14](#d-14) | média | plataforma | Não há administração de usuários, apesar de o perfil admin prometê-la |
| [D-15](#d-15) | média | plataforma | Desativar um usuário no banco não encerra a sessão dele |
| [D-16](#d-16) | média | plataforma | Os formulários não têm proteção contra CSRF |
| [D-17](#d-17) | média | plataforma | Nó e vínculo não podem ser corrigidos depois de criados |
| [D-07](#d-07) | baixa | plataforma | Os agregados contínuos são criados e nunca consultados |
| [D-18](#d-18) | baixa | plataforma | O admin não cadastra meliponário para outra organização |
| [D-19](#d-19) | baixa | plataforma | Calibrações e alertas existem no modelo e não têm tela |

---


### D-02

**Medições anteriores ao vínculo ficam órfãs para sempre.**

*Onde:* `platform/meliponet/ingest/store.py`, `store()`.

*Sintoma:* liga-se o nó em campo antes de vinculá-lo a uma colmeia na interface. As
leituras desse período existem no banco, mas o gráfico da colmeia começa só a partir do
vínculo. Nada quebra, nada avisa; o gráfico só começa mais tarde do que se esperava.

*Por que acontece:* o `hive_id` é carimbado na linha da medição no instante da ingestão,
por `resolve_hive()`. Sem vínculo naquele instante, a coluna fica `NULL` — e vincular
depois não reprocessa o passado. A interface promete o contrário: o texto de "Nós
aguardando vínculo" diz que as leituras "passam a aparecer nos gráficos assim que o
vínculo existir", o que só vale para o que chegar depois.

*Contorno hoje:* vincule o nó à colmeia **antes** de deixá-lo publicando.

*Como corrigir:* ao criar um `NodeAssignment`, reatribuir as medições daquele nó que
caem dentro do período e ainda estão com `hive_id IS NULL`. São poucas linhas em
`manage.assign_node`, e o teste é direto: ingerir duas medições, vincular, conferir que
as duas aparecem em `series()`. Corrigir o texto da interface faz parte da correção.

---



### D-06

**O Last Will é publicado e ninguém o assina.**

*Onde:* o contrato reserva o tópico `meliponet/v1/<node_id>/status` para o Last Will do
nó, e nada em `platform/meliponet/ingest/` assina esse tópico.

*Sintoma:* um nó que morre em campo não gera aviso nenhum. "O nó parou de enviar" segue
indistinguível de "ainda não chegou a hora de enviar", que é exatamente o problema que o
Last Will existe para resolver.

*Como corrigir:* assinar `meliponet/v1/+/status` no ingestor e registrar a transição em
`nodes`. O alerta de nó mudo em si é assunto maior, mas guardar a transição pode ser feito
antes e barato — e dá sentido à etapa de MQTT do roteiro do nó.

---

### D-07

**Os agregados contínuos são criados e nunca consultados.**

*Onde:* `platform/meliponet/db.py` cria `measurements_1h` e `measurements_1d`;
`platform/meliponet/services/series.py` sempre lê a tabela bruta e reamostra em Python.

*Sintoma:* nenhum hoje — funciona e responde rápido com meses de dados de poucas
colmeias. Vira problema com dezenas de nós e anos de série, e vira problema de uma vez,
não gradualmente.

*Como corrigir:* escolher a fonte pela janela — bruto para 24 h, `measurements_1h` para
7 e 30 dias. O contrato de `series()` não muda; os testes existentes de lacuna e de
reamostragem continuam valendo e são a rede de segurança da mudança.

---



### D-13

**O registro fotográfico do vínculo não tem como ser anexado.**

*Onde:* `platform/meliponet/models.py`, `NodeAssignment.photo_path`. A coluna existe; não
há upload em nenhuma tela, nem rota que a preencha.

*Sintoma:* a docstring do próprio modelo diz que o registro fotográfico é um dos
metadados de instalação exigidos pelo protocolo do Edital 17, e a coluna fica `NULL` em
todas as linhas. O sintoma não aparece na tela nenhuma: aparece na prestação de contas,
ou no dia em que alguém precisa conferir como o sensor estava posicionado e só tem o
texto que a pessoa digitou.

*Como corrigir:* aceitar o arquivo na tela de vínculo e guardá-lo fora do banco, com o
caminho na coluna. Decidir antes onde os arquivos ficam no deploy — o contêiner do web é
descartável, então precisa de volume.

---

### D-14

**Não há administração de usuários, apesar de o perfil admin prometê-la.**

*Onde:* não existe. `platform/meliponet/cli.py` cria usuários pelo terminal; nenhuma
rota, tela ou comando altera um depois.

*Sintoma:* `models.py` e `services/scope.py` dizem, os dois, que o `ADMIN` "administra
cadastros **e usuários**". A segunda metade não existe: não dá para criar usuário pela
web, trocar a senha de alguém que a esqueceu, mudar um perfil de meliponicultor para
pesquisador, corrigir a organização de quem foi criado na errada, nem desativar quem
saiu do projeto. Tudo isso hoje exige acesso ao terminal do servidor — ou SQL na mão.

*Como corrigir:* uma tela de usuários sob `can_manage`, com o cuidado óbvio de um admin
não conseguir rebaixar ou desativar a si mesmo e deixar a instalação sem ninguém que
administre. Ver também [D-15](#d-15): desativar só terá efeito real junto com aquilo.

---

### D-15

**Desativar um usuário no banco não encerra a sessão dele.**

*Onde:* `platform/meliponet/blueprints/auth.py` verifica `is_active` apenas no login, e o
login é feito com `remember=True`. O `user_loader` não reverifica.

*Sintoma:* marcar `is_active = false` — hoje, por SQL — não expulsa ninguém. Quem já
está logado continua navegando, e o cookie permanente faz isso durar. Quem executou o
comando acredita que revogou o acesso e não revogou; é o pior tipo de falha de
segurança, a que dá a impressão contrária.

*Como corrigir:* checar `is_active` no `user_loader`, que é por onde toda requisição
autenticada passa.

---

### D-16

**Os formulários não têm proteção contra CSRF.**

*Onde:* todos os `POST` da plataforma. Não há Flask-WTF nem token nos formulários de
`templates/manage/`.

*Sintoma:* nenhum, no uso normal — e é isso que o torna fácil de esquecer. Uma página
qualquer aberta noutra aba pode submeter um formulário para a plataforma usando a sessão
de quem está logado. O alvo mais evidente é o `desvincular`, que é destrutivo e não pede
confirmação.

*Como corrigir:* Flask-WTF com `CSRFProtect`, e o token nos formulários. É pequeno; o
que não é pequeno é lembrar de incluí-lo em cada formulário novo, então vale um teste
que recuse um `POST` sem token.

---

### D-17

**Nó e vínculo não podem ser corrigidos depois de criados.**

*Onde:* `platform/meliponet/blueprints/manage.py`. Meliponário e colmeia ganharam tela de
edição; nó e `NodeAssignment` não.

*Sintoma:* o `label` e a `firmware_version` do nó só são preenchidos pela ingestão e não
têm onde ser ajustados. Pior é o vínculo: `sensor_placement`, `protocol_notes` e o
`installed_at` do período ficam como foram digitados na hora da instalação, em campo,
possivelmente no celular e com pressa. Um erro de digitação no posicionamento do sensor
— exatamente o metadado que o Edital 17 exige — não tem conserto pela interface, e o
único contorno é desvincular e vincular de novo, o que **parte a série em dois períodos**
e cria um remanejamento que nunca aconteceu.

*Como corrigir:* uma tela de edição do vínculo aberto, no mesmo padrão das duas que já
existem. Cuidado com `installed_at`: mudá-lo muda a que colmeia pertencem as medições já
gravadas, então a edição precisa deixar isso explícito na tela.

---

### D-18

**O admin não cadastra meliponário para outra organização.**

*Onde:* `platform/meliponet/blueprints/manage.py`, `create_apiary`, que grava sempre
`organization_id=current_user.organization_id`; o formulário não tem seletor de
organização.

*Sintoma:* não é um 403 — é a ausência do mecanismo. O administrador consegue criar uma
**colmeia** dentro do meliponário de qualquer organização, porque ali a organização vem
do meliponário escolhido, mas não consegue criar o **meliponário** de outra. As duas
operações irmãs seguem regras diferentes, e a única saída é criar um usuário dentro da
organização de destino.

*Como corrigir:* um seletor de organização visível apenas para quem tem
`sees_everything`, com a organização do próprio usuário como padrão. Depende de haver uma
consulta de organizações, que hoje não existe.

---

### D-19

**Calibrações e alertas existem no modelo e não têm tela.**

*Onde:* `platform/meliponet/models.py`: `Calibration`, `AlertRule` e `Alert`. As tabelas
são criadas pela migração e nada no código as lê ou escreve.

*Sintoma:* nenhum hoje, porque nada depende delas — o risco é o inverso: alguém lê o
modelo, conclui que a plataforma registra calibrações e emite alertas, e planeja em cima
disso. As três são estrutura preparada para a Fase 4, não funcionalidade entregue.

*Como corrigir:* nada, por ora. A entrada existe para que a leitura do modelo não engane
ninguém. Quando a Fase 4 chegar, as telas entram e esta entrada sai.

---

## Resolvidos

> **D-01, D-03, D-05, D-08 e D-10 saíram desta lista sem terem sido corrigidos.** Eram
> defeitos do firmware C++ que o repositório mantinha, e esse código deixou de existir
> aqui quando o nó virou exercício (ver [`firmware/ROTEIRO.md`](../firmware/ROTEIRO.md));
> ele está preservado na tag `firmware-referencia-v1`. Os números continuam queimados,
> como manda a regra acima.


| # | Defeito | Corrigido em |
|---|---|---|
| D-09 | O docstring do `contracts/canonical.py` apontava para `firmware/lib/MelipoNet/TelemetryCodec`, pasta que nunca existiu — e o `canonical.py` é a primeira coisa que alguém lê ao mexer no contrato | 2026-09-03 — corrigido para `firmware/lib/MelipoCore/Telemetria`, junto com a renomeação dos arquivos do firmware |
| D-12 | O administrador recebia 403 ao vincular ou desvincular um nó de outra organização, embora a tela lhe mostrasse o nó e o botão: duas views comparavam `organization_id` na mão em vez de passar pelo módulo de escopo. Junto ia um defeito mais silencioso — o vínculo carimbava no nó a organização de quem estava logado, então um admin que adotasse um nó para a colmeia de outra organização levava o nó consigo, e o dono legítimo deixava de enxergá-lo | 2026-09-02 — `manageable_nodes_for` e `can_manage_node` em `services/scope.py`, e a organização do nó passa a ser a da colmeia |
| D-04 | `tara` gravava o novo zero na NVS mas não o passava para o objeto da célula: a leitura logo após a tara saía com o offset antigo, e só um reinício fazia a tara valer — o que leva a pessoa a repetir a tara achando que não pegou | 2026-09-02 — `setCalibration()` no comando `tara`, como o `calibrar` já fazia |
| D-11 | O CI da plataforma quebrado desde a Fase 2: `pip install -e platform[dev]` falhava com "Multiple top-level packages discovered in a flat-layout", porque `pyproject.toml` não declarava o que empacotar e o Alembic trouxe `migrations/` para o lado de `meliponet/`. Passou despercebido por doze commits porque um ambiente virtual criado antes de `migrations/` existir continua funcionando — só instalação limpa falha | 2026-09-02 — `[tool.setuptools.packages.find]` em `platform/pyproject.toml` |
| D-00 | Sem comando serial para as credenciais do broker MQTT: um nó de campo não conseguia autenticar num broker com `allow_anonymous false`, e a única saída era liberar acesso anônimo no broker | 2026-09-02 — comandos `mqtt <usuario> <senha>` e `broker <host> [porta]` |
