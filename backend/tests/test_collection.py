from decimal import Decimal
from unittest.mock import Mock

import httpx
import pytest
from apify_client.errors import ApifyApiError
from backend.pipeline import AnalysisError, Settings, collect

URL = "https://www.tiktok.com/@example/video/123456789"


def settings(cap=.50):
    return Settings("test-secret", "clockworks/tiktok-scraper", cap, "small", "test", "cpu", .6)


def test_default_spend_cap_meets_actor_minimum(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "test-secret")
    monkeypatch.delenv("APIFY_MAX_COST_USD", raising=False)
    assert Settings.from_env().max_cost == .50


def test_default_vision_model_avoids_ambiguous_thinking_alias(monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "test-secret")
    monkeypatch.delenv("VISION_MODEL", raising=False)
    assert Settings.from_env().vision_model == "qwen3-vl:4b-instruct"


def test_collection_preserves_apify_reason_and_redacts_credentials(monkeypatch):
    client = Mock()
    client.actor.return_value.call.side_effect = ApifyApiError(httpx.Response(400, json={
        "error": {"type": "invalid-request", "message":
                  "Maximum cost per run is less than the allowed minimum of $0.50. token=test-secret"}
    }), attempt=1)
    monkeypatch.setattr("apify_client.ApifyClient", lambda *_: client)
    with pytest.raises(AnalysisError) as caught:
        collect(URL, settings())
    assert "$0.50" in str(caught.value)
    assert "400" in str(caught.value)
    assert "test-secret" not in str(caught.value)
    assert client.actor.return_value.call.call_args.kwargs["max_total_charge_usd"] == Decimal("0.5")


def test_invalid_low_cap_fails_before_spending_or_starting_run(monkeypatch):
    client = Mock()
    monkeypatch.setattr("apify_client.ApifyClient", lambda *_: client)
    with pytest.raises(AnalysisError, match="0.50"):
        collect(URL, settings(.10))
    client.actor.assert_not_called()
