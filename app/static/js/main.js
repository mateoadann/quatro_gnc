const flashMessages = document.querySelectorAll(".flash");
flashMessages.forEach((message) => {
  const closeBtn = message.querySelector(".flash__close");
  if (closeBtn) {
    closeBtn.addEventListener("click", () => {
      message.classList.add("dismissed");
      setTimeout(() => {
        message.remove();
      }, 250);
    });
  }
  if (message.classList.contains("persistent")) {
    return;
  }
  const delay = message.classList.contains("error") ? 12000 : 3500;
  setTimeout(() => {
    message.classList.add("dismissed");
    setTimeout(() => {
      message.remove();
    }, 250);
  }, delay);
});

const ensureToastStack = () => {
  let stack = document.querySelector("#toast-stack");
  if (!stack) {
    stack = document.createElement("div");
    stack.id = "toast-stack";
    stack.className = "toast-stack";
    document.body.appendChild(stack);
  }
  return stack;
};

const showToast = (message, type = "error", durationMs = 4200) => {
  const stack = ensureToastStack();
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  const text = document.createElement("div");
  text.className = "toast__text";
  text.textContent = message;
  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "toast__close";
  closeBtn.textContent = "\u00d7";
  closeBtn.addEventListener("click", () => {
    toast.remove();
  });
  toast.appendChild(text);
  toast.appendChild(closeBtn);
  stack.appendChild(toast);
  setTimeout(() => {
    toast.classList.add("toast--hide");
    setTimeout(() => {
      toast.remove();
    }, 200);
  }, durationMs);
};

const safeJson = async (response) => {
  const contentType = response.headers.get("content-type") || "";
  if (response.redirected) {
    window.location.href = response.url;
    throw new Error("Sesion expirada. Inicia sesion.");
  }
  if (!contentType.includes("application/json")) {
    const text = await response.text();
    if (text.toLowerCase().includes("<!doctype") || text.toLowerCase().includes("<html")) {
      window.location.href = "/login";
      throw new Error("Sesion expirada. Inicia sesion.");
    }
    throw new Error("Respuesta inesperada del servidor.");
  }
  return response.json();
};

const normalizedInputs = document.querySelectorAll(
  "input[data-uppercase='true'], input[data-strip='alnum']"
);
normalizedInputs.forEach((input) => {
  input.addEventListener("input", () => {
    const cursor = input.selectionStart;
    const rawValue = input.value;
    let nextValue = rawValue;

    if (input.dataset.strip === "alnum") {
      nextValue = nextValue.replace(/[^a-zA-Z0-9]/g, "");
    }

    if (input.dataset.uppercase === "true") {
      nextValue = nextValue.toUpperCase();
    }

    if (nextValue !== rawValue) {
      input.value = nextValue;
      if (cursor !== null) {
        let before = rawValue.slice(0, cursor);
        if (input.dataset.strip === "alnum") {
          before = before.replace(/[^a-zA-Z0-9]/g, "");
        }
        if (input.dataset.uppercase === "true") {
          before = before.toUpperCase();
        }
        input.setSelectionRange(before.length, before.length);
      }
    }
  });
});

const toggleButtons = document.querySelectorAll("[data-toggle-password]");
toggleButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const targetId = button.getAttribute("data-target");
    const target = targetId ? document.getElementById(targetId) : null;
    if (!target) {
      return;
    }
    const isPassword = target.type === "password";
    target.type = isPassword ? "text" : "password";
    button.classList.toggle("is-active", isPassword);
    button.setAttribute(
      "aria-label",
      isPassword ? "Ocultar contrase\u00f1a" : "Mostrar contrase\u00f1a"
    );
    button.setAttribute("aria-pressed", isPassword ? "true" : "false");
  });
});

const userCreateModal = document.querySelector("#user-create-modal");
const userCreateBtn = document.querySelector("#user-create-btn");
const userCreatePassword = document.querySelector("#user-create-password");
const userGeneratePassword = document.querySelector("#user-generate-password");
const userSaveModal = document.querySelector("#user-save-modal");
const userSaveConfirm = document.querySelector("#user-save-confirm");
const userActiveModal = document.querySelector("#user-active-modal");
const userActiveConfirm = document.querySelector("#user-active-confirm");
let pendingUserForm = null;
let pendingActiveToggle = null;
const metricsCard = document.querySelector("#metrics-card");

