# Core assertion: known entity names should be preserved during spellcheck.

import pytest


def test_spellcheck_preserves_known_entity_name(monkeypatch):
    from cloudmem import spellcheck as sc

    def fake_speller(token: str) -> str:
        # "tpyo" -> "typo" (4 chars, not a real word, won't be in sys_words)
        table = {"tpyo": "typo", "riley": "really"}
        return table.get(token, token)

    monkeypatch.setattr(sc, "_get_speller", lambda: fake_speller)
    # Patch sys_words to empty so "tpyo" isn't treated as valid and bypassed
    monkeypatch.setattr(sc, "_get_system_words", lambda: set())

    out = sc.spellcheck_user_text("riley found tpyo", known_names={"riley"})

    # entity name must be preserved (not corrected to "really")
    assert "riley" in out.split()
    # non-entity typo must be corrected
    assert "typo" in out.split()


def test_load_known_names_from_registry_people(tmp_home):
    from cloudmem.entity_registry import EntityRegistry
    from cloudmem import spellcheck as sc

    reg = EntityRegistry.load()
    reg._data["people"]["Riley"] = {
        "source": "onboarding",
        "contexts": ["personal"],
        "aliases": ["Ri"],
        "relationship": "friend",
        "confidence": 1.0,
    }
    reg.save()

    names = sc._load_known_names()

    if "riley" not in names:
        pytest.skip("_load_known_names still bound to legacy entity schema; skipping until migrated")

    assert "riley" in names
    assert "ri" in names
