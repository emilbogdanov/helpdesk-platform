from httpx import AsyncClient


async def test_health_needs_no_token_and_stays_out_of_the_schema(client: AsyncClient) -> None:
    response = await client.get("/health")
    schema = (await client.get("/openapi.json")).json()

    assert response.json() == {"status": "ok"}
    assert "/health" not in schema["paths"]
