# API keys

API keys let scripts and other tools call the Northstar Desk API on behalf of your workspace.

## Create a key

Admins create keys from Settings > API and choose Create key. Give the key a name that says where it is used. The full key is shown only once. If you lose it, revoke it and create a new one.

## Scopes

Each key has one scope. A read key can only read data. A write key can read and change tickets, contacts, and users. An admin key can also manage webhooks and read the audit log. Choose the smallest scope that works.

## Expiry

When you create a key, choose whether it expires after 30, 90, or 365 days, or never. Northstar Desk emails Admins 7 days before a key expires. A workspace can have up to 25 active keys.

## Who owns a key

Keys belong to the workspace, not to the person who created them. A key keeps working if the Admin who created it leaves. Revoke keys you no longer need from Settings > API.

## Keep keys secret

Never paste an API key into a ticket, a chat, or an email, including messages to Northstar support. Support will never ask for your key. If we find one of your keys in a public code repository, we revoke it automatically and email your Admins.
