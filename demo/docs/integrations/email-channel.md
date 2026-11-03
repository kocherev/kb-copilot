# Email channel settings

These settings control how Northstar Desk receives and sends email after your support address is connected.

## Sending domain

Until you verify your domain, replies are sent from slug@mail.northstardesk.example with your support address as the reply-to. To send replies from your own domain, open Settings > Channels > Email > Sending domain. Add the SPF include mail.northstardesk.example to your domain's SPF record and add the two DKIM CNAME records shown on the page. Verification usually completes within an hour of the DNS change.

## Attachment size

Attachments can be up to 25 MB per file, and a single email can be up to 40 MB in total. Inbound emails larger than 40 MB are rejected, and the sender gets a bounce message that explains the limit.

## Loop protection

Automatic replies between two systems can create an endless loop. If one sender address sends more than 20 messages to the same support address in one hour, Northstar Desk pauses new tickets from that sender. An Admin can resume the sender from Settings > Channels > Email > Paused senders.

## Signatures

Each support address can have its own signature. Agents can add a personal signature in their profile, which is placed above the address signature.
