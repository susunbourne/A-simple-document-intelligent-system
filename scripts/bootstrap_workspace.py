import argparse

from src.db.database import SessionLocal
from src.models.security import DataWorkspace, WorkspaceMembership


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a data workspace and its first owner membership."
    )
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--identity-tenant", required=True)
    parser.add_argument("--identity-subject", required=True)
    args = parser.parse_args()

    with SessionLocal() as db:
        workspace = db.get(DataWorkspace, args.workspace)
        if workspace is None:
            workspace = DataWorkspace(
                workspace_id=args.workspace,
                display_name=args.display_name,
                status="active",
            )
            db.add(workspace)
            db.flush()
        membership = (
            db.query(WorkspaceMembership)
            .filter(
                WorkspaceMembership.workspace_id == args.workspace,
                WorkspaceMembership.identity_tenant_id == args.identity_tenant,
                WorkspaceMembership.identity_subject == args.identity_subject,
            )
            .first()
        )
        if membership is None:
            db.add(
                WorkspaceMembership(
                    workspace_id=args.workspace,
                    identity_tenant_id=args.identity_tenant,
                    identity_subject=args.identity_subject,
                    role="owner",
                    status="active",
                )
            )
        else:
            membership.role = "owner"
            membership.status = "active"
        db.commit()
    print(f"workspace={args.workspace} owner={args.identity_subject} status=active")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
