# Troubleshoot email delivery

Use this page when customer emails do not become tickets or your replies do not reach customers.

## Customer emails are not arriving

Check that the forwarding rule in your email provider is still on and points to your slug@inbound.northstardesk.example address. Check that the address shows as verified in Settings > Channels > Email. Some providers send forwarded mail to spam, so look in the spam folder of the support mailbox too.

## Some emails bounce

Emails larger than 40 MB in total are rejected, and the sender gets a bounce message. Ask the customer to share large files through a link instead.

## A sender's emails stopped

If one sender sent more than 20 messages in an hour, loop protection paused them. Resume the sender from Settings > Channels > Email > Paused senders.

## Replies land in spam

Replies are much more likely to reach the inbox once your sending domain is verified. Add the SPF include and both DKIM records from the sending domain page, then wait for verification to finish.

## The workspace is read-only

A read-only workspace holds new emails instead of turning them into tickets. Fix the payment method or pick a plan, and the held emails arrive as tickets.
