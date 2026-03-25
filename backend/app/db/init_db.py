from __future__ import annotations

import asyncio

from passlib.context import CryptContext
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models import User, Workflow

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


async def seed_workflows() -> None:
    async with AsyncSessionLocal() as session:
        existing = await session.execute(select(Workflow))
        existing_workflows = {workflow.slug: workflow for workflow in existing.scalars().all()}

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

        created_any = False

        for workflow in workflows_to_create:
            if workflow.slug not in existing_workflows:
                session.add(workflow)
                created_any = True

        if created_any:
            await session.commit()


async def seed_admin_user() -> None:
    async with AsyncSessionLocal() as session:
        admin_email = "admin@autopilot.local"

        result = await session.execute(
            select(User).where(User.email == admin_email)
        )
        existing_admin = result.scalar_one_or_none()

        if existing_admin is None:
            admin_user = User(
                email=admin_email,
                hashed_password=hash_password("admin123456"),
                full_name="AutoPilot Admin",
                role="admin",
                is_active=True,
            )
            session.add(admin_user)
            await session.commit()


async def init_db() -> None:
    await seed_workflows()
    await seed_admin_user()
    print("Seed data completed.")


if __name__ == "__main__":
    asyncio.run(init_db())