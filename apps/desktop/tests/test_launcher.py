from skinflow_desktop.launcher import (
    DEFAULT_PORT,
    LOCAL_HOST,
    desktop_icon_path,
    find_available_port,
    generate_startup_token,
)


def test_startup_token_is_fresh_and_url_safe() -> None:
    first = generate_startup_token()
    second = generate_startup_token()

    assert first != second
    assert len(first) >= 32
    assert all(character.isalnum() or character in "-_" for character in first)


def test_find_available_port_prefers_default_when_free() -> None:
    port = find_available_port(preferred=0)

    assert port > 0
    assert LOCAL_HOST == "127.0.0.1"
    assert DEFAULT_PORT == 58150


def test_icon_is_project_local_and_distinct_from_legacy_path() -> None:
    icon = desktop_icon_path()
    assert icon.name == "skinflow.ico"
    assert icon.exists()
    assert "D:" not in str(icon)


def test_non_windows_single_instance_is_noop(monkeypatch) -> None:
    from skinflow_desktop import launcher

    monkeypatch.setattr(launcher.os, "name", "posix")
    assert launcher.acquire_single_instance("test") is True
