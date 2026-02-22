from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from copilot import CopilotClient
from parsers.index import parse_input
from templates.audit_prompt import AUDIT_GENERATION_PROMPT


@dataclass
class GenerateAuditOptions:
    model: str = "gpt-5"
    verbose: bool = False


async def generate_audit_report(input_file: str, output_file: str, options: GenerateAuditOptions | None = None) -> None:
    options = options or GenerateAuditOptions()
    model, verbose = options.model, options.verbose

    # 1. Parse input document (doc/excel/pdef/txt))
    # verbose: Logging for debugging and user feedback
    if verbose:
        print("📖 Parsing input document...")
    parsed = await parse_input(input_file)

    if verbose and parsed.kind == "text":
        print(f"   Extracted {len(parsed.text or '')} characters")
    if verbose and parsed.kind == "image":
        print("   Detected image input: will use Copilot attachments.")

    if verbose:
        print("🔐 Authenticating with GitHub Copilot...")

    # 2. Initialize Copilot client
    client = CopilotClient()
    try:
        try:
            await client.start()
        except Exception as e:
            msg = str(e).lower()
            # auth err
            if "not authenticated" in msg:
                raise RuntimeError("GitHub authentication required. Run: gh auth login") from e
            # subscription err
            if "subscription" in msg:
                raise RuntimeError("GitHub Copilot subscription required. Visit: https://github.com/features/copilot") from e
            raise

        if verbose:
            print(f"🤖 Creating session with model: {model}")

        # 3. Create a session and enable streaming for real-time output
        session = await client.create_session({"model": model, "streaming": True})

        print("✨ Generating audit report...\n")
        print("─" * 60)

        # asyncio Event to signal when generation is complete
        done = asyncio.Event()
        audit_chunks: list[str] = []

        # 4. Collect deltas for the audit report and detect when generation is complete
        def on_event(event):
            event_type = getattr(event.type, "value", str(event.type))

            if event_type == "assistant.message_delta":
                chunk = event.data.delta_content or ""
                print(chunk, end="", flush=True)
                audit_chunks.append(chunk)

            elif event_type == "session.idle":
                done.set()

        session.on(on_event)  # python SDK event and streaming delta [1](https://pypi.org/project/github-copilot-sdk/)[2](https://github.com/github/copilot-sdk/blob/main/docs/getting-started.md)

        # upload img as attachments
        if parsed.kind == "image":
            # img: attachments
            full_prompt = (
                f"{AUDIT_GENERATION_PROMPT}\n\n---\n\n"
                "Convert the attached image into a structured governance audit report.\n"
                "First, extract any readable text from the image. If parts are unreadable, say so.\n"
            )
            await session.send({
                "prompt": full_prompt,
                "attachments": parsed.attachments,  # SDK support img as attachements [1](https://pypi.org/project/github-copilot-sdk/)
            })
        else:
            # text: document_text
            full_prompt = (
                f"{AUDIT_GENERATION_PROMPT}\n\n---\n\n"
                "Convert the following document into a structured report:\n\n"
                f"{parsed.text}"
            )
            await session.send({"prompt": full_prompt})

        await done.wait()

        print("\n" + "─" * 60)

        if verbose:
            print("\n💾 Saving audit report to file...")

        Path(output_file).write_text("".join(audit_chunks), encoding="utf-8")

        await session.destroy()
    finally:
        await client.stop()