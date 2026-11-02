# Set up SSO with Okta

This guide connects Okta to Northstar Desk with SAML 2.0. You need the Enterprise plan and Admin access in both tools.

## Create the app in Okta

In the Okta admin console, go to Applications and create a new app integration. Choose SAML 2.0 as the sign-in method and name the app Northstar Desk.

## Fill in the SAML settings

Paste the ACS URL from Northstar Desk into the Single sign-on URL field. Paste the Entity ID into the Audience URI field. Set the Name ID format to EmailAddress and the application username to Email. Leave the default signature settings in place.

## Upload the metadata

When the Okta app is saved, download its identity provider metadata XML file. In Northstar Desk, open Settings > Security > Single sign-on, choose Upload metadata, and select the file.

## Assign people and test

Assign the people or groups who should use Northstar Desk to the Okta app. People who are not assigned see a "User not assigned" error at sign-in. Then use the Test connection button in Northstar Desk. A common mistake is a typo in the Audience URI, which shows up as an "Audience mismatch" error during the test.
