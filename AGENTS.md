# Repository Guidelines

## Project Structure & Module Organization

This Python 3.10+ research pipeline analyzes 2025 Brazilian Computer Science coauthorship using OpenAlex and IBGE data.

- `run.py` orchestrates collection, analysis, and verification.
- `codigo/nacional.py` implements the default national study; `coletar.py`, `analisar.py`, and `verificar.py` implement the faculty pilot. `comunidades.py` shares Louvain detection and visualization.
- `codigo/configuracao/` contains versioned JSON study definitions; `codigo/configuracao.py` defines the year and shared paths.
- `dados/brutos/` stores collection caches; `dados/limpos/` stores processed tables. `dados/` is ignored by Git.
- `resultados/` contains tracked graphs, figures, metrics, and `relatorio.md`. `docs/` holds research notes; `artigo-sbc-latex/` holds the paper and its assets.
- Local regression tests live in `tests/`, which is currently ignored by Git and may be absent from fresh clones.

## Build, Test, and Development Commands

Run from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

- `python run.py`: collect data, analyze, and verify the national study.
- `python run.py --offline`: rebuild from a complete, validated local cache.
- `python run.py --atualizar`: replace cached collection with fresh API responses.
- `python run.py --recorte piloto --diretorio /tmp/coautoria-piloto`: run the faculty pilot separately.
- `python -m unittest discover -s tests -v`: run available local tests without internet.

There is no separate application build step.

## Coding Style & Naming Conventions

Use four-space Python indentation, `snake_case` functions and variables, `UPPER_CASE` constants, and two-space JSON indentation. Follow existing Portuguese identifiers, comments, and documentation. Use `pathlib.Path` and explicit text encodings. Keep shared community logic in `comunidades.py`. No formatter or linter is configured.

## Testing Guidelines

Use standard-library `unittest`, `test_*.py` files, and `test_*` methods. Cover weighted communities, deterministic ordering, corrupted artifacts, and both study flows using small synthetic datasets and temporary directories. No coverage threshold is configured. Check that discovery actually finds tests; ignored local files are not distributed automatically.

## Commit & Pull Request Guidelines

History uses short, descriptive subjects, mostly in Portuguese, without an enforced prefix convention. Keep commits focused. PRs should explain the change, affected study, validation commands and outcomes, and any configuration or numerical changes. Link relevant issues and include updated figures when visualization changes.

## Configuration & Reproducibility

Set `OPENALEX_API_KEY` through the environment; never commit credentials. Preserve cache hashes, identity rules, and fixed random seeds unless intentionally revising methodology. Regenerate results through the pipeline and review tracked output changes before committing.
