"""Configuracao comum dos testes da plataforma.

Poe a raiz do monorepo e o diretorio ``contracts/`` no ``sys.path`` para que os testes
possam importar tanto o pacote ``meliponet`` quanto o modulo ``canonical`` do
contrato, que e compartilhado com o gerador de vetores dourados.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = REPO_ROOT / "contracts"
TESTDATA_DIR = CONTRACTS_DIR / "testdata"

for path in (REPO_ROOT / "platform", CONTRACTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.fixture(scope="session")
def testdata_dir() -> Path:
    return TESTDATA_DIR
