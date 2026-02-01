import asyncio
import uuid
from datetime import datetime

from backend.app.infrastructure.database import get_db_session
from backend.app.domains.template.models import Template
from backend.app.domains.template.repository import TemplateRepository
from backend.app.domains.document.models import Document
from backend.app.domains.document.repository import DocumentRepository
from backend.app.domains.audit.repository import AuditRepository
from backend.app.domains.audit.models import AuditLog

async def verify_persistence():
    print("Starting persistence verification...")
    async for session in get_db_session():
        try:
            # 1. Template CRUD
            template_repo = TemplateRepository(session)
            template = Template(name=f"Test Template {uuid.uuid4()}")
            created_tmpl = await template_repo.create(template)
            print(f"Created Template: {created_tmpl.id}")

            fetched_tmpl = await template_repo.get_by_id(created_tmpl.id)
            assert fetched_tmpl is not None
            assert fetched_tmpl.name == template.name
            print("Verified Template retrieval")

            # 2. Audit Log
            audit_repo = AuditRepository(session)
            log = AuditLog(
                entity_type="TEMPLATE",
                entity_id=created_tmpl.id,
                action="TEST_CREATE",
                metadata_={"test": True}
            )
            await audit_repo.create(log)
            print("Created Audit Log")
            
            # Commit to ensure persistence
            await session.commit()
            print("Committed transaction")
            
        except Exception as e:
            print(f"Verification failed: {e}")
            await session.rollback()
            raise
        finally:
            # Cleanup (Optional, but good for local dev DB)
            # await template_repo.delete(fetched_tmpl)
            pass

if __name__ == "__main__":
    asyncio.run(verify_persistence())
