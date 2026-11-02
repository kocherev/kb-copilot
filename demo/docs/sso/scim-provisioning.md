# SCIM user provisioning

SCIM keeps your Northstar Desk team in sync with your identity provider. It is available on the Enterprise plan and works alongside SAML single sign-on.

## Generate a token

An Admin opens Settings > Security > SCIM provisioning and chooses Generate token. The token is shown only once, so copy it straight into your identity provider. It stays valid until you revoke it. Generating a new token revokes the old one.

## Connection details

The SCIM base URL is https://api.northstardesk.example/scim/v2. Your identity provider uses it with the token as a bearer credential.

## What SCIM can do

SCIM can create users, update their names and email addresses, and deactivate them. Group push is supported, and each group can be mapped to a role such as Agent or Light agent.

## Deactivating people

When you deactivate or unassign someone in your identity provider, Northstar Desk suspends that person within 5 minutes. A suspended person cannot sign in, and their seat becomes free for someone else. Their tickets and notes stay in the workspace. Reactivating the person in your identity provider restores their access with the same role.
