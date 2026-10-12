"""Execute example notebooks against the installed checkout in CI."""
from pathlib import Path
import tempfile

import nbformat
from nbclient import NotebookClient

root = Path(__file__).resolve().parents[1]
for path in sorted((root / 'examples').glob('*.ipynb')):
    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook)
    # CI already installed this checkout. Colab's install cell uses public PyPI.
    notebook.cells = [cell for cell in notebook.cells if 'install' not in cell.metadata.get('tags', [])]
    with tempfile.TemporaryDirectory() as directory:
        NotebookClient(notebook, timeout=180, kernel_name='python3', resources={'metadata': {'path': directory}}).execute()
    print(f'Executed all example cells: {path.name}')
