"""The LLM-call knob: `${AMPLIFIER_MEMORY_CONFIG:-~/.amplifier/memory-config.toml}`.

Three questions, and the file answers all three the same way every time:

* **absent** -> built-in defaults, and the job behaves exactly as it did before the file
  existed (no `-p/-m/-B`, so `amplifier run`'s own default wins);
* **good** -> provider/model/bundle become flags, in that order, and only when set;
* **bad** (unreadable, not TOML, a wrong type, an unknown call type or key) -> one honest
  reason and the same defaults, *returned* and never raised (suggestions.v1 Core 10).

Nothing here reads this device's real `~/.amplifier/memory-config.toml`: every test names
its own file, and `load()` refuses the default path under pytest for exactly that reason.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from amplifier_memory import llm_config


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / llm_config.CONFIG_NAME
    path.write_text(body, encoding="utf-8")
    return path


# ------------------------------------------------------------------ absent: today's behaviour


def test_no_file_means_defaults_and_no_flags(tmp_path: Path) -> None:
    config = llm_config.load(tmp_path / "nothing-here.toml")
    judge = config.call()
    print(f"path={config.path} present={config.present} reason={config.reason}")
    print(f"judge={judge} flags={judge.flags()} render={judge.render()!r}")

    assert config.present is False
    assert config.reason is None and config.usable
    assert judge == llm_config.CallConfig(provider="", model="", bundle="", role="fast")
    assert judge.inherits is True
    assert judge.flags() == [], "an absent file must add no flag at all"
    assert judge.render() == "inherits the CLI default"


def test_the_default_path_is_beside_the_store_never_inside_it(monkeypatch) -> None:
    """store.v2 §2 fixes the store's layout; a config file inside it would break it."""
    monkeypatch.delenv(llm_config.CONFIG_ENV, raising=False)
    default = llm_config.config_path()
    store = Path.home() / ".amplifier" / "memory"
    print(f"config path: {default}\nstore home:  {store}")

    assert default == Path.home() / ".amplifier" / llm_config.CONFIG_NAME
    assert store not in default.parents, "the config file must not live inside the store"

    monkeypatch.setenv(llm_config.CONFIG_ENV, "/tmp/elsewhere.toml")
    assert llm_config.config_path() == Path("/tmp/elsewhere.toml")
    print(f"{llm_config.CONFIG_ENV} honoured: {llm_config.config_path()}")


def test_load_refuses_this_devices_own_config_from_a_test(monkeypatch) -> None:
    """The same guard as `default_model_call`: a suite must not read the steward's file."""
    monkeypatch.delenv(llm_config.CONFIG_ENV, raising=False)
    config = llm_config.load()
    print(f"load() under pytest -> present={config.present} reason={config.reason}")
    assert config.path == Path.home() / ".amplifier" / llm_config.CONFIG_NAME
    assert config.present is False and config.call().inherits


# ------------------------------------------------------------------ good: the flags it makes


def test_a_good_file_becomes_p_m_b_in_that_order(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        '[llm.judge]\nprovider = "luna"\nmodel = "gpt-5.6-luna"\nbundle = "foundation"\n'
        'role = "fast"\n',
    )
    config = llm_config.load(path)
    judge = config.call()
    print(path.read_text(encoding="utf-8"))
    print(f"present={config.present} reason={config.reason} flags={judge.flags()}")

    assert config.present and config.usable
    assert (judge.provider, judge.model, judge.bundle, judge.role) == (
        "luna",
        "gpt-5.6-luna",
        "foundation",
        "fast",
    )
    assert judge.flags() == ["-p", "luna", "-m", "gpt-5.6-luna", "-B", "foundation"]
    assert judge.inherits is False
    assert "provider luna" in judge.render()


