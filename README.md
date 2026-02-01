# bestarion-adk-example

## Prerequisites
Run local Jenkins for testing
```bash
docker run -d \
  --name jenkins \
  -p 8080:8080 \
  -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  jenkins/jenkins:lts
```

Getting Jenkins admin password
```bash
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

## Run Agent
```bash
adk web
```

## Telegram notifications (market_agent)

When `/analyze` is triggered (e.g. by Cloud Scheduler), market_agent can send a message to Telegram on success or failure.

1. **Create a bot:** In Telegram, message [@BotFather](https://t.me/BotFather), send `/newbot`, follow the steps, and copy the **bot token**.
2. **Get your chat ID:** Message your bot (or add it to a group), then open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and find `"chat":{"id": ...}`.
3. **Set env vars:** In `.env` (local) and in GitHub Secrets (Cloud Run): `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. If either is missing, notifications are skipped.