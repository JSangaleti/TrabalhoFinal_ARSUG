# Grupo 2 — Rede de coautoria científica

Piloto com publicações de 2025 de pesquisadores selecionados a partir da lista de docentes do PPGCC da UTFPR Campo Mourão e seus coautores. Dados reais obtidos da API OpenAlex.

## Executar o projeto

Com Python 3.10 ou superior, instale as dependências uma vez:

```bash
python -m pip install -r requirements.txt
```

Execute o fluxo completo na raiz do projeto:

```bash
python run.py
```

Esse comando cria as pastas, prepara a seleção de docentes, obtém as fontes e publicações ausentes, limpa os dados, constrói e exporta os grafos, calcula métricas, gera figuras, relatório e roteiro de apresentação, e verifica a consistência dos artefatos. Uma falha interrompe o fluxo e devolve código de saída diferente de zero.

Na primeira execução é necessário acesso à internet. As seguintes reutilizam o cache quando os parâmetros e os hashes coincidem. Caso a cota pública da OpenAlex se esgote, configure `OPENALEX_API_KEY` no ambiente; não coloque a chave no repositório. Consulte a [documentação oficial de autenticação](https://help.openalex.org/api/authentication/).

Para reconstruir os resultados usando somente a coleta local:

```bash
python run.py --offline
```

Para obter uma nova coleta, substituindo o cache:

```bash
python run.py --atualizar
```

Também é possível direcionar os arquivos gerados para outra pasta:

```bash
python run.py --diretorio /tmp/coautoria
```

Os scripts localizam código e configuração a partir de seus próprios caminhos; o fluxo também funciona se `run.py` for chamado de outro diretório.

## Arquivos gerados

| Conteúdo | Local |
| --- | --- |
| Seleção dos docentes usada no processamento | `dados/docentes_selecionados.json` |
| Fontes, buscas, publicações, manifesto e índice da coleta | `dados/brutos/` |
| Publicações, autores, autorias, arestas, métricas e registros de exclusão | `dados/limpos/` |
| Grafos GraphML e GML | `resultados/rede_coautoria.graphml` e `.gml` |
| Estatísticas e registro de reprodutibilidade | `resultados/estatisticas.json` e `reprodutibilidade.json` |
| Figuras | `resultados/rede_coautoria.png` e `distribuicao_grau.png` |
| Relatório com resultados atuais | [resultados/relatorio.md](resultados/relatorio.md) |
| Roteiro com resultados atuais | [resultados/apresentacao.md](resultados/apresentacao.md) |

`dados/` e `resultados/` são ignorados pelo Git e podem ser reconstruídos por `python run.py`. Apagar apenas os resultados ou tabelas limpas permite refazê-los sem internet, desde que a coleta bruta validada esteja disponível. Apagar também `dados/brutos/` exige uma nova coleta; os valores podem mudar, pois as fontes são dinâmicas.

## Configuração versionada

- [codigo/configuracao/docentes.json](codigo/configuracao/docentes.json): nomes oficiais, OpenAlex IDs, ORCIDs, aliases e justificativas da seleção.
- [codigo/configuracao.py](codigo/configuracao.py): ano e fonte institucional do recorte.
- [codigo/modelos/apresentacao.md](codigo/modelos/apresentacao.md): modelo do roteiro, preenchido com os resultados calculados.

A configuração das identidades é uma entrada do estudo. O coletor gera uma cópia em `dados/` automaticamente, mas não redefine a amostra por coincidência de nomes. Alterações no recorte exigem conferir a seleção e executar o fluxo novamente.

As buscas de candidatos são preservadas para auditoria. Para exibi-las separadamente: `python codigo/coletar.py --buscar-autores`.

Os testes do cache e do tratamento de falhas podem ser executados sem internet:

```bash
python -m unittest discover -s tests -v
```
