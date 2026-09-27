# Geração de cargas sintéticas com stack distance controlada

*Documento de trabalho. Cresce conforme o experimento avança; cada seção descreve uma parte
já construída e testada. Os números citados vêm das execuções reais registradas em
`geracao/fases/f01-linha-de-base/analise/` (50 mil requisições por cenário) e, onde indicado, em
`geracao/fases/f02-500k/analise/` (500 mil).*

**Seções prontas:** 1 a 8.
**Seções previstas:** amostragem de cache (SHARDS, simulação em miniatura); políticas de despejo
além de LRU.

O desenho do estudo — variáveis, valores e hipóteses — está em [`EXPERIMENTO.md`](EXPERIMENTO.md).
Este documento trata do instrumento; aquele, do que se faz com ele.

---

## 1. Por que gerar a carga

Avaliar um cache exige uma carga de trabalho, e existem duas fontes: traces de produção ou
cargas sintéticas. Traces reais têm a vantagem óbvia do realismo e duas desvantagens que pesam
neste experimento. A primeira é a disponibilidade: traces de sistemas em produção costumam ser
considerados privados, e os poucos públicos fixam as características que trazem. A segunda é
mais fundamental — mesmo com um trace real em mãos, não há como pedir a ele *"o mesmo tráfego,
porém com localidade temporal mais fraca"*.

Quando a pergunta do estudo é justamente **como o comportamento do cache muda conforme a
localidade muda**, a localidade deixa de ser uma característica do dado e passa a ser a variável
independente do experimento. Isso só é possível se a carga for construída com essa variável sob
controle. É o que este trabalho faz.

---

## 2. A grandeza controlada: stack distance

A **stack distance (SD)** de um reúso é o número de objetos **distintos** requisitados entre dois
pedidos consecutivos ao mesmo objeto. Se o mesmo objeto é pedido duas vezes seguidas, a stack
distance é 0. Na sequência `A B C B A`, a stack distance do segundo `A` é 2 (os objetos distintos
no meio são `B` e `C`; `B` conta uma vez só).

A escolha dessa grandeza, e não de outra medida de localidade, vem de um resultado clássico. Pelo
algoritmo de pilha de Mattson et al. (1970), um cache LRU de C objetos mantém sempre os C objetos
usados mais recentemente. Um reúso, portanto, **acerta se, e somente se, a sua stack distance for
menor que C**. Não há outro caso a considerar: se entre os dois pedidos passaram menos de C
objetos distintos, o objeto ainda está lá; se passaram C ou mais, ele foi expulso.

Desse fato decorre a relação que sustenta todo o método:

```
hit(C) = (1 − P(∞)) · P(d < C)
```

Em palavras: acerta a requisição que é um reúso — isto é, não é a primeira aparição do objeto — e
cuja stack distance cabe no cache. `P(∞)` é a fração de requisições a objetos vistos pela primeira
vez, que nunca podem ser acerto (os chamados *misses compulsórios*), e `P(d < C)` é a fração dos
reúsos cuja distância cabe em C objetos.

A **curva de hit rate** inteira — o acerto para todo tamanho de cache — é, portanto, a acumulada
da distribuição de stack distance, escalada por 1 − P(∞). Controlar essa distribuição é controlar
a curva. O teto da curva é 1 − P(∞): nem um cache infinito acerta uma primeira aparição. (A curva
de miss ratio é o complemento, 1 − hit(C); as análises deste trabalho usam a de hit rate.)

> **Nota sobre terminologia.** Parte da literatura chama de *reuse distance* o que aqui é stack
> distance, e reserva *stack distance* para o mesmo conceito. Outra parte usa *reuse distance*
> para a contagem de requisições (não de objetos distintos) entre dois pedidos. Neste trabalho,
> stack distance é sempre a contagem de objetos **distintos**. Vale registrar também que o IRR
> (*Inter-Reference Recency*) do algoritmo LIRS é exatamente essa mesma grandeza, de modo que
> controlar a distribuição de stack distance é controlar a distribuição de IRR.

---

## 3. O gerador de carga: LRU Stack Model

O gerador implementa o **LRU Stack Model**, proposto por Mattson et al. (1970) e formalizado para
simulação por Turner e Strecker (1977). A ideia é usar a pilha LRU ao contrário: em vez de
processar um trace e medir a que profundidade cada pedido caiu, sorteia-se a profundidade e
constrói-se o pedido.