const openUserCreateModal = () => {
  if (!userCreateModal) {
    return;
  }
  userCreateModal.classList.add("is-open");
  userCreateModal.setAttribute("aria-hidden", "false");
  const firstInput = userCreateModal.querySelector("input[name='username']");
  if (firstInput) {
    firstInput.focus();
  }
};

const closeUserCreateModal = () => {
  if (!userCreateModal) {
    return;
  }
  userCreateModal.classList.remove("is-open");
  userCreateModal.setAttribute("aria-hidden", "true");
};

const openUserSaveModal = () => {
  if (!userSaveModal) {
    return;
  }
  userSaveModal.classList.add("is-open");
  userSaveModal.setAttribute("aria-hidden", "false");
};

const closeUserSaveModal = () => {
  if (!userSaveModal) {
    return;
  }
  userSaveModal.classList.remove("is-open");
  userSaveModal.setAttribute("aria-hidden", "true");
  pendingUserForm = null;
};

const openUserActiveModal = () => {
  if (!userActiveModal) {
    return;
  }
  userActiveModal.classList.add("is-open");
  userActiveModal.setAttribute("aria-hidden", "false");
};

const closeUserActiveModal = (clearPending = true) => {
  if (!userActiveModal) {
    return;
  }
  userActiveModal.classList.remove("is-open");
  userActiveModal.setAttribute("aria-hidden", "true");
  if (clearPending) {
    pendingActiveToggle = null;
  }
};

const generatePassword = () => {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
  const length = 12;
  let value = "";
  const bytes = new Uint8Array(length);
  if (window.crypto && window.crypto.getRandomValues) {
    window.crypto.getRandomValues(bytes);
    bytes.forEach((byte) => {
      value += alphabet[byte % alphabet.length];
    });
  } else {
    for (let i = 0; i < length; i += 1) {
      value += alphabet[Math.floor(Math.random() * alphabet.length)];
    }
  }
  return value;
};

if (userCreateBtn) {
  userCreateBtn.addEventListener("click", openUserCreateModal);
}
if (userCreateModal) {
  userCreateModal.addEventListener("click", (event) => {
    if (event.target.closest("[data-modal-close]")) {
      closeUserCreateModal();
    }
  });
}
if (userSaveModal) {
  userSaveModal.addEventListener("click", (event) => {
    if (event.target.closest("[data-modal-close]")) {
      closeUserSaveModal();
    }
  });
}
if (userActiveModal) {
  userActiveModal.addEventListener("click", (event) => {
    if (event.target.closest("[data-modal-close]")) {
      if (pendingActiveToggle) {
        pendingActiveToggle.checked = !pendingActiveToggle.checked;
      }
      closeUserActiveModal();
    }
  });
}
if (userGeneratePassword && userCreatePassword) {
  userGeneratePassword.addEventListener("click", () => {
    const password = generatePassword();
    userCreatePassword.value = password;
    userCreatePassword.focus();
  });
}
const userGenerateButtons = document.querySelectorAll("[data-generate-password]");
userGenerateButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const targetId = button.getAttribute("data-target");
    const target = targetId ? document.getElementById(targetId) : null;
    if (!target) {
      return;
    }
    const password = generatePassword();
    target.value = password;
    target.focus();
  });
});
const userSaveButtons = document.querySelectorAll("[data-user-save]");
userSaveButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const formId = button.getAttribute("data-form-id");
    const form = formId ? document.getElementById(formId) : null;
    if (!form) {
      return;
    }
    pendingUserForm = form;
    openUserSaveModal();
  });
});
if (userSaveConfirm) {
  userSaveConfirm.addEventListener("click", () => {
    if (!pendingUserForm) {
      closeUserSaveModal();
      return;
    }
    if (pendingUserForm.requestSubmit) {
      pendingUserForm.requestSubmit();
    } else {
      pendingUserForm.submit();
    }
    closeUserSaveModal();
  });
}

