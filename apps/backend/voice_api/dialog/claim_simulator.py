"""Explicit offline Claim Status HTTP simulation; never contacts a real insurer."""

import json
from datetime import date
from pathlib import Path

import httpx

from .api import BusinessAPI
from .config import DialogConfig
from .engine import missing_fields


def simulated_claim_api() -> BusinessAPI:
    """Exercise normal HTTP binding/decoding with a deterministic synthetic response."""
    config = DialogConfig.model_validate_json(
        (Path(__file__).resolve().parents[2] / "dialog-policy.claim-status.json").read_text(
            encoding="utf-8"
        )
    )
    intent = next(i for i in config.intents if i.name == "CLAIM_STATUS")

    def handle(request: httpx.Request) -> httpx.Response:
        if request.method != "GET" or request.url.path != "/ivr/claims/search":
            return httpx.Response(404)
        values = dict(request.url.params)
        try:
            if missing_fields(intent, values):
                raise ValueError("Insufficient lookup criteria")
            for name in ("dateOfBirth", "dateOfService"):
                if name in values:
                    date.fromisoformat(values[name])
            if "providerNpi" in values and (
                len(values["providerNpi"]) != 10
                or not values["providerNpi"].isascii()
                or not values["providerNpi"].isdigit()
            ):
                raise ValueError("Invalid NPI")
            if values.get("searchType", "SPECIFIC_CLAIM") not in {
                "SPECIFIC_CLAIM",
                "RECENT_CLAIMS",
            }:
                raise ValueError("Invalid search type")
            if int(values.get("maxResults", "3")) < 1:
                raise ValueError("Invalid result limit")
        except ValueError:
            return httpx.Response(400, json={"detail": "Invalid simulated lookup criteria"})
        claim = {
            "claimNumber": "DEMO-10001",
            "claimNumberDigitsOnly": "10001",
            "memberFullName": "Demo Member",
            "providerName": "Demo Clinic",
            "internalStatus": "PAID",
            "claimStatusSpeechText": "Your demonstration claim is fully paid.",
            "isFinalized": True,
            "pendingActionRequired": False,
            "actionRequiredSpeechText": "No action is required.",
            "dateOfServiceFormatted": "September fourteenth, twenty twenty-six",
            "dateReceivedFormatted": "October first, twenty twenty-six",
            "paymentDateFormatted": "October twelfth, twenty twenty-six",
            "totalBilledAmountSpeech": "five hundred dollars",
            "allowedAmountSpeech": "four hundred dollars",
            "memberResponsibilitySpeech": "fifty dollars",
            "amountPaidSpeech": "three hundred and fifty dollars",
            "paymentMethod": "EFT",
            "checkNumberOrTraceId": "000123456",
            "denialReasonSpeechText": "",
            "transferTargetQueue": "DEMO_SUPPORT",
        }
        return httpx.Response(
            200, json={"callerAuthenticated": True, "totalMatchesFound": 1, "claims": [claim]}
        )

    return BusinessAPI(
        {"claim_status": "https://claim-status.invalid/ivr/claims/search"},
        transport=httpx.MockTransport(handle),
    )
