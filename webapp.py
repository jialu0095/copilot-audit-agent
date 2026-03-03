# webapp.py
from __future__ import annotations

import sys
import uuid
import subprocess
import tempfile
import os
import time
from pathlib import Path

from flask import Flask, render_template, request, send_from_directory, abort
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

RUNS_DIR = BASE_DIR / "runs"
OUTPUT_DIR = RUNS_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT = {".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".txt"}

app = Flask(__name__, template_folder=str(WEB_DIR))
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

env = os.environ.copy()
env["PYTHONUTF8"] = "1"          # force UTF-8 encoding
env["PYTHONIOENCODING"] = "utf-8" # force stdin/stdout/stderr use UTF-8 encoding

# Allowed file types for upload
def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXT

# get: render upload form
@app.get("/")
def index():
    return render_template("index.html")

# post: handle file upload and trigger audit generation
@app.post("/generate")
def generate():
    # params
    files = request.files.getlist("files")
    model = request.form.get("model", "gpt-5")
    verbose = request.form.get("verbose") == "on"

    if not files or all(f.filename == "" for f in files):
        return render_template("result.html", ok=False, error="No files uploaded")

    # run_id to isolate executions outputs
    run_id = uuid.uuid4().hex
    run_output_dir = OUTPUT_DIR / run_id
    run_output_dir.mkdir(parents=True, exist_ok=True)

    # tmp storage for per-file outputs and errors
    per_file_outputs: list[Path] = []
    errors: list[str] = []

    # process each uploaded file
    for f in files:
        if not f or not f.filename:
            continue
        
        # validate file type
        filename = secure_filename(f.filename)
        if not allowed_file(filename):
            errors.append(f"{filename}: unsupported file type")
            continue
        # output path    
        suffix = Path(filename).suffix.lower()
        out_md = run_output_dir / (Path(filename).stem + ".md")

        tmp_path = None
        try:
            # 1) upload file to a temp location (streaming to handle large files without loading into memory)
            with tempfile.NamedTemporaryFile(prefix="upload_", suffix=suffix, delete=False) as tmp:
                tmp_path = tmp.name
                # stream copy to temp file
                f.stream.seek(0)
                while True:
                    chunk = f.stream.read(1024 * 1024)  # 1MB chunk
                    if not chunk:
                        break
                    tmp.write(chunk)

            # 2) run CLI for uploaded file
            cmd = [
                sys.executable, str(BASE_DIR / "cli.py"),
                "--input", str(tmp_path),
                "--output", str(out_md),
                "--model", model,
            ]
            if verbose:
                cmd.append("--verbose")

            proc = subprocess.run(
                cmd,
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",   # subprocess utf-8 encoding
                errors="replace",   # in case encoding issues
                env=env,
            )

            if proc.returncode != 0:
                stdout_tail = (proc.stdout or "")[-4000:]
                stderr_tail = (proc.stderr or "")[-4000:]
                errors.append(
                    f"{filename}: CLI failed (code={proc.returncode})\n\n"
                    f"--- stdout (tail) ---\n{stdout_tail}\n\n"
                    f"--- stderr (tail) ---\n{stderr_tail}\n"
                )
                continue

            # wait for output file to be created (since CLI writes asynchronously), with timeout
            for _ in range(10):           # for 10 seconds
                if out_md.exists() and out_md.stat().st_size > 0:
                    break
                time.sleep(0.1)

            if not out_md.exists():
                produced = "\n".join([p.name for p in run_output_dir.glob("*")]) or "(none)"
                errors.append(
                    f"{filename}: CLI returned success but output not found\n"
                    f"Expected: {out_md}\n"
                    f"Directory listing:\n{produced}\n"
                    f"--- stdout (tail) ---\n{(proc.stdout or '')[-2000:]}\n"
                    f"--- stderr (tail) ---\n{(proc.stderr or '')[-2000:]}\n"
                )
                continue

            if out_md.stat().st_size == 0:
                errors.append(f"{filename}: output markdown is empty: {out_md}")
                continue

            per_file_outputs.append(out_md)


        finally:
            # 3) cleanup tmp file
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    # debug info
    print("DEBUG outputs:", list(run_output_dir.glob("*.md")))
    print("DEBUG errors:", errors)
    if not per_file_outputs:
        return render_template("result.html", ok=False, error="All files failed", errors=errors)

    # merge report.md
    report_path = run_output_dir / "report.md"
    sections: list[str] = []

    for md_path in per_file_outputs:
        try:
            content = md_path.read_text(encoding="utf-8")
        except Exception:
            content = md_path.read_text(encoding="latin-1")

        sections.append(f"\n\n---\n\n# Source: {md_path.stem}\n\n")
        sections.append(content.strip() + "\n")

    report_path.write_text("".join(sections).lstrip(), encoding="utf-8")

    # render result page with download link
    return render_template(
        "result.html",
        ok=True,
        run_id=run_id,
        download_url=f"/download/{run_id}/report.md",
        errors=errors,
    )

# download endpoint for generated report
@app.get("/download/<run_id>/<path:filename>")
def download(run_id: str, filename: str):
    run_output_dir = OUTPUT_DIR / run_id
    if not run_output_dir.exists():
        abort(404)
    return send_from_directory(run_output_dir, filename, as_attachment=True)
# err handle
@app.get("/.well-known/appspecific/<path:anything>")
def well_known_appspecific(anything: str):
    return ("", 204)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)