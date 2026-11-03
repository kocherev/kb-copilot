"""The Linear OAuth and GraphQL calls. No database here."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, Field, ValidationError

from kb_api.linear_secrets import LinearConfig

AUTHORIZE_URL = "https://linear.app/oauth/authorize"
TOKEN_URL = "https://api.linear.app/oauth/token"
REVOKE_URL = "https://api.linear.app/oauth/revoke"
GRAPHQL_URL = "https://api.linear.app/graphql"
# Reading the workspace needs read, which every grant has. issues:create is all
# the app does with it.
SCOPE = "read,issues:create"
TIMEOUT_SECONDS = 10

WORKSPACE_QUERY = """
query { organization { name } teams(first: 1) { nodes { id key name } } }
"""
ISSUE_CREATE = """
mutation($input: IssueCreateInput!) {
  issueCreate(input: $input) { success issue { identifier url } }
}
"""


class LinearError(Exception):
    """Linear refused or could not be reached. The message is safe to log."""


class TokenGrant(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_in: int | None = None


class Team(BaseModel):
    id: str
    key: str
    name: str


@dataclass(frozen=True)
class Workspace:
    name: str
    team: Team


class _Organization(BaseModel):
    name: str


class _Teams(BaseModel):
    nodes: list[Team]


class _WorkspaceData(BaseModel):
    organization: _Organization
    teams: _Teams


class CreatedIssue(BaseModel):
    identifier: str
    url: str


class _IssuePayload(BaseModel):
    success: bool
    issue: CreatedIssue | None


class _IssueData(BaseModel):
    issue_create: _IssuePayload = Field(alias="issueCreate")


async def get_linear_http() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        yield client


def authorize_url(config: LinearConfig, state: str) -> str:
    query = urlencode(
        {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


async def _token_request(
    http: httpx.AsyncClient, config: LinearConfig, form: dict[str, str]
) -> TokenGrant:
    try:
        response = await http.post(
            TOKEN_URL,
            data={
                **form,
                "client_id": config.client_id,
                "client_secret": config.client_secret,
            },
        )
        response.raise_for_status()
        return TokenGrant.model_validate_json(response.content)
    except (httpx.HTTPError, ValidationError) as exc:
        # The response may echo a code or a token, so only the type is kept.
        raise LinearError(f"token request failed: {type(exc).__name__}") from exc


async def exchange_code(
    http: httpx.AsyncClient, config: LinearConfig, code: str
) -> TokenGrant:
    return await _token_request(
        http,
        config,
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.redirect_uri,
        },
    )


async def refresh(
    http: httpx.AsyncClient, config: LinearConfig, refresh_token: str
) -> TokenGrant:
    return await _token_request(
        http, config, {"grant_type": "refresh_token", "refresh_token": refresh_token}
    )


async def revoke(http: httpx.AsyncClient, token: str) -> None:
    try:
        await http.post(REVOKE_URL, data={"token": token})
    except httpx.HTTPError as exc:
        raise LinearError(f"revoke failed: {type(exc).__name__}") from exc


async def _graphql[T: BaseModel](
    http: httpx.AsyncClient,
    authorization: str,
    query: str,
    model: type[T],
    variables: dict[str, object] | None = None,
) -> T:
    try:
        response = await http.post(
            GRAPHQL_URL,
            json={"query": query, "variables": variables or {}},
            headers={"authorization": authorization},
        )
        body = response.json()
        # GraphQL reports failures in the body, often with HTTP 200.
        if response.status_code != 200 or body.get("errors"):
            raise LinearError(f"GraphQL request failed: HTTP {response.status_code}")
        return model.model_validate(body["data"])
    except (httpx.HTTPError, ValueError, KeyError, ValidationError) as exc:
        raise LinearError(f"GraphQL request failed: {type(exc).__name__}") from exc


async def workspace(http: httpx.AsyncClient, authorization: str) -> Workspace:
    data = await _graphql(http, authorization, WORKSPACE_QUERY, _WorkspaceData)
    if not data.teams.nodes:
        raise LinearError("the workspace has no teams")
    return Workspace(name=data.organization.name, team=data.teams.nodes[0])


async def create_issue(
    http: httpx.AsyncClient,
    authorization: str,
    team_id: str,
    title: str,
    description: str,
) -> CreatedIssue:
    data = await _graphql(
        http,
        authorization,
        ISSUE_CREATE,
        _IssueData,
        {"input": {"teamId": team_id, "title": title, "description": description}},
    )
    created = data.issue_create
    if not created.success or created.issue is None:
        raise LinearError("issueCreate did not succeed")
    return created.issue
