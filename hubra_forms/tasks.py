"""Celery task: remind members a day before a form closes, and delete the
answers of members who are no longer in the club."""

from __future__ import annotations

from hubra.core.modules import per_tenant_job
from hubra.core.tasks import celery_app

from . import services


@celery_app.task(name="hubra_forms.tasks.remind")
@per_tenant_job("forms")
def remind() -> int:
    from hubra.core.extensions import db

    sent = services.remind()
    services.purge_orphans()
    db.session.commit()
    return sent
