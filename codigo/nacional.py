import hashlib
import json
import math
import os
import unicodedata
from collections import Counter, defaultdict
from itertools import combinations, product
from pathlib import Path

from analisar import salvar_csv, tabela_markdown
from coletar import Coleta, salvar_json
from configuracao import ANO, CODIGO, parser_diretorio

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from scipy.sparse.linalg import eigsh

SEM_UF = 'Brasil sem UF'
EXTERIOR = 'Exterior'
SEM_AFILIACAO = 'Sem afiliação identificada'
CONFIG = CODIGO / 'configuracao/nacional.json'
CAMPOS_OBRAS = ('id,doi,display_name,publication_year,publication_date,type,is_retracted,'
                'is_paratext,authorships,is_authors_truncated,primary_topic')


def especificacao():
    return dict(json.loads(CONFIG.read_text(encoding='utf-8')), ano=ANO)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entrada(raiz, path):
    return {'arquivo': path.relative_to(raiz).as_posix(), 'sha256': digest(path)}


def paginar(coleta, entidade, parametros, prefixo):
    cursor = '*' if os.getenv('OPENALEX_API_KEY') else None
    page, total = 1, None
    vistos, cursores, arquivos, resultados = set(), set(), [], []
    while True:
        consulta = dict(parametros, **{'per-page': 100})
        consulta.update({'cursor': cursor} if cursor is not None else {'page': page})
        nome = f'nacional/{prefixo}_{page:04d}.json'
        data = coleta.obter(f'https://api.openalex.org/{entidade}', consulta, nome)
        if total is None:
            total = data['meta']['count']
            if cursor is None and total > 10000:
                raise RuntimeError('O recorte ultrapassa 10.000 registros. Configure OPENALEX_API_KEY '
                                   'para a paginação completa; nenhum resultado parcial será analisado.')
        if data['meta']['count'] != total:
            raise RuntimeError('O total da consulta mudou durante a coleta. Repita com --atualizar.')
        ids = [item['id'] for item in data['results']]
        if len(set(ids)) != len(ids) or vistos.intersection(ids):
            raise RuntimeError('Paginação com registros repetidos. Repita com --atualizar.')
        vistos.update(ids)
        resultados.extend(data['results'])
        arquivos.append(entrada(coleta.raiz, coleta.raw / nome))
        print(f'{prefixo}: {len(vistos)}/{total} registros', flush=True)
        if len(vistos) == total:
            break
        if not ids or len(vistos) > total:
            raise RuntimeError('Paginação incompleta ou inconsistente; análise cancelada.')
        if cursor is not None:
            proximo = data['meta'].get('next_cursor')
            if not proximo or proximo in cursores:
                raise RuntimeError('Cursor ausente ou repetido antes de concluir a consulta.')
            cursores.add(proximo)
            cursor = proximo
        page += 1
    return resultados, arquivos


def coletar(raiz, offline=False, atualizar=False):
    coleta = Coleta(raiz, offline=offline, atualizar=atualizar)
    if not atualizar and (coleta.raw / 'coleta_nacional.json').exists():
        try:
            indice, _, _, _ = ler_coleta(coleta.raiz)
        except (ValueError, OSError):
            if offline:
                raise
        else:
            print(f'Cache nacional validado: {indice["total_api"]} registros.', flush=True)
            return
    spec = especificacao()
    filtro = (f'authorships.institutions.country_code:{spec["pais"].lower()},'
              f'primary_topic.field.id:{spec["campo_openalex"]},publication_year:{spec["ano"]}')
    obras, paginas = paginar(coleta, 'works', {
        'filter': filtro, 'select': CAMPOS_OBRAS, 'sort': 'publication_date:asc',
    }, f'publicacoes_{spec["ano"]}')
    ids = sorted({i['id'].rsplit('/', 1)[-1] for w in obras for au in w.get('authorships') or []
                  for i in au.get('institutions') or [] if i.get('country_code') == 'BR' and i.get('id')})
    institucionais = []
    for inicio in range(0, len(ids), 100):
        lote = ids[inicio:inicio + 100]
        instituicoes, arquivos = paginar(coleta, 'institutions', {
            'filter': 'ids.openalex:' + '|'.join(lote),
            'select': 'id,display_name,country_code,geo,ror',
        }, f'instituicoes_{inicio // 100 + 1:03d}')
        retornados = {i['id'].rsplit('/', 1)[-1] for i in instituicoes}
        if not retornados.issubset(lote):
            raise RuntimeError('A consulta de instituições retornou IDs não solicitados.')
        institucionais.extend(arquivos)
    coleta.obter(spec['fonte_ufs'], {}, 'nacional/ufs_ibge.json', json_lista=True)
    spec_path = coleta.raiz / 'dados/recorte_nacional.json'
    salvar_json(spec_path, spec)
    salvar_json(coleta.raw / 'coleta_nacional.json', {
        'recorte': spec, 'filtro': filtro, 'total_api': len(obras), 'paginas': paginas,
        'instituicoes': institucionais,
        'fontes': [entrada(coleta.raiz, coleta.raw / 'nacional/ufs_ibge.json'), entrada(coleta.raiz, spec_path)],
    })


