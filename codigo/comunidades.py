"""Detecção ponderada por Louvain e visualização comum aos dois recortes."""
import colorsys
import math
from collections import defaultdict

import networkx as nx
import numpy as np


PARAMETROS_LOUVAIN = {'algoritmo': 'Louvain', 'peso': 'weight', 'resolucao': 1.0, 'semente': 42}
CAMPOS_COMUNIDADES = ['comunidade_louvain', 'cor_comunidade', 'autores', 'arestas_internas', 'peso_interno',
                      'na_maior_componente']
ATRIBUTOS_COMUNIDADE = ['comunidade_louvain', 'cor_comunidade']
ARQUIVO_FIGURA = 'rede_comunidades_louvain.png'
_CORES = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
          '#8c564b', '#e377c2', '#17becf', '#bcbd22', '#7f7f7f',
          '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5',
          '#c49c94', '#f7b6d2', '#9edae5', '#dbdb8d', '#c7c7c7']
_CORES_USADAS = set(_CORES)


def cor_comunidade(indice):
    # As primeiras comunidades usam uma paleta categórica; as demais recebem
    # cores geradas sem repetir ciclicamente as primeiras vinte entradas.
    while len(_CORES) <= indice:
        i = len(_CORES)
        r, g, b = colorsys.hsv_to_rgb((i * .618033988749895) % 1,
                                     .55 + .25 * ((i * .4142135623730951) % 1),
                                     .70 + .25 * ((i * .7320508075688772) % 1))
        codigo = (round(255 * r) << 16) + (round(255 * g) << 8) + round(255 * b)
        cor = f'#{codigo:06x}'
        while cor in _CORES_USADAS:
            codigo = (codigo + 1) % 0x1000000
            cor = f'#{codigo:06x}'
        _CORES.append(cor)
        _CORES_USADAS.add(cor)
    return _CORES[indice]


def detectar_comunidades(g):
    """Atribui IDs a partir de 1, ordenados por tamanho, e cores aos autores."""
    if not g.number_of_edges():
        raise ValueError('A detecção de comunidades exige uma rede com arestas de coautoria.')
    # Canonizar a inserção torna a semente independente da ordem de leitura.
    ordenado = nx.Graph()
    ordenado.add_nodes_from(sorted(g, key=str))
    ordenado.add_edges_from(sorted(g.edges(data=True), key=lambda e: tuple(sorted(map(str, e[:2])))))
    grupos = nx.community.louvain_communities(
        ordenado, weight=PARAMETROS_LOUVAIN['peso'],
        resolution=PARAMETROS_LOUVAIN['resolucao'], seed=PARAMETROS_LOUVAIN['semente'])
    grupos.sort(key=lambda membros: (-len(membros), sorted(map(str, membros))))
    maior = min(nx.connected_components(g), key=lambda c: (-len(c), min(map(str, c))))
    resumo = []
    for indice, membros in enumerate(grupos):
        cor = cor_comunidade(indice)
        comunidade = indice + 1
        for autor in membros:
            g.nodes[autor].update(comunidade_louvain=comunidade, cor_comunidade=cor)
        subgrafo = g.subgraph(membros)
        resumo.append(dict(comunidade_louvain=comunidade, cor_comunidade=cor,
                           autores=len(membros), arestas_internas=subgrafo.number_of_edges(),
                           peso_interno=subgrafo.size(weight='weight'), na_maior_componente=membros <= maior))
    modularidade = nx.community.modularity(g, grupos, weight='weight', resolution=PARAMETROS_LOUVAIN['resolucao'])
    g.graph.update(algoritmo_comunidades='Louvain', resolucao_louvain=PARAMETROS_LOUVAIN['resolucao'],
                   semente_louvain=PARAMETROS_LOUVAIN['semente'], modularidade_louvain=modularidade)
    return dict(PARAMETROS_LOUVAIN, quantidade=len(grupos), modularidade=modularidade, comunidades=resumo,
                quantidade_maior_componente=sum(c['na_maior_componente'] for c in resumo),
                autores_maior_componente=len(maior))


