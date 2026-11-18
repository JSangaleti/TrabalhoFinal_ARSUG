#!.venv/bin/python3

import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument('--offline', action='store_true', help='Reprocessar o cache sem acesso à rede.')
    modo.add_argument('--atualizar', action='store_true', help='Refazer a coleta antes da análise.')
    parser.add_argument('--recorte', choices=['nacional', 'piloto'], default='nacional',
                        help='Recorte da pesquisa (padrão: nacional; piloto: docentes do PPGCC-CM).')
    parser.add_argument('--diretorio', type=Path, default=ROOT,
                        help='Pasta de saída para dados/ e resultados/ (padrão: raiz do projeto).')
    args = parser.parse_args()
    ausentes = [nome for nome in ['requests', 'networkx', 'matplotlib', 'numpy', 'scipy']
                if importlib.util.find_spec(nome) is None]

    if ausentes:
        parser.exit(1, 'Bibliotecas ausentes: ' + ', '.join(ausentes)
                    + '\nInstale as dependências: python -m pip install -r requirements.txt\n')

    etapas = ([(script, None) for script in ['coletar.py', 'analisar.py', 'verificar.py']]
              if args.recorte == 'piloto' else
              [('nacional.py', etapa) for etapa in ['coleta', 'analise', 'verificacao']])
    for script, etapa in etapas:
        comando = [sys.executable, str(ROOT / 'codigo' / script), '--diretorio', str(args.diretorio.resolve())]
        if etapa:
            comando.extend(['--etapa', etapa])
        if script == 'coletar.py' or etapa == 'coleta':
            if args.offline:
                comando.append('--offline')
            elif args.atualizar:
                comando.append('--atualizar')
        nome_etapa = etapa or script
        print(f'\nExecutando {nome_etapa}...', flush=True)
        resultado = subprocess.run(comando, check=False)
        if resultado.returncode:
            parser.exit(resultado.returncode, f'Processamento interrompido na etapa {script}.\n')

    print(f'\nProcessamento concluído. Abra {args.diretorio.resolve() / "resultados/relatorio.md"}.')


if __name__ == '__main__':
    main()
