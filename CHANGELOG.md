# Forms

## Unreleased

- Security: an anonymous form that has answers can't be switched to named any more (that showed the board who answered what).
- Security: anonymous results and their CSV no longer show when each answer came in, nor the answers in the order they came, both of which could point to who gave them.
- Privacy: deleting a form deletes its answers too, and the hourly job deletes the answers of members who are no longer in the club. Club schemas have no cascading foreign keys, so these answers stayed in the database before.
- Changing, copying and exporting a form (CSV) are written to the audit log.
- A form title with characters outside ASCII no longer breaks the CSV download name.

## 1.1.0

- Gives the standard roles access when a club first switches it on (`role_defaults`, docs/roles.md in hubra-app/hubra): Mitglied Ansehen, Vorstand Bearbeiten, Aktuar/in Bearbeiten. Roles without access don't see it; their own data from it stays on their profile. Needs Hubra 0.2.5 or later.
- Dashboard widget **Auszufüllen**: open forms the member may fill in and hasn't yet, the ones closing first on top.

## 1.0.0

First version: forms with seven field kinds, open to every member or one
group, optional closing time, anonymous answers, public results, a reminder
the day before closing, and results as a summary, a table and a CSV.
