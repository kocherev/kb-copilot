# Audit log

The audit log records important actions in your workspace so you can review who changed what. It is available on the Enterprise plan.

## What is recorded

The log records sign-ins and failed sign-ins, role changes, security setting changes, API key creation and revocation, data exports, and changes to single sign-on. Each entry shows the person, the action, the time, and the IP address.

## Viewing the log

Admins open Settings > Security > Audit log. You can filter by person, action type, and date range.

## How long entries are kept

Audit log entries are kept for 1 year. Older entries are deleted automatically. If you need a longer record, export the log regularly.

## Exporting the log

Choose Export CSV on the audit log page to download the entries that match your current filters. You can also read entries with the API at /v2/audit-events, which needs a key with the admin scope.

## What is not recorded

Reading a ticket is not recorded in the audit log. Ticket changes, such as a new status or a reassignment, appear in the ticket's own history instead.
