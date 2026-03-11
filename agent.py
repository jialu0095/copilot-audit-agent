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
    prompt_text: str | None = None
    prompt_template_id: str | None = None


def _resolve_prompt(options: GenerateAuditOptions) -> str:
    """Resolve the final prompt text based on options and precedence.
    
    Precedence (highest to lowest):
    1. options.prompt_text (explicit custom prompt)
    2. options.prompt_template_id (selected template)
    3. default from templates/audit_prompt.py
    """
    # 1. Use explicit prompt text if provided
    if options.prompt_text:
        return options.prompt_text
    
    # 2. Try to load from template if provided
    if options.prompt_template_id:
        try:
            from prompt_store import get_store
            store = get_store()
            template = store.get_template(options.prompt_template_id)
            if template:
                return template.content
        except Exception:
            pass
    
    # 3. Fall back to default
    return AUDIT_GENERATION_PROMPT


async def generate_audit_report(input_file: str, output_file: str, options: GenerateAuditOptions | None = None) -> None:
    options = options or GenerateAuditOptions()
    model, verbose = options.model, options.verbose

    # Resolve the final prompt to use
    prompt = _resolve_prompt(options)

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
                f"{prompt}\n\n---\n\n"
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
                f"{prompt}\n\n---\n\n"
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


async def generate_audit_report_multi(
    input_files: list[str], output_file: str, options: GenerateAuditOptions | None = None
) -> None:
    """Analyze multiple files together and generate a single unified governance audit report."""
    options = options or GenerateAuditOptions()
    model, verbose = options.model, options.verbose

    # Resolve the final prompt to use
    prompt = _resolve_prompt(options)

    # Ensure output directory exists
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    # Stage 1: Extract text from each file
    if verbose:
        print("📖 Parsing input documents...")
    
    extracted = []
    for fp in input_files:
        if verbose:
            print(f"   Processing: {Path(fp).name}")
        parsed = await parse_input(fp)
        extracted.append({"file": Path(fp).name, "parsed": parsed})

    if verbose:
        total_chars = sum(len(p["parsed"].text or "") for p in extracted if p["parsed"].kind == "text")
        print(f"   Extracted {len(extracted)} files, {total_chars} total characters")

    if verbose:
        print("🔐 Authenticating with GitHub Copilot...")

    # Initialize Copilot client
    client = CopilotClient()
    try:
        try:
            await client.start()
        except Exception as e:
            msg = str(e).lower()
            if "not authenticated" in msg:
                raise RuntimeError("GitHub authentication required. Run: gh auth login") from e
            if "subscription" in msg:
                raise RuntimeError("GitHub Copilot subscription required. Visit: https://github.com/features/copilot") from e
            raise

        if verbose:
            print(f"🤖 Creating session with model: {model}")

        # Create a single session for multi-file synthesis
        session = await client.create_session({"model": model, "streaming": True})

        print("✨ Generating unified audit report...\n")
        print("─" * 60)

        # Collect output chunks
        done = asyncio.Event()
        audit_chunks: list[str] = []

        def on_event(event):
            event_type = getattr(event.type, "value", str(event.type))
            if event_type == "assistant.message_delta":
                chunk = event.data.delta_content or ""
                print(chunk, end="", flush=True)
                audit_chunks.append(chunk)
            elif event_type == "session.idle":
                done.set()

        session.on(on_event)

        # Build multi-file prompt for cross-file synthesis
        # Include file names and their content in a structured format
        file_contents_str = ""
        for item in extracted:
            fname = item["file"]
            parsed = item["parsed"]
            
            if parsed.kind == "image":
                file_contents_str += f"\n\n### File: {fname} (Image)\nNote: Image content will be processed as attachment.\n"
            else:
                content = parsed.text or "[No content extracted]"
                file_contents_str += f"\n\n### File: {fname}\n{content}\n"

        # Send request for multi-file synthesis
        has_images = any(item["parsed"].kind == "image" for item in extracted)
        
        if has_images:
            image_attachments = [
                item["parsed"].attachments[0] 
                for item in extracted 
                if item["parsed"].kind == "image" and item["parsed"].attachments
            ]
            if image_attachments:
                full_prompt = (
                    f"{prompt}\n\n---\n\n"
                    "You are analyzing multiple documents together as a unified audit.\n"
                    "The following documents and images have been provided for cross-file synthesis:\n"
                    f"{file_contents_str}\n\n"
                    "Generate a single comprehensive governance audit report that synthesizes findings across all input files."
                )
                await session.send({
                    "prompt": full_prompt,
                    "attachments": image_attachments,
                })
            else:
                full_prompt = (
                    f"{prompt}\n\n---\n\n"
                    "You are analyzing multiple documents together as a unified audit.\n"
                    "The following documents have been provided for cross-file synthesis:\n"
                    f"{file_contents_str}\n\n"
                    "Generate a single comprehensive governance audit report that synthesizes findings across all input files."
                )
                await session.send({"prompt": full_prompt})
        else:
            full_prompt = (
                f"{prompt}\n\n---\n\n"
                "You are analyzing multiple documents together as a unified audit.\n"
                "The following documents have been provided for cross-file synthesis:\n"
                f"{file_contents_str}\n\n"
                "Generate a single comprehensive governance audit report that synthesizes findings across all input files."
            )
            await session.send({"prompt": full_prompt})

        await done.wait()

        print("\n" + "─" * 60)

        if verbose:
            print("\n💾 Saving unified audit report to file...")

        Path(output_file).write_text("".join(audit_chunks), encoding="utf-8")

        await session.destroy()
    finally:
        await client.stop()