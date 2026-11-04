"""Prepara os dados do recorte automaticamente e preserva um cache auditável."""
import json
import os
import time
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from configuracao import ANO, FONTE, carregar_docentes, parser_diretorio


def salvar_json(path, valor):
    """Só substitui um arquivo depois que a escrita estiver completa."""
    temporario = path.with_suffix(path.suffix + '.tmp')
    temporario.write_text(json.dumps(valor, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporario.replace(path)


class Coleta:
    def __init__(self, raiz, offline=False, atualizar=False):
        self.raiz = Path(raiz).resolve()
        self.raw = self.raiz / 'dados/brutos'
        self.raw.mkdir(parents=True, exist_ok=True)
        self.offline = offline
        self.atualizar = atualizar
        self.manifesto = self.raw / 'manifesto.json'
        self.registros = json.loads(self.manifesto.read_text(encoding='utf-8')) if self.manifesto.exists() else []
        self.session = requests.Session()
        self.session.mount('https://', HTTPAdapter(max_retries=Retry(
            total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])))

    def obter(self, url, parametros, nome, json_api=True):
        destino = self.raw / nome
        relativo = destino.relative_to(self.raiz).as_posix()
        entradas = [r for r in self.registros if r.get('arquivo') == relativo]
        ultimo = entradas[-1] if entradas else {}
        cache_valido = (destino.exists() and ultimo.get('url') == url
                        and ultimo.get('parametros') == parametros
                        and ultimo.get('sha256') == sha256(destino.read_bytes()).hexdigest())
        if cache_valido and not self.atualizar:
            return json.loads(destino.read_text(encoding='utf-8')) if json_api else destino.read_text(encoding='utf-8')
        if self.offline:
            raise RuntimeError(f'Cache ausente, alterado ou incompatível: {relativo}. '
                               'Execute sem --offline para fazer a coleta.')
        consulta = dict(parametros)
        if json_api and os.getenv('OPENALEX_API_KEY'):
            consulta['api_key'] = os.environ['OPENALEX_API_KEY']
        print(f'Coletando {nome}...', flush=True)
        try:
            response = self.session.get(url, params=consulta, timeout=60)
            response.raise_for_status()
        except requests.RequestException as exc:
            # A URL da exceção pode conter api_key; nunca a imprimir.
            status = exc.response.status_code if exc.response is not None else 'sem resposta'
            raise RuntimeError(f'Falha de rede ao coletar {nome} (HTTP {status}). '
                               'Confira a conexão e a cota da API; OPENALEX_API_KEY é opcional.') from None
        if json_api:
            data = response.json()
            if not isinstance(data.get('results'), list) or 'meta' not in data:
                raise RuntimeError(f'Resposta inesperada da OpenAlex em {nome}.')
            salvar_json(destino, data)
        else:
            data = response.text
            temporario = destino.with_suffix(destino.suffix + '.tmp')
            temporario.write_text(data, encoding='utf-8')
            temporario.replace(destino)
        self.registros.append({'url': url, 'parametros': parametros, 'arquivo': relativo,
                               'coletado_em_utc': datetime.now(timezone.utc).isoformat(),
                               'sha256': sha256(destino.read_bytes()).hexdigest()})
        salvar_json(self.manifesto, self.registros)
        time.sleep(0.2)
        return data


def executar(raiz, offline=False, atualizar=False, so_autores=False):
    coleta = Coleta(raiz, offline=offline, atualizar=atualizar)
    docentes = carregar_docentes()
    # A seleção é uma entrada versionada; esta cópia local é gerada para o processamento.
    salvar_json(coleta.raiz / 'dados/docentes_selecionados.json', docentes)
    coleta.obter(FONTE, {}, 'docentes_oficial.html', json_api=False)
    for i, docente in enumerate(docentes):
        nome = docente['nome_oficial']
        data = coleta.obter('https://api.openalex.org/authors',
                            {'search': nome, 'per-page': 5}, f'autor_busca_{i:02d}.json')
        if so_autores:
            print('\n' + nome, flush=True)
            for autor in data['results']:
                print(autor['id'], autor['display_name'], autor.get('orcid'), flush=True)
    if so_autores:
        return
    ids = '|'.join(sorted({i.rsplit('/', 1)[-1] for d in docentes for i in d['aliases_openalex']}))
    filtro = f'authorships.author.id:{ids},publication_year:{ANO}'
    cursor = '*'
    page = 1
    usados = set()
    arquivos = []
    obras = set()
    total = None
    while cursor:
        if cursor in usados:
            raise RuntimeError('A OpenAlex repetiu um cursor; coleta interrompida para evitar um laço.')
        usados.add(cursor)
        nome = f'publicacoes_{page:03d}.json'
        parametros = {'filter': filtro, 'per-page': 200, 'cursor': cursor, 'sort': 'publication_date:asc'}
        data = coleta.obter('https://api.openalex.org/works', parametros, nome)
        if total is None:
            total = data['meta']['count']
        if data['meta']['count'] != total:
            raise RuntimeError('O total de resultados mudou durante a paginação. Repita com --atualizar.')
        obras.update(w['id'] for w in data['results'])
        arquivos.append({'arquivo': f'dados/brutos/{nome}',
                         'sha256': sha256((coleta.raw / nome).read_bytes()).hexdigest()})
        print(f"Página {page}: {len(data['results'])} registros; total informado: {total}", flush=True)
        cursor = data['meta'].get('next_cursor') if data['results'] else None
        page += 1
    if len(obras) != total:
        raise RuntimeError('A paginação não recuperou todas as publicações. Repita com --atualizar.')
    # O índice define as páginas da coleta concluída. Arquivos antigos não entram por glob.
    salvar_json(coleta.raw / 'coleta.json', {
        'ano': ANO, 'filtro': filtro, 'total_api': total, 'paginas': arquivos,
        'docentes_sha256': sha256((coleta.raiz / 'dados/docentes_selecionados.json').read_bytes()).hexdigest(),
    })
    print(f'Dados preparados em {coleta.raiz / "dados"}.', flush=True)


def main():
    parser = parser_diretorio(__doc__)
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument('--offline', action='store_true', help='Usar apenas cache validado, sem rede.')
    modo.add_argument('--atualizar', action='store_true', help='Consultar novamente as fontes, substituindo o cache.')
    parser.add_argument('--buscar-autores', action='store_true', help='Consultar e exibir apenas candidatos a autores.')
    args = parser.parse_args()
    try:
        executar(args.diretorio, offline=args.offline, atualizar=args.atualizar, so_autores=args.buscar_autores)
    except (RuntimeError, ValueError, OSError) as exc:
        parser.exit(1, f'Erro na coleta: {exc}\n')


if __name__ == '__main__':
    main()