def ler_coleta(raiz):
    indice_path = raiz / 'dados/brutos/coleta_nacional.json'
    indice = json.loads(indice_path.read_text(encoding='utf-8'))
    if indice['recorte'] != especificacao():
        raise ValueError('O recorte nacional difere da coleta. Execute python run.py.')
    for item in indice['paginas'] + indice['instituicoes'] + indice['fontes']:
        path = raiz / item['arquivo']
        if digest(path) != item['sha256']:
            raise ValueError(f'Entrada alterada desde a coleta: {item["arquivo"]}')
    obras = [w for pagina in indice['paginas']
             for w in json.loads((raiz / pagina['arquivo']).read_text(encoding='utf-8'))['results']]
    if len(obras) != indice['total_api'] or len({w['id'] for w in obras}) != len(obras):
        raise ValueError('Coleta nacional incompleta ou com duplicações.')
    instituicoes = {i['id']: i for pagina in indice['instituicoes']
                    for i in json.loads((raiz / pagina['arquivo']).read_text(encoding='utf-8'))['results']}
    ufs = json.loads((raiz / 'dados/brutos/nacional/ufs_ibge.json').read_text(encoding='utf-8'))
    return indice, obras, instituicoes, ufs


def normalizar(valor):
    return ''.join(c for c in unicodedata.normalize('NFKD', valor or '')
                   if not unicodedata.combining(c)).casefold().strip()


def mapa_ufs(ufs):
    return {normalizar(chave): uf['regiao']['nome'] for uf in ufs
            for chave in [uf['nome'], uf['sigla'], 'BR-' + uf['sigla']]}


def regioes_autoria(autoria, instituicoes, ufs):
    regioes, paises = set(), set(autoria.get('countries') or [])
    for referencia in autoria.get('institutions') or []:
        inst = instituicoes.get(referencia.get('id'), referencia)
        pais = inst.get('country_code') or referencia.get('country_code')
        if pais:
            paises.add(pais)
        if pais == 'BR':
            regioes.add(ufs.get(normalizar((inst.get('geo') or {}).get('region')), SEM_UF))
    if 'BR' in paises and not regioes:
        regioes.add(SEM_UF)
    return regioes, paises


def categorias_autor(regioes, paises):
    return sorted(regioes) if regioes else [EXTERIOR if paises and 'BR' not in paises else SEM_AFILIACAO]


def identidades(obras):
    grupos = nx.utils.UnionFind()
    for w in obras:
        for au in w.get('authorships') or []:
            a = au.get('author') or {}
            ids = [i for i in [a.get('id'), a.get('orcid')] if i]
            if ids:
                grupos.union(*ids)
    aliases = {}
    for grupo in grupos.to_sets():
        canon = min((i for i in grupo if '/A' in i), default=min(grupo))
        aliases.update({i: canon for i in grupo})
    return aliases


