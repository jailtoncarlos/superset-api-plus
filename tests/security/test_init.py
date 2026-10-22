def test_client(client):
    "Test basic superset client"

    assert client.access_token is not None
    assert client.access_token == "example_access_token"
