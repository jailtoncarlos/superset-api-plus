def test_client(client):
    "Test basic superset client"

    assert client.access_token is not None
    assert client.access_token == {
        "access_token": "example_access_token",
        "refresh_token": "example_refresh_token",
    }
