import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'codigo'))

from coletar import Coleta
from nacional import (EXTERIOR, SEM_UF, agregar_regioes, construir_rede, especificacao,
                      mapa_ufs, metricas, paginar, regioes_autoria, top_autores)


UFS = [{'nome': 'Pará', 'sigla': 'PA', 'regiao': {'nome': 'Norte'}},
       {'nome': 'Paraná', 'sigla': 'PR', 'regiao': {'nome': 'Sul'}}]
INSTITUICOES = {
    'I1': {'id': 'I1', 'country_code': 'BR', 'geo': {'region': 'Para'}},
    'I2': {'id': 'I2', 'country_code': 'BR', 'geo': {'region': 'Paraná'}},
}


def autoria(identificador, instituicoes=(), orcid=None, paises=()):
    return {'author': {'id': identificador, 'display_name': identificador, 'orcid': orcid},
            'institutions': [{'id': i, 'country_code': 'BR'} for i in instituicoes],
            'countries': list(paises)}


def obra(identificador, autores, **extras):
    return dict({'id': identificador, 'publication_year': 2025, 'type': 'article',
                 'primary_topic': {'field': {'id': 'https://openalex.org/fields/17'}},
                 'authorships': autores}, **extras)


class RedeRegionalTests(unittest.TestCase):
    def test_geografia_usa_uf_da_instituicao_e_nao_nome(self):
        regs, paises = regioes_autoria(autoria('Autor', ['I1', 'I2'], paises=['US']), INSTITUICOES, mapa_ufs(UFS))
        self.assertEqual(regs, {'Norte', 'Sul'})
        self.assertEqual(paises, {'BR', 'US'})
        regs, _ = regioes_autoria(autoria('Pesquisador do Paraná', ['Inexistente']), {}, mapa_ufs(UFS))
        self.assertEqual(regs, {SEM_UF})

    def test_multiafiliacao_preserva_totais_de_autores_publicacoes_e_arestas(self):
        works = [obra('W1', [autoria('A1', ['I1', 'I2']), autoria('A2', ['I2']), autoria('A3', paises=['US'])])]
        g, pubs, _, _, _, _, producao, _, _ = construir_rede(works, INSTITUICOES, UFS, especificacao())
        metricas(g)
        linhas, ligacoes = agregar_regioes(g, producao, especificacao()['regioes'])
        por_regiao = {r['regiao']: r for r in linhas}
        self.assertAlmostEqual(por_regiao['Norte']['autores_fracionados'], .5)
        self.assertAlmostEqual(por_regiao['Sul']['autores_fracionados'], 1.5)
        self.assertAlmostEqual(por_regiao[EXTERIOR]['autores_fracionados'], 1.)
        self.assertAlmostEqual(sum(r['autores_fracionados'] for r in linhas), 3.)
        self.assertAlmostEqual(sum(r['publicacoes_fracionadas'] for r in linhas), len(pubs))
        self.assertAlmostEqual(sum(r['pagerank_fracionado'] for r in linhas), 1.)
        self.assertAlmostEqual(sum(ligacoes.values()), g.size(weight='weight'))
        self.assertAlmostEqual(ligacoes['Norte', 'Sul'], .5)
        self.assertAlmostEqual(ligacoes['Sul', 'Sul'], .5)

    def test_orcid_unifica_identidades_e_nao_inventa_autorias(self):
        works = [obra('W1', [autoria('A1', ['I1'], orcid='O1'), autoria('A2', ['I2']), autoria(None, ['I1'])]),
                 obra('W2', [autoria('A9', ['I1'], orcid='O1'), autoria(None, ['I2'], orcid='O2')])]
        g, pubs, _, _, descartadas, _, _, audit, aliases = construir_rede(works, INSTITUICOES, UFS, especificacao())
        self.assertEqual(aliases['A1'], aliases['A9'])
        self.assertEqual(len(g), 3)
        self.assertEqual(len(pubs), 2)
        self.assertEqual(len(descartadas), 1)
        self.assertEqual(audit['autorias_recuperadas_por_orcid'], 1)

    def test_rejeita_truncados_duplicatas_e_anos_fora_do_recorte(self):
        autores = [autoria('A1', ['I1']), autoria('A2', ['I2'])]
        works = [obra('W1', autores, doi='https://doi.org/exemplo'),
                 obra('W2', autores, doi='https://DOI.ORG/EXEMPLO'),
                 obra('W3', autores, is_authors_truncated=True),
                 obra('W4', autores, publication_year=2020)]
        _, pubs, _, excluidas, _, _, _, audit, _ = construir_rede(works, INSTITUICOES, UFS, especificacao())
        self.assertEqual(len(pubs), 1)
        self.assertEqual(len(excluidas), 3)
        self.assertEqual(audit['autorias_truncadas_na_fonte'], 1)
        self.assertEqual(audit['id_ou_doi_duplicado'], 1)
        self.assertEqual(audit['fora_do_ano'], 1)

    def test_autovetor_apenas_na_maior_componente(self):
        works = [obra('W1', [autoria('A1', ['I1']), autoria('A2', ['I1']), autoria('A3', ['I2'])]),
                 obra('W2', [autoria('A4', ['I1']), autoria('A5', ['I1'])])]
        g, *_ = construir_rede(works, INSTITUICOES, UFS, especificacao())
        componentes = metricas(g)
        self.assertEqual([len(c) for c in componentes], [3, 2])
        self.assertNotIn('autovetor_maior_componente', g.nodes['A4'])
        self.assertAlmostEqual(sum(d['pagerank'] for _, d in g.nodes(data=True)), 1.)

    def test_top_10_considera_brasileiros_e_corpora_menores(self):
        ranking = [{'autor_id': str(i), 'afiliacao_brasileira': i % 3 != 0} for i in range(30)]
        self.assertEqual([r['autor_id'] for r in top_autores(ranking, 10)],
                         ['1', '2', '4', '5', '7', '8', '10', '11', '13', '14'])
        self.assertEqual(len(top_autores(ranking[:3], 10)), 2)


class ColetaRegionalTests(unittest.TestCase):
    def test_chave_openalex_nunca_e_enviada_ao_ibge(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ', {'OPENALEX_API_KEY': 'chave-teste'}), patch('coletar.time.sleep'):
            coleta = Coleta(tmp)
            coleta.session.get = Mock(return_value=Mock(json=lambda: UFS))
            coleta.obter('https://servicodados.ibge.gov.br/api/v1/localidades/estados', {},
                         'nacional/ufs_ibge.json', json_lista=True)
            self.assertNotIn('api_key', coleta.session.get.call_args.kwargs['params'])
            resposta = {'results': [], 'meta': {'count': 0}}
            coleta.session.get = Mock(return_value=Mock(json=lambda: resposta))
            coleta.obter('https://api.openalex.org/works', {}, 'nacional/works.json')
            self.assertEqual(coleta.session.get.call_args.kwargs['params']['api_key'], 'chave-teste')
            self.assertNotIn('chave-teste', coleta.manifesto.read_text())

    def test_paginacao_incompleta_nao_e_aceita(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict('os.environ', {}, clear=True):
            coleta = Mock(raiz=Path(tmp), raw=Path(tmp))
            def obter(url, parametros, nome):
                data = {'results': [{'id': 'W1'}] if parametros['page'] == 1 else [], 'meta': {'count': 2}}
                destino = coleta.raw / nome
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_text(json.dumps(data))
                return data
            coleta.obter.side_effect = obter
            with self.assertRaisesRegex(RuntimeError, 'incompleta'):
                paginar(coleta, 'works', {}, 'teste')


if __name__ == '__main__':
    unittest.main()
