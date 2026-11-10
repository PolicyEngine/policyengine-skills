"""Auth0 client-credentials tokens for the PolicyEngine Public API, cached across instances.

Copy this file into a server that calls the Public API (api.policyengine.org)
itself: a Modal backend, a Cloud Run service or a scheduled job. Browser code
never calls the Public API; pages use www.policyengine.org's dashboard API
(the policyengine-api-access skill).

It reads the five variables below from the server's secret store, asks the
Auth0 tenant for one token, and keeps it until five minutes before it expires:
first in this process's memory, then in a store the server's instances share,
so a deployment asks Auth0 for about one token a day rather than one per
request or per container. Auth0 counts the machine-to-machine tokens it issues
per tenant per month.

    POLICYENGINE_API_URL                  https://api.policyengine.org in production
    POLICYENGINE_API_AUTH0_DOMAIN         policyengine-api.uk.auth0.com in production
    POLICYENGINE_API_AUTH0_AUDIENCE       https://api.policyengine.org/ in production
    POLICYENGINE_API_AUTH0_CLIENT_ID      this caller's own client
    POLICYENGINE_API_AUTH0_CLIENT_SECRET  that client's secret

On Modal, the shared store is a Dict, and each container builds one provider the
first time it needs one (the secret's variables exist only inside the container):

    import functools

    import modal
    from public_api_token import PublicApiSettings, PublicApiTokenProvider, call_public_api

    TOKEN_STORE = modal.Dict.from_name("TOOL_NAME-public-api-token", create_if_missing=True)

    @functools.cache
    def public_api_tokens() -> PublicApiTokenProvider:
        return PublicApiTokenProvider(PublicApiSettings.from_environment(), shared_store=TOKEN_STORE)

    @app.function(secrets=[modal.Secret.from_name("TOOL_NAME-policyengine-api")])
    def household(situation: dict) -> dict:
        return call_public_api(public_api_tokens(), "POST", "/us/calculate", {"household": situation})

Any object with ``get(key)`` and item assignment works as the shared store; a
plain ``dict`` keeps the token for one process only. Only the token and when to
replace it are stored, never the client secret.

Requests never follow redirects: a followed redirect would send the client
secret, or the token, to wherever it points.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any

LOGGER = logging.getLogger(__name__)

# Replace a token this long before it expires (half its life, if shorter).
TOKEN_REFRESH_MARGIN_SECONDS = 300
TOKEN_REQUEST_TIMEOUT_SECONDS = 10
PUBLIC_API_TIMEOUT_SECONDS = 120

SETTING_VARIABLES = {
    "api_url": "POLICYENGINE_API_URL",
    "token_endpoint_host": "POLICYENGINE_API_AUTH0_DOMAIN",
    "audience": "POLICYENGINE_API_AUTH0_AUDIENCE",
    "client_id": "POLICYENGINE_API_AUTH0_CLIENT_ID",
    "client_secret": "POLICYENGINE_API_AUTH0_CLIENT_SECRET",
}


class PublicApiSettingsError(ValueError):
    """A setting is missing or malformed."""


class PublicApiTokenError(RuntimeError):
    """Auth0 refused the token request or gave no usable token."""


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        return None  # urllib then raises HTTPError with the 3xx status


NO_REDIRECT_OPENER = urllib.request.build_opener(_RefuseRedirects)


@dataclass(frozen=True)
class PublicApiSettings:
    api_url: str
    token_endpoint_host: str
    audience: str
    client_id: str
    client_secret: str

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> PublicApiSettings:
        environment = os.environ if environment is None else environment
        values = {field: environment.get(name, "").strip() for field, name in SETTING_VARIABLES.items()}
        missing = [SETTING_VARIABLES[field] for field, value in values.items() if not value]
        if missing:
            raise PublicApiSettingsError(f"Set {', '.join(missing)}.")
        values["api_url"] = values["api_url"].rstrip("/")
        # Accept "tenant.uk.auth0.com", with or without https:// and a trailing slash.
        values["token_endpoint_host"] = (
            values["token_endpoint_host"].removeprefix("https://").rstrip("/")
        )
        return cls(**values)


class PublicApiTokenProvider:
    """Gives out one cached access token per client; thread-safe within a process."""

    def __init__(
        self,
        settings: PublicApiSettings,
        shared_store: MutableMapping[str, Any] | None = None,
        clock: Callable[[], float] = time.time,
        opener: Any = NO_REDIRECT_OPENER,
    ) -> None:
        self.settings = settings
        self.shared_store = shared_store
        self.clock = clock
        self.opener = opener
        # The client secret is not part of the key, so it never reaches the store.
        self.cache_key = " ".join(
            ("public-api-token", settings.token_endpoint_host, settings.audience, settings.client_id)
        )
        self._remembered: dict[str, Any] | None = None
        self._lock = threading.Lock()

    def access_token(self) -> str:
        with self._lock:
            if self._is_usable(self._remembered):
                return self._remembered["access_token"]
            shared_token = self._read_shared_token()
            if self._is_usable(shared_token):
                self._remembered = shared_token
                return shared_token["access_token"]
            self._remembered = self._request_token()
            self._write_shared_token(self._remembered)
            return self._remembered["access_token"]

    def forget(self, access_token: str) -> None:
        """Drops a token the Public API refused, so the next call gets a new one."""
        with self._lock:
            if self._remembered is not None and self._remembered["access_token"] == access_token:
                self._remembered = None
            shared_token = self._read_shared_token()
            if shared_token is not None and shared_token.get("access_token") == access_token:
                self._write_shared_token({"access_token": "", "refresh_at": 0})

    def _is_usable(self, token: dict[str, Any] | None) -> bool:
        return (
            isinstance(token, dict)
            and isinstance(token.get("access_token"), str)
            and bool(token["access_token"])
            and isinstance(token.get("refresh_at"), (int, float))
            and self.clock() < token["refresh_at"]
        )

    def _read_shared_token(self) -> dict[str, Any] | None:
        if self.shared_store is None:
            return None
        try:
            return self.shared_store.get(self.cache_key)
        except Exception as error:  # a store outage must not stop requests
            LOGGER.warning("Could not read the Public API token from the shared store: %s", error)
            return None

    def _write_shared_token(self, token: dict[str, Any]) -> None:
        if self.shared_store is None:
            return
        try:
            self.shared_store[self.cache_key] = token
        except Exception as error:
            LOGGER.warning("Could not store the Public API token in the shared store: %s", error)

    def _request_token(self) -> dict[str, Any]:
        request = urllib.request.Request(
            f"https://{self.settings.token_endpoint_host}/oauth/token",
            data=json.dumps(
                {
                    "grant_type": "client_credentials",
                    "client_id": self.settings.client_id,
                    "client_secret": self.settings.client_secret,
                    "audience": self.settings.audience,
                }
            ).encode(),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with self.opener.open(request, timeout=TOKEN_REQUEST_TIMEOUT_SECONDS) as response:
                answer = json.loads(response.read())
        except urllib.error.HTTPError as error:
            # Auth0's "error" field is a fixed code such as "access_denied"; the
            # rest of the answer is not logged.
            try:
                error_code = json.loads(error.read()).get("error", "")
            except Exception:
                error_code = ""
            raise PublicApiTokenError(
                f"Auth0 refused the token request with HTTP {error.code} {error_code}".strip()
            ) from None
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            raise PublicApiTokenError(f"The Auth0 token request failed: {error}") from None

        access_token = answer.get("access_token")
        lifetime_seconds = answer.get("expires_in")
        if not isinstance(access_token, str) or not access_token or not isinstance(
            lifetime_seconds, (int, float)
        ) or lifetime_seconds <= 0:
            raise PublicApiTokenError("Auth0's answer has no access token or lifetime.")
        margin_seconds = min(TOKEN_REFRESH_MARGIN_SECONDS, lifetime_seconds / 2)
        return {
            "access_token": access_token,
            "refresh_at": self.clock() + lifetime_seconds - margin_seconds,
        }


def call_public_api(
    tokens: PublicApiTokenProvider,
    method: str,
    path: str,
    body: Any = None,
    *,
    opener: Any = None,
    timeout_seconds: float = PUBLIC_API_TIMEOUT_SECONDS,
) -> Any:
    """Sends one request with the server token and returns the parsed JSON answer.

    A 401 means the token was refused: it is dropped and the request is sent once
    more with a new token. A second 401 is raised, because the client is then not
    on the Public API's allow list for this environment, or its tenant or
    audience is wrong; asking Auth0 again would not help. Every other error is
    raised as urllib's HTTPError, with the status and the answer's body.
    """
    opener = tokens.opener if opener is None else opener
    data = None if body is None else json.dumps(body).encode()
    for attempt in (1, 2):
        access_token = tokens.access_token()
        headers = {"Accept": "application/json", "Authorization": f"Bearer {access_token}"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{tokens.settings.api_url}{path}", data=data, headers=headers, method=method
        )
        try:
            with opener.open(request, timeout=timeout_seconds) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            if error.code == 401 and attempt == 1:
                tokens.forget(access_token)
                continue
            raise
    raise AssertionError("unreachable")