def construir_rede(obras, instituicoes, ufs, spec):
    aliases = identidades(obras)
    por_uf = mapa_ufs(ufs)
    g = nx.Graph(ano=spec['ano'], campo=spec['campo'], recorte='Afiliação brasileira e coautores',
                 peso='Publicações conjuntas', geografia='Instituição da autoria; UF da sede no OpenAlex')
    auditoria = Counter(registros_recebidos=len(obras))
    pubs, autorias, exclusoes, descartadas = [], [], [], []
    vistos, dois = set(), set()
    suporte = defaultdict(list)
    regioes_por_autor, paises_por_autor = defaultdict(set), defaultdict(set)
    producao = Counter()
    for w in sorted(obras, key=lambda item: item['id']):
        doi = (w.get('doi') or '').strip().lower()
        campo = ((w.get('primary_topic') or {}).get('field') or {}).get('id') or ''
        motivo = ''
        if w.get('publication_year') != spec['ano']:
            motivo = 'fora_do_ano'
        elif campo.rsplit('/', 1)[-1] != spec['campo_openalex']:
            motivo = 'fora_da_computacao'
        elif w.get('type') not in spec['tipos']:
            motivo = 'tipo_' + str(w.get('type'))
        elif w.get('is_retracted') or w.get('is_paratext'):
            motivo = 'retratado_ou_paratexto'
        elif w.get('is_authors_truncated'):
            motivo = 'autorias_truncadas_na_fonte'
        elif w['id'] in vistos or doi and doi in dois:
            motivo = 'id_ou_doi_duplicado'
        autores, regioes_pub = {}, set()
        if not motivo:
            for au in w.get('authorships') or []:
                a = au.get('author') or {}
                regioes, paises = regioes_autoria(au, instituicoes, por_uf)
                regioes_pub.update(regioes)
                aid = aliases.get(a.get('id')) or aliases.get(a.get('orcid'))
                if not aid:
                    auditoria['autorias_sem_identificador'] += 1
                    descartadas.append({'publicacao_id': w['id'], 'nome_informado': a.get('display_name') or
                                        au.get('raw_author_name') or '', 'motivo': 'sem_id_e_sem_orcid'})
                    continue
                if not a.get('id'):
                    auditoria['autorias_recuperadas_por_orcid'] += 1
                info = autores.setdefault(aid, {'nome': a.get('display_name') or aid,
                    'regioes': set(), 'paises': set(), 'instituicoes': set()})
                info['regioes'].update(regioes)
                info['paises'].update(paises)
                info['instituicoes'].update(i['id'] for i in au.get('institutions') or [] if i.get('id'))
            if not regioes_pub:
                motivo = 'sem_afiliacao_brasileira_nas_autorias'
            elif not autores:
                motivo = 'sem_autores_identificaveis'
        if motivo:
            auditoria[motivo] += 1
            exclusoes.append({'publicacao_id': w['id'], 'titulo': w.get('display_name') or '', 'motivo': motivo})
            continue
        vistos.add(w['id'])
        if doi:
            dois.add(doi)
        for regiao in regioes_pub:
            producao[regiao] += 1 / len(regioes_pub)
        pubs.append({'publicacao_id': w['id'], 'doi': doi, 'titulo': w.get('display_name') or '',
                     'ano': spec['ano'], 'tipo': w['type'], 'numero_autores': len(autores),
                     'regioes_brasileiras': ' | '.join(sorted(regioes_pub))})
        for aid, info in sorted(autores.items()):
            if aid not in g:
                g.add_node(aid, nome=info['nome'], publicacoes=0)
            g.nodes[aid]['publicacoes'] += 1
            regioes_por_autor[aid].update(info['regioes'])
            paises_por_autor[aid].update(info['paises'])
            autorias.append({'publicacao_id': w['id'], 'autor_id': aid, 'nome': info['nome'],
                            'instituicoes': ' | '.join(sorted(info['instituicoes'])),
                            'paises': ' | '.join(sorted(info['paises'])),
                            'regioes_brasileiras': ' | '.join(sorted(info['regioes']))})
        for u, v in combinations(sorted(autores), 2):
            suporte[u, v].append(w['id'])
    for (u, v), works in suporte.items():
        g.add_edge(u, v, weight=len(works))
    for aid in g:
        g.nodes[aid]['regioes'] = ' | '.join(categorias_autor(regioes_por_autor[aid], paises_por_autor[aid]))
        g.nodes[aid]['afiliacao_brasileira'] = bool(regioes_por_autor[aid])
    return g, pubs, autorias, exclusoes, descartadas, suporte, producao, auditoria, aliases


def metricas(g):
    componentes = sorted(nx.connected_components(g), key=lambda c: (-len(c), min(c)))
    maior = g.subgraph(componentes[0])
    pr = nx.pagerank(g, alpha=.85, weight='weight', max_iter=1000, tol=1e-12)
    agrupamento = nx.clustering(g, weight=None)
    ids = sorted(maior)
    if len(ids) <= 2:
        ev = nx.eigenvector_centrality(maior, weight='weight', max_iter=5000, tol=1e-10)
    else:
        adj = nx.to_scipy_sparse_array(maior, nodelist=ids, weight='weight', dtype=float)
        _, vetores = eigsh(adj, k=1, which='LA', v0=np.full(len(ids), 1 / math.sqrt(len(ids))), tol=1e-10)
        ev = dict(zip(ids, np.abs(vetores[:, 0])))
    for a in g:
        g.nodes[a].update(grau=g.degree(a), forca=g.degree(a, weight='weight'), pagerank=pr[a],
                          agrupamento_local=agrupamento[a])
        if a in ev:
            g.nodes[a]['autovetor_maior_componente'] = float(ev[a])
    return componentes


def agregar_regioes(g, producao, regioes):
    categorias = regioes + [SEM_UF, EXTERIOR, SEM_AFILIACAO]
    linhas = {r: {'regiao': r, 'autores_com_afiliacao': 0, 'autores_fracionados': 0.,
                  'publicacoes_fracionadas': producao[r], 'pagerank_fracionado': 0.,
                  'agrupamento_medio': 0., 'grau_medio': 0.} for r in categorias}
    for a, info in g.nodes(data=True):
        regs = info['regioes'].split(' | ')
        for r in regs:
            linha = linhas[r]
            fracao = 1 / len(regs)
            linha['autores_com_afiliacao'] += 1
            linha['autores_fracionados'] += fracao
            linha['pagerank_fracionado'] += info['pagerank'] * fracao
            linha['agrupamento_medio'] += info['agrupamento_local'] * fracao
            linha['grau_medio'] += info['grau'] * fracao
    total_pr = sum(linhas[r]['pagerank_fracionado'] for r in regioes)
    total_pub = sum(linhas[r]['publicacoes_fracionadas'] for r in regioes)
    total_autores = sum(linhas[r]['autores_fracionados'] for r in regioes)
    for linha in linhas.values():
        n = linha['autores_fracionados']
        linha['agrupamento_medio'] = linha['agrupamento_medio'] / n if n else None
        linha['grau_medio'] = linha['grau_medio'] / n if n else None
        brasileira = linha['regiao'] in regioes
        linha['participacao_pagerank_br_classificado'] = linha['pagerank_fracionado'] / total_pr if brasileira and total_pr else None
        linha['participacao_publicacoes_br_classificado'] = linha['publicacoes_fracionadas'] / total_pub if brasileira and total_pub else None
        linha['participacao_autores_br_classificado'] = linha['autores_fracionados'] / total_autores if brasileira and total_autores else None
    ligacoes = Counter()
    for u, v, info in g.edges(data=True):
        origens, destinos = g.nodes[u]['regioes'].split(' | '), g.nodes[v]['regioes'].split(' | ')
        fracao = info['weight'] / (len(origens) * len(destinos))
        for origem, destino in product(origens, destinos):
            ligacoes[tuple(sorted([origem, destino]))] += fracao
    return list(linhas.values()), ligacoes


