# webapp.py
from __future__ import annotations

import sys
import uuid
import subprocess
import tempfile
import os
import time
import shutil
from pathlib import Path

from flask import Flask, render_template, request, send_from_directory, abort, jsonify
from werkzeug.utils import secure_filename

from prompt_store import get_store
from ensure_static_files import ensure_static_files


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

RUNS_DIR = BASE_DIR / "runs"
OUTPUT_DIR = RUNS_DIR / "outputs"
TMP_DIR = RUNS_DIR / "tmp"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)

# Ensure static files exist
ensure_static_files()

ALLOWED_EXT = {".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".txt"}

app = Flask(__name__, template_folder=str(WEB_DIR), static_folder=str(WEB_DIR / "static"), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

env = os.environ.copy()
env["PYTHONUTF8"] = "1"          # force UTF-8 encoding
env["PYTHONIOENCODING"] = "utf-8" # force stdin/stdout/stderr use UTF-8 encoding

# Allowed file types for upload
def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXT

# get: render upload form with templates context
@app.get("/")
def index():
    store = get_store()
    templates = store.list_templates()
    template_list = [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "built_in": t.built_in,
        }
        for t in templates
    ]
    return render_template("index.html", prompt_templates=template_list)

# post: handle file upload and trigger audit generation
@app.post("/generate")
def generate():
    # params
    files = request.files.getlist("files")
    model = request.form.get("model", "gpt-5")
    verbose = request.form.get("verbose") == "on"
    prompt_template_id = request.form.get("prompt_template_id")
    prompt_text_override = request.form.get("prompt_text")

    if not files or all(f.filename == "" for f in files):
        return render_template("result.html", ok=False, error="No files uploaded")

    # run_id to isolate executions outputs
    run_id = uuid.uuid4().hex
    run_output_dir = OUTPUT_DIR / run_id
    run_tmp_dir = TMP_DIR / run_id
    run_tmp_dir.mkdir(parents=True, exist_ok=True)
    run_output_dir.mkdir(parents=True, exist_ok=True)

    input_paths: list[Path] = []
    errors: list[str] = []

    try:
        # 1) Save multiple uploaded files to temporary directory
        for f in files:
            if not f or not f.filename:
                continue
            
            filename = secure_filename(f.filename)
            if not allowed_file(filename):
                errors.append(f"{filename}: unsupported file type")
                continue
            
            # Create unique name to avoid conflicts
            unique_name = f"{uuid.uuid4().hex[:8]}__{filename}"
            tmp_path = run_tmp_dir / unique_name
            
            try:
                f.save(str(tmp_path))
                input_paths.append(tmp_path)
            except Exception as e:
                errors.append(f"{filename}: failed to save - {str(e)}")
                continue

        if not input_paths:
            return render_template("result.html", ok=False, error="No valid files to process", errors=errors)

        # 2) Handle prompt options and call CLI
        report_path = run_output_dir / "report.md"

        cmd = [sys.executable, str(BASE_DIR / "cli.py")]
        for p in input_paths:
            cmd += ["--input", str(p)]
        cmd += ["--output", str(report_path), "--model", model]
        
        # Handle prompt: prefer explicit text, then template id
        if prompt_text_override:
            # Write prompt to temp file (safer than command line)
            prompt_file = run_tmp_dir / "prompt.txt"
            prompt_file.write_text(prompt_text_override, encoding="utf-8")
            cmd += ["--prompt-file", str(prompt_file)]
        elif prompt_template_id and prompt_template_id != "default":
            cmd += ["--prompt-template", prompt_template_id]
        # else: use default (no --prompt-* flags)
        
        if verbose:
            cmd.append("--verbose")

        # Execute CLI command once for all files
        proc = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

        # Handle CLI execution errors
        if proc.returncode != 0:
            stdout_tail = (proc.stdout or "")[-4000:]
            stderr_tail = (proc.stderr or "")[-4000:]
            errors.append(
                f"CLI failed (code={proc.returncode})\n\n"
                f"--- stdout (tail) ---\n{stdout_tail}\n\n"
                f"--- stderr (tail) ---\n{stderr_tail}\n"
            )
            return render_template("result.html", ok=False, error="Generation failed", errors=errors)

        # Wait for output file with timeout (Windows disk write delay)
        for _ in range(10):
            if report_path.exists() and report_path.stat().st_size > 0:
                break
            time.sleep(0.1)

        # Verify output was created
        if not report_path.exists():
            errors.append("report.md was not created by CLI")
            return render_template("result.html", ok=False, error="Output file not created", errors=errors)

        if report_path.stat().st_size == 0:
            errors.append("report.md is empty")
            return render_template("result.html", ok=False, error="Output file is empty", errors=errors)

        # Render result page with download link
        return render_template(
            "result.html",
            ok=True,
            run_id=run_id,
            download_url=f"/download/{run_id}/report.md",
            errors=errors,
        )

    finally:
        # 3) Cleanup temporary upload directory (don't persist uploads)
        shutil.rmtree(run_tmp_dir, ignore_errors=True)

# download endpoint for generated report
@app.get("/download/<run_id>/<path:filename>")
def download(run_id: str, filename: str):
    run_output_dir = OUTPUT_DIR / run_id
    if not run_output_dir.exists():
        abort(404)
    return send_from_directory(run_output_dir, filename, as_attachment=True)

# Prompt template endpoints
@app.get("/prompts")
def list_prompts():
    """List all prompt templates."""
    store = get_store()
    templates = store.list_templates()
    return jsonify([
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "built_in": t.built_in,
        }
        for t in templates
    ])

@app.get("/prompts/<template_id>")
def get_prompt(template_id: str):
    """Get a single prompt template with full content."""
    store = get_store()
    template = store.get_template(template_id)
    
    if not template:
        return jsonify({"error": "Template not found"}), 404
    
    return jsonify({
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "content": template.content,
        "built_in": template.built_in,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    })

@app.post("/prompts")
def create_prompt():
    """Create a new prompt template."""
    data = request.get_json()
    name = data.get("name", "").strip()
    content = data.get("content", "").strip()
    description = data.get("description", "").strip()
    
    if not name or not content:
        return jsonify({"error": "name and content are required"}), 400
    
    store = get_store()
    template = store.create_template(name, content, description)
    
    return jsonify({
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "created_at": template.created_at,
    }), 201

@app.put("/prompts/<template_id>")
def update_prompt(template_id: str):
    """Update a prompt template."""
    if template_id == "default":
        return jsonify({"error": "Cannot modify default template"}), 403
    
    data = request.get_json()
    name = data.get("name")
    content = data.get("content")
    description = data.get("description")
    
    store = get_store()
    template = store.update_template(template_id, name, content, description)
    
    if not template:
        return jsonify({"error": "Template not found"}), 404
    
    return jsonify({
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "updated_at": template.updated_at,
    })

@app.delete("/prompts/<template_id>")
def delete_prompt(template_id: str):
    """Delete a prompt template."""
    if template_id == "default":
        return jsonify({"error": "Cannot delete default template"}), 403
    
    store = get_store()
    if store.delete_template(template_id):
        return jsonify({"ok": True})
    else:
        return jsonify({"error": "Template not found"}), 404

# err handle
@app.get("/.well-known/appspecific/<path:anything>")
def well_known_appspecific(anything: str):
    return ("", 204)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)