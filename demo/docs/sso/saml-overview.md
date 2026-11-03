# Single sign-on with SAML

Single sign-on lets your team sign in to Northstar Desk with your company identity provider. It is available on the Enterprise plan only.

## Supported identity providers

Northstar Desk supports SAML 2.0. We publish setup guides for Okta and Microsoft Entra ID. Google Workspace and any other identity provider that speaks SAML 2.0 also work with the generic settings below.

## Values you need

Open Settings > Security > Single sign-on to find two values for your identity provider. The ACS URL has the form https://auth.northstardesk.example/saml/acs/your-slug. The Entity ID has the form northstardesk:your-slug. The identity provider must send the user's email address as the NameID. First name and last name attributes are optional.

## Just-in-time provisioning

With just-in-time provisioning on, a person who is assigned to the app in your identity provider gets a Northstar Desk account at their first sign-in. New accounts get the default role you choose, either Agent or Light agent. Agent is the default. An Agent account still needs a free paid seat.

## Testing before you enforce

After you upload your identity provider metadata, use the Test connection button. It opens a sign-in in a new tab without changing anyone else's sign-in. Only enforce SSO after a test succeeds. The enforce SSO page explains what changes for your team.