def comparar_eixos(resumo):
    linhas = {r['regiao']: r for r in resumo}
    campos = ['autores_fracionados', 'publicacoes_fracionadas', 'pagerank_fracionado',
              'participacao_pagerank_br_classificado', 'participacao_publicacoes_br_classificado']
    return [dict(eixo=nome, **{campo: sum(linhas[r][campo] or 0. for r in regs) for campo in campos})
            for nome, regs in [('Sudeste + Sul', ['Sudeste', 'Sul']),
                               ('Norte + Nordeste', ['Norte', 'Nordeste']), ('Centro-Oeste', ['Centro-Oeste'])]]


def figuras(out, resumo, ligacoes, g, spec):
    regs = spec['regioes']
    dados = {r['regiao']: r for r in resumo}
    cores = ['#16a34a', '#ea580c', '#9333ea', '#2563eb', '#dc2626']
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for ax, campo, titulo in zip(axes, ['participacao_publicacoes_br_classificado', 'participacao_pagerank_br_classificado'],
                                 ['Publicações fracionadas', 'PageRank fracionado']):
        valores = [100 * (dados[r][campo] or 0.) for r in regs]
        barras = ax.bar(regs, valores, color=cores)
        ax.bar_label(barras, fmt='%.1f%%', padding=3)
        ax.set(title=titulo, ylabel='% do Brasil com região identificada', ylim=(0, max(valores + [1]) * 1.18))
        ax.tick_params(axis='x', rotation=20)
    fig.suptitle(f'Computação — afiliação brasileira — {spec["ano"]}')
    fig.tight_layout()
    fig.savefig(out / 'distribuicao_regional.png', dpi=160)
    plt.close(fig)
    regional = nx.Graph()
    regional.add_nodes_from(regs)
    for (origem, destino), peso in ligacoes.items():
        if origem in regs and destino in regs and origem != destino:
            regional.add_edge(origem, destino, weight=peso)
    pos = nx.circular_layout(regional)
    fig, ax = plt.subplots(figsize=(10, 8))
    max_peso = max((info['weight'] for _, _, info in regional.edges(data=True)), default=1.)
    nx.draw_networkx_edges(regional, pos, ax=ax, edge_color='#94a3b8', alpha=.65,
        width=[.5 + 10 * math.sqrt(d['weight'] / max_peso) for _, _, d in regional.edges(data=True)])
    nx.draw_networkx_nodes(regional, pos, ax=ax, node_color=cores,
        node_size=[1000 + 12000 * (dados[r]['participacao_pagerank_br_classificado'] or 0.) for r in regs])
    nx.draw_networkx_labels(regional, pos, ax=ax, font_size=11)
    nx.draw_networkx_edge_labels(regional, pos, ax=ax,
        edge_labels={(u, v): f'{d["weight"]:.1f}' for u, v, d in regional.edges(data=True)}, font_size=8)
    ax.set_title(f'Coautorias entre regiões — {spec["ano"]}\nTamanho: PageRank fracionado · Arestas: coautorias fracionadas')
    ax.margins(.2)
    ax.axis('off')
    fig.tight_layout()
    fig.savefig(out / 'colaboracao_regional.png', dpi=160)
    plt.close(fig)
    graus = Counter(dict(g.degree()).values())
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(list(graus), list(graus.values()), color='#2563eb')
    ax.set(xlabel='Grau', ylabel='Pesquisadores', title=f'Distribuição de grau — {spec["ano"]}')
    fig.tight_layout()
    fig.savefig(out / 'distribuicao_grau.png', dpi=160)
    plt.close(fig)


def top_autores(ranking, limite):
    return [r for r in ranking if r['afiliacao_brasileira']][:limite]


