# Skill: Strategia test per GnomeThemeManager

Quando scrivi test per un nuovo modulo in `core/`, applica queste regole.

## Principi
1. I test in `core/` NON toccano il filesystem reale → usa fixture `tmp_path`
2. I test NON toccano gsettings reale → usa monkeypatch su `Gio.Settings`
3. Coverage ≥ 80% su `core/`, ≥ 60% su `cli/`, GUI NON testata unitariamente (solo smoke test)

## Template fixture

```python
@pytest.fixture
def fake_gsettings(monkeypatch):
    """Mock gsettings per test isolati."""
    state = {}
    class FakeSettings:
        def get_string(self, key): return state.get(key, "")
        def set_string(self, key, val): state[key] = val
    # monkeypatch qui
    yield FakeSettings()
```

## Categorie test obbligatorie per ogni modulo
- Happy path (input valido, output atteso)
- Input mancante / None
- Input corrotto (file inesistenti, `index.theme` malformato)
- Error handling (cosa succede se un componente fallisce)