O estado do gerador é uma pilha com os objetos já requisitados, do mais recente ao mais antigo.
Cada requisição tem dois movimentos:

1. **Sortear** uma profundidade `d` da distribuição-alvo P(d).
2. **Requisitar** o objeto que está naquela profundidade e promovê-lo ao topo. Se o sorteio
   resultar em ∞, entra um objeto inédito no topo.

O método é exato, e a razão é direta: por construção da pilha, o objeto na profundidade `d` tem
exatamente `d` objetos distintos usados mais recentemente que ele. A stack distance da requisição
gerada **é** o número sorteado — sem aproximação, sem arredondamento.

### Exemplo verificável

Com quatro objetos na pilha (A no topo, depois B, C, D) e os sorteios `2, 0, ∞, 3, 1`:

| Passo | Sorteio | Pilha antes (topo → base) | Emite |
|---|---|---|---|
| 1 | d = 2 | A B C D | C |
| 2 | d = 0 | C A B D | C |
| 3 | d = ∞ | C A B D | E (novo) |
| 4 | d = 3 | E C A B D | B |
| 5 | d = 1 | B E C A D | E |

Medindo a stack distance do trace produzido, as cinco requisições dão `2, 0, ∞, 3, 1` — os mesmos
números sorteados.

### Aquecimento

O gerador começa com a pilha cheia, com `d_max` objetos, para que qualquer distância sorteada
tenha um objeto correspondente. Isso cria um detalhe que precisa de cuidado: para quem lê o trace
depois, esses objetos aparecem pela primeira vez, e toda primeira aparição é um miss compulsório.
Sem tratamento, pede-se P(∞) = 5% e mede-se algo bem maior.

A solução adotada é emitir a pilha inicial, da base para o topo, como um **prefixo de
aquecimento** do trace. Quem reproduzir o trace chega ao fim do prefixo com o cache no mesmo
estado do gerador, e a partir daí as medidas coincidem com o que foi pedido. Nas análises, as
`d_max` primeiras linhas são descartadas das estatísticas.

### Implementação

A pilha é mantida em uma árvore de Fenwick sobre posições, o que torna "ler o objeto na
profundidade d" e "mover para o topo" operações O(log n). Uma lista simples daria O(n) por
requisição e inviabilizaria cargas grandes. Na prática, 500 mil requisições levam poucos segundos.

---

## 4. A distribuição de stack distance

O gerador não decide a localidade: ele obedece à distribuição que recebe. A localidade da carga
está inteiramente em P(d), que é escrita em um arquivo separado, legível e versionável:

```
0 0.09706
1 0.04853
2 0.03235
...
inf 0.05
```

Cada linha associa uma distância a uma probabilidade; a linha `inf` é a fração de requisições a
objetos novos. As probabilidades são normalizadas em conjunto.

### A família escolhida: lei de potência

A distribuição-alvo segue uma lei de potência:

```
P(d) ∝ (d + 1)^(−β)
```

A chance de um reúso ter distância `d` decresce conforme `d` cresce, e **β é a velocidade dessa
queda**. Valores altos de β concentram os reúsos em distâncias curtas; valores baixos espalham a
massa para distâncias longas. Comparando com um reúso imediato, um reúso de distância 9 é 32
vezes menos provável com β = 1,5, dez vezes menos provável com β = 1,0 e três vezes menos
provável com β = 0,5.

A escolha da lei de potência tem duas justificativas. A primeira é empírica: distribuições de
localidade em cargas reais têm cauda pesada, e a lei de potência é a forma tradicionalmente
usada para descrevê-las. A segunda é prática: **um único parâmetro governa o nível de stack
distance**, o que mantém o desenho experimental simples de descrever e de defender.

Além de β, dois parâmetros completam a distribuição:

- **`d_max`** — a maior stack distance possível. Define a escala do experimento: nenhum reúso
  passa disso. Note que não é o tamanho do acervo: a pilha começa com `d_max` objetos, mas cada
  sorteio de ∞ acrescenta um objeto novo em definitivo, então o número de objetos distintos
  cresce ao longo da carga.
