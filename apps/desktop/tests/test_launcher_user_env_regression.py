from skinflow_api.settings import Settings
from skinflow_desktop import launcher


def test_desktop_resolves_user_environment_after_explorer_started(monkeypatch) -> None:
    settings = Settings(environment="test", csqaq_api_token="")
    monkeypatch.setattr(
        launcher,
        "read_user_environment",
        lambda name: "secret-from-user-environment" if name == launcher.CSQAQ_TOKEN_ENV else "",
    )

    resolved = launcher.resolve_desktop_settings(settings)

    assert resolved.csqaq_api_token == "secret-from-user-environment"


def test_explicit_desktop_token_wins_over_user_environment(monkeypatch) -> None:
    settings = Settings(environment="test", csqaq_api_token="explicit-token")
    monkeypatch.setattr(launcher, "read_user_environment", lambda _name: "registry-token")

    resolved = launcher.resolve_desktop_settings(settings)

    assert resolved.csqaq_api_token == "explicit-token"
