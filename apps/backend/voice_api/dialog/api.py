"""Bounded business API calls to operator-approved destinations only."""

import httpx

from .config import APIContract


class BusinessAPI:
    """Map database endpoint aliases to deployment-owned URLs and credentials."""

    def __init__(
        self,
        endpoints: dict[str, str],
        headers: dict[str, dict[str, str]] | None = None,
        transport=None,
    ):
        """Keep URLs and authentication outside caller data and database templates."""
        for url in endpoints.values():
            parsed = httpx.URL(url)
            if parsed.scheme not in {"http", "https"} or not parsed.host or parsed.userinfo:
                raise ValueError("Business endpoints require HTTP(S) URLs without userinfo")
        self.endpoints = endpoints.copy()
        self.headers = headers or {}
        self.transport = transport

    async def call(self, contract: APIContract, entities: dict[str, str]) -> dict[str, str]:
        """Bind extracted entities and map JSON response paths to template placeholders."""
        url = self.endpoints[contract.endpoint]
        query = {key: entities[name] for key, name in contract.query.items()}
        query.update(
            {
                key: entities[name]
                for key, name in contract.optional_query.items()
                if entities.get(name)
            }
        )
        body = {key: entities[name] for key, name in contract.body.items()}
        async with httpx.AsyncClient(
            follow_redirects=False, trust_env=False, transport=self.transport
        ) as client:
            # Includes connect, response streaming and JSON decoding wall-clock time.
            import asyncio

            async with asyncio.timeout(contract.timeout_seconds):
                async with client.stream(
                    contract.method,
                    url,
                    params=query,
                    json=body if body else None,
                    headers=self.headers.get(contract.endpoint, {}),
                    timeout=contract.timeout_seconds,
                ) as response:
                    response.raise_for_status()
                    if response.is_redirect:
                        raise ValueError("Business API redirects are forbidden")
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > 1024 * 1024:
                            raise ValueError("Business API response too large")
                    import json

                    payload = json.loads(content)
        values = {}
        for placeholder, path in contract.response.items():
            value = payload
            for component in path.split("."):
                value = value[int(component)] if isinstance(value, list) else value[component]
            if value is None or isinstance(value, (dict, list)):
                raise ValueError("Response placeholders must resolve to scalar values")
            values[placeholder] = str(value)
        return values