def relatorio(out, spec, stats, resumo, eixos, ligacoes, ranking):
    def numero(n):
        return f'{n:.6f}' if n is not None else None

    def percentual(n):
        return f'{n:.2%}' if n is not None else None

    brasileiras = [r for r in resumo if r['regiao'] in spec['regioes']]
    outras = [r for r in resumo if r['regiao'] not in spec['regioes']]
    top = top_autores(ranking, spec['limite_autores_relatorio'])
    secoes = [
        f'# Resultados — Computação no Brasil — {spec["ano"]}',
        '## Recorte',
        tabela_markdown(['Parâmetro', 'Valor'], [
            ('Ano', spec['ano']), ('Campo OpenAlex', spec['campo'] + ' (' + spec['campo_openalex'] + ')'),
            ('País de afiliação', spec['pais']), ('Tipos retidos', ', '.join(spec['tipos'])),
            ('Geografia', 'UF da sede da instituição informada na autoria'),
            ('Contagem regional', 'Fracionada entre regiões brasileiras distintas'),
            ('Domínio das centralidades', 'Rede completa, incluindo coautores externos'),
            ('Domínio do autovetor', 'Maior componente'),
        ]),
        '## Estatísticas',
        tabela_markdown(['Estatística', 'Valor'], [
            ('Publicações recebidas', stats['publicacoes_recebidas']),
            ('Publicações retidas', stats['publicacoes_retidas']),
            ('Publicações excluídas', stats['publicacoes_excluidas']),
            ('Autores identificados', stats['autores_identificados']),
            ('Isolados removidos da rede', stats['isolados_removidos']),
            ('Nós', stats['nos']), ('Arestas', stats['arestas']),
            ('Densidade', numero(stats['densidade'])), ('Grau médio', numero(stats['grau_medio'])),
            ('Agrupamento médio não ponderado', numero(stats['agrupamento_medio_nao_ponderado'])),
            ('Componentes conectadas', stats['componentes']),
            ('Nós na maior componente', stats['nos_maior_componente']),
            ('Autores com afiliação brasileira na rede', stats['autores_afiliacao_brasileira']),
            ('Autores com múltiplas regiões brasileiras', stats['autores_multirregionais']),
        ]),
        '## Distribuição por região',
        tabela_markdown(['Região', 'Autores fracionados', 'Publicações fracionadas', '% publicações BR classificado',
                         'PageRank fracionado', '% PageRank BR classificado', 'Agrupamento médio dos autores'], [
            (r['regiao'], numero(r['autores_fracionados']), numero(r['publicacoes_fracionadas']),
             percentual(r['participacao_publicacoes_br_classificado']), numero(r['pagerank_fracionado']),
             percentual(r['participacao_pagerank_br_classificado']), numero(r['agrupamento_medio'])) for r in brasileiras
        ]),
        '## Eixos regionais',
        tabela_markdown(['Eixo', 'Autores fracionados', 'Publicações fracionadas', '% publicações BR classificado',
                         'PageRank fracionado', '% PageRank BR classificado'], [
            (r['eixo'], numero(r['autores_fracionados']), numero(r['publicacoes_fracionadas']),
             percentual(r['participacao_publicacoes_br_classificado']), numero(r['pagerank_fracionado']),
             percentual(r['participacao_pagerank_br_classificado'])) for r in eixos
        ]),
        '## Cobertura geográfica complementar',
        tabela_markdown(['Categoria', 'Autores fracionados', 'Publicações fracionadas', 'PageRank fracionado'], [
            (r['regiao'], numero(r['autores_fracionados']), numero(r['publicacoes_fracionadas']),
             numero(r['pagerank_fracionado'])) for r in outras
        ]),
        '## Coautorias fracionadas por par de regiões',
        tabela_markdown(['Região 1', 'Região 2', 'Coautorias fracionadas'], [
            (r, s, numero(ligacoes.get(tuple(sorted([r, s])), 0.)))
            for i, r in enumerate(spec['regioes']) for s in spec['regioes'][i:]
        ]),
        f'## Métricas por autor — Top {spec["limite_autores_relatorio"]} por PageRank — afiliação brasileira',
        tabela_markdown(['Posição', 'Autor ID', 'Pesquisador', 'Regiões', 'Grau', 'Força',
                         'PageRank ponderado (α = 0,85)', 'Agrupamento local não ponderado',
                         'Autovetor ponderado (maior componente)'], [
            (i, r['autor_id'], r['nome'], r['regioes'], r['grau'], r['forca'], f'{r["pagerank"]:.8f}',
             numero(r['agrupamento_local']), f'{r["autovetor_maior_componente"]:.8g}'
             if r['autovetor_maior_componente'] != '' else None) for i, r in enumerate(top, 1)
        ]),
        '## Tipos de publicação retidos',
        tabela_markdown(['Tipo', 'Publicações'], sorted(stats['tipos_retidos'].items())),
        '## Auditoria',
        tabela_markdown(['Registro', 'Quantidade'], sorted(stats['auditoria'].items())),
        '## Distribuição regional', '![Distribuição regional](distribuicao_regional.png)',
        '## Colaboração regional', '![Colaboração regional](colaboracao_regional.png)',
        '## Distribuição de grau', '![Distribuição de grau](distribuicao_grau.png)',
    ]
    (out / 'relatorio.md').write_text('\n\n'.join(secoes) + '\n', encoding='utf-8')


