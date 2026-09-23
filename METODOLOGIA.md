# Geração de cargas sintéticas com stack distance controlada

*Documento de trabalho. Cresce conforme o experimento avança; cada seção descreve uma parte
já construída e testada. Os números citados vêm das execuções reais registradas em
`geracao/analise/`.*

**Seções prontas:** 1 a 8.
**Seções previstas:** amostragem de cache (SHARDS, simulação em miniatura); políticas de despejo
além de LRU.

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

- **`d_max`** — a maior distância possível. Define a escala do experimento: nenhum reúso passa
  disso, e o acervo de objetos disponíveis tem esse tamanho.
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

Um comando roda tudo:

```bash
cd geracao && python3 pipeline.py
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

As curvas crescem com o tamanho do cache e saturam em 1 − P(∞) = 0,95. O erro máximo é de
0,0057 com 50 mil requisições e cai para 0,0009 com 500 mil — é ruído
amostral, e diminui como esperado ao aumentar a carga. A conferência não é um resultado do
experimento: é a verificação de que o instrumento funciona.

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

## 7. Footprint: o que emerge junto

O **footprint** de uma janela é o número de objetos distintos que aparecem nela. Medido nas cargas
geradas, em média, sobre janelas sorteadas ao acaso:

| Objetos distintos em uma janela de… | SD baixa | SD média | SD alta |
|---|---|---|---|
| 100 requisições | 26 | 62 | 95 |
| 1.000 requisições | 138 | 431 | 818 |
| 10.000 requisições | 813 | 2.522 | 5.061 |

Em fração da janela, a leitura fica mais clara: numa janela de 100 requisições, 26% das
requisições da carga de SD baixa são para objetos distintos, contra 95% na carga de SD alta.
Na carga de SD alta, quase tudo o que passa é objeto diferente.

**O footprint não é um parâmetro do gerador — ele emerge da distribuição de stack distance.** E
não por acaso: a stack distance de um reúso é, por definição, a contagem de objetos distintos na
janela entre dois pedidos ao mesmo objeto. Reúsos longos significam janelas com muitos objetos
distintos. As duas grandezas descrevem a mesma localidade por ângulos diferentes — uma olhando
para janelas de reúso, outra para janelas quaisquer.

Três consequências para o desenho experimental:

1. **Não é possível fixar as duas separadamente.** Não existe "stack distance alta com footprint
   pequeno". Mexer em β move as duas juntas.
2. **`d_max` é o teto do footprint.** A curva da carga de SD alta começa a achatar quando se
   aproxima do acervo disponível.
3. **O footprint deve ser reportado como medida, não como parâmetro.** Se for levantada a questão
   "a diferença observada veio da stack distance ou do footprint?", a resposta honesta é que se
   trata da mesma mudança descrita de dois modos.

O mesmo vale para o número de objetos distintos da carga inteira: 3.118 na carga de SD baixa,
7.125 na média e 10.170 na alta, com o mesmo `d_max` e o mesmo P(∞) nas três.

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
- **Popularidade emergente.** Controla-se a stack distance; quantas vezes cada objeto é pedido é
  consequência. Não é possível fixar as duas coisas. Em particular, a popularidade de um objeto
  aqui é passageira, diferente do que ocorre sob o Independent Reference Model, em que um objeto
  popular é popular o tempo todo.
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
python3 pipeline.py                      # 50.000 requisições por cenário (validação)
python3 pipeline.py --requisicoes 500000 # tamanho do experimento
```

Os cenários ficam em `geracao/cenarios.json`; os detalhes de cada arquivo produzido estão em
`geracao/README.md`. A semente é fixa: a mesma configuração gera exatamente a mesma carga.
