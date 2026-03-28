import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture(autouse=True)
def tmp_workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_github_push_stats_skips_without_token(monkeypatch):
    """PAT_TOKEN が未設定の場合はスキップしてエラーを出さないこと"""
    import importlib
    import config
    monkeypatch.setattr(config, "PAT_TOKEN", None)
    import main as m
    importlib.reload(m)
    m.github_push_stats()  # should not raise


def test_github_push_stats_skips_without_file(monkeypatch):
    """stats.json が存在しない場合はスキップしてエラーを出さないこと"""
    import importlib
    import config
    monkeypatch.setattr(config, "PAT_TOKEN", "fake-token")
    import main as m
    importlib.reload(m)
    with patch("requests.get") as mock_get, patch("requests.put") as mock_put:
        m.github_push_stats()
    mock_put.assert_not_called()


def test_github_push_stats_new_file(tmp_path, monkeypatch):
    """stats.json が新規ファイル（SHA なし）で PUT が呼ばれること"""
    import importlib
    import config
    monkeypatch.setattr(config, "PAT_TOKEN", "fake-token")
    import main as m
    importlib.reload(m)

    os.makedirs("logs")
    (tmp_path / "logs" / "stats.json").write_text('{"balance": 100000}', encoding="utf-8")

    mock_get = MagicMock()
    mock_get.return_value.status_code = 404

    mock_put = MagicMock()
    mock_put.return_value.status_code = 201

    with patch("requests.get", mock_get), patch("requests.put", mock_put):
        m.github_push_stats()

    mock_put.assert_called_once()
    payload = mock_put.call_args[1]["json"]
    assert "content" in payload
    assert "sha" not in payload


def test_github_push_stats_existing_file(tmp_path, monkeypatch):
    """既存ファイルの場合（SHA あり）で PUT に sha が含まれること"""
    import importlib
    import config
    monkeypatch.setattr(config, "PAT_TOKEN", "fake-token")
    import main as m
    importlib.reload(m)

    os.makedirs("logs")
    (tmp_path / "logs" / "stats.json").write_text('{"balance": 100000}', encoding="utf-8")

    mock_get = MagicMock()
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"sha": "abc123"}

    mock_put = MagicMock()
    mock_put.return_value.status_code = 200

    with patch("requests.get", mock_get), patch("requests.put", mock_put):
        m.github_push_stats()

    payload = mock_put.call_args[1]["json"]
    assert payload["sha"] == "abc123"