def analisar(raiz):
    raiz = Path(raiz).resolve()
    spec = especificacao()
    indice, obras, instituicoes, ufs = ler_coleta(raiz)
    clean, out = raiz / 'dados/limpos', raiz / 'resultados'
    clean.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    print('Construindo a rede nacional...', flush=True)
    completo, pubs, autorias, exclusoes, descartadas, suporte, producao, auditoria, aliases = construir_rede(obras, instituicoes, ufs, spec)
    g = completo.copy()
    isolados = set(nx.isolates(g))
    g.remove_nodes_from(isolados)
    if not g:
        raise ValueError('O recorte não produziu arestas de coautoria.')
    print(f'Calculando centralidades: {len(g)} autores e {g.number_of_edges()} arestas...', flush=True)
    componentes = metricas(g)
    resumo, ligacoes = agregar_regioes(g, producao, spec['regioes'])
    eixos = comparar_eixos(resumo)
    stats = {'recorte': 'nacional', 'ano': spec['ano'], 'publicacoes_recebidas': len(obras),
             'publicacoes_retidas': len(pubs), 'publicacoes_excluidas': len(exclusoes),
             'tipos_retidos': dict(Counter(p['tipo'] for p in pubs)),
             'autores_identificados': len(completo), 'isolados_removidos': len(isolados),
             'nos': len(g), 'arestas': g.number_of_edges(), 'densidade': nx.density(g),
             'grau_medio': 2 * g.number_of_edges() / len(g),
             'agrupamento_medio_nao_ponderado': sum(nx.get_node_attributes(g, 'agrupamento_local').values()) / len(g),
             'componentes': len(componentes), 'tamanhos_componentes': [len(c) for c in componentes],
             'nos_maior_componente': len(componentes[0]),
             'autores_afiliacao_brasileira': sum(d['afiliacao_brasileira'] for _, d in g.nodes(data=True)),
             'autores_multirregionais': sum(len(set(d['regioes'].split(' | ')) & set(spec['regioes'])) > 1
                                           for _, d in g.nodes(data=True)), 'auditoria': dict(auditoria)}
    campos = ['autor_id', 'nome', 'regioes', 'afiliacao_brasileira', 'grau', 'forca', 'pagerank',
              'agrupamento_local', 'autovetor_maior_componente']
    ranking = [{'autor_id': a, **{k: d.get(k, '') for k in campos[1:]}} for a, d in g.nodes(data=True)]
    ranking.sort(key=lambda r: (-r['pagerank'], r['autor_id']))
    salvar_csv(clean, 'publicacoes.csv', pubs, ['publicacao_id', 'doi', 'titulo', 'ano', 'tipo', 'numero_autores', 'regioes_brasileiras'])
    salvar_csv(clean, 'autorias.csv', autorias, ['publicacao_id', 'autor_id', 'nome', 'instituicoes', 'paises', 'regioes_brasileiras'])
    salvar_csv(clean, 'exclusoes.csv', exclusoes, ['publicacao_id', 'titulo', 'motivo'])
    salvar_csv(clean, 'autorias_descartadas.csv', descartadas, ['publicacao_id', 'nome_informado', 'motivo'])
    salvar_csv(clean, 'autores.csv', [dict(autor_id=a, **d, isolado_removido=a in isolados)
        for a, d in completo.nodes(data=True)], ['autor_id', 'nome', 'publicacoes', 'regioes', 'afiliacao_brasileira', 'isolado_removido'])
    salvar_csv(clean, 'arestas.csv', [{'origem': u, 'destino': v, 'peso': len(ws), 'publicacoes': ' | '.join(ws)}
        for (u, v), ws in sorted(suporte.items())], ['origem', 'destino', 'peso', 'publicacoes'])
    salvar_csv(clean, 'metricas_autores.csv', ranking, campos)
    salvar_csv(clean, 'metricas_regioes.csv', resumo, list(resumo[0]))
    salvar_csv(clean, 'comparacao_eixos.csv', eixos, list(eixos[0]))
    salvar_csv(clean, 'ligacoes_regioes.csv', [{'origem': u, 'destino': v, 'peso_fracionado': peso}
        for (u, v), peso in sorted(ligacoes.items())], ['origem', 'destino', 'peso_fracionado'])
    salvar_csv(clean, 'instituicoes.csv', [{'instituicao_id': i, 'nome': d.get('display_name') or '',
        'uf_informada': (d.get('geo') or {}).get('region') or '',
        'regiao': mapa_ufs(ufs).get(normalizar((d.get('geo') or {}).get('region')), SEM_UF)}
        for i, d in sorted(instituicoes.items())], ['instituicao_id', 'nome', 'uf_informada', 'regiao'])
    salvar_json(out / 'estatisticas.json', stats)
    salvar_json(out / 'metricas_regioes.json', resumo)
    salvar_json(out / 'identidades_unificadas.json', {k: v for k, v in aliases.items() if k != v})
    print('Exportando grafos e resultados regionais...', flush=True)
    nx.write_graphml(g, out / 'rede_coautoria.graphml')
    nx.write_graphml(completo, out / 'rede_com_isolados.graphml')
    nx.write_gml(g, out / 'rede_coautoria.gml')
    figuras(out, resumo, ligacoes, g, spec)
    import platform
    import scipy
    import matplotlib
    fontes = indice['paginas'] + indice['instituicoes'] + indice['fontes'] + [entrada(raiz, raiz / 'dados/brutos/coleta_nacional.json')]
    salvar_json(out / 'reprodutibilidade.json', {'python': platform.python_version(), 'networkx': nx.__version__,
        'numpy': np.__version__, 'scipy': scipy.__version__, 'matplotlib': matplotlib.__version__,
        'recorte': spec, 'sha256_entradas': {item['arquivo']: item['sha256'] for item in fontes}})
    relatorio(out, spec, stats, resumo, eixos, ligacoes, ranking)
    print(json.dumps({k: v for k, v in stats.items() if k != 'tamanhos_componentes'}, ensure_ascii=False, indent=2))