def _posicoes_componente(g):
    """Layout em dois níveis; evita calcular forças entre todos os autores da rede."""
    grupos = defaultdict(list)
    for autor in sorted(g, key=str):
        grupos[g.nodes[autor]['comunidade_louvain']].append(autor)
    agregado = nx.Graph()
    agregado.add_nodes_from(sorted(grupos))
    for u, v, dados in g.edges(data=True):
        origem, destino = g.nodes[u]['comunidade_louvain'], g.nodes[v]['comunidade_louvain']
        if origem != destino:
            if not agregado.has_edge(origem, destino):
                agregado.add_edge(origem, destino, weight=0)
            agregado[origem][destino]['weight'] += dados.get('weight', 1)
    centros = nx.spring_layout(agregado, seed=42, weight='weight', iterations=150)
    posicoes = {}
    for comunidade, membros in grupos.items():
        centro = centros[comunidade]
        raio = (.4 * min(np.linalg.norm(centro - outro) for c, outro in centros.items() if c != comunidade)
                if len(centros) > 1 else 1.)
        if len(membros) <= 500:
            local = nx.spring_layout(g.subgraph(membros), seed=42, weight='weight', iterations=60)
        else:
            # Disco determinístico para comunidades grandes, sem custo quadrático.
            local = {autor: math.sqrt((i + .5) / len(membros)) *
                     np.array([math.cos(i * 2.399963229728653), math.sin(i * 2.399963229728653)])
                     for i, autor in enumerate(membros)}
        posicoes.update({autor: centro + raio * local[autor] for autor in membros})
    return posicoes


