"""Gera a entrega da semana 8 a partir dos JSONs locais, sem acessar a internet."""
import csv
import hashlib
import json
import os
import platform
import tempfile
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from string import Template

from configuracao import ANO, CODIGO, parser_diretorio

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'coautoria-matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import networkx as nx
import numpy as np
import scipy

def salvar_csv(pasta, nome, rows, campos):
    with (pasta / nome).open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()
        writer.writerows(rows)


def executar(raiz):
    ROOT = Path(raiz).resolve()
    CLEAN = ROOT / 'dados/limpos'
    OUT = ROOT / 'resultados'
    for pasta in [CLEAN, OUT]:
        pasta.mkdir(parents=True, exist_ok=True)
    docentes = json.loads((ROOT / 'dados/docentes_selecionados.json').read_text())
    seeds = {alias: d['openalex_id'] for d in docentes for alias in d['aliases_openalex']}
    nomes = {d['openalex_id']: d['nome_oficial'] for d in docentes}
    indice_path = ROOT / 'dados/brutos/coleta.json'
    if not indice_path.exists():
        raise ValueError('Coleta concluída não encontrada. Execute python run.py.')
    indice = json.loads(indice_path.read_text(encoding='utf-8'))
    if indice['ano'] != ANO:
        raise ValueError('O ano configurado difere da coleta. Execute python run.py --atualizar.')
    docentes_path = ROOT / 'dados/docentes_selecionados.json'
    if hashlib.sha256(docentes_path.read_bytes()).hexdigest() != indice['docentes_sha256']:
        raise ValueError('A seleção dos docentes difere da coleta. Execute python run.py.')
    arquivos = [ROOT / p['arquivo'] for p in indice['paginas']]
    for path, pagina in zip(arquivos, indice['paginas']):
        if hashlib.sha256(path.read_bytes()).hexdigest() != pagina['sha256']:
            raise ValueError(f'Página alterada desde a coleta: {path.name}')
    paginas = [json.loads(p.read_text()) for p in arquivos]
    raw = [w for p in paginas for w in p['results']]
    total_api = indice['total_api']
    if len({w['id'] for w in raw}) != total_api:
        raise ValueError('Coleta incompleta ou cache inconsistente: confira a paginação.')
    # Identidades são unificadas por ORCID informado pela fonte; nomes nunca são chave.
    orcids = defaultdict(set)
    for w in raw:
        for au in w.get('authorships') or []:
            a = au.get('author') or {}
            if a.get('id') and a.get('orcid'):
                orcids[a['orcid']].add(a['id'])
    aliases = dict(seeds)
    for ids in orcids.values():
        canon = sorted({seeds[i] for i in ids if i in seeds} or ids)[0]
        aliases.update({i: canon for i in ids})
    por_orcid = {o: aliases.get(sorted(ids)[0], sorted(ids)[0]) for o, ids in orcids.items()}
    por_orcid.update({d['orcid']: d['openalex_id'] for d in docentes if d.get('orcid')})
    G = nx.Graph(periodo=str(ANO), recorte='Docentes da lista atual do PPGCC-CM e coautores',
                 peso='Numero de publicacoes conjuntas no corpus selecionado')
    auditoria = Counter(registros_recebidos=len(raw))
    vistos_ids, vistos_dois = set(), set()
    publicacoes, autorias, exclusoes, autorias_descartadas = [], [], [], []
    edge_works = defaultdict(list)
    for w in sorted(raw, key=lambda x: x['id']):
        motivo = ''
        doi = (w.get('doi') or '').lower().strip()
        if w.get('publication_year') != ANO:
            motivo = 'fora_do_ano'
        elif w.get('type') not in {'article', 'conference-paper', 'review'}:
            motivo = 'tipo_' + str(w.get('type'))
        elif w.get('is_retracted') or w.get('is_paratext'):
            motivo = 'retratado_ou_paratexto'
        elif w['id'] in vistos_ids or (doi and doi in vistos_dois):
            motivo = 'id_ou_doi_duplicado'
        if motivo:
            auditoria[motivo] += 1
            exclusoes.append({'publicacao_id': w['id'], 'titulo': w.get('display_name') or '', 'motivo': motivo})
            continue
        authors = {}
        for au in w.get('authorships') or []:
            a = au.get('author') or {}
            if not a.get('id') and not a.get('orcid'):
                auditoria['autorias_sem_identificador_ignoradas'] += 1
                autorias_descartadas.append({'publicacao_id': w['id'], 'nome_informado': a.get('display_name') or au.get('raw_author_name') or '',
                                             'motivo': 'Sem OpenAlex ID e sem ORCID; identidade não inferida pelo nome'})
                continue
            aid = por_orcid.get(a.get('orcid')) or aliases.get(a.get('id'), a.get('id')) or a['orcid']
            if not a.get('id'):
                auditoria['autorias_recuperadas_por_orcid'] += 1
            inst = au.get('institutions') or []
            info = authors.setdefault(aid, {'nome': nomes.get(aid, a.get('display_name') or aid),
                                            'orcid': a.get('orcid') or '', 'instituicoes': set(), 'paises': set()})
            info['instituicoes'].update(i['display_name'] for i in inst if i.get('display_name'))
            info['paises'].update(i['country_code'] for i in inst if i.get('country_code'))
        if not (set(authors) & set(nomes)):
            raise ValueError(f"Publicação sem docente selecionado: {w['id']}")
        vistos_ids.add(w['id'])
        if doi:
            vistos_dois.add(doi)
        publicacoes.append({'publicacao_id': w['id'], 'doi': doi, 'titulo': w.get('display_name') or '',
                            'ano': ANO, 'data': w.get('publication_date') or '', 'tipo': w['type'],
                            'numero_autores': len(authors), 'docentes_semente': sum(a in nomes for a in authors)})
        for aid, info in sorted(authors.items()):
            if aid not in G:
                G.add_node(aid, nome=info['nome'], orcid=info['orcid'], docente_semente=aid in nomes, publicacoes=0)
            G.nodes[aid]['publicacoes'] += 1
            autorias.append({'publicacao_id': w['id'], 'autor_id': aid, 'nome': info['nome'],
                             'instituicoes': ' | '.join(sorted(info['instituicoes'])),
                             'paises': ' | '.join(sorted(info['paises'])), 'docente_semente': aid in nomes})
        for u, v in combinations(sorted(authors), 2):
            edge_works[u, v].append(w['id'])
    for (u, v), works in edge_works.items():
        G.add_edge(u, v, weight=len(works))
    completos = G.copy()
    isolados = list(nx.isolates(G))
    G.remove_nodes_from(isolados)
    if not G:
        raise ValueError('Corpus não produziu arestas de coautoria.')
    componentes = sorted(nx.connected_components(G), key=lambda c: (-len(c), sorted(c)))
    H = G.subgraph(componentes[0]).copy()
    pr = nx.pagerank(G, alpha=0.85, weight='weight', max_iter=1000, tol=1e-10)
    clustering = nx.clustering(G, weight=None)
    # Em rede desconectada, autovetor é calculado apenas na maior componente.
    ev = nx.eigenvector_centrality(H, weight='weight', max_iter=5000, tol=1e-10)
    for a in G:
        G.nodes[a].update(grau=G.degree(a), forca=G.degree(a, weight='weight'), pagerank=pr[a],
                          agrupamento_local=clustering[a])
        if a in ev:
            G.nodes[a]['autovetor_maior_componente'] = ev[a]
    stats = {'publicacoes_recebidas': len(raw), 'publicacoes_retidas': len(publicacoes),
             'tipos_retidos': dict(Counter(p['tipo'] for p in publicacoes)),
             'autores_antes_remocao_isolados': len(completos), 'isolados_removidos': len(isolados),
             'nos': len(G), 'arestas': G.number_of_edges(), 'densidade': nx.density(G),
             'grau_medio': sum(dict(G.degree()).values()) / len(G),
             'componentes': len(componentes), 'tamanhos_componentes': [len(c) for c in componentes],
             'nos_maior_componente': len(H), 'diametro_rede_completa': nx.diameter(G) if len(componentes) == 1 else None,
             'diametro_maior_componente': nx.diameter(H),
             'agrupamento_medio_nao_ponderado': nx.average_clustering(G),
             'docentes_lista': len(docentes), 'docentes_com_publicacao_retida': len(set(completos) & set(nomes)),
             'docentes_sem_publicacao_retida': [nomes[a] for a in nomes if a not in completos],
             'auditoria': dict(auditoria)}
    salvar_csv(CLEAN, 'publicacoes.csv', publicacoes, ['publicacao_id','doi','titulo','ano','data','tipo','numero_autores','docentes_semente'])
    salvar_csv(CLEAN, 'autorias.csv', autorias, ['publicacao_id','autor_id','nome','instituicoes','paises','docente_semente'])
    salvar_csv(CLEAN, 'exclusoes.csv', exclusoes, ['publicacao_id','titulo','motivo'])
    salvar_csv(CLEAN, 'autorias_descartadas.csv', autorias_descartadas, ['publicacao_id','nome_informado','motivo'])
    salvar_csv(CLEAN, 'autores.csv', [dict(autor_id=a, **d, isolado_removido=a in isolados) for a,d in completos.nodes(data=True)],
               ['autor_id','nome','orcid','docente_semente','publicacoes','isolado_removido'])
    salvar_csv(CLEAN, 'arestas.csv', [{'origem':u,'destino':v,'peso':len(ws),'publicacoes':' | '.join(ws)} for (u,v),ws in sorted(edge_works.items())],
               ['origem','destino','peso','publicacoes'])
    campos = ['autor_id','nome','docente_semente','grau','forca','pagerank','agrupamento_local','autovetor_maior_componente']
    ranking = [{'autor_id':a, **{k:d.get(k,'') for k in campos[1:]}} for a,d in G.nodes(data=True)]
    ranking.sort(key=lambda d: (-d['pagerank'], d['autor_id']))
    salvar_csv(CLEAN, 'metricas_autores.csv', ranking, campos)
    (OUT / 'estatisticas.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2))
    (OUT / 'identidades_unificadas.json').write_text(json.dumps({k:v for k,v in aliases.items() if k!=v},ensure_ascii=False,indent=2))
    nx.write_graphml(G, OUT / 'rede_coautoria.graphml')
    nx.write_graphml(completos, OUT / 'rede_com_isolados.graphml')
    nx.write_gml(G, OUT / 'rede_coautoria.gml')
    fig, axes = plt.subplots((len(componentes)+1)//2, 2, figsize=(16, 11), facecolor='white', squeeze=False)
    for idx, ax in enumerate(axes.flat):
        ax.axis('off')
        if idx >= len(componentes):
            continue
        C = G.subgraph(componentes[idx]).copy()
        pos = nx.spring_layout(C, seed=42, iterations=200, weight='weight', k=2 / np.sqrt(len(C)))
        nx.draw_networkx_edges(C,pos,ax=ax,alpha=.23,edge_color='#64748b',width=[.5+.3*d['weight'] for _,_,d in C.edges(data=True)])
        nx.draw_networkx_nodes(C,pos,ax=ax,node_color=['#ea580c' if C.nodes[a]['docente_semente'] else '#2563eb' for a in C],
                               node_size=[35+2500*pr[a] for a in C],alpha=.9,linewidths=.5,edgecolors='white')
        nx.draw_networkx_labels(C,pos,ax=ax,labels={a:C.nodes[a]['nome'] for a in C if a in nomes},font_size=7)
        ax.set_title(f'Componente {idx+1} · {len(C)} autores · {C.number_of_edges()} ligações',fontsize=12)
        ax.margins(.15)
    fig.suptitle(f'Coautoria de docentes do PPGCC-CM e colaboradores — {ANO}\n{len(G)} autores · {G.number_of_edges()} ligações · {len(publicacoes)} publicações',fontsize=17)
    fig.legend(handles=[Line2D([0],[0],marker='o',color='w',markerfacecolor=c,label=l,markersize=9)
                        for c,l in [('#ea580c','Docentes da lista institucional'),('#2563eb','Demais coautores')]],loc='lower left')
    fig.text(.99,.02,'Painéis com escalas espaciais independentes; posições sem significado geográfico.\nTamanho: PageRank | Espessura: publicações conjuntas | Fonte: OpenAlex.',ha='right',fontsize=8)
    fig.tight_layout(rect=[0,.06,1,.93])
    fig.savefig(OUT / 'rede_coautoria.png',dpi=180)
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4.5))
    graus=Counter(dict(G.degree()).values())
    ax.bar(list(graus),list(graus.values()),color='#2563eb')
    ax.set(xlabel='Grau (número de coautores distintos)',ylabel='Número de pesquisadores',title=f'Distribuição de grau — corpus de {ANO}')
    fig.tight_layout(); fig.savefig(OUT / 'distribuicao_grau.png',dpi=180); plt.close(fig)
    fontes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in arquivos + [docentes_path, indice_path]}
    (OUT/'reprodutibilidade.json').write_text(json.dumps({'python':platform.python_version(),'networkx':nx.__version__,
        'matplotlib':matplotlib.__version__,'numpy':np.__version__,'scipy':scipy.__version__,'semente_layout':42,'sha256_entradas':fontes},indent=2))
    tabela='\n'.join(f"| {r['nome']} | {r['grau']} | {r['pagerank']:.5f} | {r['agrupamento_local']:.3f} |" for r in ranking[:10])
    metricas='\n'.join(f'| {k} | {v} |' for k,v in [
        ('Publicações recebidas',len(raw)),('Publicações retidas',len(publicacoes)),('Nós',len(G)),
        ('Arestas',G.number_of_edges()),('Densidade',f'{nx.density(G):.6f}'),('Grau médio',f"{stats['grau_medio']:.2f}"),
        ('Componentes conectadas',len(componentes)),('Nós na maior componente',len(H)),
        ('Diâmetro da maior componente',nx.diameter(H)),('Isolados removidos',len(isolados))])
    (OUT/'relatorio.md').write_text(f'''# Resultados do piloto — semana 8

Valores calculados pelo script `codigo/analisar.py`, a partir dos dados reais obtidos na coleta local. Arquivo gerado automaticamente; execute `python run.py` para reconstruí-lo.

| Estatística | Valor |
| --- | --- |
{metricas}

Tamanhos das componentes: {', '.join(map(str,stats['tamanhos_componentes']))}.
Tipos retidos: {json.dumps(stats['tipos_retidos'],ensure_ascii=False)}.
Docentes da lista com publicação retida: {stats['docentes_com_publicacao_retida']} de {len(docentes)}.
Docentes sem publicação retida: {', '.join(stats['docentes_sem_publicacao_retida']) or 'nenhum'}.

O diâmetro usa distâncias em número de arestas, sem pesos. {"A rede é desconectada: não existe um diâmetro finito para toda a rede; o valor apresentado pertence somente à maior componente." if len(componentes)>1 else "A rede é conectada: o diâmetro da maior componente é também o da rede inteira."}

## Rede de coautoria

![Rede de coautoria](rede_coautoria.png)

Laranja identifica docentes usados como sementes; azul identifica demais coautores. Os colaboradores não foram classificados automaticamente como docentes ou alunos. As posições são apenas um arranjo visual, sem significado geográfico.

![Distribuição de grau](distribuicao_grau.png)

## Dez maiores valores de PageRank no corpus

| Pesquisador | Grau | PageRank | Agrupamento local |
| --- | --- | --- | --- |
{tabela}

PageRank ponderado pelo número de publicações conjuntas, com amortecimento 0,85. Agrupamento local não ponderado. A centralidade de autovetor ponderada está em `dados/limpos/metricas_autores.csv` e foi calculada apenas na maior componente; células vazias significam “fora do domínio de cálculo”, e não zero. Os rankings descrevem esta amostra e não medem qualidade científica.

## Leitura dos resultados

A densidade de {nx.density(G):.4%} indica a fração das ligações possíveis que aparece no corpus. Existem {len(componentes)} componentes, e a maior reúne {len(H)/len(G):.1%} dos autores. Uma componente é um conjunto de pesquisadores ligados por caminhos de coautoria nas publicações selecionadas. Ausência de ligação nesta amostra não comprova ausência de colaboração fora dela.

Cada artigo com k autores gera até k(k−1)/2 pares, aumentando mecanicamente o agrupamento local. Esse indicador, isoladamente, não demonstra exclusão social ou “panelas”. A coleta é centrada em docentes: não inclui necessariamente artigos publicados apenas pelos demais colaboradores.

## Auditoria

Contagens de entrada e exclusões: `{json.dumps(dict(auditoria),ensure_ascii=False)}`.
As linhas excluídas estão em `dados/limpos/exclusoes.csv`; as ligações têm publicações de suporte em `dados/limpos/arestas.csv`. Autorias sem OpenAlex ID e sem ORCID foram descartadas e registradas em `autorias_descartadas.csv`. Isso pode reduzir graus e ligações; a rede representa apenas autores com identificador persistente disponível. ORCID permite recuperar autorias mesmo sem OpenAlex ID. Nomes e afiliações ausentes não são inventados. Isolados são preservados no arquivo alternativo `rede_com_isolados.graphml`.
''',encoding='utf-8')
    modelo = Template((CODIGO / 'modelos/apresentacao.md').read_text(encoding='utf-8'))
    texto = modelo.substitute(
        ano=ANO, docentes=len(docentes), recebidas=len(raw), publicacoes=len(publicacoes),
        tipos='; '.join(f'{n} {tipo}' for tipo, n in stats['tipos_retidos'].items()),
        exclusoes='; '.join(f'{n} {motivo}' for motivo, n in auditoria.items() if motivo.startswith('tipo_')) or 'nenhuma exclusão por tipo',
        descartadas=auditoria.get('autorias_sem_identificador_ignoradas', 0),
        recuperadas=auditoria.get('autorias_recuperadas_por_orcid', 0),
        nos=len(G), arestas=f'{G.number_of_edges():,}'.replace(',', '.'),
        densidade=f'{nx.density(G):.2%}'.replace('.', ','), componentes=len(componentes),
        maior=len(H), fracao=f'{len(H)/len(G):.1%}'.replace('.', ','),
        diametro=stats['diametro_maior_componente'],
        explicacao_diametro=('A rede é desconectada: esse diâmetro pertence apenas à maior componente.'
                             if len(componentes) > 1 else 'A rede é conectada: esse também é o diâmetro da rede inteira.'))
    (OUT / 'apresentacao.md').write_text(texto, encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=False,indent=2))


def main():
    parser = parser_diretorio(__doc__)
    args = parser.parse_args()
    try:
        executar(args.diretorio)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Erro na análise: {exc}\n')


if __name__ == '__main__':
    main()
