# Grupo 2 — Rede de coautoria científica

Rede de coautoria de publicações de Computação de 2025 com afiliação brasileira, obtidas da API OpenAlex. Compara Norte, Nordeste, Centro-Oeste, Sudeste e Sul, incluindo a distribuição de publicações, de PageRank e das coautorias entre regiões.

## Executar o projeto

O método recomendado é usar um ambiente virtual Python (`venv`) para isolar as dependências do projeto.

Com Python 3.10 ou superior, abra um terminal na raiz do projeto. No Linux ou macOS, crie e ative o ambiente:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Com o ambiente ativo, instale as dependências uma vez:

```bash
python -m pip install -r requirements.txt
```

O `run.py` usa o shebang `#!.venv/bin/python3` para executar o Python do ambiente virtual. Execute o fluxo completo diretamente na raiz do projeto:

```bash
./run.py
```

Nas próximas execuções, basta reutilizar o ambiente existente com `./run.py`. A execução pelo shebang dispensa a ativação do ambiente. Caso o arquivo esteja sem permissão de execução, conceda-a uma vez:

```bash
chmod +x run.py
```

Todos os comandos `python` deste README pressupõem o ambiente ativo. Ao terminar, use `deactivate` para sair dele. A pasta `.venv/` já é ignorada pelo Git.

O comando `./run.py` coleta as publicações nacionais, os metadados das instituições e as UFs do IBGE, limpa os dados, exporta os grafos, calcula métricas e verifica os resultados. Gera um único Markdown (`resultados/relatorio.md`), apenas com tabelas e gráficos recalculados em cada execução. Uma falha interrompe o fluxo e devolve código de saída diferente de zero.

