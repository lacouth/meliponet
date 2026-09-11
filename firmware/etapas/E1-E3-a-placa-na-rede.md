# E1 a E3 — a placa, a rede e o relógio

**Tempo:** ~5 h no total · voltar ao [índice](../ROTEIRO.md)

Três etapas antes de qualquer sensor. Elas parecem pouco — uma contagem no serial, um IP,
um horário — mas são as três coisas que, quando estão erradas mais tarde, fazem você
suspeitar do sensor, do cabo e da solda antes de suspeitar delas.

Ao fim das três você tem um nó que **fala, tem endereço e sabe que horas são**. Falta o que
medir.

---

## E1 — a placa fala com você

**Tempo:** ~1 h

O programa mais curto que existe: imprimir alguma coisa no monitor serial a cada segundo.
Nenhum sensor, nenhuma rede.

> **O conceito: o monitor serial é o seu único instrumento, por enquanto.**
> A placa não tem tela. Tudo o que você vai saber sobre o que ela está fazendo, das
> próximas semanas até a etapa E6, chega por um cabo USB em forma de texto. Por isso o
> primeiro passo do roteiro não é ler sensor: é garantir que o canal por onde você vai ver
> tudo o mais está funcionando. Um projeto que imprime pouco é um projeto que você depura
> às cegas — imprima mais do que parece necessário.

### E1.1 — a placa aparece no computador

Ligue a placa pelo USB e descubra em que porta ela apareceu (`/dev/ttyACM0`,
`/dev/ttyUSB0`, `COM3`, conforme o sistema).

**Pronto quando:** a sua IDE lista a porta, e ela desaparece da lista quando você desliga
o cabo — é assim que você confirma que é a sua placa, e não outro dispositivo.

### E1.2 — a contagem anda

Grave o programa que imprime um número crescente a cada segundo, a 115200 bps.

**Pronto quando:** você vê a contagem andando no monitor serial, sem caracteres estranhos.

### E1.3 — o reset é visível

Aperte o botão de reset com o monitor aberto.

**Pronto quando:** a contagem volta ao começo. Você acabou de aprender a distinguir "o
programa travou" de "o programa reiniciou" — distinção que vai voltar em E8, quando a `seq`
tiver de sobreviver justamente a isso.

### Pistas — E1

<details>
<summary>O monitor mostra lixo: <code>ÿÿ</code>, acentos aleatórios, símbolos</summary>

Velocidade errada. O monitor e o programa precisam concordar no mesmo número (115200).
Lixo no serial é quase sempre isso, e quase nunca defeito de hardware.
</details>

<details>
<summary>Nada aparece, e a porta existe</summary>

Duas hipóteses, nesta ordem: o programa não chegou a ser gravado (a IDE reportou sucesso
mesmo?), ou o monitor foi aberto antes de a placa reiniciar e você perdeu as primeiras
linhas. Aperte o reset com o monitor já aberto.
</details>

<details>
<summary>A porta não aparece de jeito nenhum</summary>

No Linux, é comum ser permissão: o seu usuário precisa estar no grupo que dá acesso às
portas seriais (`uucp` ou `dialout`, conforme a distribuição), e a mudança só vale depois
de sair e entrar na sessão. Teste o cabo também — cabo de carregar celular, sem os fios de
dados, alimenta a placa e não comunica nada.
</details>

---

## E2 — o nó entra na rede

**Tempo:** ~2 h

Conecte no WiFi, imprima o IP recebido e imprima o `node_id`.

> **O conceito: `node_id` é a identidade do seu nó, e ela vem do hardware.**
> São os quatro últimos bytes do endereço MAC da placa, escritos em hexadecimal
> **maiúsculo**, oito dígitos — `A4C1380F`. O MAC é único e vem de fábrica, então dois nós
> nunca colidem e você não precisa de nenhum cadastro para batizar o seu. É por isso que o
> contrato exige esse formato em vez de deixar você escolher um nome: um nome escolhido à
> mão eventualmente se repete, e duas colmeias mandando `seq` no mesmo `node_id` produzem
> uma série sem sentido que ninguém vai conseguir separar depois.

> **O conceito: a senha do WiFi não entra no código versionado.**
> Assim que o seu projeto for para um repositório, tudo o que está escrito nele fica lá
> para sempre — apagar depois não apaga do histórico. Guarde as credenciais fora do
> código: num arquivo que o `.gitignore` ignora, ou na NVS da placa (que é o assunto de
> E7.6). Além da segurança, tem uma vantagem prática: a mesma placa passa a trocar de rede
> — bancada, casa, apiário — sem recompilar.

### E2.1 — a placa vê a sua rede

Antes de tentar conectar, faça o nó **listar** as redes que ele encontra e imprimir os
nomes e a potência de cada uma.

**Pronto quando:** o nome da sua rede aparece na lista. Se não aparece, nenhuma senha do
mundo vai conectar — e você descobriu isso em um minuto em vez de em uma hora.

### E2.2 — o nó conecta e recebe IP

Conecte e imprima o IP.

**Pronto quando:** o serial mostra um IP da sua rede (algo como `192.168.x.y`), e o
`ping` desse IP, do seu computador, responde.

### E2.3 — o `node_id`

Imprima o `node_id` no formato do contrato.

**Pronto quando:** saem oito dígitos hexadecimais **maiúsculos**, e o valor é o mesmo a
cada reinício. Anote-o: é por ele que você vai achar as suas leituras no banco e vincular
o seu nó a uma colmeia.

### E2.4 — o nó sobrevive à rede que cai

Desligue o roteador (ou tire a senha do ar) e veja o que o seu programa faz.

