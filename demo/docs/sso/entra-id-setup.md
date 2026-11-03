# Set up SSO with Microsoft Entra ID

This guide connects Microsoft Entra ID to Northstar Desk with SAML 2.0. You need the Enterprise plan.

## Create the enterprise application

In the Entra admin center, open Enterprise applications and choose New application, then Create your own application. Name it Northstar Desk and pick the option for an application not found in the gallery.

## Basic SAML configuration

Under Single sign-on, choose SAML. In Basic SAML Configuration, set the Identifier to the Entity ID from Northstar Desk and set the Reply URL to the ACS URL. Under Attributes and Claims, make sure the unique user identifier uses user.mail.

## Upload the metadata

Download the Federation Metadata XML file from the SAML certificates section. Upload it in Northstar Desk under Settings > Security > Single sign-on, then run Test connection.

## Certificate expiry

Entra signing certificates expire after 3 years by default. Northstar Desk emails every Admin 30 days before the identity provider certificate in your settings expires. When you renew the certificate in Entra, upload the new metadata file in Northstar Desk so sign-in keeps working.