- **`P(∞)`** — a fração de requisições a objetos novos. Mantida igual em todos os cenários, para
  que a taxa de novidade não se confunda com o efeito da localidade.

### Os três cenários

| | SD baixa | SD média | SD alta |
|---|---|---|---|
| β | 1,5 | 1,0 | 0,5 |
| SD mediana medida | 1 | 72 | 2.510 |
| SD no percentil 90 | 49 | 3.713 | 8.091 |
| SD no percentil 99 | 1.749 | 9.003 | 9.788 |

Com `d_max` = 10.000, P(∞) = 5% e 50.000 requisições por cenário.

Note que **a mediana sozinha não descreve o cenário**: a carga de SD baixa tem mediana 1, mas
percentil 99 igual a 1.749 — ou seja, quase todo reúso é imediato, e ainda assim existe uma cauda
longa. Por isso o relatório reporta percentis, e não uma medida central apenas.

---

## 5. O pipeline

A geração está organizada em três etapas, cada uma com uma entrada e uma saída explícitas:

```
distribuição de SD   →   carga (trace)   →   conferência
  dist/sd_*.txt          cargas/carga_*.txt    analise/
```

A separação entre a primeira e a segunda etapa é deliberada. A distribuição é um objeto de estudo
por si só: pode ser versionada, publicada junto com o experimento, comparada com a de um trace
real, e — o ponto mais importante — **permite calcular o resultado esperado antes de gerar uma
única requisição**.

O trabalho é organizado em **fases**: cada fase é uma rodada de experimentação com seus próprios
parâmetros comuns (`dmax`, `inf`, `requisicoes`, `semente`, `caches`), e o que varia entre os
cenários daquela fase — hoje o β — entra no nome dos arquivos. Assim, `carga_f01_alta-b050.txt` é
a carga do cenário de SD alta (β = 0,5) da fase `f01`. Cada fase registra num `manifesto.json` os
parâmetros usados, o resumo dos resultados e a identificação do código: o commit, o aviso de
árvore suja e um hash do conteúdo de `genwl.py`, `mkps.py` e `pipeline.py`. O hash é necessário
porque o manifesto é escrito antes do commit que o inclui, então o commit sozinho não
identificaria o código que de fato rodou.

Os números desta seção e das seguintes vêm da fase `f01-linha-de-base`. Um comando roda tudo:

```bash
cd geracao && python3 pipeline.py --fase f01
```

---

## 6. A conferência

Como a distribuição é conhecida, toda medida feita na carga tem um valor teórico correspondente,
calculado diretamente de P(d) pela relação da seção 2. A conferência compara os dois.

Resultados com 50.000 requisições por cenário:

| Cenário | Cache | Hit teórico | Hit medido | Erro |
|---|---|---|---|---|
| SD baixa | 10 | 0,7312 | 0,7364 | +0,0052 |
| SD baixa | 100 | 0,8842 | 0,8862 | +0,0020 |
| SD baixa | 1.000 | 0,9342 | 0,9366 | +0,0024 |
| SD média | 10 | 0,2843 | 0,2859 | +0,0016 |
| SD média | 100 | 0,5035 | 0,5092 | +0,0057 |
| SD média | 1.000 | 0,7266 | 0,7314 | +0,0049 |
| SD alta | 10 | 0,0240 | 0,0247 | +0,0007 |
| SD alta | 100 | 0,0890 | 0,0901 | +0,0011 |
| SD alta | 1.000 | 0,2957 | 0,2978 | +0,0021 |

As curvas crescem com o tamanho do cache e saturam em 1 − P(∞) = 0,95.

O eixo dos tamanhos de cache vai de 1 objeto até o **tamanho da carga** — na `f03`, 1 milhão. Não é
para propor caches desse tamanho: é para a curva aparecer inteira. Ela tem um joelho em `d_max` e é
plana dali para a direita, porque nenhum reúso tem stack distance maior que `d_max`; cache nenhum,
por maior que seja, acerta o que nunca é pedido de novo. O patamar é o teto 1 − P(∞), e vê-lo na
figura evita a leitura errada de que a curva continuaria subindo fora do quadro. O mesmo vale para
a acumulada da stack distance, que chega a 100% em `d_max` e fica lá.

