import asyncio
import os

import httpx
import pytest
from kb_api.linear import GRAPHQL_URL, create_issue, workspace

pytestmark = pytest.mark.skipif(
    os.environ.get("KB_LIVE_LINEAR") != "1" or not os.environ.get("LINEAR_API_KEY"),
    reason="set KB_LIVE_LINEAR=1 and LINEAR_API_KEY to hit Linear",
)

ARCHIVE = "mutation($id: String!) { issueArchive(id: $id) { success } }"


def test_live_issue_create_in_the_first_team_then_archive() -> None:
    async def run() -> None:
        # A personal API key is sent as is. An OAuth token would have Bearer.
        key = os.environ["LINEAR_API_KEY"]
        async with httpx.AsyncClient(timeout=15) as http:
            found = await workspace(http, key)
            issue = await create_issue(
                http,
                key,
                found.team.id,
                "[kb-copilot test] Handoff from the live test",
                "Created by services/api/tests/test_linear_live.py. Safe to delete.",
            )
            print(f"created {issue.identifier} {issue.url}")
            try:
                assert issue.identifier.startswith(f"{found.team.key}-")
                assert issue.url.startswith("https://linear.app/")
            finally:
                archived = await http.post(
                    GRAPHQL_URL,
                    json={"query": ARCHIVE, "variables": {"id": issue.identifier}},
                    headers={"authorization": key},
                )
                print(f"archive {archived.status_code} {archived.json()}")

    asyncio.run(run())
