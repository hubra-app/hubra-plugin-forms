"""Celery task: remind members a day before a form closes."""

from __future__ import annotations

from hubra.core.modules import per_tenant_job
from hubra.core.tasks import celery_app

from . import services


@celery_app.task(name="hubra_forms.tasks.remind")
@per_tenant_job("forms")
def remind() -> int:
    from hubra.core.extensions import db

    sent = services.remind()
    db.session.commit()
    return sent