def test_only_the_keys_actually_set_become_flags(tmp_path: Path) -> None:
    """The measured recommendation is a provider alone (`-p luna`); model/bundle stay off."""
    config = llm_config.load(_write(tmp_path, '[llm.judge]\nprovider = "luna"\n'))
    judge = config.call()
    print(f"flags={judge.flags()} role={judge.role!r}")
    assert judge.flags() == ["-p", "luna"], "an unset model or bundle must add nothing"
    assert judge.role == llm_config.DEFAULT_ROLE, "role defaults even when unwritten"
    assert judge.inherits is False


def test_empty_strings_are_the_same_as_absent(tmp_path: Path) -> None:
    body = '[llm.judge]\nprovider = ""\nmodel = "  "\nbundle = ""\nrole = ""\n'
    judge = llm_config.load(_write(tmp_path, body)).call()
    print(f"flags={judge.flags()} role={judge.role!r} inherits={judge.inherits}")
    assert judge.flags() == [] and judge.inherits
    assert judge.role == llm_config.DEFAULT_ROLE


def test_an_empty_file_and_a_file_with_no_llm_table_are_both_fine(tmp_path: Path) -> None:
    for body in ("", "# nothing yet\n", '[something_else]\nkey = "value"\n'):
        config = llm_config.load(_write(tmp_path, body))
        print(f"{body!r} -> present={config.present} reason={config.reason}")
        assert config.usable and config.call().inherits


# ------------------------------------------------------------------ bad: one honest reason


@pytest.mark.parametrize(
    ("body", "needle"),
    [
        ("[llm.judge\nprovider = 'luna'\n", "not valid TOML"),
        ('llm = "luna"\n', "[llm] is str, expected a table"),
        ('[llm]\njudge = "luna"\n', "[llm.judge] is str, expected a table"),
        ("[llm.judge]\nprovider = 5\n", "llm.judge.provider is int, expected a string"),
        ("[llm.judge]\nmodel = true\n", "llm.judge.model is bool, expected a string"),
        ('[llm.judg]\nprovider = "luna"\n', "unknown call type(s) judg"),
        ('[llm.judge]\nprovidor = "luna"\n', "unknown key(s) providor"),
    ],
)
def test_a_bad_file_returns_one_reason_and_the_defaults(
    tmp_path: Path, body: str, needle: str
) -> None:
    """Never raised into the job (Core 10) — reported, and the CLI default is inherited."""
    config = llm_config.load(_write(tmp_path, body))
    print(f"--- config ---\n{body}--- reason ---\n{config.reason}")

    assert config.present is True, "the file is there; that is part of the honesty"
    assert config.reason is not None and needle in config.reason
    assert config.usable is False
    assert config.call().flags() == [], "a bad file must fall back to today's behaviour"
    assert config.source().startswith(f"{llm_config.CONFIG_NAME} unusable:")


def test_a_directory_where_the_file_should_be_is_reported_not_raised(tmp_path: Path) -> None:
    (tmp_path / llm_config.CONFIG_NAME).mkdir()
    config = llm_config.load(tmp_path / llm_config.CONFIG_NAME)
    print(f"present={config.present} reason={config.reason}")
    assert config.present and config.reason and "Error" in config.reason
    assert config.call().flags() == []


def test_invalid_utf8_is_reported_not_raised(tmp_path: Path) -> None:
    path = tmp_path / llm_config.CONFIG_NAME
    path.write_bytes(b'[llm.judge]\nprovider = "\xff\xfe"\n')
    config = llm_config.load(path)
    print(f"present={config.present} reason={config.reason}")
    assert config.present and config.reason and "not valid TOML" in config.reason
    assert config.call().flags() == []


def test_the_example_in_the_docs_parses(tmp_path: Path) -> None:
    """The documented shape and the parser cannot drift: the docs print `EXAMPLE`."""
    config = llm_config.load(_write(tmp_path, llm_config.EXAMPLE))
    judge = config.call()
    print(llm_config.EXAMPLE)
    print(f"parsed -> flags={judge.flags()} role={judge.role!r} reason={config.reason}")
    assert config.usable, config.reason
    assert judge.flags() == ["-p", "luna"] and judge.role == llm_config.DEFAULT_ROLE
