# Troubleshoot sign-in problems

Use this page when someone cannot sign in to Northstar Desk.

## Too many attempts

After 5 failed attempts in a row, sign-in is locked for 15 minutes. Wait for the lock to end, then try again or reset the password.

## The reset link does not work

Reset links expire after 30 minutes, and only the newest link works. Request a new link and use it right away.

## SSO error: Audience mismatch

This error means the Entity ID set in your identity provider does not match the one in Northstar Desk. Copy the Entity ID again from Settings > Security > Single sign-on and paste it into the Audience URI or Identifier field.

## SSO error: User not assigned

This error means the person is not assigned to the Northstar Desk app in your identity provider. Assign them, or the group they belong to, and try again.

## Lost two-factor device

Use one of the backup codes saved during setup. If none are left, an Admin can reset two-factor authentication from Settings > Team. The Owner must contact support instead.

## Suspended account

People suspended through SCIM see a message that their account is suspended. Reactivate them in your identity provider.
