Claro, meu amigo. **O seu grupo 2 vai estudar quem publica artigos científicos com quem e o que essa rede revela sobre a colaboração entre regiões brasileiras.** Vocês precisam usar dados reais, aplicar algoritmos de grafos e escrever um artigo científico explicando os resultados.

**O primeiro passo é preparar um projeto preliminar de uma página:** definir a pergunta da pesquisa, o recorte dos dados e como o grafo será construído.

Pelo enunciado: 01-PRojeto-artigo.pdf

A indicação do seu grupo está em: 02-pasted.txt

Pense neste exemplo: Ana e Bruno publicaram um artigo juntos. No grafo, cada um será um vértice, e haverá uma aresta entre eles. Se Carla também assinou esse artigo, haverá ligações entre os três pares de autores. Assim, os artigos se transformam em uma **rede de coautoria**.

Para o seu grupo, as exigências são estas:

| Elemento                         | O que significa no trabalho                                               |
| -------------------------------- | ------------------------------------------------------------------------- |
| Vértices                         | Pesquisadores/docentes                                                    |
| Arestas não direcionadas         | Dois pesquisadores escreveram uma publicação juntos                       |
| Fonte recomendada                | OpenAlex, uma base de publicações científicas                             |
| PageRank                         | Identificar pesquisadores centrais na estrutura de colaboração            |
| Coeficiente de agrupamento local | Medir quanto os colaboradores de um pesquisador também colaboram entre si |
| Centralidade de autovetor        | Identificar pesquisadores conectados a outros pesquisadores centrais      |

Vocês podem propor **pesos nas arestas**, como a quantidade de artigos publicados juntos, desde que expliquem essa escolha. E centralidade na colaboração não deve ser tratada automaticamente como qualidade científica.

A pergunta sugerida pelo professor é: **a colaboração científica continua concentrada no Sudeste e no Sul, ou surgiram polos importantes no Nordeste e no Norte?**

Para responder bem, precisamos transformar essa ideia ampla em uma investigação viável. Eu começaria nesta ordem:

1. **Delimitar o estudo.** Escolher uma área ou subárea da Computação, um período e um conjunto justificável de instituições ou programas. O próprio professor recomenda recortes pequenos.
2. **Refinar a pergunta.** Determinar exatamente o que será comparado. Se quisermos afirmar que novos polos “emergiram”, precisaremos comparar períodos; uma rede de um único período mostra a situação daquela janela.
3. **Testar os dados com uma pequena coleta.** Conferir se conseguimos identificar autores, publicações e afiliações, além de relacionar as instituições às regiões brasileiras.
4. **Definir as regras do grafo.** Quem entra na rede? Incluiremos colaboradores estrangeiros? Como trataremos autores com várias afiliações? O peso será a quantidade de publicações conjuntas?
5. **Pesquisar trabalhos semelhantes.** Verificar o que já foi estudado e preencher a tabela de originalidade exigida.
6. **Reunir essas decisões no projeto de uma página.** Esse é o primeiro entregável previsto.

Há dois detalhes do tema que precisamos resolver desde o início. O título sugerido menciona **fomentos regionais**: para investigar financiamento, seria necessário acrescentar dados sobre financiamento; a rede de coautoria sozinha não responde isso. Além disso, como o tema fala em **pós-graduação**, precisamos definir como identificaremos pesquisadores ligados a programas de pós-graduação.

Para buscar nota máxima, a distribuição dos pontos ajuda a organizar o esforço:

| Critério                        | Peso | O que precisamos demonstrar                                  |
| ------------------------------- | ---- | ------------------------------------------------------------ |
| Metodologia                     | 25%  | Dados e grafo bem definidos; código reproduzível             |
| Algoritmos                      | 25%  | Aplicação correta e escolhas justificadas                    |
| Discussão e contribuição social | 25%  | Explicar o significado dos resultados no contexto brasileiro |
| Estrutura e formatação          | 15%  | Artigo no modelo SBC, texto claro e figuras legíveis         |
| Revisão por pares               | 10%  | Avaliar seriamente o artigo de outro grupo                   |

**Três quartos da nota estão na metodologia, nos algoritmos e na interpretação.** Por isso, vale dedicar atenção à pergunta e à construção da rede desde agora.

Também há uma exigência importante: o artigo deve atender a **pelo menos três dos cinco critérios de originalidade** — dados recentes/inéditos, recorte geográfico inédito, combinação inédita de métricas, relação com uma variável externa e comparação temporal/espacial. Essas contribuições precisam ser demonstradas na introdução e conferidas na literatura. O documento prevê bônus de até **0,5 ponto** por originalidade exemplar e limita a **7,0** trabalhos sem nenhum diferencial.

As entregas previstas são:

| Marco     | Entrega                                                  |
| --------- | -------------------------------------------------------- |
| Semana 4  | Projeto preliminar de uma página                         |
| Semana 8  | Dados limpos, grafo exportado e estatísticas descritivas |
| Semana 12 | Primeira versão completa do artigo e revisão por pares   |
| Semana 15 | Artigo final em PDF no modelo SBC e notebook Python      |

O artigo precisa ter introdução, fundamentação, metodologia, resultados, discussão, conclusão e **pelo menos 15 referências**.

**Nossa primeira tarefa concreta é escolher um recorte que permita responder uma pergunta interessante com dados acessíveis.** A partir dessa decisão, conseguimos montar a página preliminar e orientar toda a coleta e a análise.
