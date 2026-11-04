# Metodologia do piloto — Grupo 2

## Objetivo e recorte

Construir uma rede de coautoria a partir de publicações de 2025 associadas aos perfis de pesquisadores presentes na lista atual de docentes do Programa de Pós-Graduação em Ciência da Computação da UTFPR Campo Mourão. O piloto pergunta: **como se organiza a colaboração no corpus de publicações selecionado?**

O tema original do grupo prevê comparar regiões brasileiras. Este piloto valida a coleta, a limpeza e a representação por grafos; não representa toda a pós-graduação brasileira. Não usa dados de fomento e não testa influência de financiamento.

## Fontes e seleção das identidades

- [Lista oficial dos docentes do PPGCC-CM](https://www.utfpr.edu.br/cursos/programas-de-pos-graduacao/ppgcc-cm/area-academica/docentes): define as 15 sementes da coleta. Snapshot em `dados/brutos/docentes_oficial.html`.
- [OpenAlex](https://openalex.org/): fonte dos perfis e metadados das publicações. Respostas originais em `dados/brutos/`.
- [DBLP de Diego Bertolini](https://dblp.org/pid/47/7382.html), vinculado pela página institucional do docente: usado para conferir o ORCID, pois o nome retornado pela OpenAlex diverge do nome oficial.

`codigo/configuracao/docentes.json` é a entrada versionada do recorte; o coletor gera automaticamente uma cópia em `dados/docentes_selecionados.json`. Essa seleção registra nomes oficiais, IDs selecionados, ORCIDs, aliases e observações. Foram procuradas variantes dos nomes e afiliações compatíveis. A página institucional inclui Igor Steinmacher, embora o perfil OpenAlex informe afiliações estrangeiras. Portanto, não se impôs filtro de afiliação brasileira às publicações: isso poderia excluir parte da produção das sementes escolhidas.

Perfis candidatos com o mesmo ORCID foram unificados. Candidatos adicionais sem ORCID não foram automaticamente associados apenas por coincidência nominal. Nomes, afiliações e ORCID podem conter erros na fonte; a validação das identidades é preliminar. A lista atual de docentes não é um cadastro histórico de 2025.

## Consulta e cobertura

O coletor consulta `/works` com filtro `publication_year:2025` e uma disjunção dos IDs das sementes em `authorships.author.id`, páginas de até 200 registros e paginação por cursor. Consulta todos os resultados informados pela API; não aplica limite arbitrário de artigos. O filtro exato está registrado em `dados/brutos/manifesto.json`.

A fonte é dinâmica: novas consultas podem produzir outros números. O cache local preserva a entrada da análise. O manifesto registra a URL, os parâmetros, o instante da coleta e o hash de cada resposta. O cache só é reutilizado quando parâmetros e hash coincidem. O índice `dados/brutos/coleta.json` identifica as páginas da coleta concluída; arquivos antigos fora desse índice não entram na análise. Os hashes das entradas da análise estão em `resultados/reprodutibilidade.json`. As contagens da execução estão em [resultados/relatorio.md](../resultados/relatorio.md).

## Limpeza

1. Manter apenas o ano 2025 e os tipos `article`, `conference-paper` e `review`.
2. Excluir registros marcados como retratados ou paratexto. Excluir preprints, datasets e erratas. Excluir IDs ou DOIs repetidos, quando presentes. DOI ausente permanece vazio; não é inventado.
3. Usar OpenAlex ID ou ORCID para identificar autores. Unificar identidades pelo mesmo ORCID, quando informado. Nunca juntar pessoas somente pelo nome.
4. Descartar da projeção autorias sem ambos os identificadores e registrar publicação e nome informado em `autorias_descartadas.csv`. Manter as publicações e seus autores identificáveis, com essa limitação explícita.
5. Preservar instituições e países informados em cada autoria. Afiliação ausente permanece vazia. Não atribuir região brasileira automaticamente.
6. Deduplicar autores dentro de cada publicação e remover laços. Detectar e remover isolados do grafo principal, preservando uma exportação alternativa. A quantidade removida é informada nas estatísticas da execução.

O processamento calcula e registra automaticamente as quantidades retidas, excluídas e recuperadas por ORCID. As contagens de autorias são de ocorrências em publicações, não de pessoas distintas. A incompletude pode reduzir a conectividade observada.

## Definição do grafo

Seja G = (V, E, w). V contém os autores com identificadores disponíveis nas publicações retidas, após remoção dos isolados. Uma aresta não direcionada {u,v} pertence a E quando os dois autores aparecem em pelo menos uma publicação retida. O peso w(u,v) é o número de publicações do corpus assinadas pelos dois.

Uma publicação com k autores identificados gera k(k−1)/2 pares. Uma colaboração repetida incrementa o peso da aresta, sem criar arestas paralelas. Os nós externos são incluídos independentemente do país. A rede contém também arestas entre dois coautores externos quando ambos assinam uma publicação de uma semente. Não são coletadas recursivamente todas as publicações desses coautores.

## Estatísticas e algoritmos

- **Nós e arestas:** tamanho e número de pares distintos ligados.
- **Densidade:** 2m/[n(n−1)], sem ponderação, para grafo simples não direcionado.
- **Grau:** número de coautores distintos; **força:** soma dos pesos incidentes.
- **Diâmetro:** maior distância mínima, em número de arestas. Na rede desconectada não se reporta um diâmetro finito global; calcula-se o valor da maior componente e informa-se seu tamanho.
- **PageRank:** calculado na rede principal, ponderado por publicações conjuntas, com amortecimento 0,85. Em uma rede não direcionada, tende a acompanhar a força; não é indicador independente de mérito científico.
- **Agrupamento local:** não ponderado, mede a proporção de pares de vizinhos conectados; grau inferior a dois recebe zero pela convenção da biblioteca. A projeção de artigos com múltiplos autores favorece triângulos.
- **Autovetor:** ponderado, calculado somente na maior componente conectada, evitando comparar vetores de componentes diferentes. Ausência de valor para outros nós significa fora do domínio de cálculo.

As duas últimas métricas e PageRank foram incluídas como análise exploratória adicional. O requisito da semana 8 permanece o dataset, a exportação e as estatísticas descritivas.

## Reprodutibilidade e arquivos

`python run.py` executa as três etapas: `coletar.py` prepara automaticamente as entradas e faz consultas HTTP; `analisar.py` transforma o snapshot local em CSVs, grafos GraphML/GML, figuras, estatísticas, relatório e roteiro de apresentação; `verificar.py` confere a consistência das exportações e a rastreabilidade das arestas às autorias. A opção `--offline` exige cache local validado e não acessa a rede; `--atualizar` substitui o cache por uma nova coleta. Os diretórios `dados/` e `resultados/` são gerados e ignorados pelo Git; a configuração e o modelo do roteiro permanecem versionados em `codigo/`. O layout usa semente 42; suas posições não têm significado geográfico. Os painéis das componentes usam escalas independentes.

## Próximas etapas

Validar identidades e vínculo histórico dos docentes, revisar autorias sem identificador, ampliar o recorte com critérios comparáveis entre regiões e definir tratamento das múltiplas afiliações. Uma análise de emergência de polos exige comparação temporal; uma análise de fomento exige dados externos. A originalidade precisa de revisão da literatura antes de ser afirmada.

## Referências técnicas iniciais

- [Documentação da API OpenAlex](https://help.openalex.org/api/).
- [Documentação do NetworkX](https://networkx.org/documentation/stable/).
- Enunciado local `PRojeto - artigo.pdf`, cronograma da semana 8 e ficha do grupo 2.

Esta entrega parcial não substitui a revisão bibliográfica exigida para o artigo final.