**Pronto quando:** o programa **não trava** — ele avisa que não conectou e continua
rodando. Um nó que fica preso esperando WiFi é um nó que para de medir a colmeia quando a
internet cai, e a colmeia não para.

### Pistas — E2

<details>
<summary>Conecta e desconecta em laço</summary>

Duas causas comuns: senha errada (alguns módulos relatam isso como desconexão, não como
erro), ou a rede é de 5 GHz e o rádio do ESP32-C6 só fala 2,4 GHz. Confira a banda antes
de conferir o código.
</details>

<details>
<summary>O <code>node_id</code> sai com letras minúsculas</summary>

É o modo de impressão do hexadecimal. O contrato exige maiúsculo
(`^[0-9A-F]{8}$`) — a plataforma recusa a mensagem com `400 node_id ...`, e é exatamente o
tipo de erro que só aparece em E5, horas depois de você ter dado o assunto por encerrado.
</details>

<details>
<summary>O <code>node_id</code> tem menos de 8 dígitos</summary>

Zeros à esquerda sumindo. Um MAC que termina em `0F` precisa sair `0F`, não `F`. O
contrato conta oito dígitos, sempre.
</details>

<details>
<summary>Conecta na bancada e não conecta no apiário</summary>

Anote o `rssi` desde já e mande-o na mensagem (é um campo opcional do contrato). Ele é o
que vai te dizer, meses depois, que o problema era distância do roteador e não o seu
código.
</details>

---

## E3 — o nó sabe que horas são

**Tempo:** ~2 h

Acerte o relógio pela rede e imprima o instante no formato do contrato:
`2027-03-14T12:05:00Z`.

> **O conceito: o relógio da placa começa errado, todas as vezes.**
> O ESP32 não tem bateria de relógio. Ao ligar, ele acha que são poucos segundos depois de
> uma data de referência qualquer — e continua achando isso até alguém contar a verdade.
> Quem conta é o NTP, um protocolo que pergunta a hora a um servidor na internet e corrige
> o relógio local. A consequência prática: **entre ligar e o NTP responder existe uma janela em
> que qualquer `ts` que você produzir está errado**, e é por isso que o contrato tem a flag
> `clock_unsynced`. Verbete no [glossário](../../docs/guia/06-glossario.md).

> **O conceito: UTC, e por que não a hora da Paraíba.**
> O `ts` da mensagem é sempre UTC, terminando em `Z` — três horas à frente do horário
> local. Não é preciosismo: o horário local de um lugar muda (horário de verão vai e
> volta por decisão política) e não é comparável com o de outro lugar. UTC não muda nunca.
> A plataforma guarda UTC e converte só na hora de desenhar a tela, para que a série de
> 2025 continue comparável com a de 2030. Sem o `Z`, a plataforma não tem como saber a que
> fuso aquele horário se refere, e recusa a mensagem — esse é o `400 ts sem fuso horario`.

### E3.1 — o horário antes do NTP

Imprima o instante que a placa acha que é, **antes** de sincronizar.

**Pronto quando:** você vê o valor absurdo (uma data de 1970, ou de 2016, conforme a
biblioteca) e entende que esse é o valor que iria para o `ts` se você não sincronizasse.

### E3.2 — o NTP responde

Sincronize e imprima o horário de novo.

**Pronto quando:** o horário impresso bate com o horário real, em UTC — confira contra o
relógio do seu computador, somando as três horas da Paraíba.

### E3.3 — o formato do contrato

Formate o instante exatamente como `2027-03-14T12:05:00Z`.

**Pronto quando:** a sua string tem o mesmo comprimento, o mesmo `T` no meio e o mesmo `Z`
no fim de `"ts"` em `../../contracts/exemplos/02-completa.json`. Compare caractere por
caractere — é mais rápido agora que em E5.

### E3.4 — a flag `clock_unsynced`

Decida o que o nó faz quando o NTP **não** responde. A resposta do contrato: ele manda a
mensagem de qualquer forma, com o horário estimado e a flag `clock_unsynced` acesa.

**Pronto quando:** com a internet cortada logo após o reset, o seu nó ainda produz uma
mensagem, e ela traz a flag. Uma leitura com horário duvidoso e aviso vale mais que
nenhuma leitura: a curadoria dos dados consegue decidir depois o que fazer com ela, e não
consegue inventar o que não foi medido.

### Pistas — E3

<details>
<summary>O NTP nunca responde</summary>

Sincronizar exige rede funcionando (E2) e, em rede institucional, às vezes a saída para
servidores de hora está bloqueada. Teste num celular compartilhando internet para separar
"meu código" de "esta rede".
</details>

<details>
<summary>O horário bate, mas está três horas atrasado (ou adiantado)</summary>

Você está imprimindo a hora local com o `Z` do UTC, ou o contrário. O `Z` é uma afirmação
sobre o fuso: colá-lo num horário local produz uma mensagem que a plataforma aceita e
grava **errada** — o pior dos dois mundos, porque não dá erro. Confira somando três horas
ao relógio da parede.
</details>

<details>
<summary>O horário vem certo e, depois de horas rodando, derrapa</summary>

Normal: o oscilador da placa não é preciso. Sincronize de novo de vez em quando — uma vez
por dia resolve com folga para um nó que mede a cada cinco minutos.
</details>

---

## O que levar daqui

**Imprima mais do que parece necessário.** Das três etapas, duas se resolvem olhando uma
saída que você teve o cuidado de produzir antes de precisar dela.

**O que não pode travar o nó:** rede fora e relógio não sincronizado são situações
normais de campo, não erros. O nó continua medindo nas duas.

→ Próximo: [E4 a E6 — a primeira mensagem](E4-E6-a-primeira-mensagem.md)
