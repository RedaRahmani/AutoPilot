from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password, normalize_email
from app.db.session import AsyncSessionLocal
from app.models import User, Workflow

settings = get_settings()


async def seed_workflows() -> int:
    async with AsyncSessionLocal() as session:
        existing = await session.execute(select(Workflow))
        existing_workflows = {
            workflow.slug: workflow for workflow in existing.scalars().all()
        }

        workflows_to_create = [
            Workflow(
                name="Invoice Processing",
                slug="invoice_processing",
                description="Extract invoice fields from uploaded documents.",
                is_active=True,
                config={
                    "document_type": "invoice",
                    "required_fields": [
                        "invoice_number",
                        "supplier_name",
                        "issue_date",
                        "due_date",
                        "total_amount",
                    ],
                    "confidence_threshold": 0.80,
                },
            ),
            Workflow(
                name="Request Triage",
                slug="request_triage",
                description="Classify and route incoming business requests.",
                is_active=True,
                config={
                    "document_type": "request",
                    "categories": ["billing", "support", "legal", "other"],
                    "confidence_threshold": 0.75,
                },
            ),
        ]

        created_count = 0

        for workflow in workflows_to_create:
            if workflow.slug not in existing_workflows:
                session.add(workflow)
                created_count += 1

        if created_count:
            await session.commit()

        return created_count


async def seed_admin_user() -> bool:
    admin_email = normalize_email(settings.seed_admin_email)
    admin_password = settings.seed_admin_password

    if not admin_password:
        raise RuntimeError(
            "SEED_ADMIN_PASSWORD is required to seed the initial admin user."
        )

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == admin_email))
        existing_admin = result.scalar_one_or_none()

        if existing_admin is None:
            admin_user = User(
                email=admin_email,
                hashed_password=hash_password(admin_password),
                full_name="AutoPilot Admin",
                role="admin",
                is_active=True,
            )
            session.add(admin_user)
            await session.commit()
            return True

        return False


async def init_db() -> None:
    workflow_count = await seed_workflows()
    admin_created = await seed_admin_user()

    print(f"Workflow seed completed. Added {workflow_count} workflow(s).")
    if admin_created:
        print("Admin seed completed. Created the initial admin user.")
    else:
        print("Admin seed completed. Initial admin user already exists.")


if __name__ == "__main__":
    asyncio.run(init_db())
