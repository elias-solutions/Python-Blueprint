from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

CHAT_ROLES = frozenset({"reader", "writer", "admin"})

KeyResolver = Callable[[str], Any]


@dataclass(frozen=True)
class User:
    subject: str
    name: str
    roles: frozenset[str]


class InvalidTokenError(Exception):
    pass


class KeysUnavailableError(Exception):
    pass


class TokenVerifier:
    def __init__(self, issuer: str, resolve_key: KeyResolver) -> None:
        self._issuer = issuer
        self._resolve_key = resolve_key

    def verify(self, token: str) -> User:
        try:
            claims = jwt.decode(
                token,
                self._resolve_key(token),
                algorithms=["RS256"],
                issuer=self._issuer,
                options={"verify_aud": False, "require": ["exp", "iss", "sub"]},
            )
        except jwt.PyJWKClientConnectionError as error:
            raise KeysUnavailableError(str(error)) from error
        except jwt.PyJWTError as error:
            raise InvalidTokenError(str(error)) from error
        return User(
            subject=claims["sub"],
            name=claims.get("preferred_username", claims["sub"]),
            roles=frozenset(claims.get("realm_access", {}).get("roles", [])),
        )


def jwks_key_resolver(jwks_url: str) -> KeyResolver:
    client = jwt.PyJWKClient(jwks_url, cache_keys=True)
    return lambda token: client.get_signing_key_from_jwt(token).key


_bearer = HTTPBearer(auto_error=False)


def get_verifier(request: Request) -> TokenVerifier:
    return request.app.state.verifier


def require_chat_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    verifier: Annotated[TokenVerifier, Depends(get_verifier)],
) -> User:
    if credentials is None:
        raise _unauthorized("Missing bearer token.")
    try:
        user = verifier.verify(credentials.credentials)
    except InvalidTokenError as error:
        raise _unauthorized(f"Invalid token: {error}") from error
    except KeysUnavailableError as error:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Token keys are not reachable."
        ) from error
    if not user.roles & CHAT_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The user may not use the chat.")
    return user


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"}
    )
