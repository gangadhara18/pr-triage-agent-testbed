import os
from anthropic import Anthropic

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """You summarize code changes (pull requests) for a busy software engineer who is about to review them.

Given a PR's title, description, and diff, write a short summary (2-4 sentences) that explains:
- What the change actually does
- Why it appears to be needed (based on the title/description, if that's informative)

Write in plain language. Do not restate the diff line-by-line. Do not use bullet points.
If the description is empty or unhelpful, rely on the diff itself to infer intent.
"""


class Summarizer:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

        if not self.api_key:
            raise ValueError(
                "No Anthropic API key found. Set ANTHROPIC_API_KEY in your "
                "local .env file before running this."
            )

        self.client = Anthropic(api_key=self.api_key)

    def summarize(self, title: str, body: str | None, diff: str) -> str:
        body_text = body if body else "(no description provided)"

        user_message = f"""PR Title: {title}

PR Description: {body_text}

Diff:
{diff}"""

        response = self.client.messages.create(
            model=MODEL,
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_message}
            ],
        )

        for block in response.content:
            if block.type == "text":
                return block.text

        raise RuntimeError(
            f"Claude's response had no text content (stop_reason={response.stop_reason}). "
            "This can happen on an occasional bad response — try again."
        )