def figura_comunidades(g, out, ano, resultado):
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    componentes = sorted(nx.connected_components(g), key=lambda c: (-len(c), min(map(str, c))))
    maior = g.subgraph(componentes[0])
    outras = g.subgraph(set(g) - set(maior))
    fig, axes = plt.subplots(1, 2 if outras else 1, figsize=(18 if outras else 12, 11), squeeze=False,
                             gridspec_kw={'width_ratios': [1.5, 1]} if outras else None)
    pos_maior = _posicoes_componente(maior)
    pos_outras = {}
    colunas = math.ceil(math.sqrt(len(componentes) - 1))
    for indice, membros in enumerate(componentes[1:]):
        local = _posicoes_componente(g.subgraph(membros))
        deslocamento = np.array([3. * (indice % colunas), -3. * (indice // colunas)])
        pos_outras.update({autor: pos * .6 + deslocamento for autor, pos in local.items()})
    max_pr = max(nx.get_node_attributes(g, 'pagerank').values(), default=1.)
    for ax, rede, pos, titulo in zip(axes.flat, [maior, outras], [pos_maior, pos_outras],
                                    ['Maior componente', 'Demais componentes']):
        nx.draw_networkx_edges(rede, pos, ax=ax, edge_color='#94a3b8', alpha=.18,
                               width=[.25 + .15 * math.log1p(d.get('weight', 1)) for _, _, d in rede.edges(data=True)])
        nx.draw_networkx_nodes(rede, pos, ax=ax,
                              node_color=[rede.nodes[a]['cor_comunidade'] for a in rede],
                              node_size=[5 + 65 * math.sqrt(rede.nodes[a].get('pagerank', 0.) / max_pr) for a in rede],
                              linewidths=0, alpha=.85)
        comunidades = {rede.nodes[a]['comunidade_louvain'] for a in rede}
        ax.set_title(f'{titulo}\n{len(rede):,} autores · {len(comunidades):,} comunidades', fontsize=12)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.margins(.04)
    # IDs permitem localizar as maiores comunidades também no CSV e no GraphML.
    for comunidade in resultado['comunidades'][:10]:
        membros = [a for a in maior if maior.nodes[a]['comunidade_louvain'] == comunidade['comunidade_louvain']]
        if membros:
            centro = np.mean([pos_maior[a] for a in membros], axis=0)
            axes[0, 0].annotate(str(comunidade['comunidade_louvain']), centro, ha='center', va='center', fontsize=9,
                                bbox=dict(boxstyle='round,pad=.2', fc='white', ec=comunidade['cor_comunidade'], alpha=.9))
    fig.suptitle(f'Comunidades de coautoria — Louvain ponderado — {ano}\n'
                 f'{len(g):,} autores · {resultado["quantidade"]:,} comunidades · modularidade Q = {resultado["modularidade"]:.4f}',
                 fontsize=17)
    fig.legend(handles=[Line2D([], [], marker='o', linestyle='', color=c['cor_comunidade'],
                               label=f'C{c["comunidade_louvain"]} · {c["autores"]} autores')
                        for c in resultado['comunidades'][:10]], loc='lower center', ncol=5, fontsize=9,
               title='Maiores comunidades — identificação completa em comunidades_louvain.csv')
    fig.text(.5, .11, 'Cor: comunidade Louvain · Tamanho: PageRank · Arestas: coautorias\n'
             'Layout por comunidade; componentes em escalas independentes. Posições sem significado geográfico.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=[0, .16, 1, .92])
    fig.savefig(out / ARQUIVO_FIGURA, dpi=180)
    plt.close(fig)


def verificar_comunidades(g, resultado, resumo_csv, ranking):
    """Confere cobertura, pesos, modularidade e correspondência entre exportações."""
    assert all(resultado[chave] == valor for chave, valor in PARAMETROS_LOUVAIN.items())
    grupos = defaultdict(set)
    for autor, dados in g.nodes(data=True):
        grupos[dados['comunidade_louvain']].add(autor)
    resumo = resultado['comunidades']
    assert len(grupos) == resultado['quantidade'] == len(resumo) == len(resumo_csv)
    assert set(grupos) == set(range(1, len(grupos) + 1))
    assert nx.community.is_partition(g, grupos.values())
    assert [r['autores'] for r in resumo] == sorted(map(len, grupos.values()), reverse=True)
    maior = min(nx.connected_components(g), key=lambda c: (-len(c), min(map(str, c))))
    ids_maior = {g.nodes[a]['comunidade_louvain'] for a in maior}
    assert resultado['quantidade_maior_componente'] == len(ids_maior)
    assert resultado['autores_maior_componente'] == len(maior)
    for esperado, linha in zip(resumo, resumo_csv):
        comunidade = esperado['comunidade_louvain']
        membros = grupos[comunidade]
        assert esperado['cor_comunidade'] == cor_comunidade(comunidade - 1)
        assert all(g.nodes[a]['cor_comunidade'] == esperado['cor_comunidade'] for a in membros)
        assert esperado['autores'] == len(membros)
        assert membros <= maior or membros.isdisjoint(maior)
        assert esperado['na_maior_componente'] == (comunidade in ids_maior)
        subgrafo = g.subgraph(membros)
        assert esperado['arestas_internas'] == subgrafo.number_of_edges()
        assert esperado['peso_interno'] == subgrafo.size(weight='weight')
        assert all(str(linha[campo]) == str(esperado[campo]) for campo in CAMPOS_COMUNIDADES)
    assert abs(nx.community.modularity(g, grupos.values(), weight='weight', resolution=resultado['resolucao'])
               - resultado['modularidade']) < 1e-12
    assert g.graph['algoritmo_comunidades'] == 'Louvain'
    assert g.graph['semente_louvain'] == resultado['semente']
    assert g.graph['resolucao_louvain'] == resultado['resolucao']
    assert abs(g.graph['modularidade_louvain'] - resultado['modularidade']) < 1e-12
    assert len(ranking) == len(g) and {r['autor_id'] for r in ranking} == set(g)
    for linha in ranking:
        dados = g.nodes[linha['autor_id']]
        assert int(linha['comunidade_louvain']) == dados['comunidade_louvain']
        assert linha['cor_comunidade'] == dados['cor_comunidade']