const fetchMetricsCard = async (form, params) => {
  if (!metricsCard || !form) {
    return;
  }
  const targetUrl = form.dataset.metricsUrl || form.action || window.location.href;
  const url = new URL(targetUrl, window.location.origin);
  if (params) {
    url.search = params;
  }
  try {
    const response = await fetch(url.toString(), {
      headers: { "X-Requested-With": "fetch", Accept: "text/html" },
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error("No se pudo actualizar las m\u00e9tricas.");
    }
    const html = await response.text();
    metricsCard.innerHTML = html;
  } catch (error) {
    showToast(error.message, "error", 4200);
  }
};

document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!form || form.id !== "metrics-form") {
    return;
  }
  event.preventDefault();
  const data = new FormData(form);
  const params = new URLSearchParams(data).toString();
  fetchMetricsCard(form, params);
});

document.addEventListener("click", (event) => {
  const clearBtn = event.target.closest("#metrics-clear");
  if (!clearBtn) {
    return;
  }
  event.preventDefault();
  const form = document.querySelector("#metrics-form");
  if (form) {
    form.reset();
    fetchMetricsCard(form, "");
  }
});

const userActiveToggles = document.querySelectorAll("[data-active-toggle]");
userActiveToggles.forEach((toggle) => {
  toggle.addEventListener("change", () => {
    if (pendingActiveToggle === toggle) {
      return;
    }
    pendingActiveToggle = toggle;
    openUserActiveModal();
  });
});
if (userActiveConfirm) {
  userActiveConfirm.addEventListener("click", () => {
    if (!pendingActiveToggle) {
      closeUserActiveModal();
      return;
    }
    const formId = pendingActiveToggle.getAttribute("data-form-id");
    const form = formId ? document.getElementById(formId) : null;
    if (form) {
      if (form.requestSubmit) {
        form.requestSubmit();
      } else {
        form.submit();
      }
    }
    closeUserActiveModal();
  });
}

const loginForm = document.querySelector("[data-login-form]");

if (loginForm) {
  loginForm.addEventListener("submit", () => {
    const submitBtn = loginForm.querySelector("button[type='submit']");
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Ingresando...";
    }
    loginForm.setAttribute("aria-busy", "true");
  });
}

const imgForm = document.querySelector("#img-pdf-upload-form");
const imgFileInput = document.querySelector("#img-pdf-files");
const imgEnhanceSelect = document.querySelector("#img-pdf-enhance");
const imgPreviewBtn = document.querySelector("#img-pdf-preview-btn");
const imgPreviewWrap = document.querySelector("#img-pdf-preview");
const imgPreviewGrid = document.querySelector("#img-pdf-preview-grid");
const imgGenerateBtn = document.querySelector("#img-pdf-generate-btn");
const imgFilenameInput = document.querySelector("#img-pdf-filename");
const imgRefreshCard = document.querySelector("[data-img-refresh-url]");
const imgTableBody = document.querySelector("#img-pdf-table-body");
const imgUploadList = document.querySelector("#img-upload-list");
const getImgPdfCsrf = () => {
  if (!imgForm) {
    return "";
  }
  const tokenInput = imgForm.querySelector('input[name="csrf_token"]');
  return tokenInput ? tokenInput.value : "";
};

