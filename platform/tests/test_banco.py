"""Testes do que ``banco.py`` promete: criar o esquema inteiro.

Existe por causa de uma linha que parece sobra: o import de ``modelos_futuros`` em
``banco.py``. Nenhum codigo usa as tabelas da Fase 4, entao apagar esse import nao
quebraria teste nenhum -- o esquema so sairia incompleto, em silencio.
"""

from sqlalchemy import inspect

#: Todas as tabelas que o banco precisa ter, inclusive as que nenhum codigo usa ainda.
TABELAS_ESPERADAS = {
    "organizations",
    "users",
    "apiaries",
    "hives",
    "nodes",
    "node_assignments",
    "measurements",
    "ingest_rejects",
    "calibrations",
    "alert_rules",
    "alerts",
}


def test_criar_tabelas_cria_o_esquema_inteiro(db) -> None:
    """A fixture ``db`` chama ``criar_tabelas``; aqui se confere o que ficou no banco."""
    tabelas = set(inspect(db).get_table_names())

    faltando = TABELAS_ESPERADAS - tabelas
    assert not faltando, f"criar_tabelas nao criou: {sorted(faltando)}"
