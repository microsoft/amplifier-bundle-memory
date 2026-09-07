"""The instance's own configuration: `<instance>/config.yaml` (store.v3 §2, §11).

Two keys, and the file answers for both the same way every time:

* **absent** -> built-in defaults, and everything behaves exactly as it did before the
  file existed (`enabled: true`; no `-p/-m/-B`, so `amplifier run`'s own default wins);
* **good** -> `enabled` is honoured, and provider/model/bundle become flags, in that
  order, and only when set;
* **bad** (unreadable, not YAML, a wrong type, an unknown call type or key) -> one honest
  reason and the same defaults, *returned* and never raised (suggestions.v1 Core 10) —
  and the instance stays **enabled**, because a parse error must never silently switch
  memory off.

store.v3 §1 made a store an instance and §2 gave the layout a place for this file, so
the knob that shipped as `~/.amplifier/memory-config.toml` now travels with the instance
it configures. Nothing here reads this device's real config: every test names its own
instance, and `load()` refuses the default path under pytest for exactly that reason.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import amplifier_memory
from amplifier_memory import llm_config, store


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / llm_config.CONFIG_NAME
    path.write_text(body, encoding="utf-8")
    return path


# ------------------------------------------------------------------ absent: today's behaviour


def test_no_file_means_defaults_and_no_flags(tmp_path: Path) -> None:
    config = llm_config.load(tmp_path / "nowhere")
    judge = config.call()
    print(f"path={config.path} present={config.present} reason={config.reason}")
    print(f"enabled={config.enabled} judge={judge} flags={judge.flags()}")

    assert config.present is False
    assert config.reason is None and config.usable
    assert config.enabled is True, "an instance with no config.yaml is live (store.v3 §11)"
    assert judge == llm_config.CallConfig(provider="", model="", bundle="", role="fast")
    assert judge.inherits is True
    assert judge.flags() == [], "an absent file must add no flag at all"
    assert judge.render() == "inherits the CLI default"


def test_the_config_lives_inside_the_instance_it_configures(monkeypatch) -> None:
    """store.v3 §2 puts `config.yaml` in the layout, so config travels with its instance."""
    monkeypatch.setenv(store.HOME_ENV, "/tmp/instance-one")
    print(f"config path: {llm_config.config_path()}")
    assert llm_config.config_path() == Path("/tmp/instance-one") / llm_config.CONFIG_NAME

    other = llm_config.config_path("/tmp/instance-two")
    print(f"a named instance: {other}")
    assert other == Path("/tmp/instance-two") / llm_config.CONFIG_NAME

    # The file itself is accepted too, so a caller holding one config path need not
    # strip the name off it first.
    assert llm_config.config_path(other) == other


def test_load_refuses_this_devices_own_config_from_a_test(monkeypatch) -> None:
    """The same guard as `default_model_call`: a suite must not read the steward's file."""
    monkeypatch.delenv(store.HOME_ENV, raising=False)
    config = llm_config.load()
    print(f"load() under pytest -> path={config.path} present={config.present}")
    assert config.path == store.default_home() / llm_config.CONFIG_NAME
    assert config.present is False and config.call().inherits and config.enabled


# ------------------------------------------------------------------ good: the flags it makes


