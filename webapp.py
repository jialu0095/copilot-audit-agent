# webapp.py
from __future__ import annotations

import sys
import uuid
import subprocess
from pathlib import Path

from flask import Flask, render_template, request, send_from_directory, abort
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

RUNS_DIR = BASE_DIR / "runs"
UPLOAD_DIR = RUNS_DIR / "uploads"
OUTPUT_DIR = RUNS_DIR / "outputs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT = {".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".txt"}

app = Flask(
    __name__,
    template_folder=str(WEB_DIR),  # ✅ Jinja2 template
)

# mas size 50MB
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXT


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/generate")
def generate():
    files = request.files.getlist("files")
    model = request.form.get("model", "gpt-5")
    verbose = request.form.get("verbose") == "on"

    if not files or all(f.filename == "" for f in files):
        return render_template("result.html", ok=False, error="No files uploaded")

    run_id = uuid.uuid4().hex
    run_upload_dir = UPLOAD_DIR / run_id
    run_output_dir = OUTPUT_DIR / run_id
    run_upload_dir.mkdir(parents=True, exist_ok=True)
    run_output_dir.mkdir(parents=True, exist_ok=True)

    per_file_outputs: list[Path] = []
    errors: list[str] = []

    # 1) 逐文件生成 md
    for f in files:
        if not f or not f.filename:
            continue

        filename = secure_filename(f.filename)
        if not allowed_file(filename):
            errors.append(f"{filename}: unsupported file type")
            continue

        in_path = run_upload_dir / filename
        f.save(in_path)

        out_md = run_output_dir / (Path(filename).stem + ".md")

        cmd = [
            sys.executable, str(BASE_DIR / "cli.py"),
            "--input", str(in_path),
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
        )

        if proc.returncode != 0:
            stderr_tail = (proc.stderr or "")[-2000:]
            errors.append(f"{filename}: CLI failed\n{stderr_tail}")
            continue

        per_file_outputs.append(out_md)

    if not per_file_outputs:
        return render_template("result.html", ok=False, error="All files failed", errors=errors)

    # 2) merge into report.md
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

    return render_template(
        "result.html",
        ok=True,
        run_id=run_id,
        download_url=f"/download/{run_id}/report.md",
        errors=errors,
    )


@app.get("/download/<run_id>/<path:filename>")
def download(run_id: str, filename: str):
    run_output_dir = OUTPUT_DIR / run_id
    if not run_output_dir.exists():
        abort(404)
    return send_from_directory(run_output_dir, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)