import os
import re
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from notion_client import Client as NotionClient
from google import genai
from google.genai import types as genai_types

# 1. Load variables from .env before doing anything else
load_dotenv()

# 2. Configuration using the new google-genai SDK
gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
notion = NotionClient(auth=os.getenv("NOTION_TOKEN"))

# Slack App initialization
app = App(token=os.getenv("SLACK_BOT_TOKEN"))

def search_and_get_notion_data():
    """Searches for all accessible databases and aggregates their content."""
    print("[Notion] Searching for data sources...")
    search_results = notion.search(filter={"value": "data_source", "property": "object"}).get("results", [])  # type: ignore[union-attr]
    print(f"[Notion] Found {len(search_results)} data source(s)")

    if not search_results:
        return "No accessible databases found."

    all_context = ""
    for db in search_results:
        db_id = db["id"]
        title_list = db.get("title", [])
        db_title = title_list[0].get("plain_text", "Unnamed Database") if title_list else "Unnamed Database"
        print(f"[Notion] Querying database: '{db_title}' (id: {db_id})")
        all_context += f"\n--- Database: {db_title} ---\n"

        pages = notion.data_sources.query(data_source_id=db_id).get("results", [])  # type: ignore[union-attr]
        print(f"[Notion] Got {len(pages)} page(s) from '{db_title}'")
        for page in pages:
            props = page.get("properties", {})
            for prop_data in props.values():
                if prop_data.get("type") == "title":
                    titles = prop_data.get("title", [])
                    if titles:
                        all_context += f"- {titles[0]['plain_text']}\n"
    return all_context

def markdown_to_slack(text: str) -> str:
    """Convert Gemini markdown to Slack mrkdwn format."""
    # Bold: **text** -> *text*
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    # Italic: *text* or _text_ -> _text_ (after bold is handled)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'_\1_', text)
    # Strikethrough: ~~text~~ -> ~text~
    text = re.sub(r'~~(.+?)~~', r'~\1~', text)
    # Headers: ## Heading -> *Heading*
    text = re.sub(r'^#{1,6}\s+(.+)$', r'*\1*', text, flags=re.MULTILINE)
    # Inline code stays the same (`code`)
    # Code blocks: ```lang\n...\n``` -> ```\n...\n```
    text = re.sub(r'```\w*\n', '```\n', text)
    # Links: [text](url) -> <url|text>
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<\2|\1>', text)
    return text


notion_tool = genai_types.Tool(
    function_declarations=[
        genai_types.FunctionDeclaration(
            name="search_notion",
            description=(
                "Retrieves data from the user's Notion workspace databases. "
                "Call this tool ONLY when the user is asking about information that is likely stored in Notion, "
                "such as tasks, projects, notes, team info, schedules, or anything workspace-related. "
                "Do NOT call this for general conversation, greetings, or questions answerable from general knowledge."
            ),
            parameters=genai_types.Schema(type=genai_types.Type.OBJECT, properties={}),
        )
    ]
)
notion_tool_config = genai_types.GenerateContentConfig(tools=[notion_tool])
google_search_config = genai_types.GenerateContentConfig(
    tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())]
)

@app.event("app_mention")
def handle_mention(event, say, client):
    user_query = event["text"]
    channel = event["channel"]
    thread_ts = event.get("thread_ts", event["ts"])
    print(f"[Slack] Received mention: {user_query}")

    # React with 👀 immediately
    client.reactions_add(channel=channel, name="eyes", timestamp=event["ts"])

    try:
        # Pass 1: function declarations only — decide if Notion is needed
        print("[Gemini] Pass 1 — checking if Notion lookup is needed...")
        response = gemini.models.generate_content(
            model='gemini-3.1-flash-lite-preview',
            contents=user_query,
            config=notion_tool_config,
        )

        tool_call = None
        candidates = response.candidates or []
        for part in (candidates[0].content.parts if candidates and candidates[0].content else []):  # type: ignore[union-attr]
            if hasattr(part, "function_call") and part.function_call and part.function_call.name == "search_notion":
                tool_call = part.function_call
                break

        if tool_call:
            print("[Gemini] Notion lookup triggered, fetching data...")
            notion_data = search_and_get_notion_data()
            context_prompt = (
                f"The user asked: {user_query}\n\n"
                f"Here is the relevant data from their Notion workspace:\n{notion_data}\n\n"
                "Answer the user's question using this data. If you need more detail than Notion provides, "
                "use Google Search to supplement."
            )
        else:
            print("[Gemini] No Notion needed, going straight to answer...")
            context_prompt = user_query

        # Pass 2: google_search only — generate the final answer
        print("[Gemini] Pass 2 — generating final answer...")
        final_response = gemini.models.generate_content(
            model='gemini-3.1-flash-lite-preview',
            contents=context_prompt,
            config=google_search_config,
        )
        print("[Gemini] Response received, sending to Slack")
        say(text=markdown_to_slack(final_response.text or ""), thread_ts=thread_ts)

    except Exception as e:
        say(text=f"Error: {str(e)}", thread_ts=thread_ts)

if __name__ == "__main__":
    # Start the handler
    handler = SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN"))
    handler.start()