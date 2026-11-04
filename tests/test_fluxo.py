"""Regressões do cache e da interrupção do fluxo; não acessam a rede."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'codigo'))
from coletar import Coleta


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='coautoria-teste-')
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.url = 'https://api.openalex.org/works'
        self.parametros = {'filter': 'publication_year:2025'}

    def criar_cache(self):
        coleta = Coleta(self.raiz)
        response = Mock()
        response.json.return_value = {'meta': {'count': 0}, 'results': []}
        with patch.object(coleta.session, 'get', return_value=response), patch('coletar.time.sleep'):
            coleta.obter(self.url, self.parametros, 'pagina.json')

    def test_cache_offline_funciona_sem_rede(self):
        self.criar_cache()
        coleta = Coleta(self.raiz, offline=True)
        with patch.object(coleta.session, 'get', side_effect=AssertionError('Tentativa de rede')):
            dados = coleta.obter(self.url, self.parametros, 'pagina.json')
        self.assertEqual(dados['meta']['count'], 0)

    def test_offline_recusa_cache_ausente(self):
        coleta = Coleta(self.raiz, offline=True)
        with patch.object(coleta.session, 'get', side_effect=AssertionError('Tentativa de rede')):
            with self.assertRaisesRegex(RuntimeError, 'Cache ausente'):
                coleta.obter(self.url, self.parametros, 'pagina.json')

    def test_offline_recusa_conteudo_alterado(self):
        self.criar_cache()
        (self.raiz / 'dados/brutos/pagina.json').write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'alterado'):
            Coleta(self.raiz, offline=True).obter(self.url, self.parametros, 'pagina.json')

    def test_offline_recusa_outro_recorte(self):
        self.criar_cache()
        with self.assertRaisesRegex(RuntimeError, 'incompatível'):
            Coleta(self.raiz, offline=True).obter(self.url, {'filter': 'publication_year:2024'}, 'pagina.json')

    def test_atualizar_substitui_cache_existente(self):
        self.criar_cache()
        coleta = Coleta(self.raiz, atualizar=True)
        response = Mock()
        response.json.return_value = {'meta': {'count': 1}, 'results': [{'id': 'W1'}]}
        with patch.object(coleta.session, 'get', return_value=response) as get, patch('coletar.time.sleep'):
            dados = coleta.obter(self.url, self.parametros, 'pagina.json')
        get.assert_called_once()
        self.assertEqual(dados['meta']['count'], 1)
        self.assertEqual(Coleta(self.raiz, offline=True).obter(self.url, self.parametros, 'pagina.json'), dados)

    def test_chave_nao_fica_no_manifesto(self):
        with patch.dict('os.environ', {'OPENALEX_API_KEY': 'chave-apenas-para-teste'}):
            self.criar_cache()
        texto = (self.raiz / 'dados/brutos/manifesto.json').read_text(encoding='utf-8')
        self.assertNotIn('chave-apenas-para-teste', texto)
        self.assertNotIn('api_key', json.loads(texto)[0]['parametros'])

    def test_run_interrompe_quando_coleta_falha(self):
        resultado = subprocess.run([sys.executable, str(ROOT / 'run.py'), '--offline',
                                    '--diretorio', str(self.raiz)], cwd=self.raiz,
                                   text=True, capture_output=True)
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn('Processamento interrompido', resultado.stderr)
        self.assertNotIn('Executando analisar.py', resultado.stdout)
        self.assertFalse((self.raiz / 'resultados').exists())


if __name__ == '__main__':
    unittest.main()
