"""Configuração versionada do recorte e caminhos dos artefatos gerados."""
import argparse
import json
from pathlib import Path

CODIGO = Path(__file__).resolve().parent
ROOT = CODIGO.parent
ANO = 2025
FONTE = 'https://www.utfpr.edu.br/cursos/programas-de-pos-graduacao/ppgcc-cm/area-academica/docentes'
DOCENTES = CODIGO / 'configuracao/docentes.json'


def carregar_docentes():
    """Identidades selecionadas para o estudo; não inferidas automaticamente por nome."""
    return json.loads(DOCENTES.read_text(encoding='utf-8'))


def adicionar_diretorio(parser):
    parser.add_argument('--diretorio', type=Path, default=ROOT,
                        help='Pasta onde dados/ e resultados/ serão criados (padrão: raiz do projeto).')


def parser_diretorio(descricao):
    parser = argparse.ArgumentParser(description=descricao)
    adicionar_diretorio(parser)
    return parser
