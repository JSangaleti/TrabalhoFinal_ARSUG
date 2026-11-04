# Roteiro de apresentação — Grupo 2

Arquivo gerado automaticamente pelo processamento. Duração sugerida: cinco a sete minutos. As contagens abaixo correspondem à coleta utilizada nesta execução. Consulte também [o relatório](relatorio.md).

## 1. Tema e objetivo

**Rede de coautoria científica na pós-graduação: piloto com docentes do PPGCC-CM e colaboradores, em $ano.**

Fala sugerida:

“Nosso grupo estuda redes de coautoria científica. Nesta entrega parcial, delimitamos um piloto com pesquisadores presentes na lista atual de docentes do PPGCC de Campo Mourão. O objetivo foi obter dados reais, construir o grafo e descrever sua estrutura. A comparação entre regiões faz parte da continuação do projeto.”

## 2. Fonte e preparação dos dados

- Lista institucional: $docentes docentes usados como ponto de partida.
- Metadados obtidos pela API OpenAlex para $ano.
- $recebidas registros recebidos e $publicacoes publicações retidas.
- Tipos retidos: $tipos.
- Exclusões por tipo: $exclusoes. A auditoria completa, incluindo eventuais exclusões por outros critérios, está no relatório.
- Identificação por OpenAlex ID ou ORCID. Nomes iguais não bastam para juntar pessoas.

Fala sugerida:

“Preservamos os dados originais e geramos tabelas limpas. Encontramos autorias sem OpenAlex ID: $recuperadas ocorrências foram recuperadas pelo ORCID. Outras $descartadas ocorrências não tinham nenhum dos dois identificadores e ficaram fora da rede. Essa perda está registrada e é uma limitação do piloto.”

## 3. Construção do grafo

- Nó: autor identificado nas publicações retidas.
- Aresta: publicação conjunta entre dois autores.
- Grafo não direcionado, com peso igual ao número de publicações conjuntas.
- Coautores externos também entram; não são automaticamente classificados como alunos ou docentes.

Exemplo para explicar: “Um artigo assinado por Ana, Bruno e Carla cria três ligações: Ana–Bruno, Ana–Carla e Bruno–Carla. Outro artigo de Ana e Bruno aumenta o peso dessa ligação para dois.”

## 4. Resultados

| Medida | Resultado |
| --- | --- |
| Autores | $nos |
| Ligações distintas | $arestas |
| Densidade | $densidade |
| Componentes conectadas | $componentes |
| Autores na maior componente | $maior ($fracao da rede) |
| Diâmetro da maior componente | $diametro |

![Rede de coautoria](rede_coautoria.png)

Laranja identifica docentes usados como sementes; azul identifica os demais coautores. Os painéis mostram componentes em escalas próprias, sem significado geográfico.

Fala sugerida:

“A maior componente reúne $maior autores. Seu diâmetro é $diametro: o maior caminho mínimo entre dois autores dessa componente tem $diametro ligações. $explicacao_diametro”

## 5. Interpretação e limites

“A coleta e a construção do grafo são reproduzíveis. Também calculamos PageRank, agrupamento local e autovetor como exploração inicial. Esses resultados descrevem o recorte e não permitem concluir sobre toda a ciência brasileira, qualidade dos pesquisadores ou efeito do financiamento. A próxima etapa é validar identidades e ampliar o desenho para comparar regiões.”

## 6. Entregáveis

- Dados originais e tabelas limpas em `dados/`.
- Grafos em [GraphML](rede_coautoria.graphml) e [GML](rede_coautoria.gml).
- Estatísticas, figuras e relatório em `resultados/`.
- Código Python e configuração versionada das identidades selecionadas.

## Perguntas que podem aparecer

**Por que apenas Campo Mourão?** É um piloto delimitado para validar o procedimento. A adequação ao desenho final do grupo e a ampliação regional ainda precisam ser discutidas.

**Todos os nós são docentes do programa?** Os docentes são sementes; os demais são coautores das publicações. Seus papéis acadêmicos não foram classificados.

**Ausência de publicações no corpus significa ausência de produção?** A cobertura da base e a identificação dos perfis podem ser incompletas. As contagens descrevem somente os registros recuperados e retidos.

**A lista de docentes é histórica?** Usamos a lista atual para selecionar pessoas e suas publicações de $ano. O credenciamento histórico ainda precisa ser verificado.

**Vocês demonstraram novos polos de colaboração ou efeitos do financiamento?** Essas perguntas exigem amostras comparáveis entre regiões/períodos e dados externos. Permanecem como etapas posteriores.

**A rede tem todas as colaborações dessas pessoas?** A rede inclui o corpus recuperado das sementes, no ano e nos tipos selecionados, com autores identificáveis. A produção dos colaboradores externos não foi coletada recursivamente.

**Por que o autovetor foi calculado só na maior componente?** Para analisar um domínio conectado. Valores fora desse domínio aparecem vazios, e não como zero.

**O que significa alta centralidade?** Uma posição central segundo a métrica e o corpus usados. Isso não significa automaticamente maior qualidade científica.
