import importlib.util
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "recover_telegram_owner",
    Path(__file__).parent / "scripts" / "recover-telegram-owner.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_existing_owner_uses_persisted_private_home_channel(tmp_path, monkeypatch):
    monkeypatch.setattr(MODULE, "HOME", tmp_path)
    monkeypatch.setattr(MODULE, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(MODULE, "OWNER_FILE", tmp_path / "telegram_owner.json")
    monkeypatch.setattr(MODULE, "CONFIG_FILE", tmp_path / "config.yaml")
    monkeypatch.setattr(MODULE, "APPROVED_FILE", tmp_path / "platforms" / "pairing" / "telegram-approved.json")
    MODULE.CONFIG_FILE.write_text(
        "gateway:\n  platforms:\n    telegram:\n      home_channel:\n        chat_id: '8890901423'\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("TELEGRAM_OWNER_CHAT_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_ALLOWED_USERS", raising=False)
    assert MODULE.existing_owner() == "8890901423"


def test_existing_owner_does_not_use_group_home_channel(tmp_path, monkeypatch):
    monkeypatch.setattr(MODULE, "HOME", tmp_path)
    monkeypatch.setattr(MODULE, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(MODULE, "OWNER_FILE", tmp_path / "telegram_owner.json")
    monkeypatch.setattr(MODULE, "CONFIG_FILE", tmp_path / "config.yaml")
    monkeypatch.setattr(MODULE, "APPROVED_FILE", tmp_path / "platforms" / "pairing" / "telegram-approved.json")
    MODULE.CONFIG_FILE.write_text(
        "gateway:\n  platforms:\n    telegram:\n      home_channel:\n        chat_id: '-1001234567890'\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("TELEGRAM_OWNER_CHAT_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_ALLOWED_USERS", raising=False)
    assert MODULE.existing_owner() == ""


def test_existing_owner_reads_current_root_platforms_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(MODULE, "HOME", tmp_path)
    monkeypatch.setattr(MODULE, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(MODULE, "OWNER_FILE", tmp_path / "telegram_owner.json")
    monkeypatch.setattr(MODULE, "CONFIG_FILE", tmp_path / "config.yaml")
    monkeypatch.setattr(MODULE, "APPROVED_FILE", tmp_path / "platforms" / "pairing" / "telegram-approved.json")
    MODULE.CONFIG_FILE.write_text(
        "platforms:\n  telegram:\n    home_channel:\n      platform: telegram\n      chat_id: '8890901423'\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("TELEGRAM_OWNER_CHAT_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_ALLOWED_USERS", raising=False)
    assert MODULE.existing_owner() == "8890901423"
