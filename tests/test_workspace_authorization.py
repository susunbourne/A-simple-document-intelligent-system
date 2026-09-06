import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.database import Base
from src.models.security import DataWorkspace, WorkspaceMembership
from src.services.auth import (
    RequestIdentity,
    identity_from_claims,
    require_workspace_permission,
)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add_all(
        [
            DataWorkspace(workspace_id="finance", display_name="Finance"),
            DataWorkspace(workspace_id="legal", display_name="Legal"),
            WorkspaceMembership(
                workspace_id="finance",
                identity_tenant_id="entra-tenant",
                identity_subject="owner-oid",
                role="owner",
                status="active",
            ),
            WorkspaceMembership(
                workspace_id="finance",
                identity_tenant_id="entra-tenant",
                identity_subject="reviewer-oid",
                role="reviewer",
                status="active",
            ),
        ]
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()


def test_entra_claims_require_expected_tenant_and_object_id():
    identity = identity_from_claims(
        {"tid": "entra-tenant", "oid": "user-oid", "preferred_username": "user@example.edu"},
        "entra-tenant",
    )

    assert identity.subject == "user-oid"
    assert identity.email == "user@example.edu"
    with pytest.raises(HTTPException) as exc_info:
        identity_from_claims({"tid": "other", "oid": "user-oid"}, "entra-tenant")
    assert exc_info.value.status_code == 401


def test_owner_can_ingest_only_in_a_workspace_with_active_membership(db):
    authorize = require_workspace_permission("document.ingest")
    owner = RequestIdentity("entra-tenant", "owner-oid", "entra")

    access = authorize(workspace_id="finance", identity=owner, db=db)
    assert access.workspace_id == "finance"
    assert access.role == "owner"

    with pytest.raises(HTTPException) as exc_info:
        authorize(workspace_id="legal", identity=owner, db=db)
    assert exc_info.value.status_code == 403


def test_reviewer_can_read_but_cannot_submit_documents(db):
    reviewer = RequestIdentity("entra-tenant", "reviewer-oid", "entra")
    read_access = require_workspace_permission("document.read")(
        workspace_id="finance",
        identity=reviewer,
        db=db,
    )

    assert read_access.role == "reviewer"
    with pytest.raises(HTTPException) as exc_info:
        require_workspace_permission("document.ingest")(
            workspace_id="finance",
            identity=reviewer,
            db=db,
        )
    assert exc_info.value.detail["code"] == "permission_denied"
