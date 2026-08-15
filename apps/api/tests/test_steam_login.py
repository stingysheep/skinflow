from http.cookies import SimpleCookie

from skinflow_api.infrastructure.platforms.steam.login import extract_credentials


def test_extract_credentials_accepts_encoded_login_cookie() -> None:
    login = SimpleCookie()
    login.load("steamLoginSecure=76561198000000000%7C%7Ctoken")
    session = SimpleCookie()
    session.load("sessionid=csrf")
    credentials = extract_credentials([login, session])
    assert credentials is not None
    assert credentials.steamid64 == "76561198000000000"
    assert "token" not in repr(credentials)


def test_extract_credentials_rejects_partial_session() -> None:
    assert extract_credentials([{"name": "sessionid", "value": "csrf"}]) is None
