# 12. O comando `intervalo`

**Área:** firmware · **Tempo:** ~2 h · **Contribuição** — corrige [D-10](../defeitos-conhecidos.md#d-10)

> **Combine antes de começar.** Vira um PR; só uma pessoa deve fazê-lo.

## Por que este exercício existe

É a menor contribuição do firmware que passa pelo caminho inteiro — uma função pequena e
uma linha numa tabela — e ela conserta uma armadilha real.

Hoje, quem quiser mudar o intervalo de amostragem vai encontrar isto no `platformio.ini`:

```ini
-DMELIPO_SAMPLE_INTERVAL_S=300
```

Vai editar, recompilar, gravar — e **o nó vai continuar amostrando a cada 5 minutos**,
porque nenhum arquivo do firmware referencia esse flag. O valor real vem da NVS. Um
parâmetro que parece configurar algo e não configura é pior do que nenhum: ele custa uma
hora de quem confia nele.

## Antes de começar

- Bloco B feito.
- Leia [D-10](../defeitos-conhecidos.md#d-10) e
  [Acrescentar um comando ao console](../guia/04-o-firmware.md#acrescentar-um-comando-ao-console).
- Leia `firmware/src/main.cpp`, do comentário `--- comandos do console ---` até a tabela
  `kComandos`.

```bash
git switch main && git pull
git switch -c firmware/comando-intervalo
```

## Passo 1 — confirme a armadilha

Não acredite no registro: verifique.

```bash
grep -rn "MELIPO_SAMPLE_INTERVAL_S" firmware/
```

<details>
<summary>O que você deve encontrar</summary>

Uma ocorrência só: a definição em `firmware/platformio.ini`. Nenhum `#ifdef`, nenhum uso.

Agora ache de onde o valor **realmente** vem:

```bash
grep -rn "intervalo_amostra_s" firmware/
```

Ele é campo de `Configuracao` (`MelipoHardware/Configuracao.h`), com padrão 300, carregado
da NVS pela chave `interval_s`, e usado uma vez em `setup()`:

```cpp
g_agenda.iniciar(g_configuracao.intervalo_amostra_s * 1000UL, millis());
```

Ou seja: **o mecanismo inteiro já existe.** A NVS guarda, o `Configuracao` carrega, a
`Agenda` usa. Falta só a porta de entrada — e sobra um flag que finge ser essa porta.
</details>

## Passo 2 — escreva o comando

O esqueleto está em [O firmware](../guia/04-o-firmware.md#acrescentar-um-comando-ao-console).
São dois passos: a função, e uma linha na tabela `kComandos`.

Antes de escrever, releia os comandos que já existem e repare no padrão — ele não é
enfeite:

- **valide tudo antes de gravar qualquer coisa** (veja `comandoWifi`, que confere os dois
  tamanhos antes de copiar qualquer um);
- **comando recusado não altera nada** — `lerNumero` e `lerPorta` não tocam na variável de
  saída quando recusam;
- **nunca ecoe uma senha** (não se aplica aqui, mas é a regra da casa).

`lerNumero(texto, maximo, saida)` já faz a validação que você precisa: recusa vazio, texto
não numérico, zero, acima do teto, e números grandes o bastante para dar a volta num
`uint32_t`. Ela já tem teste nativo em `test_console.cpp` — **não escreva outra**.

> **Pergunta 1.** Que teto usar para o intervalo, e por quê?
>
> **Pergunta 2.** O comando deve pedir reinício, como o `wifi` e o `broker`, ou pode valer
> na hora?

<details>
<summary>Respostas</summary>

**1.** O guia sugere 3600 s (uma hora). O teto existe pelo mesmo motivo do
`kMaxLeiturasDeBancada`: um número digitado errado não pode deixar o nó praticamente mudo.
Um intervalo de 4 294 967 s seriam 49 dias entre amostras, e ninguém em campo perceberia o
erro de digitação — só a série vazia, semanas depois.

O piso `lerNumero` já garante: ela recusa zero.

**2.** Pode valer na hora, e é melhor — `Agenda` tem `definirIntervalo()` exatamente para
isso.

Repare por que essa pergunta importa. `comandoTara` existe hoje porque o `tara`
**gravava na NVS e não atualizava o objeto**: a leitura seguinte saía com a tara antiga, e
quem estava na bancada repetia o comando achando que não tinha pegado. Foi o defeito
[D-04](../defeitos-conhecidos.md#resolvidos), e a correção foi uma linha —
`definirCalibracao()` junto do `gravarConfiguracao()`.

Você está prestes a escrever um comando com a mesma forma. **Não repita o D-04:** atualize
o objeto **e** a NVS. Se preferir só gravar e pedir reinício, tudo bem — mas então diga
isso na mensagem impressa, para que ninguém fique testando um valor que ainda não vale.
</details>

## Passo 3 — remova o flag

Apague `-DMELIPO_SAMPLE_INTERVAL_S=300` do `platformio.ini`.

Se um padrão de compilação for desejável um dia, ele deve ser o valor usado por
`carregarConfiguracao()` quando a chave da NVS está ausente — **não** uma constante
paralela que ninguém lê. Hoje esse padrão já existe: é o `= 300` na declaração do campo.

## Passo 4 — verifique

```bash
./verificar firmware     # a validacao do argumento e pura, e ja tem teste
./verificar alvo         # o comando novo compila para a placa
```

E, se você tiver placa:

```bash
pio run -e esp32c6 -d firmware -t upload -t monitor
```

No monitor:

```
ajuda            o comando novo aparece sozinho na lista?
intervalo 60
estado
intervalo 0      recusado, sem alterar nada?
intervalo abc    recusado?
intervalo 99999  recusado pelo teto?
```

> **Por que o comando novo aparece no `ajuda` sem você mexer no `ajuda`?**

<details>
<summary>Resposta</summary>

Porque `comandoAjuda` percorre a **mesma** tabela `kComandos` que despacha os comandos:

```cpp
void comandoAjuda(const Comando &) {
  for (const ComandoDoConsole &entrada : kComandos) {
    Serial.println(entrada.ajuda);
  }
}
```

Não existe uma segunda lista para lembrar de atualizar. É o mesmo padrão do dicionário
`WINDOWS` no exercício [08](08-uma-janela-nova.md), do outro lado do sistema: uma fonte de
verdade, e a interface acompanha.
</details>

## Passo 5 — registro e commit

Remova D-10 da tabela de abertos e da lista de seções; acrescente em **Resolvidos**, com a
data. Atualize também a lista de comandos no `README.md` — ela está lá para quem prepara um
nó, e um comando ausente da lista é um comando que ninguém usa.

No commit: o sintoma (*"quem edita o flag, recompila e grava não vê efeito nenhum"*) e a
decisão do passo 2 (vale na hora, ou pede reinício).

## Critério de pronto

- [ ] `grep -rn "MELIPO_SAMPLE_INTERVAL_S" firmware/` não devolve nada
- [ ] `ajuda` lista `intervalo` sem você ter tocado no `comandoAjuda`
- [ ] Argumento inválido é recusado **sem alterar** o valor que já valia
- [ ] `./verificar` e `./verificar alvo` verdes
- [ ] D-10 saiu do registro e o `README.md` lista o comando novo

## Pistas

<details>
<summary>Meu comando compila mas nunca é chamado</summary>

Faltou a linha na tabela `kComandos`, ou o nome na tabela não bate com o que você digita.
`atenderConsole` percorre a tabela comparando com `cmd.ehComando(entrada.nome)`, que é
comparação exata — `Intervalo` não é `intervalo`.
</details>

<details>
<summary>`lerNumero` recusa tudo o que eu digito</summary>

Confira o índice do argumento. Em `intervalo 60`, o `60` é `cmd.argumento[1]` — o
`argumento[0]` é o nome do comando. E confira `cmd.quantidade < 2` antes de ler, senão você
lê uma string vazia.
</details>

<details>
<summary>Não tenho placa</summary>

Faça tudo menos o passo do monitor. `./verificar alvo` compila sem placa, e a validação do
argumento — a parte que erra de verdade — é exercitada no PC pelos testes de
`test_console.cpp`. Deixe no PR uma linha dizendo que a verificação de bancada não foi
feita: é o que o commit da tara fez, e é mais útil do que o silêncio.
</details>

## O que levar daqui

**Configuração que não configura é pior do que ausente.** Ela desvia o tempo de quem
confia nela — e o custo aparece justamente quando alguém tem pressa.

**Antes de construir, procure o que já existe.** Aqui, a NVS, o carregamento e o uso já
estavam prontos: a contribuição inteira foi uma função pequena e uma linha numa tabela.

**Um defeito velho ensina onde o próximo vai nascer.** O D-04 é o mesmo formato de comando
que você acabou de escrever. Ler os resolvidos antes de escrever código parecido é barato.

→ Próximo: [RSSI no painel](13-rssi-no-painel.md)
