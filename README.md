# agent-brad

A Slack bot that uses Gemini AI with tool-calling to answer questions — pulling from your Notion workspace only when relevant.

## How it works

1. Mention the bot in Slack (`@agent-brad your question`)
2. The bot reacts with 👀 immediately
3. Gemini decides whether the question requires a Notion lookup or can be answered directly
4. If Notion is needed, all connected databases are queried and the results are fed back to Gemini
5. The answer is posted as a thread reply

## Setup

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/your-username/agent-brad.git
cd agent-brad
python3 -m venv .venv
source .venv/bin/activate
pip install slack-bolt notion-client google-genai python-dotenv
```

### 2. Environment variables

Create a `.env` file in the project root:

```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
NOTION_TOKEN=secret_...
GEMINI_API_KEY=...
```

### 3. Slack app configuration

In [api.slack.com/apps](https://api.slack.com/apps), your bot needs the following **Bot Token Scopes**:

- `app_mentions:read`
- `chat:write`
- `channels:history`
- `reactions:write`

Enable **Socket Mode** and create an **App-Level Token** with `connections:write` scope for `SLACK_APP_TOKEN`.

Under **Event Subscriptions**, subscribe to the `app_mention` bot event.

### 4. Notion integration

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations) and create an integration
2. Copy the **Internal Integration Token** → `NOTION_TOKEN`
3. Open each Notion database you want the bot to access → **...** menu → **Connect to** → select your integration

### 5. Run

```bash
python main.py
```

## Tech stack

- [Slack Bolt for Python](https://github.com/slackapi/bolt-python) — Slack event handling
- [notion-client](https://github.com/ramnes/notion-sdk-py) — Notion API
- [Google Gemini](https://ai.google.dev/) (`gemini-2.5-flash`) — LLM with function/tool calling
