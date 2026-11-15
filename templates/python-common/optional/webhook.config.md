## Webhook notification (opt-in)

Added when the project was scaffolded with the webhook notifier. The platform (Slack or
Teams) is detected from the URL, and the message fires only when `ENV` is a production value.
Leave `WEBHOOK_URL` empty to opt out: a no-op notifier is used and nothing is sent.

| Variable | In .env.example | Read when | Required | Default | Example | Notes |
|---|---|---|---|---|---|---|
| `WEBHOOK_URL` | yes | `ENV` is a production value | no | empty (opted out) | `https://hooks.slack.com/services/T000/B000/XXXX` | Incoming-webhook URL. Never commit a real value: this file ships as `.env.example` too. |