A conferência é feita sobre **toda a curva** — 44 tamanhos de cache espaçados em escala log entre
1 objeto e o tamanho da carga, não só os da tabela —,
e o limite aceito acompanha o tamanho da carga: o desvio esperado de uma proporção é 0,5/√n, e o
critério é cinco desses desvios. Na fase `f01`, o erro máximo é 0,0072 contra um limite de 0,0112;
na `f02`, com dez vezes mais requisições, cai para 0,0009 contra um limite de 0,0035, e na `f03`,
com 1 milhão, para 0,0008 contra 0,0025. É ruído
amostral, e diminui como esperado ao aumentar a carga.

Duas ressalvas sobre o que essa conferência prova e o que não prova. **Primeira:** os três
cenários de uma fase compartilham a semente, e portanto o mesmo fluxo de números aleatórios. É um
desenho pareado, bom para comparar cenários — a diferença entre eles não carrega ruído de
amostragem diferente —, mas significa que as três concordâncias são três projeções de **uma
amostra só**, não evidências independentes. **Segunda:** a conferência verifica que o trace
reproduz a distribuição pedida; não verifica a distribuição em si. Para medir a sensibilidade do
critério, injetamos um erro de uma unidade na distância sorteada e reexecutamos: os cenários de
stack distance baixa e média acusaram erro de 0,37 e 0,10, muito acima do limite, e o pipeline
falhou — mas o cenário de SD alta, cuja distribuição é larga o bastante para absorver o
deslocamento, passou sozinho. A conferência é a verificação de que o instrumento funciona, não um
resultado do experimento.

### "Alta" em relação a quê

Um valor absoluto de stack distance não significa nada sozinho: 500 é alto para um cache de 100
objetos e baixo para um de 10.000. Por isso a análise reporta, para **cada tamanho de cache do
experimento**, a fração de reúsos que aquele cache não consegue atender:

| Reúsos com SD ≥ cache | cache 10 | cache 100 | cache 1.000 |
|---|---|---|---|
| SD baixa | 22,6% | 6,9% | 1,6% |
| SD média | 70,0% | 46,5% | 23,1% |
| SD alta | 97,4% | 90,5% | 68,7% |

É essa tabela — e não um limiar fixo — que sustenta a afirmação "esta carga tem stack distance
alta para os caches estudados".

---

## 7. O que emerge junto: footprint e frequência

O **footprint** de uma janela é o número de objetos distintos que aparecem nela. Aqui ele é medido
de forma **exata**: não sobre uma amostra de janelas, mas sobre *todas* as janelas daquele tamanho
que existem no trace. A conta é feita pelo avesso, como em Xiang et al. (ASPLOS 2013) — uma janela
deixa de ver um objeto exatamente quando cabe inteira dentro de um intervalo em que ele não
aparece, e um intervalo de L posições acomoda L − w + 1 janelas de tamanho w:

```
fp(w) = m − ( Σ máx(0, L − w + 1) ) / (n − w + 1)
```

com `m` = objetos distintos da carga, `n` = tamanho da carga, e a soma correndo sobre os intervalos
sem acesso de todos os objetos (o trecho antes da estreia de cada um, os buracos entre acessos
consecutivos e o trecho depois do último acesso). O histograma desses L sai em uma passada pelo
trace, então a curva inteira é barata — e, por não amostrar nada, a medida não depende de semente.

Medido assim na fase `f03`, com 1 milhão de requisições por cenário (entre parênteses, a fração da
janela):

| Objetos distintos em uma janela de… | SD baixa | SD média | SD alta |
|---|---|---|---|
| 100 requisições | 26 (26%) | 63 (63%) | 94 (94%) |
| 1.000 requisições | 140 (14%) | 435 (44%) | 819 (82%) |
| 10.000 requisições | 835 (8%) | 2.560 (26%) | 5.085 (51%) |
| 100.000 requisições | 5.860 (6%) | 10.305 (10%) | 12.708 (13%) |
| 1.000.000 — a carga inteira | 50.489 (5%) | 54.852 (5%) | 57.264 (6%) |

A fração da janela torna a leitura direta: numa janela de 100 requisições, 26% do que passa na
carga de SD baixa são objetos distintos, contra 94% na de SD alta — ali quase tudo o que passa é
objeto diferente.

### O footprint em um número só

