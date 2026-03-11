# Frontend Bootstrap Refactor + Prompt UI Adjustment (Edit Only)

## ✅ Context (Already Complete — Do Not Rework Backend)
The multi-file combined analysis feature is already implemented and verified end-to-end:

- `cli.py`: supports repeatable `--input` flags, single batch run, Windows UTF-8 safety.
- `agent.py`: supports cross-file synthesis and outputs a single `report.md`.
- `webapp.py`: accepts multi-file upload, saves uploads to a temp directory, calls CLI **once** with repeated `--input`, cleans up temp files with `shutil.rmtree()`.

**This task is FRONTEND-ONLY.**  
Do **NOT** change the multi-file batch logic in `webapp.py`, `cli.py`, or `agent.py`, except a minimal static-folder wiring change if required.

---

## 🎯 Goals
1) Refactor the Web UI using **Bootstrap 5 (CDN)** — no npm, no bundlers, no build tools.
2) Remove any `<View Prompt>` UI. Keep **only** `<Edit Prompt>` button.
3) Split frontend into separate files:
   - `web/index.html` (template)
   - `web/result.html` (template)
   - `web/static/styles.css`
   - `web/static/app.js`
4) Improve UX for multi-file upload:
   - show selected file count + filename list
   - keep existing “Running…” (Generating...) state (no streaming logs)

---

## 🚫 Non-Goals
- No SSE/WebSocket/log streaming.
- No background tasks/queues.
- No redesign of backend routes or request contract.
- No per-file report generation — keep one combined `report.md`.

---

## ✅ Backend Contract Must Stay the Same
Form submission:
- `POST /generate`
- `enctype="multipart/form-data"`
- field names must remain:
  - files: `files` (multi upload)
  - model: `model`
  - verbose: `verbose`
- optional prompt override:
  - hidden field: `prompt_text` (only set if user edits prompt)

**Multi-file upload must be enabled:**
- `<input type="file" name="files" multiple required>`

---

## 🧩 UI Requirements (Bootstrap)

### A) Index Page Layout
Use Bootstrap components:
- `container`, `row`, `col`
- `card` for grouped sections
- `btn`, `btn-primary`, `btn-outline-secondary`
- `alert` for hints / notes

Sections on index page:
1) File uploader (multiple)
2) Model input
3) Verbose checkbox
4) Prompt section (Edit only)
5) Generate button
6) Running state panel (spinner)

---

### B) Multi-File Selection UX
When files selected:
- show “Selected N files”
- show list of filenames (truncate long names)
- show hint about allowed extensions:
  - `.pdf .docx .xlsx .png .jpg .jpeg .txt`
- show max upload size hint:
  - “Max total upload size: 50MB”

Implementation: JavaScript in `web/static/app.js`.

---

### C) Running State (Immediate Feedback)
On submit:
- disable submit button and form fields (prevent double submit)
- optionally visually dim/hide the form
- show a Bootstrap spinner area with text:
  - “Generating report… Please keep this page open. This may take a few minutes.”

No backend changes required (request remains synchronous).

---

### D) Prompt UI (Remove View Prompt, Keep Edit Prompt Modal)
**Remove `<View Prompt>` button/link completely.**

Keep only:
- Button: **Edit Prompt** (`btn btn-outline-secondary`)

Clicking Edit Prompt opens a **Bootstrap Modal** with:
- Title: “Edit Prompt”
- Large `<textarea>` (resizable vertically)
- Buttons:
  - “Use Prompt” (primary) — writes textarea content into hidden form input `prompt_text` and closes modal
  - “Cancel” — closes modal without updating hidden input

Hidden input in the form:
- `<input type="hidden" name="prompt_text" id="promptTextHidden">`

Default behavior:
- If user never edits prompt, `prompt_text` should remain empty/unset.
- Backend continues to use the default prompt as before.

> If a template dropdown already exists:
> - keep it (optional)
> - “Edit Prompt” loads the selected template content into the textarea
> - still no “View Prompt”

---

### E) Result Page UX (Bootstrap)
Refactor `web/result.html` with Bootstrap styling and clearer messaging.

**Success**
- Title: “Generation Result: Success”
- Primary button: download `report.md`
- If `errors` list is non-empty, show as “Warnings” (do not mark as failed)

**Failure**
- Title: “Generation Result: Failed”
- Show a short top-level `error` message
- Show `errors` details in a `<pre>` or collapsible element
- Provide “Back” button to `/`

**Important display rule:**
- Use `ok` as source of truth for success/failure.
- If `ok=True` and `errors` exist → show success + warnings.

---

## 🔌 Bootstrap CDN Requirements
Include Bootstrap via CDN in both templates:

- Bootstrap CSS (CDN)
- Bootstrap JS bundle (CDN) — required for modal
- Custom CSS: `/static/styles.css`
- Custom JS: `/static/app.js` (at least on index page)

**No npm, no bundlers, no build steps.**

---

## 🗂 Static Assets Serving (Minimal backend change allowed ONLY if needed)
If Flask is not serving `web/static/*` as `/static/*`, apply minimal change in `webapp.py`:

- Set `static_folder` to `WEB_DIR / "static"`
- `static_url_path="/static"`

Example intent (do not over-refactor):
- `Flask(__name__, template_folder=str(WEB_DIR), static_folder=str(WEB_DIR / "static"), static_url_path="/static")`

Only do this if CSS/JS cannot be loaded otherwise.

---

## ✅ Acceptance Criteria
- [ ] UI uses Bootstrap layout and components consistently
- [ ] File input supports multiple files
- [ ] Selected file count + filename list appear after selection
- [ ] Submit shows “Generating…” spinner immediately and disables form
- [ ] View Prompt removed everywhere
- [ ] Edit Prompt opens Bootstrap modal and saves text to hidden `prompt_text`
- [ ] Result page uses Bootstrap and shows correct state based on `ok`
- [ ] No regression to backend behavior: still single combined report.md

---

## 📦 Deliverables
- Update:
  - `web/index.html`
  - `web/result.html`
- Add:
  - `web/static/styles.css`
  - `web/static/app.js`
- Optional minimal update:
  - `webapp.py` static folder wiring only if necessary

---

## 🤖 Copilot Instruction
Implement this Bootstrap-based frontend refactor exactly as described:
- Remove “View Prompt”; keep only “Edit Prompt” modal
- Split HTML/CSS/JS into separate files under `web/` and `web/static/`
- Keep backend contract and multi-file batch behavior unchanged
- Use Bootstrap 5 CDN (no build tooling)
- Modify `webapp.py` only if static assets require it
``