const formatBytes = (bytes) => {
  if (!bytes) {
    return "0 KB";
  }
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(size >= 10 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
};

const syncFileInput = () => {
  if (!imgFileInput) {
    return;
  }
  const dt = new DataTransfer();
  selectedFiles.forEach((file) => {
    dt.items.add(file);
  });
  imgFileInput.files = dt.files;
};

const renderUploadList = () => {
  if (!imgUploadList) {
    return;
  }
  imgUploadList.innerHTML = "";
  if (!selectedFiles.length) {
    const empty = document.createElement("p");
    empty.className = "muted upload-list__empty";
    empty.textContent = "No hay imagenes seleccionadas.";
    imgUploadList.appendChild(empty);
    return;
  }
  const header = document.createElement("div");
  header.className = "upload-list__header";
  header.textContent = `Imagenes seleccionadas (${selectedFiles.length})`;
  imgUploadList.appendChild(header);
  selectedFiles.forEach((file, index) => {
    const row = document.createElement("div");
    row.className = "upload-list__item";
    const info = document.createElement("div");
    const nameEl = document.createElement("div");
    nameEl.className = "upload-list__name";
    nameEl.textContent = file.name;
    const metaEl = document.createElement("div");
    metaEl.className = "upload-list__meta";
    metaEl.textContent = formatBytes(file.size);
    info.appendChild(nameEl);
    info.appendChild(metaEl);
    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "ghost-btn";
    removeBtn.dataset.removeIndex = String(index);
    removeBtn.textContent = "Quitar";
    row.appendChild(info);
    row.appendChild(removeBtn);
    imgUploadList.appendChild(row);
  });
};

const cropModal = document.querySelector("#img-crop-modal");
const cropCanvas = document.querySelector("#img-crop-canvas");
const cropApplyBtn = document.querySelector("#img-crop-apply");
const cropResetBtn = document.querySelector("#img-crop-reset");
const cropRestartBtn = document.querySelector("#img-crop-restart");
const cropRotateButtons = document.querySelectorAll("[data-crop-rotate]");

let previewItems = [];
let activeCropIndex = null;
let cropImage = null;
let cropRect = null;
let cropStart = null;
let cropDragging = false;
let cropDrawState = null;
let cropCanvasBase = null;
const CROP_MAX_WIDTH = 680;
const CROP_MAX_HEIGHT = 520;
const MAX_IMG_FILES = 6;
let selectedFiles = [];
const buildFileKey = (file) => `${file.name}_${file.size}_${file.lastModified}`;

if (imgFileInput) {
  imgFileInput.addEventListener("click", (event) => {
    if (selectedFiles.length >= MAX_IMG_FILES) {
      event.preventDefault();
      showToast(
        `Ya alcanzaste el limite de ${MAX_IMG_FILES} imagenes.`,
        "error",
        5200
      );
    }
  });
  imgFileInput.addEventListener("change", () => {
    const incoming = Array.from(imgFileInput.files || []);
    if (!incoming.length) {
      return;
    }
    const existingKeys = new Set(
      selectedFiles.map((file) => buildFileKey(file))
    );
    incoming.forEach((file) => {
      const key = buildFileKey(file);
      if (!existingKeys.has(key)) {
        selectedFiles.push(file);
        existingKeys.add(key);
      }
    });
    if (selectedFiles.length > MAX_IMG_FILES) {
      selectedFiles = selectedFiles.slice(0, MAX_IMG_FILES);
      showToast(`Solo podes cargar hasta ${MAX_IMG_FILES} imagenes.`);
    }
    syncFileInput();
    renderUploadList();
    if (previewItems.length) {
      const nextKeys = new Set(selectedFiles.map((file) => buildFileKey(file)));
      previewItems = previewItems.filter(
        (item) => item.sourceKey && nextKeys.has(item.sourceKey)
      );
      renderPreviewGrid();
    }
  });
}

if (imgUploadList) {
  imgUploadList.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-remove-index]");
    if (!button) {
      return;
    }
    const index = Number.parseInt(button.dataset.removeIndex || "", 10);
    if (Number.isNaN(index)) {
      return;
    }
    selectedFiles.splice(index, 1);
    syncFileInput();
    renderUploadList();
    if (previewItems.length) {
      const nextKeys = new Set(selectedFiles.map((file) => buildFileKey(file)));
      previewItems = previewItems.filter(
        (item) => item.sourceKey && nextKeys.has(item.sourceKey)
      );
    }
    renderPreviewGrid();
  });
}

renderUploadList();

const renderPreviewGrid = () => {
  if (!imgPreviewGrid) {
    return;
  }
  imgPreviewGrid.innerHTML = "";
  previewItems.forEach((item, index) => {
    const card = document.createElement("div");
    card.className = "preview-card";
    const img = document.createElement("img");
    img.src = item.editedUrl;
    img.alt = `Documento ${index + 1}`;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ghost-btn";
    btn.textContent = "Editar";
    btn.dataset.index = String(index);
    card.appendChild(img);
    card.appendChild(btn);
    imgPreviewGrid.appendChild(card);
  });
  if (imgPreviewWrap) {
    imgPreviewWrap.classList.toggle("is-empty", previewItems.length === 0);
  }
  if (imgGenerateBtn) {
    imgGenerateBtn.disabled = previewItems.length === 0;
  }
};