A curva tem dois extremos forçados. Em `w = 1`, fp = 1: uma requisição toca um objeto. Em `w = n`,
fp = `m`: a janela do tamanho da carga **é** a carga, e o número de objetos distintos nela é o
número de objetos distintos da carga. Esse extremo direito é a resposta para "qual é o footprint
desta carga, em um número só" — é a última linha da tabela, e é a mesma coluna "objetos distintos"
que o relatório já trazia. Todo o resto da curva é o caminho entre os dois extremos.

A mesma tabela mostra por que esse número único, sozinho, diz pouco sobre localidade: na janela da
carga inteira os três cenários quase empatam (50, 55 e 57 mil objetos), enquanto numa janela de
1.000 requisições estão separados por um fator de seis. O empate no extremo tem explicação: com
P(∞) = 5% e 1 milhão de requisições, cerca de 50 mil objetos entram na carga como estreia, e esse
termo domina a soma qualquer que seja a localidade. A localidade decide quantos objetos ficam
**ativos ao mesmo tempo**, não quantos existem ao todo. Por isso o footprint é reportado como
curva, com o número único no extremo dela.

**O footprint não é um parâmetro do gerador — ele emerge da distribuição de stack distance.** E
não por acaso: a stack distance de um reúso é, por definição, a contagem de objetos distintos na
janela entre dois pedidos ao mesmo objeto. Reúsos longos significam janelas com muitos objetos
distintos. As duas grandezas descrevem a mesma localidade por ângulos diferentes — uma olhando
para janelas de reúso, outra para janelas quaisquer.

### A terceira vista: frequência por objeto

A contagem de requisições por objeto — feita no trace já sem o aquecimento, sem correção de borda —
é a terceira maneira de olhar para a mesma carga. Na `f03`:

| | SD baixa | SD média | SD alta |
|---|---|---|---|
| Requisições por objeto, em média | 19,8 | 18,2 | 17,5 |
| Objeto mais pedido | 242 | 176 | 130 |
| Objetos pedidos **uma vez só** | 5,0% | 5,3% | 5,7% |
| Requisições nos 10% mais pedidos | 32,7% | 31,9% | 31,6% |

A **média** tem referência analítica: um objeto novo nasce a cada 1/P(∞) = 20 requisições, logo
cada objeto rende 20 pedidos em média — desde que a carga seja grande diante da pilha de
aquecimento. Os objetos da pilha inicial que são tocados entram na conta sem terem nascido ali e
puxam a média para baixo: com 1 milhão de requisições o efeito é pequeno (19,8 contra 20), mas na
`f01`, com 50 mil, a média cai para 16,0 no cenário de SD baixa e para 4,9 no de SD alta, porque
ali os 10.000 objetos do aquecimento pesam mais que os ~2.500 que nasceram na carga. O resto da tabela é medida, não
conferência — a popularidade não é parâmetro: o que se sorteia é a profundidade na pilha, nunca o
objeto.

E o resultado é instrutivo, porque **contraria** o que valia para o footprint. Stack distance e
footprint andam juntos; a frequência, não. As três cargas têm mediana de SD de 1, 74 e 2.536 e
footprint de 140, 435 e 819 objetos em 1.000 requisições — mas popularidade praticamente igual. Duas
referências para ler a última linha: se todos os objetos fossem pedidos o mesmo tanto, os 10% mais
pedidos levariam 10% das requisições; num trace real, com popularidade Zipf-like de expoente entre
0,8 e 1,0, levariam de 60% a 80%. As cargas ficam em 32%, isto é, muito mais planas que tráfego
real e só um pouco mais concentradas que o caso uniforme.

Isso não é defeito de implementação, é a natureza do LRU Stack Model: nele a popularidade de um
objeto é passageira — ele nasce no topo, é reusado enquanto está raso e some quando afunda. Não
existe um atributo "objeto popular" que dure a carga inteira, como existe sob o Independent
Reference Model. O modelo reproduz a distribuição de stack distance, não a de popularidade.

A consequência prática é bem delimitada. Para **LRU**, não muda nada: a curva de hit rate depende
só da stack distance, e a seção 6 mostra que ela bate com a teoria até a quarta casa. Para
políticas guiadas por **frequência** (LFU e parentes), muda tudo — sem cauda de popularidade não há
o que explorar, e uma comparação de políticas feita aqui atribuiria ao LFU um desempenho que ele
não teria em tráfego real. É mais um motivo para o experimento se restringir a LRU, e é o número
que responde a "por que não LFU?" sem precisar de argumento.

