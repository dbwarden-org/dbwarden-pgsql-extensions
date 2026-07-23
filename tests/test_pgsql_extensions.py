def test_import():
    from dbwarden_pgsql_extensions import setup
    assert callable(setup)