const openCropModal = (index) => {
  if (!cropModal || !cropCanvas) {
    return;
  }
  activeCropIndex = index;
  cropRect = null;
  cropStart = null;
  cropDragging = false;
  cropDrawState = null;
  const maxWidth = Math.min(
    CROP_MAX_WIDTH,
    Math.floor(window.innerWidth * 0.8)
  );
  const maxHeight = Math.min(
    CROP_MAX_HEIGHT,
    Math.floor(window.innerHeight * 0.6)
  );
  cropCanvasBase = {
    width: Math.max(280, maxWidth),
    height: Math.max(240, maxHeight),
  };
  cropImage = new Image();
  cropImage.onload = () => {
    cropCanvas.width = cropCanvasBase.width;
    cropCanvas.height = cropCanvasBase.height;
    drawCropCanvas();
  };
  cropImage.src = previewItems[index].editedUrl;
  cropModal.classList.add("is-open");
  cropModal.setAttribute("aria-hidden", "false");
};

const closeCropModal = () => {
  if (!cropModal) {
    return;
  }
  cropModal.classList.remove("is-open");
  cropModal.setAttribute("aria-hidden", "true");
};

const drawCropCanvas = () => {
  if (!cropCanvas || !cropImage) {
    return;
  }
  const ctx = cropCanvas.getContext("2d");
  if (!ctx) {
    return;
  }
  const scale = Math.min(
    cropCanvas.width / cropImage.width,
    cropCanvas.height / cropImage.height
  );
  const drawWidth = cropImage.width * scale;
  const drawHeight = cropImage.height * scale;
  const offsetX = (cropCanvas.width - drawWidth) / 2;
  const offsetY = (cropCanvas.height - drawHeight) / 2;
  cropDrawState = { scale, drawWidth, drawHeight, offsetX, offsetY };
  ctx.clearRect(0, 0, cropCanvas.width, cropCanvas.height);
  ctx.drawImage(cropImage, offsetX, offsetY, drawWidth, drawHeight);
  if (cropRect) {
    ctx.strokeStyle = "#c96b2a";
    ctx.lineWidth = 2;
    ctx.strokeRect(cropRect.x, cropRect.y, cropRect.w, cropRect.h);
    ctx.fillStyle = "rgba(201, 107, 42, 0.12)";
    ctx.fillRect(cropRect.x, cropRect.y, cropRect.w, cropRect.h);
  }
};

const canvasPoint = (event) => {
  const rect = cropCanvas.getBoundingClientRect();
  return {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  };
};

if (cropCanvas) {
  cropCanvas.addEventListener("mousedown", (event) => {
    cropDragging = true;
    cropStart = canvasPoint(event);
    cropRect = { x: cropStart.x, y: cropStart.y, w: 0, h: 0 };
  });

  cropCanvas.addEventListener("mousemove", (event) => {
    if (!cropDragging || !cropStart) {
      return;
    }
    const point = canvasPoint(event);
    cropRect = {
      x: Math.min(cropStart.x, point.x),
      y: Math.min(cropStart.y, point.y),
      w: Math.abs(point.x - cropStart.x),
      h: Math.abs(point.y - cropStart.y),
    };
    drawCropCanvas();
  });

  cropCanvas.addEventListener("mouseup", () => {
    cropDragging = false;
  });
  cropCanvas.addEventListener("mouseleave", () => {
    cropDragging = false;
  });
}

if (imgPreviewGrid) {
  imgPreviewGrid.addEventListener("click", (event) => {
    const btn = event.target.closest("button[data-index]");
    if (!btn) {
      return;
    }
    const index = Number.parseInt(btn.dataset.index, 10);
    if (Number.isNaN(index)) {
      return;
    }
    openCropModal(index);
  });
}