def verificar(raiz):
    import csv

    raiz = Path(raiz).resolve()
    out, clean = raiz / 'resultados', raiz / 'dados/limpos'
    spec = especificacao()
    ler_coleta(raiz)
    esperados = ['relatorio.md', 'estatisticas.json', 'metricas_regioes.json', 'reprodutibilidade.json',
                 'rede_coautoria.graphml', 'rede_coautoria.gml', 'rede_com_isolados.graphml',
                 'distribuicao_regional.png', 'colaboracao_regional.png', 'distribuicao_grau.png',
                 'identidades_unificadas.json']
    for nome in esperados:
        if not (out / nome).is_file() or not (out / nome).stat().st_size:
            raise ValueError(f'Artefato ausente ou vazio: resultados/{nome}')

    def csv_linhas(nome):
        with (clean / nome).open(encoding='utf-8-sig', newline='') as fonte:
            return list(csv.DictReader(fonte))

    stats = json.loads((out / 'estatisticas.json').read_text(encoding='utf-8'))
    assert stats['recorte'] == 'nacional' and stats['ano'] == spec['ano']
    pubs = csv_linhas('publicacoes.csv')
    assert len(pubs) == stats['publicacoes_retidas']
    assert len({p['publicacao_id'] for p in pubs}) == len(pubs)
    assert all(p['ano'] == str(spec['ano']) and p['tipo'] in spec['tipos'] for p in pubs)
    dois = [p['doi'] for p in pubs if p['doi']]
    assert len(dois) == len(set(dois))
    assert len(csv_linhas('exclusoes.csv')) == stats['publicacoes_excluidas']
    assert stats['publicacoes_retidas'] + stats['publicacoes_excluidas'] == stats['publicacoes_recebidas']
    csv_linhas('autorias_descartadas.csv')
    csv_linhas('instituicoes.csv')
    g = nx.read_graphml(out / 'rede_coautoria.graphml')
    assert not g.is_directed() and nx.number_of_selfloops(g) == 0
    assert len(g) == stats['nos'] and g.number_of_edges() == stats['arestas']
    assert abs(nx.density(g) - stats['densidade']) < 1e-12
    por_pub = defaultdict(set)
    for linha in csv_linhas('autorias.csv'):
        por_pub[linha['publicacao_id']].add(linha['autor_id'])
    suporte = defaultdict(set)
    for pub, autores in por_pub.items():
        for u, v in combinations(sorted(autores), 2):
            suporte[u, v].add(pub)
    assert len(suporte) == g.number_of_edges()
    for (u, v), works in suporte.items():
        assert g[u][v]['weight'] == len(works)
    for linha in csv_linhas('arestas.csv'):
        chave = tuple(sorted([linha['origem'], linha['destino']]))
        assert set(linha['publicacoes'].split(' | ')) == suporte[chave]
    gml = nx.read_gml(out / 'rede_coautoria.gml')
    assert set(gml) == set(g)
    assert {frozenset(e) for e in gml.edges} == {frozenset(e) for e in g.edges}
    assert all(d['weight'] == g[u][v]['weight'] for u, v, d in gml.edges(data=True))
    del gml
    assert abs(sum(nx.get_node_attributes(g, 'pagerank').values()) - 1) < 1e-8
    componentes = sorted(nx.connected_components(g), key=lambda c: (-len(c), min(c)))
    assert [len(c) for c in componentes] == stats['tamanhos_componentes']
    maior = g.subgraph(componentes[0])
    ids = sorted(maior)
    x = np.array([maior.nodes[a]['autovetor_maior_componente'] for a in ids])
    adj = nx.to_scipy_sparse_array(maior, nodelist=ids, weight='weight', dtype=float)
    ax = adj @ x
    autovalor = float(x @ ax / (x @ x))
    assert abs(float(x @ x) - 1) < 1e-8
    assert np.linalg.norm(ax - autovalor * x) < 1e-6 * max(1., abs(autovalor))
    assert all('autovetor_maior_componente' not in g.nodes[a] for a in set(g) - set(maior))
    autores = csv_linhas('autores.csv')
    assert len(autores) == stats['autores_identificados']
    assert sum(r['isolado_removido'] == 'True' for r in autores) == stats['isolados_removidos']
    ranking = csv_linhas('metricas_autores.csv')
    assert len(ranking) == len(g)
    assert [r['autor_id'] for r in ranking] == sorted(g, key=lambda a: (-g.nodes[a]['pagerank'], a))
    for r in ranking:
        d = g.nodes[r['autor_id']]
        assert int(r['grau']) == g.degree(r['autor_id'])
        assert int(r['forca']) == g.degree(r['autor_id'], weight='weight')
        for campo in ['pagerank', 'agrupamento_local', 'autovetor_maior_componente']:
            assert (r[campo] == '' and campo not in d) or abs(float(r[campo]) - d[campo]) < 1e-12
    regioes = csv_linhas('metricas_regioes.csv')
    assert {r['regiao'] for r in regioes} == set(spec['regioes'] + [SEM_UF, EXTERIOR, SEM_AFILIACAO])
    assert abs(sum(float(r['autores_fracionados']) for r in regioes) - len(g)) < 1e-6
    assert abs(sum(float(r['publicacoes_fracionadas']) for r in regioes) - len(pubs)) < 1e-6
    assert abs(sum(float(r['pagerank_fracionado']) for r in regioes) - 1) < 1e-8
    recalculada = Counter()
    for p in pubs:
        regs = p['regioes_brasileiras'].split(' | ')
        for r in regs:
            recalculada[r] += 1 / len(regs)
    for r in regioes:
        assert abs(float(r['publicacoes_fracionadas']) - recalculada[r['regiao']]) < 1e-6
    resumo, ligacoes = agregar_regioes(g, recalculada, spec['regioes'])
    for original, recalculo in zip(regioes, resumo):
        for campo, valor in recalculo.items():
            if isinstance(valor, (int, float)):
                assert abs(float(original[campo]) - valor) < 1e-6
    linhas_ligacoes = csv_linhas('ligacoes_regioes.csv')
    assert len(linhas_ligacoes) == len(ligacoes)
    for r in linhas_ligacoes:
        assert abs(float(r['peso_fracionado']) - ligacoes[r['origem'], r['destino']]) < 1e-6
    assert abs(sum(ligacoes.values()) - g.size(weight='weight')) < 1e-6
    eixos = csv_linhas('comparacao_eixos.csv')
    for original, recalculo in zip(eixos, comparar_eixos(resumo)):
        assert original['eixo'] == recalculo['eixo']
        for campo, valor in recalculo.items():
            if campo != 'eixo':
                assert abs(float(original[campo]) - valor) < 1e-6
    report = (out / 'relatorio.md').read_text(encoding='utf-8')
    assert all(not linha.strip() or linha.startswith(('#', '|', '![')) for linha in report.splitlines())
    top = [r for r in ranking if r['afiliacao_brasileira'] == 'True'][:spec['limite_autores_relatorio']]
    secao = report.split('## Métricas por autor', 1)[1].split('\n\n## ', 1)[0]
    linhas_top = [linha for linha in secao.splitlines() if linha.startswith('| ')][2:]
    assert len(linhas_top) == len(top)
    assert [linha.split('|')[2].strip() for linha in linhas_top] == [r['autor_id'] for r in top]
    assert '## Docentes sem publicação retida' not in report
    assert not (out / 'apresentacao.md').exists()
    provenance = json.loads((out / 'reprodutibilidade.json').read_text(encoding='utf-8'))
    for nome, hash_entrada in provenance['sha256_entradas'].items():
        assert digest(raiz / nome) == hash_entrada
    print('OK: coleta completa, CSVs, grafos, suporte das arestas, centralidades, contagens fracionadas, '
          'eixos regionais, Top 10 e hashes conferidos.')


def main():
    parser = parser_diretorio('Coleta e compara as cinco regiões brasileiras na Computação em 2025.')
    parser.add_argument('--etapa', choices=['coleta', 'analise', 'verificacao', 'todas'], default='todas')
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument('--offline', action='store_true')
    modo.add_argument('--atualizar', action='store_true')
    args = parser.parse_args()
    try:
        if args.etapa in ['coleta', 'todas']:
            coletar(args.diretorio, offline=args.offline, atualizar=args.atualizar)
        if args.etapa in ['analise', 'todas']:
            analisar(args.diretorio)
        if args.etapa in ['verificacao', 'todas']:
            verificar(args.diretorio)
    except (AssertionError, ValueError, RuntimeError, OSError, nx.NetworkXException) as exc:
        parser.exit(1, f'Erro no recorte nacional: {exc or "artefatos inconsistentes"}\n')


if __name__ == '__main__':
    main()
