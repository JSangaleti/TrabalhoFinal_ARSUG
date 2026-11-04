# Projeto preliminar — Grupo 2

**Título provisório:** Estrutura de coautoria de pesquisadores da pós-graduação em Computação: um piloto com docentes do PPGCC-CM e colaboradores.

**Problema:** Como se organiza a colaboração nas publicações de 2025 dos pesquisadores selecionados? A etapa posterior investigará diferenças entre recortes regionais comparáveis. A emergência de polos ao longo do tempo depende de ampliar também a janela temporal.

**Objetivo desta etapa:** validar um procedimento reproduzível de coleta, limpeza e construção de redes de coautoria, produzindo os entregáveis da semana 8.

**Dados:** lista atual dos 15 docentes do PPGCC-CM da UTFPR como sementes e publicações de 2025 recuperadas pela OpenAlex. A seleção atual não comprova vínculo histórico. Serão considerados artigos, trabalhos de eventos e revisões; preprints, datasets e erratas serão excluídos. As identidades serão tratadas por OpenAlex ID ou ORCID.

**Grafo:** não direcionado, simples e ponderado. Vértices são autores identificados; arestas representam coautorias em publicações retidas; pesos representam o número dessas publicações em conjunto. Incluir colaboradores externos presentes nos trabalhos recuperados. Não expandir recursivamente a coleta.

**Análise:** nós, arestas, densidade, componentes, diâmetro da maior componente, distribuição de grau e, exploratoriamente, PageRank, coeficiente de agrupamento local e centralidade de autovetor na maior componente. Interpretar os resultados com as limitações da cobertura e da seleção centrada em docentes.

**Planejamento de originalidade:** pelo menos três critérios precisam ser demonstrados para o artigo final. Esta tabela registra intenções, não comprovações.

| Critério do enunciado | Possibilidade de contribuição | Situação |
| --- | --- | --- |
| Dados recentes | Corpus de 2025 com snapshot reproduzível | Recorte implementado; novidade precisa de revisão bibliográfica |
| Recorte geográfico inédito | Programa/instituições com recorte explicitado | Piloto implementado; ineditismo não verificado |
| Combinação inédita de métricas | Investigar combinação que acrescente interpretação | Não demonstrada; métricas obrigatórias não garantem novidade |
| Correlação com variável externa | Incorporar indicador de fomento ou outra variável justificada | Não implementada; depende de fonte e desenho adequados |
| Comparação temporal/espacial | Comparar instituições ou períodos com critérios equivalentes | Planejada; não implementada neste piloto |

**Limites e continuação:** conferir identidade e vínculo histórico dos docentes, revisar autorias sem identificador, selecionar recortes regionais comparáveis e revisar literatura antes de declarar originalidade. O piloto não permite atribuir diferenças ao financiamento.