if (cropApplyBtn) {
  cropApplyBtn.addEventListener("click", () => {
    if (
      activeCropIndex === null ||
      !cropImage ||
      !cropCanvas ||
      !previewItems[activeCropIndex]
    ) {
      return;
    }
    if (!cropDrawState) {
      return;
    }
    const drawRect = {
      x: cropDrawState.offsetX,
      y: cropDrawState.offsetY,
      w: cropDrawState.drawWidth,
      h: cropDrawState.drawHeight,
    };
    let rect = cropRect;
    if (!rect || rect.w < 5 || rect.h < 5) {
      rect = drawRect;
    }
    const x0 = Math.max(drawRect.x, rect.x);
    const y0 = Math.max(drawRect.y, rect.y);
    const x1 = Math.min(drawRect.x + drawRect.w, rect.x + rect.w);
    const y1 = Math.min(drawRect.y + drawRect.h, rect.y + rect.h);
    if (x1 - x0 < 2 || y1 - y0 < 2) {
      rect = drawRect;
    } else {
      rect = { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
    }
    const sx = (rect.x - drawRect.x) / cropDrawState.scale;
    const sy = (rect.y - drawRect.y) / cropDrawState.scale;
    const sw = rect.w / cropDrawState.scale;
    const sh = rect.h / cropDrawState.scale;

    const output = document.createElement("canvas");
    output.width = Math.max(1, Math.floor(sw));
    output.height = Math.max(1, Math.floor(sh));
    const ctx = output.getContext("2d");
    if (!ctx) {
      return;
    }
    ctx.drawImage(cropImage, sx, sy, sw, sh, 0, 0, output.width, output.height);
    previewItems[activeCropIndex].editedUrl = output.toDataURL("image/png");
    cropRect = null;
    cropStart = null;
    if (cropImage) {
      cropImage.src = previewItems[activeCropIndex].editedUrl;
    } else {
      drawCropCanvas();
    }
    renderPreviewGrid();
  });
}

const rotateDataUrl = (dataUrl, direction) =>
  new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = image.height;
      canvas.height = image.width;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        reject(new Error("No se pudo preparar la rotacion."));
        return;
      }
      ctx.translate(canvas.width / 2, canvas.height / 2);
      ctx.rotate(direction === "left" ? -Math.PI / 2 : Math.PI / 2);
      ctx.drawImage(image, -image.width / 2, -image.height / 2);
      resolve(canvas.toDataURL("image/png"));
    };
    image.onerror = () => reject(new Error("No se pudo rotar la imagen."));
    image.src = dataUrl;
  });

if (cropRotateButtons.length) {
  cropRotateButtons.forEach((button) => {
    button.addEventListener("click", async () => {
      if (activeCropIndex === null || !previewItems[activeCropIndex]) {
        return;
      }
      const direction = button.dataset.cropRotate;
      if (!direction) {
        return;
      }
      try {
        const rotatedUrl = await rotateDataUrl(
          previewItems[activeCropIndex].editedUrl,
          direction
        );
        previewItems[activeCropIndex].editedUrl = rotatedUrl;
        cropRect = null;
        if (cropImage) {
          cropImage.src = rotatedUrl;
        }
        renderPreviewGrid();
      } catch (error) {
        showToast(error.message);
      }
    });
  });
}

if (cropResetBtn) {
  cropResetBtn.addEventListener("click", () => {
    if (activeCropIndex === null) {
      return;
    }
    previewItems[activeCropIndex].editedUrl = previewItems[activeCropIndex].baseUrl;
    cropRect = null;
    if (cropImage) {
      cropImage.src = previewItems[activeCropIndex].editedUrl;
    }
    renderPreviewGrid();
  });
}

if (cropRestartBtn) {
  cropRestartBtn.addEventListener("click", () => {
    if (activeCropIndex === null || !previewItems[activeCropIndex]) {
      return;
    }
    cropRect = null;
    cropStart = null;
    const sourceUrl =
      previewItems[activeCropIndex].fullUrl ||
      previewItems[activeCropIndex].baseUrl;
    if (cropImage) {
      cropImage.src = sourceUrl;
    }
  });
}

if (cropModal) {
  cropModal.addEventListener("click", (event) => {
    if (event.target.closest("[data-crop-close]")) {
      closeCropModal();
    }
  });
}

const setPreviewLoading = (loading) => {
  if (!imgPreviewBtn) {
    return;
  }
  imgPreviewBtn.disabled = loading;
  imgPreviewBtn.textContent = loading ? "Procesando..." : "Previsualizar";
};

