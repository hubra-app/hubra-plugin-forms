"""Forms: the board builds a form, members fill it in.

A form has fields (short text, long text, number, date, one choice, several
choices, yes/no), is open to every member or to one group, and can close on
a date. Each member answers once and may change the answer while the form is
open. Anonymous forms never show who answered. Results: counts per choice,
averages for numbers, every answer as a table and as CSV; members see the
summary too when the form says so.

Permission:
    forms.forms.update   build forms and see every answer
"""

from hubra.core.modules import Blueprint, Module, NavItem, Schedule

module = Module(
    code="forms",
    name="Forms",
    description="Forms and surveys members fill in",
    default_enabled=False,
    depends_on=("members",),
    blueprints=(Blueprint("hubra_forms.routes", "forms_bp", "/api/v1/app/forms"),),
    nav=(NavItem("/app/forms", "shell.nav.forms", "forms", section="more", order=31),),
    tasks=("hubra_forms.tasks",),
    schedule=(Schedule("forms-remind-hourly", "hubra_forms.tasks.remind", 3600.0),),
    tables=("forms_forms", "forms_fields", "forms_responses"),
)
