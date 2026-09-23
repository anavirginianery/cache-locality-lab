# Desenho experimental

*Rascunho para discussão. A `METODOLOGIA.md` descreve o instrumento — como as cargas são geradas
e por que são confiáveis. Este documento descreve o estudo: o que se pergunta, o que se mede, que
valores foram escolhidos e com que fundamento.*

---

## 1. O que é este experimento

**Pergunta:** como o nível de localidade temporal de uma carga — medido pela stack distance —
afeta (a) o desempenho relativo das políticas de despejo e (b) a precisão da estimativa da curva
de hit rate por amostragem.

O ponto de partida é que a localidade deixa de ser uma característica herdada do dado e passa a
ser **manipulada**: as cargas são sintéticas, com a distribuição de stack distance definida por
um parâmetro, e a curva de hit rate de um cache LRU é conhecida analiticamente antes de qualquer
simulação. Isso permite medir efeitos com um gabarito, em vez de comparar traces cuja localidade
ninguém controla.

**O que este experimento não é.** Não é uma afirmação sobre tráfego real. As cargas são
estacionárias, os objetos têm todos o mesmo tamanho e a popularidade é uma consequência, não um
parâmetro. Os resultados descrevem o mecanismo — como cache e estimadores respondem ao nível de
stack distance —, não o comportamento de uma CDN ou de um servidor específico.

---

## 2. Variáveis

### 2.1 Independentes (fatores manipulados)

Nesta etapa — a geração das cargas — há **um fator só**:

| Fator | Níveis |
|---|---|
| **Nível de stack distance** | baixa (β = 1,5), média (β = 1,0), alta (β = 0,5) |

É o que define uma carga. Tudo o mais que varia depois — política de despejo, taxa de amostragem,
tamanho do cache — não é propriedade da carga: são parâmetros de quem a consome.

| Fator | Níveis | Onde é definido |
|---|---|---|
| Política de despejo | LRU, FIFO, LFU *(+ uma adaptativa, a decidir)* | desenho da parte 2 |
| Taxa de amostragem | 1 (exato), 0,1, 0,01 | desenho da parte 3 |
| Tamanho do cache | grade logarítmica, limitada a `d_max` | desenho das partes 2 e 3 |

**O tamanho do cache não é fator desta etapa.** Ele é o eixo das curvas de resposta, e quem o
escolhe é a simulação. A única amarra que a geração impõe é o teto: um cache maior que `d_max` já
atende todo reúso possível, então medir além disso não acrescenta nada (seção 4.4). O campo
`caches` do `cenarios.json` existe só para a conferência do gerador — é onde ela compara hit
medido e hit teórico — e não define o experimento.

### 2.2 Dependentes (respostas medidas)

| Resposta | Definição | Unidade |
|---|---|---|
| **Hit rate** | fração das requisições atendidas pelo cache, depois do aquecimento | fração de 0 a 1 |
| **Erro de estimativa** | hit rate estimado pela amostra menos o hit rate exato, no mesmo tamanho de cache | pontos percentuais |
| **Distância entre políticas** | hit rate da política X menos o de LRU, no mesmo ponto | pontos percentuais |

As duas últimas são derivadas da primeira. O hit rate é a única grandeza efetivamente medida.

### 2.3 Controladas (fixas em todas as execuções)

| Variável | Valor | Por quê |
|---|---|---|
| Tamanho dos itens | **todos iguais** | seção 3 |
| Requisições por carga | 1.000.000 | seção 4.1 |
| Aquecimento | 10.000 requisições (1% da carga), descartadas das medidas | seção 4.2 |
| Objetos novos, P(∞) | 0,05 | seção 4.3 |
| Alcance do reúso, `d_max` | 10.000 | seção 4.4 |
| Família da distribuição | lei de potência, P(d) ∝ (d+1)^−β | seção 4.5 |
| Réplicas | 5 sementes por nível | seção 4.6 |

---

## 3. O tamanho dos itens não importa aqui

**Todos os objetos têm o mesmo tamanho.** Isso é uma decisão de escopo, não uma simplificação por
conveniência, e vale explicitar o raciocínio.

