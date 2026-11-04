"""Confere os artefatos reais produzidos pela análise, sem acesso à rede."""
import csv
import hashlib
import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path

from configuracao import ANO, parser_diretorio

import networkx as nx
import numpy as np

def ler(raiz, nome):
    with (raiz / 'dados/limpos' / nome).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def executar(raiz):
    ROOT = Path(raiz).resolve()
    esperados = [
        'dados/docentes_selecionados.json', 'dados/brutos/manifesto.json',
        'dados/brutos/coleta.json', 'dados/brutos/docentes_oficial.html',
        'dados/limpos/publicacoes.csv', 'dados/limpos/autores.csv',
        'dados/limpos/autorias.csv', 'dados/limpos/arestas.csv',
        'dados/limpos/metricas_autores.csv', 'dados/limpos/exclusoes.csv',
        'dados/limpos/autorias_descartadas.csv', 'resultados/relatorio.md',
        'resultados/apresentacao.md', 'resultados/rede_coautoria.png',
        'resultados/distribuicao_grau.png', 'resultados/rede_coautoria.graphml',
        'resultados/rede_coautoria.gml', 'resultados/rede_com_isolados.graphml',
        'resultados/estatisticas.json', 'resultados/reprodutibilidade.json',
        'resultados/identidades_unificadas.json',
    ]
    for relativo in esperados:
        path = ROOT / relativo
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f'Artefato ausente ou vazio: {relativo}')
    g = nx.read_graphml(ROOT / 'resultados/rede_coautoria.graphml')
    gml = nx.read_gml(ROOT / 'resultados/rede_coautoria.gml')
    stats = json.loads((ROOT / 'resultados/estatisticas.json').read_text())
    pubs = ler(ROOT, 'publicacoes.csv')
    assert len(pubs) == stats['publicacoes_retidas']
    assert all(p['ano'] == str(ANO) for p in pubs)
    assert len({p['publicacao_id'] for p in pubs}) == len(pubs)
    dois = [p['doi'] for p in pubs if p['doi']]
    assert len(set(dois)) == len(dois)
    assert len(g) == stats['nos'] and g.number_of_edges() == stats['arestas']
    assert set(g) == set(gml)
    assert {frozenset(e) for e in g.edges} == {frozenset(e) for e in gml.edges}
    assert not g.is_directed() and nx.number_of_selfloops(g) == 0
    por_pub = defaultdict(set)
    for a in ler(ROOT, 'autorias.csv'):
        por_pub[a['publicacao_id']].add(a['autor_id'])
    suporte = defaultdict(set)
    for pub, autores in por_pub.items():
        for u,v in combinations(sorted(autores),2):
            suporte[u,v].add(pub)
    assert len(suporte) == g.number_of_edges()
    for (u,v), obras in suporte.items():
        assert g[u][v]['weight'] == len(obras) == gml[u][v]['weight']
    for linha in ler(ROOT, 'arestas.csv'):
        u,v=linha['origem'],linha['destino']
        assert set(linha['publicacoes'].split(' | ')) == suporte[tuple(sorted([u,v]))]
    componentes=sorted(nx.connected_components(g),key=lambda c: (-len(c), sorted(c)))
    h=g.subgraph(componentes[0])
    assert len(componentes)==stats['componentes']
    assert nx.diameter(h)==stats['diametro_maior_componente']
    assert abs(nx.density(g)-stats['densidade']) < 1e-12
    assert abs(sum(nx.get_node_attributes(g,'pagerank').values())-1) < 1e-8
    ids=sorted(h)
    x=np.array([h.nodes[i]['autovetor_maior_componente'] for i in ids])
    ax=nx.to_numpy_array(h,nodelist=ids,weight='weight') @ x
    eigenvalue=float(x @ ax / (x @ x))
    assert np.linalg.norm(ax-eigenvalue*x) < 1e-6
    provenance=json.loads((ROOT/'resultados/reprodutibilidade.json').read_text())
    for nome,digest in provenance['sha256_entradas'].items():
        assert hashlib.sha256((ROOT/nome).read_bytes()).hexdigest()==digest
    print('OK: CSVs, rastreabilidade das arestas, pesos, GraphML/GML, estatísticas, PageRank, autovetor e hashes conferidos.')


def main():
    parser = parser_diretorio(__doc__)
    args = parser.parse_args()
    try:
        executar(args.diretorio)
    except (AssertionError, ValueError, OSError) as exc:
        parser.exit(1, f'Erro na verificação: {exc or "artefatos inconsistentes"}\n')


if __name__ == '__main__':
    main()
