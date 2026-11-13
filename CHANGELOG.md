# Forms

## Unreleased

- Date, date-and-time and time fields use Hubra's date pickers: dd.mm.yyyy, a calendar that starts on Monday and 24-hour times, whatever the browser language; typed dates like 1.2.26 work too. Needs Hubra 0.2.6 or later.

## 1.2.0

- Security: an anonymous form that has answers can't be switched to named any more (that showed the board who answered what).
- Security: anonymous results and their CSV no longer show when each answer came in, nor the answers in the order they came, both of which could point to who gave them.
- Privacy: deleting a form deletes its answers too, and the hourly job deletes the answers of members who are no longer in the club. Club schemas have no cascading foreign keys, so these answers stayed in the database before.
- Every form needs a closing time, at most a year away. Closing a form by hand sets its closing time to now.
- Answers are deleted a year after their form closed (the form and its questions stay); the results page says when.
- "Members see the results" can't be switched on once a form has answers.
- Notifications follow the members' settings: a new form counts as a poll (`polls`), its reminder as a poll reminder (`poll_reminders`).
- Changing, copying and exporting a form (CSV) are written to the audit log.
- A form title with characters outside ASCII no longer breaks the CSV download name.

## 1.1.0

- Gives the standard roles access when a club first switches it on (`role_defaults`, docs/roles.md in hubra-app/hubra): Mitglied Ansehen, Vorstand Bearbeiten, Aktuar/in Bearbeiten. Roles without access don't see it; their own data from it stays on their profile. Needs Hubra 0.2.5 or later.
- Dashboard widget **Auszufüllen**: open forms the member may fill in and hasn't yet, the ones closing first on top.

## 1.0.0

First version: forms with seven field kinds, open to every member or one
group, optional closing time, anonymous answers, public results, a reminder
the day before closing, and results as a summary, a table and a CSV.