A métrica de interesse é o **hit rate por requisição**: a fração dos pedidos que o cache atende.
Quando todos os objetos têm o mesmo tamanho, o hit rate por byte é idêntico ao hit rate por
requisição — a dimensão do tamanho não acrescenta informação nenhuma à resposta. Ela só passaria a
importar se a pergunta fosse sobre **bytes** (banda consumida contra a origem, custo de tráfego),
e não é.

Três consequências práticas, todas desejáveis aqui:

- A stack distance é contada em **objetos distintos**, não em bytes. Um cache de C objetos é
  exatamente um cache de capacidade C, sem conversão.
- Não há política de admissão por tamanho, nem fragmentação, nem a escolha de despejar um objeto
  grande em vez de vários pequenos. O único critério em jogo é o de ordenação da política.
- O viés de tamanho que obriga geradores de tráfego de CDN a mecanismos especiais simplesmente
  não existe: com tamanhos iguais, sortear por byte é o mesmo que sortear por objeto.

**A limitação que isso impõe, dita de forma clara:** os resultados não se transferem
automaticamente para caches de objetos heterogêneos. Num cenário assim, o hit rate por byte e o
hit rate por requisição divergem — é justamente por isso que o TRAGEN precisa de um descritor
ponderado por bytes além do descritor por requisição —, e políticas que levam o tamanho em conta
(GD-Size, AdaptSize) passam a fazer sentido. Nada disso está no escopo deste experimento.

---

## 4. Os valores escolhidos, e por quê

Boa parte destes valores é arbitrária no sentido de que outros valores próximos serviriam. O que
não é arbitrário é a **razão de ordem de grandeza** entre eles: é ela que garante que os efeitos
procurados caibam na faixa medida.

### 4.1 Um milhão de requisições por carga

Três considerações:

- **Ruído de medição.** O desvio esperado de uma proporção medida em *n* requisições é 0,5/√n.
  Com 1 milhão, isso dá 0,0005 — meio ponto percentual dividido por dez. Diferenças entre
  políticas ou entre estimadores da ordem de 1 ponto percentual ficam muito acima do ruído.
- **Peso do aquecimento.** O prefixo de 10.000 requisições é 1% da carga, então o regime
  transitório não domina nenhuma medida.
- **Custo.** Medido no piloto: gerar e conferir os três cenários com 1 milhão levou **33,7
  segundos** e produziu 17 MB de traces. Com 5 réplicas, são cerca de 3 minutos e 85 MB — barato
  o suficiente para refazer o experimento inteiro sempre que algo mudar.

### 4.2 Aquecimento de 10.000 requisições

É `d_max`, por construção: o prefixo emite a pilha inicial inteira, de modo que qualquer simulador
que leia o trace chegue ao fim do prefixo com o cache no mesmo estado do gerador. Não é um valor
escolhido, é uma consequência.

### 4.3 Objetos novos: P(∞) = 0,05

Cinco por cento das requisições são para objetos nunca vistos — os *misses compulsórios*, que
nenhum cache acerta. Duas razões para esse valor:

- **Ancoragem empírica.** Nos modelos de tráfego real distribuídos com o TRAGEN, essa fração vai
  de 4% (downloads) a 42% (mídia social). O valor escolhido fica na ponta baixa dessa faixa: é o
  regime em que a localidade tem espaço para importar. Com 42%, o teto da curva cairia para 0,58 e
  boa parte do efeito ficaria escondida atrás dos misses compulsórios.
- **Legibilidade.** Com P(∞) = 0,05, o teto do hit rate é 0,95, um número redondo que deixa
  visível o quanto cada curva se aproxima do máximo possível.

Fica igual nos três níveis, para que a taxa de novidade não se confunda com o efeito da
localidade.

### 4.4 `d_max` = 10.000: o alcance do reúso

**`d_max` é a maior stack distance que a distribuição pode sortear.** Na prática, é o tamanho da
pilha com que o gerador começa: ele empilha `d_max` objetos e, a cada requisição, sorteia uma
profundidade dentro dela. Nenhum reúso pode ser mais longo do que a pilha é funda.

