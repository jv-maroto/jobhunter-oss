import asyncio
from types import SimpleNamespace

from app.ai.providers.anthropic_provider import AnthropicProvider


def test_complete_supports_sdk_without_temperature():
    calls = []

    def create(*, model, max_tokens, system, messages):
        calls.append((model, max_tokens, system, messages))
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"posts": []}')],
            usage=SimpleNamespace(input_tokens=12, output_tokens=8),
        )

    provider = AnthropicProvider("test-key")
    provider._client = SimpleNamespace(messages=SimpleNamespace(create=create))
    result = asyncio.run(provider.complete(
        system="Write news", user="Latest stories", temperature=0.7,
        json_mode=True, max_tokens=200,
    ))

    assert result.content == '{"posts": []}'
    assert result.input_tokens == 12
    assert result.output_tokens == 8
    assert len(calls) == 1
    assert calls[0][1] == 200
    assert "JSON" in calls[0][3][0]["content"][0]["text"]
