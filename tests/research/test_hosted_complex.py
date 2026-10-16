"""Thirty challenging scenarios; collection is offline and execution is explicitly opt-in."""

import os

import httpx
import pytest

from comtech.agents.errors import ProviderQuotaExhausted

from .complex_evaluation import evaluate_case, load_catalogue

CATALOGUE = load_catalogue()
pytestmark = [
    pytest.mark.hosted,
    pytest.mark.skipif(
        os.getenv("RUN_HOSTED_COMPLEX") != "1",
        reason="Set RUN_HOSTED_COMPLEX=1 to run the separate 30-case evaluation",
    ),
]


@pytest.mark.parametrize("case", CATALOGUE.cases, ids=lambda case: case.id + "-" + case.title)
async def test_hosted_complex(case):
    base = os.environ["HOSTED_RESEARCH_API_URL"].rstrip("/")
    directory = os.getenv("HOSTED_COMPLEX_REPORT_DIR", "var/research-evaluation/complex")
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        try:
            await evaluate_case(client, CATALOGUE, case, directory)
        except ProviderQuotaExhausted:
            pytest.exit(
                "Provider API quota exhausted; remaining cases were not submitted.", returncode=2
            )