Três consequências:

- **Nenhum reúso passa de `d_max`.** Com 10.000, a maior distância possível entre dois pedidos ao
  mesmo objeto é de 9.999 objetos distintos no meio.
- **A curva de hit rate encosta no teto em C = `d_max`.** Com um cache desse tamanho, todo reúso
  cabe, e o único miss que sobra é o compulsório. É por isso que ele limita a grade de caches que
  a simulação vai varrer: medir acima disso não acrescenta informação.
- **Não é o tamanho do acervo.** Objetos novos entram o tempo todo, à taxa de P(∞) por requisição,
  e ficam. No piloto de 1 milhão, as cargas terminaram com 50 a 57 mil objetos distintos, com
  `d_max` de 10.000. `d_max` limita o **alcance do reúso**, não a quantidade de objetos.

**Como escolher:** `d_max` precisa ser pelo menos tão grande quanto o maior cache que se pretende
estudar — senão a curva satura antes do fim da grade e a parte alta dela não diz nada. O custo de
aumentá-lo é o aquecimento (uma linha de trace por objeto da pilha) e a memória. Com 10.000, o
aquecimento é 1% de uma carga de 1 milhão.

### 4.5 A família: lei de potência

A distribuição-alvo é P(d) ∝ (d+1)^−β, e só o β muda entre os níveis.

- **Empírico:** distribuições de localidade em cargas reais têm cauda pesada, e a lei de potência
  é a forma tradicionalmente usada para descrevê-las.
- **Prático:** um parâmetro único governa o nível, o que mantém o desenho simples de descrever e
  de defender. A alternativa — a lognormal, que separa nível de espalhamento — só seria necessária
  se a pergunta exigisse variar os dois independentemente.
- **A ressalva:** com a lei de potência, mudar β desloca o nível **e** o espalhamento ao mesmo
  tempo. Os três níveis não diferem apenas no nível, e isso vai para as ameaças à validade.

Os três valores de β foram escolhidos pelo resultado que produzem, não pela estética do número.
Medidos no piloto de 1 milhão:

| Nível | β | SD mediana | SD p90 | Footprint em 1.000 req | Objetos distintos |
|---|---|---|---|---|---|
| Baixa | 1,5 | 1 | 51 | 140 | 50.489 |
| Média | 1,0 | 74 | 3.769 | 435 | 54.852 |
| Alta | 0,5 | 2.536 | 8.119 | 819 | 57.264 |

As medianas ficam separadas por cerca de duas ordens de grandeza entre níveis vizinhos, e cada uma
cai numa região diferente da grade de caches — que é exatamente a condição para os três níveis
darem respostas distintas.

### 4.6 Cinco réplicas, com blocos pareados

**Uma réplica é a mesma configuração rodada de novo com outra semente.** Os parâmetros são
idênticos — mesmo β, mesmo `d_max`, mesmo P(∞), mesmo tamanho —, mas os sorteios são outros, então
sai um trace diferente que obedece à mesma distribuição. É o equivalente a repetir uma medição:
mostra quanto do resultado é o efeito procurado e quanto é acaso.

Cinco réplicas do cenário de SD média, com 200 mil requisições cada:

| Semente | SD mediana | Objetos distintos | Hit com cache 100 | Hit com cache 1.000 |
|---|---|---|---|---|
| 7 | 74 | 15.295 | 0,5046 | 0,7274 |
| 17 | 72 | 15.345 | 0,5059 | 0,7287 |
| 27 | 74 | 15.472 | 0,5029 | 0,7245 |
| 37 | 73 | 15.308 | 0,5040 | 0,7269 |
| 47 | 74 | 15.363 | 0,5040 | 0,7272 |
| **média** | | | **0,5043** | **0,7269** |
| **faixa** | | | 0,5029 a 0,5059 | 0,7245 a 0,7287 |

A amplitude é de 0,003 no cache de 100 e 0,004 no de 1.000. Esse é o tamanho do acaso nesta
configuração: **uma diferença menor que isso entre duas condições não significa nada**. Com 1
milhão de requisições em vez de 200 mil, a amplitude cai por volta da metade.

