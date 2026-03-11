// Governance Audit Generator - Index Page Scripts

// File management
let selectedFiles = [];
let promptTemplates = {};
let currentPromptContent = "";

const form = document.getElementById("genForm");
const running = document.getElementById("running");
const fileInput = document.getElementById("fileInput");
const fileList = document.getElementById("fileList");
const submitBtn = document.getElementById("submitBtn");

// Prompt modal elements
const promptModal = document.getElementById("promptModal");
const promptTemplateSelect = document.getElementById("promptTemplate");
const promptTextInput = document.getElementById("promptText");
const editPromptBtn = document.getElementById("editPromptBtn");
const modalClose = document.getElementById("modalClose");
const modalCancel = document.getElementById("modalCancel");
const modalPromptText = document.getElementById("modalPromptText");
const modalUsePrompt = document.getElementById("modalUsePrompt");

// Load templates on page load
async function loadTemplates() {
  try {
    const response = await fetch("/prompts");
    const templates = await response.json();
    
    // Store templates by id
    templates.forEach(t => {
      promptTemplates[t.id] = t;
      if (t.id !== "default") {
        const option = document.createElement("option");
        option.value = t.id;
        option.textContent = `📝 ${t.name}`;
        promptTemplateSelect.appendChild(option);
      }
    });
    
    // Load default template content
    await loadTemplateContent("default");
  } catch (error) {
    console.error("Failed to load templates:", error);
  }
}

async function loadTemplateContent(templateId) {
  try {
    const response = await fetch(`/prompts/${templateId}`);
    if (response.ok) {
      const template = await response.json();
      currentPromptContent = template.content;
    }
  } catch (error) {
    console.error("Failed to load template content:", error);
  }
}

// Handle template selection
promptTemplateSelect.addEventListener("change", async () => {
  const templateId = promptTemplateSelect.value;
  promptTextInput.value = "";  // Clear custom text when selecting template
  await loadTemplateContent(templateId);
});

// Modal handlers
editPromptBtn.addEventListener("click", (e) => {
  e.preventDefault();
  modalPromptText.value = currentPromptContent;
  promptModal.classList.add("show");
});

function closeModal() {
  promptModal.classList.remove("show");
}

modalClose.addEventListener("click", closeModal);
modalCancel.addEventListener("click", closeModal);

// Click outside modal to close
window.addEventListener("click", (e) => {
  if (e.target === promptModal) {
    closeModal();
  }
});

// Use prompt (save to hidden field)
modalUsePrompt.addEventListener("click", async () => {
  const customText = modalPromptText.value.trim();
  if (!customText) {
    alert("Please enter a prompt");
    return;
  }
  promptTextInput.value = customText;
  currentPromptContent = customText;
  closeModal();
});

// File management
fileInput.addEventListener("change", () => {
  if (fileInput.files.length > 0) {
    for (let file of fileInput.files) {
      const isDuplicate = selectedFiles.some(f => 
        f.name === file.name && f.size === file.size
      );
      if (!isDuplicate) {
        selectedFiles.push(file);
      }
    }
    fileInput.value = "";
  }
  updateFileList();
});

function updateFileList() {
  if (selectedFiles.length === 0) {
    fileList.style.display = "none";
    return;
  }

  fileList.style.display = "block";
  fileList.innerHTML = `<strong>${selectedFiles.length} file(s) selected:</strong>`;

  selectedFiles.forEach((file, index) => {
    const size = formatFileSize(file.size);
    const item = document.createElement("div");
    item.style.padding = "8px";
    item.style.marginTop = "6px";
    item.style.color = "#374151";
    item.style.display = "flex";
    item.style.justifyContent = "space-between";
    item.style.alignItems = "center";
    item.style.background = "white";
    item.style.borderRadius = "4px";
    item.style.border = "1px solid #e5e7eb";
    
    const fileInfo = document.createElement("span");
    fileInfo.style.flex = "1";
    fileInfo.style.wordBreak = "break-all";
    fileInfo.innerHTML = `📄 ${file.name} <span style="color: #999; font-size: 11px; margin-left: 8px;">${size}</span>`;
    
    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.innerHTML = "✕";
    removeBtn.style.marginLeft = "8px";
    removeBtn.style.padding = "4px 8px";
    removeBtn.style.background = "#fee2e2";
    removeBtn.style.color = "#991b1b";
    removeBtn.style.border = "1px solid #fecaca";
    removeBtn.style.borderRadius = "4px";
    removeBtn.style.cursor = "pointer";
    removeBtn.style.fontSize = "14px";
    removeBtn.style.fontWeight = "bold";
    removeBtn.style.whiteSpace = "nowrap";
    removeBtn.onclick = (e) => {
      e.preventDefault();
      removeFile(index);
    };
    removeBtn.onmouseover = () => {
      removeBtn.style.background = "#fecaca";
      removeBtn.style.color = "#7f1d1d";
    };
    removeBtn.onmouseout = () => {
      removeBtn.style.background = "#fee2e2";
      removeBtn.style.color = "#991b1b";
    };
    
    item.appendChild(fileInfo);
    item.appendChild(removeBtn);
    fileList.appendChild(item);
  });
}

function removeFile(index) {
  selectedFiles.splice(index, 1);
  updateFileList();
}

function formatFileSize(bytes) {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + " " + sizes[i];
}

// Form submission
form.addEventListener("submit", (e) => {
  e.preventDefault();
  
  if (selectedFiles.length === 0) {
    alert("Please select at least one file");
    return;
  }
  
  const formData = new FormData();
  selectedFiles.forEach((file) => {
    formData.append("files", file);
  });
  
  formData.append("model", document.querySelector("select[name='model']").value);
  formData.append("verbose", document.querySelector("input[name='verbose']").checked ? "on" : "off");
  
  // Add prompt fields
  const templateId = promptTemplateSelect.value;
  const customPrompt = promptTextInput.value.trim();
  
  if (customPrompt) {
    formData.append("prompt_text", customPrompt);
  } else if (templateId && templateId !== "default") {
    formData.append("prompt_template_id", templateId);
  }
  
  form.style.display = "none";
  running.style.display = "block";
  submitBtn.disabled = true;
  
  fetch("/generate", {
    method: "POST",
    body: formData
  })
  .then(response => response.text())
  .then(html => {
    document.open();
    document.write(html);
    document.close();
  })
  .catch(error => {
    console.error("Error:", error);
    alert("An error occurred: " + error.message);
    form.style.display = "block";
    running.style.display = "none";
    submitBtn.disabled = false;
  });
});

// Initialize on page load
window.addEventListener("DOMContentLoaded", loadTemplates);