Três consequências para o desenho experimental:

1. **Não é possível fixar stack distance e footprint separadamente.** Não existe "stack distance
   alta com footprint pequeno". Mexer em β move as duas juntas — e quase não move a frequência.
2. **`d_max` limita a parte de reúso do footprint, não o footprint.** O acervo não é fechado:
   cada objeto novo entra em definitivo, a uma taxa de P(∞) por requisição, então o footprint
   cresce sem teto — em janelas grandes, aproximadamente P(∞)·w. Na `f03`, uma janela de 100 mil
   requisições já toca de 5,9 mil a 12,7 mil objetos distintos, e a carga inteira passa de 50 mil,
   muito acima do `d_max` de 10.000. O que achata a curva nas janelas médias é a janela ainda ser
   pequena diante do acervo de reúso, não um teto.
3. **O footprint deve ser reportado como medida, não como parâmetro.** Se for levantada a questão
   "a diferença observada veio da stack distance ou do footprint?", a resposta honesta é que se
   trata da mesma mudança descrita de dois modos.

---

## 8. Relação com a literatura

O modelo usado aqui é a versão mais simples de uma família de descritores de localidade que vem
sendo desenvolvida desde os anos 1970 e que hoje é usada em produção por grandes CDNs.

| Trabalho | Contribuição | Relação com este trabalho |
|---|---|---|
| Mattson et al. (1970) | Algoritmos de pilha; propriedade de inclusão do LRU; a curva de acerto como função da stack distance | É o teorema da seção 2 |
| Coffman e Denning (1973) | Formalização do LRU Stack Model e do Independent Reference Model | É o gerador da seção 3 |
| Turner e Strecker (1977) | Uso da distribuição de profundidade da pilha LRU para *simular* comportamento de paginação | É a ideia de gerar a partir de P(d) |
| Jiang e Zhang (2002), LIRS | Usa o IRR — a stack distance do último reúso — para decidir despejo | A grandeza controlada aqui é a mesma |
| Sundarrajan et al. (2017), CoNEXT | *Footprint descriptors*: descrição compacta de localidade usada na Akamai | Seção 7; ver abaixo |
| Sabnis e Sitaraman (2021), IMC | TRAGEN: gerador de traces sintéticos a partir de footprint descriptors | Mesmo problema, escala de CDN |
| Waldspurger et al. (2015, 2017) | SHARDS e simulação em miniatura: estimar a curva por amostragem | Base da seção futura sobre amostragem |

### O TRAGEN e o footprint descriptor

O modelo que o TRAGEN usa chama-se *footprint descriptor* (FD) justamente porque descreve
footprints de janelas. Ele é uma tripla ⟨λ, Pʳ(s,t), Pᵃ(s,t)⟩:

- **Pʳ(s,t)** é a distribuição conjunta de *bytes únicos* e *duração* das janelas de **reúso**.
  O próprio artigo registra que o número de bytes únicos numa janela de reúso é a stack distance.
- **Pᵃ(s,t)** é a mesma distribuição para janelas **quaisquer** — isto é, o footprint.
- **λ** é a taxa de tráfego, que ancora o eixo de tempo.

Ou seja, o FD é exatamente o par de grandezas das seções 2 e 7, medido em bytes e indexado por
tempo. A correspondência é esta:

| No TRAGEN (CDN, objetos de tamanhos variados) | Aqui (objetos de tamanho unitário) |
|---|---|
| Pʳ(s,t): bytes únicos nas janelas de reúso | P(d): objetos distintos nas janelas de reúso |
| Pᵃ(s,t): bytes únicos em janelas quaisquer | f(n): objetos distintos em janelas de n requisições |
| unidade: bytes | unidade: objetos |
| janela indexada por duração (segundos) | janela indexada por número de requisições |
| λ: taxa de requisições ou de bytes | não há eixo de tempo |

