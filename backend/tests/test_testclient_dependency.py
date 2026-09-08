import starlette.testclient as starlette_testclient


def test_starlette_testclient_uses_httpx2_transport():
    """The supported transport must be active instead of Starlette's deprecated fallback."""
    assert starlette_testclient.httpx.__name__ == "httpx2"
