import json
import os
from anthropic import Anthropic

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """You review pull requests for risk before a human reviewer looks at them.

Given a PR's title, changed files, and diff, decide the following. Score each one independently — a change can be security_sensitive without being a breaking_change, and vice versa. Do not let one flag influence another.

- breaking_change: true ONLY if this changes the behavior of an existing function, API, schema, or config key that other code already depends on. A brand new function, file, or endpoint that nothing else currently calls is NOT a breaking change, even if it looks risky for other reasons — that belongs under security_sensitive instead.
- security_sensitive: does this touch authentication, authorization, permissions, secrets, or user data handling?
- test_coverage_gap: did source code change without any corresponding test file changing?

If any flag above is true, also suggest a specific, concrete fix — something a reviewer could actually act on (e.g. "restore the original check: `return user.role == 'admin'`"), not a vague suggestion like "add validation." If nothing was flagged, set this to null.

Respond with ONLY a JSON object, no other text, in this exact shape:
{
  "breaking_change": true or false,
  "security_sensitive": true or false,
  "test_coverage_gap": true or false,
  "reasoning": "one or two sentences explaining the flags above",
  "suggested_fix": "a specific fix, or null if nothing was flagged"
}
"""


class RiskClassifier:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("No Anthropic API key found. Set ANTHROPIC_API_KEY in your local .env file.")
        self.client = Anthropic(api_key=self.api_key)

    def classify(self, title: str, files: list[dict], diff: str) -> dict:
        file_list = "\n".join(f"- {f['filename']} ({f['status']})" for f in files)

        user_message = f"""PR Title: {title}

Changed files:
{file_list}

Diff:
{diff}"""

        response = self.client.messages.create(
            model=MODEL,
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_text = None
        for block in response.content:
            if block.type == "text":
                raw_text = block.text
                break

        if raw_text is None:
            raise RuntimeError(
                f"Claude's response had no text content (stop_reason={response.stop_reason}). "
                "This can happen on an occasional bad response — try again."
            )

        raw_text = raw_text.strip()

        # Claude sometimes wraps JSON in ```json fences even when told not to,
        # so strip those off before parsing if they're there.
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`")
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Couldn't parse Claude's response as JSON: {e}\n\n"
                f"Raw response was:\n{raw_text}\n\n"
                f"stop_reason was: {response.stop_reason} "
                "(if this says 'max_tokens', the response got cut off before finishing)"
            ) from e