Na primeira execução é necessário acesso à internet. As seguintes reutilizam a coleta completa quando o recorte e os hashes coincidem. Para consultas com mais de 10.000 registros ou para ampliar a cota pública, configure `OPENALEX_API_KEY` no ambiente; não coloque a chave no repositório. A paginação usa 100 resultados por página e rejeita coletas incompletas. Consulte a [autenticação](https://help.openalex.org/api/authentication/) e a [paginação](https://help.openalex.org/api/paging/) da OpenAlex.

Para reconstruir os resultados usando somente a coleta local:

```bash
./run.py --offline
```

Para obter uma nova coleta, substituindo o cache:

```bash
./run.py --atualizar
```

Também é possível direcionar os arquivos gerados para outra pasta:

```bash
./run.py --diretorio /tmp/coautoria
```

Como o caminho do Python no shebang é relativo, execute `./run.py` na raiz do projeto, onde está a pasta `.venv/`. A opção `--diretorio` altera apenas o destino dos dados e resultados.

O piloto anterior com docentes do PPGCC-CM continua disponível: `./run.py --recorte piloto --diretorio /tmp/coautoria-piloto`. Use outro diretório para manter os dois recortes simultaneamente.

## Recorte e contagem regional

- Campo principal OpenAlex `17` (Computer Science), ano `2025`, ao menos uma instituição brasileira nas autorias. Tipos retidos: `article`, `conference-paper` e `review`.
- A região corresponde à UF da sede da instituição identificada na autoria da publicação, usando `geo.region` da OpenAlex e a divisão do IBGE. Instituições com vários campi podem estar representadas pela sede. Afiliações sem UF ficam em `Brasil sem UF`.
- Cada publicação é dividida igualmente entre as regiões brasileiras distintas presentes nela. Para autores, usam-se as regiões brasileiras distintas observadas em suas publicações retidas de 2025; sua contagem e seu PageRank são divididos igualmente entre essas regiões. Uma afiliação estrangeira não elimina a brasileira. Autores apenas no exterior e autores sem afiliação identificada ficam em categorias próprias.
- Cada par de autores gera uma aresta não direcionada; seu peso é o número de publicações conjuntas. No agregado regional, o peso é dividido entre as combinações das regiões de seus dois autores. Cada aresta contribui com seu peso total uma única vez.
- PageRank ponderado e agrupamento local não ponderado são calculados na rede completa, incluindo coautores externos. Autovetor ponderado é calculado apenas na maior componente; valores nas demais ficam vazios. Autores sem coautorias são preservados no grafo com isolados.
- As comunidades são detectadas em toda a rede sem isolados pelo [Louvain do NetworkX](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.community.louvain.louvain_communities.html), com peso igual ao número de publicações conjuntas, resolução `1.0` e semente `42`. Os IDs começam em `1`, em ordem decrescente de tamanho (desempate pelos IDs dos autores). A modularidade ponderada e os parâmetros são registrados nos resultados.
- Percentuais regionais de produção e PageRank usam somente as cinco regiões identificadas. As categorias complementares aparecem em tabela separada, e os CSVs permitem conferir os totais.
- Identidades usam OpenAlex ID e ORCID, sem união por nome. Duplicações de ID/DOI, tipos excluídos, registros retratados/paratextos e listas de autorias truncadas pela fonte são auditados. Não se impõe limite de autores ao grafo; somente o relatório limita os nomes ao Top 10.

O recorte descreve a distribuição em 2025. Não mede surgimento de polos ao longo do tempo, financiamento nem vínculo com a pós-graduação: esses atributos exigem outras janelas ou fontes.

## Arquivos gerados

| Conteúdo | Local |
| --- | --- |
| Configuração do recorte usado no processamento | `dados/recorte_nacional.json` |
| Publicações, instituições e UFs em cache | `dados/brutos/nacional/` |
| Índice e manifesto da coleta | `dados/brutos/coleta_nacional.json` e `manifesto.json` |
| Publicações, autores, autorias, arestas, métricas e registros de exclusão | `dados/limpos/` |
| Grafos GraphML e GML | `resultados/rede_coautoria.graphml` e `.gml` |
| Estatísticas e registro de reprodutibilidade | `resultados/estatisticas.json` e `reprodutibilidade.json` |
| Distribuição regional, comparação dos eixos e coautorias entre regiões | `dados/limpos/metricas_regioes.csv`, `comparacao_eixos.csv` e `ligacoes_regioes.csv` |
| Classificação geográfica das instituições | `dados/limpos/instituicoes.csv` |
| Resumo das comunidades, cores, autores e ligações internas | `dados/limpos/comunidades_louvain.csv` |
| Composição regional de todas as comunidades, contagens e região com maior participação | `dados/limpos/comunidades_regioes.csv` |
| Contagens, frações e percentuais por comunidade e categoria geográfica | `dados/limpos/distribuicao_regional_comunidades.csv` |
| Comunidade e cor de cada autor | Colunas `comunidade_louvain` e `cor_comunidade` de `dados/limpos/autores.csv`, `metricas_autores.csv` e dos grafos exportados |
| Figuras | `resultados/distribuicao_regional.png`, `colaboracao_regional.png` e `distribuicao_grau.png` |
| Rede colorida por comunidade Louvain | [resultados/rede_comunidades_louvain.png](resultados/rede_comunidades_louvain.png) |
| Composição regional das dez maiores comunidades Louvain | [resultados/comunidades_regioes.png](resultados/comunidades_regioes.png) |
| Relatório de dados com resultados atuais | [resultados/relatorio.md](resultados/relatorio.md) |

No relatório nacional, as métricas por autor exibem os 10 maiores valores de PageRank entre autores com afiliação brasileira. O CSV `dados/limpos/metricas_autores.csv` mantém as métricas de todos os autores da rede. O relatório do piloto mantém os docentes sem publicação retida apenas como contagem.

A figura Louvain mostra todos os autores da rede, com a maior componente em destaque e as demais em um painel separado. As cores correspondem às comunidades e o tamanho dos nós ao PageRank. A legenda identifica os dez maiores grupos; o CSV mantém todos os IDs e cores, úteis para distinguir comunidades com tons próximos em redes grandes. As posições são organizadas por comunidade, sem significado geográfico; cada componente usa sua própria escala. Autores isolados ficam sem comunidade nos arquivos que os preservam. O mesmo processamento está disponível no recorte piloto.

### Comunidades e regiões brasileiras

No recorte nacional, o relatório apresenta quantos pesquisadores das dez maiores comunidades têm afiliação em cada uma das cinco regiões brasileiras. A região continua sendo a da instituição informada nas publicações retidas de 2025. Cada autor conta uma vez em cada região observada; por isso, as contagens podem somar mais que o total de autores da comunidade. `Brasil sem UF`, `Exterior` e `Sem afiliação identificada` aparecem separadamente.

Para avaliar a concentração regional, o relatório mostra o número de regiões representadas e a região com a maior participação fracionada. Cada autor contribui `1/k` para cada uma de suas `k` categorias geográficas distintas, seguindo a regra já usada no agregado regional. O percentual da região mais representada usa apenas a soma das frações nas cinco regiões brasileiras como denominador. Empates mostram todas as regiões líderes; comunidades sem região brasileira identificada ficam sem percentual. Essa composição descreve a diversidade de afiliações, sem medir diretamente a intensidade das coautorias entre regiões.

O gráfico empilhado usa outro denominador: o total de autores de cada comunidade, incluindo as categorias complementares, para que cada barra some 100%. Os dois CSVs preservam a composição de todas as comunidades, mesmo quando o relatório exibe apenas as dez maiores.

As estatísticas também separam o total de comunidades Louvain e a quantidade que pertence à maior componente conectada. O campo `na_maior_componente` identifica esses grupos nos CSVs de comunidades. Essa contagem filtra a partição obtida na rede completa, sem executar novamente o Louvain na maior componente; os IDs, os pesos, a resolução e a semente permanecem os mesmos. A contagem na maior componente também está disponível no piloto.

`dados/` é ignorado pelo Git; `resultados/` contém saídas versionadas. Ambos podem ser reconstruídos por `./run.py`. Apagar apenas os resultados ou tabelas limpas permite refazê-los sem internet, desde que a coleta bruta validada esteja disponível. Apagar também `dados/brutos/` exige uma nova coleta; os valores podem mudar, pois as fontes são dinâmicas.

## Configuração versionada

- [codigo/configuracao/docentes.json](codigo/configuracao/docentes.json): nomes oficiais, OpenAlex IDs, ORCIDs, aliases e justificativas da seleção.
- [codigo/configuracao/nacional.json](codigo/configuracao/nacional.json): campo, tipos, regiões, fonte do IBGE e regras da comparação nacional.
- [codigo/configuracao.py](codigo/configuracao.py): ano e fonte institucional do piloto.
- [codigo/nacional.py](codigo/nacional.py): coleta, análise regional e verificação da base nacional.
- [codigo/comunidades.py](codigo/comunidades.py): Louvain ponderado, cores, visualização e verificação das comunidades nos dois recortes.

No piloto, a configuração das identidades é uma entrada do estudo. No recorte nacional, os autores são identificados nas publicações da consulta completa; a lista de docentes do piloto não limita a amostra.

As buscas de candidatos são preservadas para auditoria. Para exibi-las separadamente: `python codigo/coletar.py --buscar-autores`.

Os testes podem ser executados sem internet:

```bash
python -m unittest discover -s tests -v
```
