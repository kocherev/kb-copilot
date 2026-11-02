# Enforce single sign-on

Enforcing SSO makes your identity provider the only way to sign in for everyone except the Owner.

## Before you turn it on

Run Test connection on the single sign-on settings page and make sure it succeeds. Check that everyone who needs access is assigned to the Northstar Desk app in your identity provider.

## Turn it on

In Settings > Security > Single sign-on, switch on Require SSO. Every session that was started with a password ends immediately, and those people must sign in again through your identity provider. Password reset is turned off for everyone except the Owner.

## The Owner's break-glass access

The Owner keeps the ability to sign in with a password. This break-glass access exists so you can still reach the workspace if your identity provider has an outage. If that happens, the Owner signs in with their password and can switch off Require SSO until the provider recovers.

## What is not affected

API keys keep working after SSO is enforced, because they do not use interactive sign-in. Webhooks and the Slack integration are not affected either.
