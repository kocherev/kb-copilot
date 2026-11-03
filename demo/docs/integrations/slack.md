# Slack integration

The Slack integration posts ticket alerts to Slack channels and lets your team create tickets from Slack messages. It is available on the Team and Enterprise plans.

## Connect Slack

An Admin opens Settings > Integrations > Slack and chooses Connect to Slack. If your Slack workspace requires approval for new apps, a Slack admin must approve the Northstar Desk app before the connection finishes.

## Notification rules

A notification rule posts a message to one channel when something happens, such as a new ticket, a ticket marked Urgent, or a missed SLA target. A workspace can have up to 20 notification rules. To post in a private channel, first invite the @Northstar bot to that channel.

## Create tickets from Slack

Use the message menu action Create ticket on any Slack message, or type /northstar ticket followed by a short description. The new ticket links back to the original Slack message.

## Thread replies

When your team replies in the Slack thread under a ticket alert, each reply is added to the ticket as an internal note. Thread replies are never sent to the customer. Only replies from people whose Slack email matches a Northstar Desk account are synced.

## Disconnect

Disconnecting Slack from Settings > Integrations > Slack removes all notification rules. Tickets created from Slack stay in Northstar Desk.