def test_a_good_file_becomes_p_m_b_in_that_order(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "llm:\n"
        "  judge:\n"
        '    provider: "luna"\n'
        '    model: "gpt-5.6-luna"\n'
        '    bundle: "foundation"\n'
        '    role: "fast"\n',
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
    config = llm_config.load(_write(tmp_path, 'llm:\n  judge:\n    provider: "luna"\n'))
    judge = config.call()
    print(f"flags={judge.flags()} role={judge.role!r}")
    assert judge.flags() == ["-p", "luna"], "an unset model or bundle must add nothing"
    assert judge.role == llm_config.DEFAULT_ROLE, "role defaults even when unwritten"
    assert judge.inherits is False


def test_empty_strings_are_the_same_as_absent(tmp_path: Path) -> None:
    body = 'llm:\n  judge:\n    provider: ""\n    model: "  "\n    bundle: ""\n    role: ""\n'
    judge = llm_config.load(_write(tmp_path, body)).call()
    print(f"flags={judge.flags()} role={judge.role!r} inherits={judge.inherits}")
    assert judge.flags() == [] and judge.inherits
    assert judge.role == llm_config.DEFAULT_ROLE


def test_an_empty_file_and_a_file_with_no_llm_key_are_both_fine(tmp_path: Path) -> None:
    for body in ("", "# nothing yet\n", "enabled: true\n"):
        config = llm_config.load(_write(tmp_path, body))
        print(f"{body!r} -> present={config.present} reason={config.reason}")
        assert config.usable and config.call().inherits and config.enabled


# ------------------------------------------------------------------ store.v3 §11: enabled


def test_enabled_false_is_read_back_and_nothing_else_has_to_change(tmp_path: Path) -> None:
    """§11's key is one boolean; `enabled: false` is the only thing that makes an instance inert."""
    config = llm_config.load(_write(tmp_path, "enabled: false\n"))
    print(f"enabled={config.enabled} reason={config.reason} usable={config.usable}")
    assert config.usable and config.enabled is False
    assert llm_config.load(_write(tmp_path, "enabled: true\n")).enabled is True


def test_an_unusable_file_leaves_the_instance_enabled(tmp_path: Path) -> None:
    """The safe side of fail-open: a typo must never silently switch memory off."""
    config = llm_config.load(_write(tmp_path, "enabled: false\nllm: [oops]\n"))
    print(f"enabled={config.enabled} reason={config.reason}")
    assert config.usable is False and config.reason is not None
    assert config.enabled is True, "a file we could not read cannot disable the instance"


def test_a_non_boolean_enabled_is_reported_not_guessed_at(tmp_path: Path) -> None:
    config = llm_config.load(_write(tmp_path, 'enabled: "no"\n'))
    print(f"reason={config.reason}")
    assert config.reason is not None and "enabled is str, expected true or false" in config.reason
    assert config.enabled is True


# ------------------------------------------------------------------ bad: one honest reason


@pytest.mark.parametrize(
    ("body", "needle"),
    [
        ("llm:\n  judge:\n   provider: 'luna'\n  \tbad\n", "not valid YAML"),
        ('llm: "luna"\n', "llm: is str, expected a map"),
        ('llm:\n  judge: "luna"\n', "llm.judge is str, expected a map"),
        ("llm:\n  judge:\n    provider: 5\n", "llm.judge.provider is int, expected a string"),
        ("llm:\n  judge:\n    model: true\n", "llm.judge.model is bool, expected a string"),
        ('llm:\n  judg:\n    provider: "luna"\n', "unknown call type(s) judg"),
        ('llm:\n  judge:\n    providor: "luna"\n', "unknown key(s) providor"),
        ('judge: "luna"\n', "unknown top-level key(s) judge"),
        ("- a list, not a map\n", "config.yaml is list, expected a map"),
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
    assert "\n" not in config.reason, "a reason is one sentence, not a YAML traceback"
    assert config.usable is False
    assert config.call().flags() == [], "a bad file must fall back to today's behaviour"
    assert config.enabled is True
    assert config.source().startswith(f"{llm_config.CONFIG_NAME} unusable:")


def test_a_directory_where_the_file_should_be_is_reported_not_raised(tmp_path: Path) -> None:
    (tmp_path / llm_config.CONFIG_NAME).mkdir()
    config = llm_config.load(tmp_path / llm_config.CONFIG_NAME)
    print(f"present={config.present} reason={config.reason}")
    assert config.present and config.reason and "Error" in config.reason
    assert config.call().flags() == []


def test_invalid_utf8_is_reported_not_raised(tmp_path: Path) -> None:
    path = tmp_path / llm_config.CONFIG_NAME
    path.write_bytes(b'llm:\n  judge:\n    provider: "\xff\xfe"\n')
    config = llm_config.load(path)
    print(f"present={config.present} reason={config.reason}")
    assert config.present and config.reason and "codec" in config.reason
    assert config.call().flags() == []


# ------------------------------------------------------------------ what `init` actually writes


def test_the_body_init_writes_is_the_body_the_docs_print(tmp_path: Path) -> None:
    """The documented shape, the file `init` writes and the parser are one function."""
    assert llm_config.EXAMPLE == llm_config.default_body()
    config = llm_config.load(_write(tmp_path, llm_config.default_body()))
    judge = config.call()
    print(llm_config.default_body())
    print(f"parsed -> enabled={config.enabled} flags={judge.flags()} role={judge.role!r}")
    assert config.usable, config.reason
    assert config.enabled is True
    assert judge.flags() == [], "the shipped default inherits the CLI's provider"
    assert judge.role == llm_config.DEFAULT_ROLE


def test_init_writes_the_shipped_defaults_into_the_instance(store_dir: Path) -> None:
    """cli.v3 §8: a fresh instance carries `config.yaml` with `enabled` and `llm: judge:`."""
    path = store_dir / llm_config.CONFIG_NAME
    body = path.read_text(encoding="utf-8")
    print(f"--- {path} ---\n{body}")
    parsed = yaml.safe_load(body)
    print(f"parsed: {parsed}")

    assert parsed == {
        "enabled": True,
        "llm": {"judge": {"role": "fast", "provider": "", "model": "", "bundle": ""}},
    }
    config = llm_config.load(store_dir)
    assert config.present and config.usable and config.enabled
    assert config.call(llm_config.JUDGE).role == "fast"
    assert amplifier_memory.instance_enabled(store_dir) is True


@pytest.fixture
def store_dir(store: Path) -> Path:
    """The initialized temp instance `tests/conftest.py` builds, under this file's own name."""
    return store
