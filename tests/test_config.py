import pytest

from app import config


def test_load_watchlist_parses_creators(tmp_path):
    p = tmp_path / "watchlist.yaml"
    p.write_text(
        "creators:\n"
        "  - platform: instagram\n"
        "    handle: andrejko.epta\n"
        "  - platform: youtube\n"
        "    handle: UCxyz\n"
        "topics:\n"
        "  - random acts of kindness\n",
        encoding="utf-8",
    )
    wl = config.load_watchlist(str(p))

    assert len(wl.creators) == 2
    assert wl.creators[0].platform == "instagram"
    assert wl.creators[0].handle == "andrejko.epta"
    assert wl.topics == ["random acts of kindness"]


def test_load_watchlist_rejects_unknown_platform(tmp_path):
    p = tmp_path / "watchlist.yaml"
    p.write_text("creators:\n  - platform: myspace\n    handle: x\n", encoding="utf-8")

    with pytest.raises(ValueError, match="myspace"):
        config.load_watchlist(str(p))


def test_load_settings_returns_mapping(tmp_path):
    p = tmp_path / "settings.yaml"
    p.write_text("digest:\n  hour: 7\n", encoding="utf-8")

    assert config.load_settings(str(p)) == {"digest": {"hour": 7}}


@pytest.mark.parametrize("contents", ["- item\n", "settings\n"])
def test_load_settings_rejects_non_mapping(contents, tmp_path):
    p = tmp_path / "settings.yaml"
    p.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match="must be a YAML mapping"):
        config.load_settings(str(p))


def test_env_raises_when_missing(monkeypatch):
    monkeypatch.delenv("DEFINITELY_NOT_SET", raising=False)
    with pytest.raises(RuntimeError, match="DEFINITELY_NOT_SET"):
        config.env("DEFINITELY_NOT_SET")


def test_env_returns_default(monkeypatch):
    monkeypatch.delenv("DEFINITELY_NOT_SET", raising=False)
    assert config.env("DEFINITELY_NOT_SET", "fallback") == "fallback"