**É possível associar as duas descrições?** Sim, com duas conversões e uma ressalva. A conversão
de unidade é multiplicar a distância em objetos pelo tamanho médio do objeto; a conversão de eixo
é multiplicar a duração pela taxa de requisições. A ressalva é que essas conversões só são exatas
quando os objetos têm tamanho uniforme: em tráfego real os tamanhos variam, o FD é ponderado por
bytes, e o mesmo número de objetos distintos pode corresponder a quantidades de bytes muito
diferentes. Por isso o TRAGEN precisa de uma distribuição de tamanhos e de um algoritmo que não
enviese a escolha dos objetos pelo tamanho.

Para este experimento, em que o tamanho do objeto não é variável de interesse e a métrica é a
taxa de acerto por requisição, o caso de tamanho unitário é suficiente — e tem a vantagem de ser
exato, sem o arredondamento que a versão em bytes exige.

---

## 9. Limites do modelo

Para registro, o que este gerador **não** representa:

- **Estacionariedade.** P(d) é a mesma do início ao fim da carga. Não há ciclo dia/noite, rajadas,
  nem conteúdo que viraliza e esfria.
- **Popularidade emergente e plana.** Controla-se a stack distance; quantas vezes cada objeto é
  pedido é consequência. Em particular, a popularidade de um objeto aqui é passageira, diferente do
  que ocorre sob o Independent Reference Model, em que um objeto popular é popular o tempo todo. A
  medida da seção 7 quantifica isso: os 10% mais pedidos levam 32% das requisições, contra 60% a
  80% em tráfego real Zipf-like. Basta para LRU, não basta para políticas guiadas por frequência.
- **Tamanho de objeto.** Todos os objetos são iguais. Métricas em bytes (byte hit rate) não se
  aplicam.
- **Tempo.** Há ordem, não há relógio. Métricas baseadas em tempo (TTL, idade de despejo em
  segundos) exigiriam acrescentar timestamps.
- **Sorteios independentes.** Cada distância é sorteada sem memória da anterior, então não há
  correlação entre reúsos sucessivos nem fases de execução.

Essas limitações são aceitáveis quando a pergunta é sobre o efeito da localidade em si. Passam a
ser relevantes se o estudo se voltar para políticas guiadas por frequência, para caches com
admissão, ou para métricas de tempo.

---

## Referências

- R. L. Mattson, J. Gecsei, D. R. Slutz, I. L. Traiger. *Evaluation techniques for storage
  hierarchies.* IBM Systems Journal, 9(2), 1970.
- E. G. Coffman, P. J. Denning. *Operating Systems Theory.* Prentice-Hall, 1973.
- R. Turner, B. Strecker. *Use of the LRU stack depth distribution for simulation of paging
  behavior.* Communications of the ACM, 20(11), 1977.
- S. Jiang, X. Zhang. *LIRS: An efficient low inter-reference recency set replacement policy to
  improve buffer cache performance.* ACM SIGMETRICS, 2002.
- X. Xiang, B. Bao, C. Ding, Y. Gao. *Linear-time modeling of program working set in shared cache.*
  PACT, 2011; e X. Xiang, C. Ding, H. Luo, B. Bao. *HOTL: A higher order theory of locality.*
  ASPLOS, 2013. — o cálculo exato do footprint médio por janela usado na seção 7.
- A. Sundarrajan, M. Feng, M. Kasbekar, R. K. Sitaraman. *Footprint descriptors: Theory and
  practice of cache provisioning in a global CDN.* ACM CoNEXT, 2017.
- A. Sabnis, R. K. Sitaraman. *TRAGEN: A synthetic trace generator for realistic cache
  simulations.* ACM IMC, 2021.
- C. A. Waldspurger, N. Park, A. Garthwaite, I. Ahmad. *Efficient MRC construction with SHARDS.*
  USENIX FAST, 2015.
- C. A. Waldspurger, T. Saemundsson, I. Ahmad, N. Park. *Cache modeling and optimization using
  miniature simulations.* USENIX ATC, 2017.

---

## Como reproduzir

```bash
cd geracao
python3 pipeline.py --fase f01              # a linha de base, 50.000 requisições por cenário
python3 pipeline.py --fase f02              # o tamanho do experimento, 500.000
python3 pipeline.py --nova-fase <apelido>   # cria a fase seguinte; edite o cenarios.json dela
```

A configuração de cada fase fica em `geracao/fases/<fase>/cenarios.json`; os detalhes de cada
arquivo produzido estão em `geracao/README.md`. A semente é fixa: a mesma configuração gera
exatamente a mesma carga.