const setGenerateLoading = (loading) => {
  if (!imgGenerateBtn) {
    return;
  }
  imgGenerateBtn.disabled = loading || previewItems.length === 0;
  imgGenerateBtn.textContent = loading ? "Generando..." : "Generar PDF";
};

if (imgPreviewBtn && imgForm) {
  imgPreviewBtn.addEventListener("click", async () => {
    if (!selectedFiles.length) {
      showToast("Selecciona al menos una imagen.");
      return;
    }
    const currentKeys = new Set(
      previewItems.map((item) => item.sourceKey).filter(Boolean)
    );
    const pendingFiles = selectedFiles.filter(
      (file) => !currentKeys.has(buildFileKey(file))
    );
    if (!pendingFiles.length && previewItems.length) {
      showToast("No hay nuevas imagenes para previsualizar.", "info", 3600);
      return;
    }
    const formData = new FormData();
    formData.set("enhance_mode", imgEnhanceSelect?.value || "soft");
    const filesToSend = pendingFiles.length ? pendingFiles : selectedFiles;
    filesToSend.forEach((file) => {
      formData.append("images", file);
      formData.append("file_keys", buildFileKey(file));
    });
    setPreviewLoading(true);
    try {
      const response = await fetch("/tools/img-to-pdf/preview", {
        method: "POST",
        body: formData,
        headers: {
          "X-Requested-With": "fetch",
          "X-CSRFToken": getImgPdfCsrf(),
        },
      });
      const payload = await safeJson(response);
      if (!response.ok) {
        throw new Error(payload.error || "No se pudo procesar las imagenes.");
      }
      const newItems = payload.previews.map((item) => ({
        id: item.id,
        sourceKey: item.source_key || null,
        baseUrl: item.data_url,
        fullUrl: item.full_data_url || item.data_url,
        editedUrl: item.data_url,
      }));
      const combined = previewItems.concat(newItems);
      const ordered = [];
      const orderedKeys = selectedFiles.map((file) => buildFileKey(file));
      orderedKeys.forEach((key) => {
        combined
          .filter((item) => item.sourceKey === key)
          .forEach((item) => ordered.push(item));
      });
      combined
        .filter((item) => !item.sourceKey)
        .forEach((item) => ordered.push(item));
      previewItems = ordered;
      renderPreviewGrid();
    } catch (error) {
      showToast(error.message);
    } finally {
      setPreviewLoading(false);
    }
  });
}

if (imgGenerateBtn) {
  imgGenerateBtn.addEventListener("click", async () => {
    if (!previewItems.length) {
      return;
    }
    const filename = imgFilenameInput?.value || "";
    setGenerateLoading(true);
    try {
      const response = await fetch("/tools/img-to-pdf/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "fetch",
          "X-CSRFToken": getImgPdfCsrf(),
        },
        body: JSON.stringify({
          images: previewItems.map((item) => item.editedUrl),
          filename,
        }),
      });
      const payload = await safeJson(response);
      if (!response.ok) {
        throw new Error(payload.error || "No se pudo generar el PDF.");
      }
      if (payload.row_html && imgTableBody) {
        const wrapper = document.createElement("tbody");
        wrapper.innerHTML = payload.row_html.trim();
        const newRow = wrapper.querySelector("tr");
        if (newRow) {
          imgTableBody.prepend(newRow);
        }
      }
      previewItems = [];
      renderPreviewGrid();
      selectedFiles = [];
      syncFileInput();
      renderUploadList();
      if (imgFilenameInput) {
        imgFilenameInput.value = "";
      }
      setGenerateLoading(false);
    } catch (error) {
      showToast(error.message);
      setGenerateLoading(false);
    }
  });
}

const refreshImgTable = async () => {
  if (!imgRefreshCard || !imgTableBody) {
    return;
  }
  const url = imgRefreshCard.dataset.imgRefreshUrl;
  if (!url) {
    return;
  }
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) {
      throw new Error("refresh failed");
    }
    const payload = await safeJson(response);
    imgTableBody.innerHTML = payload.html;
  } catch (error) {
    // Silently ignore refresh errors
  }
};