Sem réplicas, cada número seria uma medição só, sem como saber se uma diferença de 0,002 entre
dois níveis é efeito ou sorte. Com cinco, reporta-se média e faixa.

As sementes escolhidas — 7, 17, 27, 37, 47 — são arbitrárias; o que importa é serem fixas,
registradas e distintas.

**A réplica *r* usa a mesma semente nos três níveis.** É um desenho pareado: a comparação entre
níveis não carrega ruído de amostragem diferente, o que reduz a variância da diferença — a
técnica conhecida como *common random numbers*. Em troca, as concordâncias dentro de uma réplica
não são independentes entre si, e isso precisa aparecer quando os resultados forem reportados.

Cinco réplicas não dão poder estatístico para um teste formal; dão o suficiente para reportar
**média e faixa** em vez de um número solitário, e para flagrar se algum efeito observado cabe
dentro da variação entre sementes.

---

## 5. O que se espera

Previsões com mecanismo e com critério de falseamento. São elas que dizem, antes de rodar, o que
contaria como resultado.

**H1 — Separação entre níveis.** A curva de hit rate desce monotonicamente da carga de SD baixa
para a de SD alta, em todo tamanho de cache. A separação é máxima nos caches intermediários — perto
da mediana de cada nível — e desaparece nos extremos: com cache de 10 objetos todos erram quase
tudo; com cache de 10.000 todos chegam ao teto de 0,95. *Falseia se* as curvas se cruzarem em
algum ponto.

**H2 — LRU contra FIFO.** LRU é melhor ou igual a FIFO em todos os pontos, e a diferença é máxima
onde o tamanho do cache é próximo da mediana da stack distance daquele nível, indo a zero nos
extremos. *Mecanismo:* as duas políticas exploram o mesmo sinal de recência, e o que FIFO perde é
a promoção do objeto reutilizado — o que só muda alguma coisa quando o objeto é pedido de novo
enquanto ainda está no cache. *Falseia se* FIFO ganhar em algum ponto, ou se a diferença for
constante ao longo da curva.

**H3 — LFU.** LFU é pior que LRU nos três níveis, e a distância cresce com o nível de stack
distance. *Mecanismo:* no LRU Stack Model a popularidade é passageira — um objeto fica "quente"
por estar perto do topo da pilha, não por uma propriedade sua —, e LFU guarda quem foi popular no
passado. *Ressalva importante:* isto é um resultado **sobre esta família de cargas**, não sobre
LFU em geral. Numa carga com popularidade estável, a conclusão se inverte.

**H4 — Amostragem (a principal).** O erro da curva estimada cresce quando a taxa de amostragem R
cai; e, para um mesmo R, o erro é **maior na carga de stack distance baixa**.

*Mecanismo:* na amostragem espacial, uma distância *d* vira aproximadamente R·d na amostra. Quando
R·d é menor que 1, a amostra não distingue essa distância de zero, e a curva estimada perde
resolução abaixo de C ≈ 1/R. A carga de SD baixa tem mediana 1 e p90 igual a 51: com R = 0,01, cuja
resolução é 100 objetos, quase toda a sua curva cai na faixa não resolvida. A carga de SD alta,
com mediana 2.536, quase não é afetada.

*Predição quantitativa:* com R = 0,01, o erro na carga de SD baixa deve concentrar-se nos caches
de até 100 objetos e ser de ordens de grandeza maior que na carga de SD alta; com R = 0,1
(resolução de 10 objetos), a diferença entre os níveis deve encolher. *Falseia se* o erro for
parecido entre os níveis, ou se não guardar relação com 1/R.

---

## 6. Como medir e reportar

- **Unidade de observação:** um hit rate por (nível, tamanho de cache, política, taxa de
  amostragem, réplica).
- **Execuções desta etapa:** 3 níveis × 5 réplicas = 15 cargas de 1 milhão. As partes 2 e 3
  consomem essas mesmas 15 cargas, cada uma com a sua grade de tamanhos de cache.
