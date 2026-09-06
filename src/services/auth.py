from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, Header, HTTPException
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from src.core.config import settings
from src.db.session import get_db
from src.models.security import DataWorkspace, WorkspaceMembership


@dataclass(frozen=True)
class RequestIdentity:
    identity_tenant_id: str
    subject: str
    provider: str
    email: str | None = None


@dataclass(frozen=True)
class AuthorizedWorkspace:
    workspace_id: str
    identity: RequestIdentity
    role: str


ROLE_PERMISSIONS = {
    "owner": {
        "document.ingest",
        "document.read",
        "ingestion.retry",
        "operations.read",
        "review.write",
        "member.manage",
    },
    "operator": {"document.ingest", "document.read", "ingestion.retry"},
    "reviewer": {"document.read", "review.write"},
    "viewer": {"document.read"},
}


@lru_cache(maxsize=4)
def _jwks_client(tenant_id: str) -> PyJWKClient:
    return PyJWKClient(
        f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys",
        cache_keys=True,
    )


def identity_from_claims(claims: dict, expected_tenant_id: str) -> RequestIdentity:
    identity_tenant_id = str(claims.get("tid") or "")
    subject = str(claims.get("oid") or "")
    if identity_tenant_id != expected_tenant_id or not subject:
        raise HTTPException(status_code=401, detail={"code": "invalid_identity_claims"})
    return RequestIdentity(
        identity_tenant_id=identity_tenant_id,
        subject=subject,
        provider="entra",
        email=claims.get("preferred_username") or claims.get("email"),
    )


def _entra_identity(authorization: str | None) -> RequestIdentity:
    if not settings.ENTRA_TENANT_ID or not settings.ENTRA_API_CLIENT_ID:
        raise HTTPException(status_code=503, detail={"code": "entra_not_configured"})
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail={"code": "authentication_required"})
    try:
        signing_key = _jwks_client(settings.ENTRA_TENANT_ID).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.ENTRA_API_CLIENT_ID,
            issuer=f"https://login.microsoftonline.com/{settings.ENTRA_TENANT_ID}/v2.0",
            options={"require": ["aud", "exp", "iss", "tid", "oid"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail={"code": "invalid_access_token"}) from exc
    return identity_from_claims(claims, settings.ENTRA_TENANT_ID)


def authenticate_identity(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> RequestIdentity:
    mode = settings.AUTH_MODE.strip().lower()
    if mode == "entra":
        return _entra_identity(authorization)
    if mode == "development":
        subject = (x_user_id or "").strip()
        if not subject:
            raise HTTPException(status_code=401, detail={"code": "development_identity_required"})
        return RequestIdentity(
            identity_tenant_id="local",
            subject=subject,
            provider="development",
        )
    raise HTTPException(status_code=503, detail={"code": "unsupported_auth_mode"})


def require_workspace_permission(permission: str):
    def authorize(
        workspace_id: str = Header(..., alias="X-Tenant-ID"),
        identity: RequestIdentity = Depends(authenticate_identity),
        db: Session = Depends(get_db),
    ) -> AuthorizedWorkspace:
        normalized_workspace = workspace_id.strip()
        workspace = (
            db.query(DataWorkspace)
            .filter(
                DataWorkspace.workspace_id == normalized_workspace,
                DataWorkspace.status == "active",
            )
            .first()
        )
        membership = (
            db.query(WorkspaceMembership)
            .filter(
                WorkspaceMembership.workspace_id == normalized_workspace,
                WorkspaceMembership.identity_tenant_id == identity.identity_tenant_id,
                WorkspaceMembership.identity_subject == identity.subject,
                WorkspaceMembership.status == "active",
            )
            .first()
        )
        if workspace is None or membership is None:
            raise HTTPException(status_code=403, detail={"code": "workspace_access_denied"})
        if permission not in ROLE_PERMISSIONS.get(membership.role, set()):
            raise HTTPException(status_code=403, detail={"code": "permission_denied"})
        return AuthorizedWorkspace(
            workspace_id=normalized_workspace,
            identity=identity,
            role=membership.role,
        )

    return authorize
