import io
import json
import urllib.error

import pytest

from trading import ai
from trading.ai import AIError, AISettings, classify, parse_classification

GOOD = {"summary": "Wins Rs 500 cr order", "event_type": "order_win",
        "symbols": ["abc"], "uncertainty": "low"}


def test_allowlist():
    with pytest.raises(ValueError):
        AISettings().endpoint()
    assert "deepseek.com" in AISettings("deepseek", "m", "k").endpoint()
    assert "z.ai" in AISettings("glm", "m", "k").endpoint()
    with pytest.raises(ValueError):
        AISettings("other", "m", "k").endpoint()


def test_parse_plain_json():
    out = parse_classification(json.dumps(GOOD))
    assert out["symbols"] == ("ABC",)


def test_parse_fenced_json():
    out = parse_classification("```json\n" + json.dumps(GOOD) + "\n```")
    assert out["event_type"] == "order_win"


@pytest.mark.parametrize("bad", [
    "", "not json", "[1, 2]",
    json.dumps({**GOOD, "event_type": "buy_now"}),
    json.dumps({**GOOD, "uncertainty": "none"}),
    json.dumps({**GOOD, "symbols": "ABC"}),
    json.dumps({k: v for k, v in GOOD.items() if k != "summary"}),
])
def test_parse_rejects_bad_output(bad):
    with pytest.raises(AIError):
        parse_classification(bad)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_classify_success(monkeypatch):
    sent = {}

    def fake_urlopen(req, timeout):
        sent["body"] = json.loads(req.data)
        payload = {"choices": [{"message": {"content": json.dumps(GOOD)}}],
                   "usage": {"prompt_tokens": 120, "completion_tokens": 40}}
        return FakeResponse(json.dumps(payload).encode())

    monkeypatch.setattr(ai.urllib.request, "urlopen", fake_urlopen)
    result = classify(AISettings("deepseek", "m", "k"), "ABC Ltd wins order")
    assert result.event_type == "order_win"
    assert (result.prompt_tokens, result.completion_tokens) == (120, 40)
    assert sent["body"]["response_format"] == {"type": "json_object"}


def test_classify_http_error_is_wrapped(monkeypatch):
    def fake_urlopen(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many", {}, None)

    monkeypatch.setattr(ai.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(AIError, match="HTTP 429"):
        classify(AISettings("glm", "m", "k"), "text")


def test_classify_bad_shape(monkeypatch):
    monkeypatch.setattr(ai.urllib.request, "urlopen",
                        lambda req, timeout: FakeResponse(b'{"choices": []}'))
    with pytest.raises(AIError, match="shape"):
        classify(AISettings("glm", "m", "k"), "text")