- **Agregação:** média das 5 réplicas, acompanhada da faixa (mínimo e máximo). Nunca o valor de
  uma semente sozinha.
- **Referência:** para LRU, o hit rate teórico calculado da distribuição serve de gabarito; o erro
  contra ele mede o instrumento, não o resultado. Para as demais políticas não há gabarito, só
  simulação.
- **Erro de estimativa:** reportado como erro médio absoluto ao longo da curva **e** como erro
  máximo, com o tamanho de cache em que ocorre — a posição do erro é parte do resultado, como diz
  a H4.

---

## 7. Ameaças à validade

- **Nível e espalhamento andam juntos.** Com a lei de potência, mudar β muda os dois. Os três
  níveis não diferem só no nível. Se isso atrapalhar a interpretação, o caminho é repetir com uma
  família que os separe (lognormal com σ fixo).
- **Footprint é consequência do nível.** Não dá para variar um sem o outro: a stack distance de um
  reúso é, por definição, a contagem de objetos distintos na janela entre dois pedidos. Efeitos
  atribuídos ao nível de SD são igualmente atribuíveis ao footprint.
- **Popularidade emergente e passageira.** Desfavorece políticas guiadas por frequência por
  construção. É a ressalva da H3.
- **Cargas estacionárias.** Sem ciclo dia/noite, sem rajadas, sem conteúdo que viraliza e esfria.
  Políticas adaptativas têm menos do que explorar aqui do que teriam em tráfego real.
- **Garantia teórica só para LRU.** O gabarito analítico existe para LRU; para as demais
  políticas, os números vêm de simulação e carregam o que a simulação carrega.
- **Réplicas pareadas.** As comparações entre níveis são pareadas, e as concordâncias dentro de
  uma réplica não são independentes.
- **Tamanho unitário.** Não vale para hit rate por byte nem para políticas cientes de tamanho.

---

## 8. Plano de execução

As cargas entram no repositório como cinco fases, uma por semente, cada uma com os três níveis:

| Fase | Apelido | Semente | Requisições | Níveis |
|---|---|---|---|---|
| f03 | exp-s7 | 7 | 1.000.000 | β 1,5 / 1,0 / 0,5 |
| f04 | exp-s17 | 17 | " | " |
| f05 | exp-s27 | 27 | " | " |
| f06 | exp-s37 | 37 | " | " |
| f07 | exp-s47 | 47 | " | " |

O campo `caches` de cada fase fica com a grade de conferência (10, 100, 1.000, 10.000), que serve
para o pipeline comparar hit medido e hit teórico — não é a grade do experimento.

```bash
cd geracao
python3 pipeline.py --nova-fase exp-s7    # e assim por diante
python3 pipeline.py --fase f03
```

Uma fase por semente é o que o pipeline de hoje suporta sem mudança: a semente é parâmetro da
fase. A alternativa seria aceitar uma lista de sementes e gerar 15 cenários numa fase só, o que
exigiria pôr a semente no nome dos arquivos (`carga_f03_baixa-b150-s17.txt`).

Depois disso, as partes 2 e 3 consomem essas 15 cargas: `simulacao/` roda as políticas,
`amostragem/` roda os estimadores, cada uma com o mesmo padrão de configuração, pipeline e
relatório.

---

## 9. Decisões ainda em aberto

1. **Quarta política.** LRU, FIFO e LFU cobrem três princípios distintos (recência com promoção,
   ordem de chegada, frequência). Vale acrescentar uma adaptativa — ARC, 2Q ou SIEVE? SIEVE é a
   mais simples de implementar corretamente; ARC é a mais citada. *Decisão da parte 2.*
2. **Taxa de amostragem mais baixa.** Com R = 0,001 sobre 1 milhão de requisições, a amostra tem
   cerca de mil requisições — pouco para uma curva estável. Ou se aceita o ruído como parte do
   resultado, ou o piso fica em 0,01. *Decisão da parte 3.*
3. **Número de réplicas.** Cinco é o suficiente para média e faixa. Se a variação entre sementes
   acabar sendo da mesma ordem dos efeitos procurados, será preciso subir para 10 ou 20 — o custo
   é linear e baixo.
