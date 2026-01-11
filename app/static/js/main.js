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
  closeBtn.textContent = "×";
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
      isPassword ? "Ocultar contraseña" : "Mostrar contraseña"
    );
    button.setAttribute("aria-pressed", isPassword ? "true" : "false");
  });
});

const refreshCard = document.querySelector("[data-refresh-url]");
const refreshBody = document.querySelector("#rpa-table-body");
const refreshPagination = document.querySelector("#rpa-pagination");
const refreshPaginationTop = document.querySelector("#rpa-pagination-top");
const totalCountEl = document.querySelector("#rpa-total-count");
const totalCountLabelEl = document.querySelector("#rpa-count-label");
const rpaDeleteBtn = document.querySelector("#rpa-delete-btn");
const rpaDeleteCsrf = document.querySelector("#rpa-delete-csrf");
const rpaDeleteModal = document.querySelector("#rpa-delete-modal");
const rpaDeleteConfirm = document.querySelector("#rpa-delete-confirm");
const rpaSelectAll = document.querySelector("#rpa-select-all");
const rpaTallerCsrf = document.querySelector("#rpa-taller-csrf");
const rpaTallerModal = document.querySelector("#rpa-taller-modal");
const rpaTallerConfirm = document.querySelector("#rpa-taller-confirm");
const rpaTallerMessage = document.querySelector("#rpa-taller-message");
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
const selectedRpaIds = new Set();
let pendingTallerChange = null;
let refreshTimerId = null;

const refreshTable = async () => {
  if (!refreshCard || !refreshBody) {
    return;
  }
  const refreshUrl = refreshCard.dataset.refreshUrl;
  const interval = Number.parseInt(
    refreshCard.dataset.refreshInterval || "5000",
    10
  );
  if (!refreshUrl || Number.isNaN(interval) || interval <= 0) {
    return;
  }

  try {
    const response = await fetch(refreshUrl, { cache: "no-store" });
    if (!response.ok) {
      throw new Error("refresh failed");
    }
    const payload = await safeJson(response);
    refreshBody.innerHTML = payload.html;
    if (payload.pagination !== undefined) {
      if (refreshPagination) {
        refreshPagination.innerHTML = payload.pagination;
      }
      if (refreshPaginationTop) {
        refreshPaginationTop.innerHTML = payload.pagination;
      }
    }
    if (totalCountEl && payload.total !== undefined) {
      totalCountEl.dataset.total = payload.total;
      if (selectedRpaIds.size === 0) {
        totalCountEl.textContent = payload.total;
      }
    }
    applySelectionToTable();
    updateRpaSelectionUI();
    updatePaginationState(payload);
    if (payload.has_pending) {
      refreshTimerId = setTimeout(refreshTable, interval);
    } else {
      refreshTimerId = null;
    }
  } catch (error) {
    refreshTimerId = setTimeout(refreshTable, interval);
  }
};

if (refreshCard && refreshCard.dataset.autoRefresh === "true") {
  refreshTimerId = setTimeout(refreshTable, 2000);
}

const ensureTableRefresh = () => {
  if (!refreshCard) {
    return;
  }
  refreshCard.dataset.autoRefresh = "true";
  if (!refreshTimerId) {
    refreshTimerId = setTimeout(refreshTable, 1500);
  }
};

const escapeHtml = (value) => {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
};

const createOptimisticRow = (patente, tallerName, placeholderId) => {
  const now = new Date();
  const formattedDate = now.toLocaleDateString("es-AR", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
  });
  const row = document.createElement("tr");
  row.dataset.placeholderId = placeholderId;
  row.classList.add("pending-row");
  row.innerHTML = `
    <td class="select-col">
      <input type="checkbox" class="rpa-select" disabled aria-label="Seleccionar proceso" />
    </td>
    <td>${formattedDate}</td>
    <td>${escapeHtml(patente)}</td>
    <td>${escapeHtml(tallerName || "-")}</td>
    <td><span class="badge en-proceso">en proceso</span></td>
    <td>-</td>
    <td>-</td>
    <td>
      <button class="ghost-btn icon-btn" type="button" disabled aria-label="Previsualizar">
        <svg viewBox="0 0 24 24" role="presentation" aria-hidden="true">
          <path d="M6 2h8l4 4v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2zm8 1.5V7h3.5L14 3.5zM8 11h8v2H8v-2zm0 4h8v2H8v-2z" fill="currentColor"/>
        </svg>
      </button>
      <button class="ghost-btn icon-btn" type="button" disabled aria-label="Descargar">
        <svg viewBox="0 0 24 24" role="presentation" aria-hidden="true">
          <path d="M12 3a1 1 0 0 1 1 1v8.6l2.3-2.3a1 1 0 1 1 1.4 1.4l-4 4a1 1 0 0 1-1.4 0l-4-4a1 1 0 1 1 1.4-1.4L11 12.6V4a1 1 0 0 1 1-1zm-7 14a1 1 0 0 1 1-1h12a1 1 0 1 1 0 2H6a1 1 0 0 1-1-1z" fill="currentColor"/>
        </svg>
      </button>
    </td>
  `;
  return row;
};

const applySelectionToTable = () => {
  if (!refreshBody) {
    return;
  }
  const idsInTable = new Set();
  refreshBody.querySelectorAll(".rpa-select").forEach((checkbox) => {
    const id = Number.parseInt(checkbox.value, 10);
    if (Number.isNaN(id)) {
      return;
    }
    idsInTable.add(id);
    checkbox.checked = selectedRpaIds.has(id);
  });
  Array.from(selectedRpaIds).forEach((id) => {
    if (!idsInTable.has(id)) {
      selectedRpaIds.delete(id);
    }
  });
  updateSelectAllState();
};

const updateSelectAllState = () => {
  if (!rpaSelectAll || !refreshBody) {
    return;
  }
  const checkboxes = Array.from(
    refreshBody.querySelectorAll(".rpa-select")
  ).filter((checkbox) => !checkbox.disabled);
  const total = checkboxes.length;
  if (total === 0) {
    rpaSelectAll.checked = false;
    rpaSelectAll.indeterminate = false;
    rpaSelectAll.disabled = true;
    return;
  }
  rpaSelectAll.disabled = false;
  const selected = checkboxes.filter((checkbox) => checkbox.checked).length;
  if (selected === 0) {
    rpaSelectAll.checked = false;
    rpaSelectAll.indeterminate = false;
  } else if (selected === total) {
    rpaSelectAll.checked = true;
    rpaSelectAll.indeterminate = false;
  } else {
    rpaSelectAll.checked = false;
    rpaSelectAll.indeterminate = true;
  }
};

const updateRpaSelectionUI = () => {
  if (!totalCountEl) {
    return;
  }
  const selectedCount = selectedRpaIds.size;
  if (selectedCount > 0) {
    if (totalCountLabelEl) {
      totalCountLabelEl.textContent = "Seleccionados";
    }
    totalCountEl.textContent = selectedCount;
  } else {
    if (totalCountLabelEl) {
      totalCountLabelEl.textContent = "Total";
    }
    const total = totalCountEl.dataset.total;
    if (total !== undefined) {
      totalCountEl.textContent = total;
    }
  }
  if (rpaDeleteBtn) {
    const shouldShow = selectedCount > 0;
    rpaDeleteBtn.hidden = !shouldShow;
    rpaDeleteBtn.disabled = !shouldShow;
  }
  updateSelectAllState();
};

updateRpaSelectionUI();

const rpaForm = document.querySelector("#rpa-form");
const loginForm = document.querySelector("[data-login-form]");
const rpaErrorModal = document.querySelector("#rpa-error-modal");
const rpaErrorDetail = document.querySelector("#rpa-error-detail");
const patenteInput = rpaForm?.querySelector("input[name='patente']");
const tallerSelect = rpaForm?.querySelector("#taller-select");
const tallerNewInput = rpaForm?.querySelector("#taller-name");
const rpaSubmit = rpaForm?.querySelector("#rpa-submit");
const tallerCreateBtn = document.querySelector("#taller-create-btn");
const tallerModal = document.querySelector("#taller-modal");
const tallerModalName = document.querySelector("#taller-modal-name");
const tallerModalSave = document.querySelector("#taller-modal-save");
const tallerModalError = document.querySelector("#taller-modal-error");

const updateTallerUI = () => {
  if (!tallerSelect || !rpaSubmit) {
    return;
  }
  const patenteValue = (patenteInput?.value || "").trim();
  const hasPatente = patenteValue.length > 0;
  const hasTaller =
    (tallerSelect.value && tallerSelect.value !== "new") ||
    (tallerSelect.value === "new" && (tallerNewInput?.value || "").trim().length > 0);
  rpaSubmit.disabled = !(hasTaller && hasPatente);
};

if (tallerSelect) {
  tallerSelect.addEventListener("change", () => {
    if (tallerSelect.value !== "new" && tallerNewInput) {
      tallerNewInput.value = "";
    }
    updateTallerUI();
  });
}
if (patenteInput) {
  patenteInput.addEventListener("input", updateTallerUI);
}
updateTallerUI();

const openTallerModal = () => {
  if (!tallerModal || !tallerModalName) {
    return;
  }
  tallerModal.classList.add("is-open");
  tallerModal.setAttribute("aria-hidden", "false");
  if (tallerModalError) {
    tallerModalError.classList.add("is-hidden");
  }
  tallerModalName.value = "";
  tallerModalName.focus();
};

const closeTallerModal = () => {
  if (!tallerModal) {
    return;
  }
  tallerModal.classList.remove("is-open");
  tallerModal.setAttribute("aria-hidden", "true");
};

const confirmNewTaller = () => {
  if (!tallerSelect || !tallerModalName || !tallerNewInput) {
    return;
  }
  const name = tallerModalName.value.trim();
  if (!name) {
    if (tallerModalError) {
      tallerModalError.classList.remove("is-hidden");
    }
    tallerModalName.focus();
    return;
  }
  const newValue = "new";
  let option = Array.from(tallerSelect.options).find(
    (item) => item.value === newValue
  );
  if (!option) {
    option = new Option(name, newValue, false, false);
    tallerSelect.add(option);
  }
  option.textContent = name;
  tallerSelect.value = newValue;
  tallerNewInput.value = name;
  updateTallerUI();
  closeTallerModal();
};

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

if (tallerCreateBtn) {
  tallerCreateBtn.addEventListener("click", openTallerModal);
}
if (tallerModalSave) {
  tallerModalSave.addEventListener("click", confirmNewTaller);
}
if (tallerModal) {
  tallerModal.addEventListener("click", (event) => {
    if (event.target.closest("[data-modal-close]")) {
      closeTallerModal();
    }
  });
}

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
      throw new Error("No se pudo actualizar las métricas.");
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

if (rpaForm) {
  rpaForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (rpaSubmit?.disabled) {
      return;
    }
    const formData = new FormData(rpaForm);
    const patente = formData.get("patente") || "";
    let tallerLabel = "-";
    if (tallerSelect) {
      const option = tallerSelect.options[tallerSelect.selectedIndex];
      tallerLabel = option ? option.textContent.trim() : "-";
    }
    const placeholderId = `pending-${Date.now()}`;
    if (refreshBody) {
      const row = createOptimisticRow(patente, tallerLabel, placeholderId);
      refreshBody.prepend(row);
    }

    try {
      const response = await fetch(rpaForm.action || window.location.href, {
        method: "POST",
        headers: {
          "X-Requested-With": "fetch",
          Accept: "application/json",
        },
        body: formData,
      });
      const payload = await safeJson(response);
      if (!response.ok) {
        throw new Error(payload.error || "Error al crear proceso.");
      }
      if (payload.row_html && refreshBody) {
        const wrapper = document.createElement("tbody");
        wrapper.innerHTML = payload.row_html.trim();
        const newRow = wrapper.querySelector("tr");
        const placeholder = refreshBody.querySelector(
          `[data-placeholder-id="${placeholderId}"]`
        );
        if (placeholder && newRow) {
          placeholder.replaceWith(newRow);
        } else if (newRow) {
          refreshBody.prepend(newRow);
        }
      }
      if (tallerSelect && payload.taller_id && payload.taller_nombre) {
        const newValue = String(payload.taller_id);
        let option = Array.from(tallerSelect.options).find(
          (item) => item.value === newValue
        );
        if (!option) {
          option = new Option(payload.taller_nombre, newValue, false, false);
          tallerSelect.add(option);
        }
        tallerSelect.value = newValue;
        const tempOption = Array.from(tallerSelect.options).find(
          (item) => item.value === "new"
        );
        if (tempOption) {
          tempOption.remove();
        }
        if (tallerNewInput) {
          tallerNewInput.value = "";
        }
      }
      ensureTableRefresh();
      if (patenteInput) {
        patenteInput.value = "";
        patenteInput.dispatchEvent(new Event("input", { bubbles: true }));
      }
      updateTallerUI();
    } catch (error) {
      const placeholder = refreshBody?.querySelector(
        `[data-placeholder-id="${placeholderId}"]`
      );
      if (placeholder) {
        placeholder.remove();
      }
      const longer =
        /patente|formato/i.test(error.message || "") ? 6000 : 4200;
      showToast(error.message, "error", longer);
    }
  });
}

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

if (refreshBody) {
  if (rpaSelectAll) {
    rpaSelectAll.addEventListener("change", () => {
      const checkboxes = refreshBody.querySelectorAll(".rpa-select");
      selectedRpaIds.clear();
      checkboxes.forEach((checkbox) => {
        if (checkbox.disabled) {
          return;
        }
        checkbox.checked = rpaSelectAll.checked;
        const id = Number.parseInt(checkbox.value, 10);
        if (!Number.isNaN(id) && rpaSelectAll.checked) {
          selectedRpaIds.add(id);
        }
      });
      updateRpaSelectionUI();
    });
  }

  refreshBody.addEventListener("change", (event) => {
    const checkbox = event.target.closest(".rpa-select");
    if (!checkbox) {
      return;
    }
    const id = Number.parseInt(checkbox.value, 10);
    if (Number.isNaN(id)) {
      return;
    }
    if (checkbox.checked) {
      selectedRpaIds.add(id);
    } else {
      selectedRpaIds.delete(id);
    }
    updateRpaSelectionUI();
  });

  refreshBody.addEventListener("change", (event) => {
    const select = event.target.closest(".rpa-taller-select");
    if (!select) {
      return;
    }
    const procesoId = select.dataset.procesoId;
    const currentName = select.dataset.currentName || "Sin taller";
    const currentId = select.dataset.currentId || "";
    const nextId = select.value;
    const nextName =
      select.selectedOptions[0]?.textContent?.trim() || "Sin taller";

    if (!procesoId) {
      return;
    }

    if (nextId === currentId) {
      return;
    }

    if (!rpaTallerModal || !rpaTallerMessage) {
      select.value = currentId;
      return;
    }

    pendingTallerChange = {
      select,
      procesoId,
      nextId,
      nextName,
      currentId,
      currentName,
    };
    rpaTallerMessage.textContent = `Cambiar "${currentName}" por "${nextName}"?`;
    rpaTallerModal.classList.add("is-open");
    rpaTallerModal.setAttribute("aria-hidden", "false");
  });

  refreshBody.addEventListener("submit", async (event) => {
    const form = event.target.closest("form");
    if (!form || !form.action.includes("/retry")) {
      return;
    }
    event.preventDefault();
    const formData = new FormData(form);
    const row = form.closest("tr");
    if (row) {
      row.classList.add("pending-row");
      const statusCell = row.querySelector("td:nth-child(5)");
      if (statusCell) {
        statusCell.innerHTML = '<span class="badge en-proceso">en proceso</span>';
      }
      const resultCell = row.querySelector("td:nth-child(6)");
      if (resultCell) {
        resultCell.textContent = "-";
      }
      const detailCell = row.querySelector("td:nth-child(7)");
      if (detailCell) {
        detailCell.textContent = "-";
      }
    }

    try {
      const response = await fetch(form.action, {
        method: "POST",
        headers: {
          "X-Requested-With": "fetch",
          Accept: "application/json",
        },
        body: formData,
      });
      const payload = await safeJson(response);
      if (!response.ok) {
        throw new Error(payload.error || "Error al reintentar.");
      }
      if (payload.row_html && refreshBody) {
        const wrapper = document.createElement("tbody");
        wrapper.innerHTML = payload.row_html.trim();
        const newRow = wrapper.querySelector("tr");
        if (newRow && row) {
          row.replaceWith(newRow);
        }
      }
      ensureTableRefresh();
    } catch (error) {
      if (row) {
        row.classList.remove("pending-row");
      }
      showToast(error.message);
    }
  });
}

const deleteSelectedProcesos = async () => {
  if (!selectedRpaIds.size) {
    return;
  }
  const ids = Array.from(selectedRpaIds);
  try {
    const response = await fetch("/tools/rpa-enargas/delete", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "fetch",
        Accept: "application/json",
        "X-CSRFToken": rpaDeleteCsrf?.value || "",
      },
      body: JSON.stringify({ ids }),
    });
    const payload = await safeJson(response);
    if (!response.ok) {
      throw new Error(payload.error || "No se pudieron eliminar los procesos.");
    }
    selectedRpaIds.clear();
    updateRpaSelectionUI();
    refreshTable();
    showToast(`Eliminados: ${payload.deleted}`, "success", 4200);
  } catch (error) {
    showToast(error.message || "No se pudieron eliminar los procesos.");
  }
};

if (rpaDeleteBtn) {
  rpaDeleteBtn.addEventListener("click", () => {
    if (!rpaDeleteModal) {
      deleteSelectedProcesos();
      return;
    }
    rpaDeleteModal.classList.add("is-open");
    rpaDeleteModal.setAttribute("aria-hidden", "false");
  });
}

const closeRpaDeleteModal = () => {
  if (!rpaDeleteModal) {
    return;
  }
  rpaDeleteModal.classList.remove("is-open");
  rpaDeleteModal.setAttribute("aria-hidden", "true");
};

if (rpaDeleteModal) {
  rpaDeleteModal.addEventListener("click", (event) => {
    if (event.target.closest("[data-delete-close]")) {
      closeRpaDeleteModal();
    }
  });
}

if (rpaDeleteConfirm) {
  rpaDeleteConfirm.addEventListener("click", async () => {
    await deleteSelectedProcesos();
    closeRpaDeleteModal();
  });
}

const closeRpaTallerModal = (revert = true) => {
  if (!rpaTallerModal) {
    return;
  }
  if (revert && pendingTallerChange?.select) {
    pendingTallerChange.select.value = pendingTallerChange.currentId;
  }
  pendingTallerChange = null;
  rpaTallerModal.classList.remove("is-open");
  rpaTallerModal.setAttribute("aria-hidden", "true");
};

if (rpaTallerModal) {
  rpaTallerModal.addEventListener("click", (event) => {
    if (event.target.closest("[data-taller-close]")) {
      closeRpaTallerModal(true);
    }
  });
}

if (rpaTallerConfirm) {
  rpaTallerConfirm.addEventListener("click", async () => {
    if (!pendingTallerChange) {
      closeRpaTallerModal(false);
      return;
    }
    const { select, procesoId, nextId, nextName, currentId } = pendingTallerChange;
    try {
      const response = await fetch(`/tools/rpa-enargas/${procesoId}/taller`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "fetch",
          Accept: "application/json",
          "X-CSRFToken": rpaTallerCsrf?.value || "",
        },
        body: JSON.stringify({ taller_id: nextId }),
      });
      const payload = await safeJson(response);
      if (!response.ok) {
        throw new Error(payload.error || "No se pudo actualizar el taller.");
      }
      select.dataset.currentId = payload.taller_id ? String(payload.taller_id) : "";
      select.dataset.currentName = payload.taller_nombre || "Sin taller";
      showToast("Taller actualizado.", "success", 3200);
    } catch (error) {
      select.value = currentId;
      showToast(error.message || "No se pudo actualizar el taller.");
    } finally {
      closeRpaTallerModal(false);
    }
  });
}

const openRpaErrorModal = (detail) => {
  if (!rpaErrorModal || !rpaErrorDetail) {
    return;
  }
  rpaErrorDetail.textContent = detail || "Sin detalle disponible.";
  rpaErrorModal.classList.add("is-open");
  rpaErrorModal.setAttribute("aria-hidden", "false");
};

const closeRpaErrorModal = () => {
  if (!rpaErrorModal) {
    return;
  }
  rpaErrorModal.classList.remove("is-open");
  rpaErrorModal.setAttribute("aria-hidden", "true");
};

if (refreshBody) {
  refreshBody.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-error-detail]");
    if (!button) {
      return;
    }
    let detail = button.dataset.errorDetail || "";
    try {
      detail = JSON.parse(detail);
    } catch (error) {
      // Keep raw detail if JSON parsing fails.
    }
    openRpaErrorModal(detail);
  });
}

if (rpaErrorModal) {
  rpaErrorModal.addEventListener("click", (event) => {
    if (event.target.closest("[data-error-close]")) {
      closeRpaErrorModal();
    }
  });
}

const filterForm = document.querySelector("#rpa-filter-form");
const filterClearBtn = document.querySelector("#rpa-filter-clear");
const filterDrawer = document.querySelector("#rpa-filter-drawer");
const filterOpenBtn = document.querySelector("#rpa-filter-open");
const sortDirInput = document.querySelector("#rpa-sort-dir");
const sortKeyInput = document.querySelector("#rpa-sort-key");
const estadoInput = document.querySelector("#filter-estado");
const resultadoInput = document.querySelector("#filter-resultado");
const chipButtons = document.querySelectorAll("[data-chip-group]");
const sortableHeaders = document.querySelectorAll("th.sortable");
const queryInput = filterForm?.querySelector("input[name='f_query']");
const dateFromInput = filterForm?.querySelector("input[name='f_date_from']");
const dateToInput = filterForm?.querySelector("input[name='f_date_to']");
let currentPage = 1;
let currentTotalPages = 1;

const buildFilterParams = () => {
  if (!filterForm) {
    return new URLSearchParams();
  }
  const formData = new FormData(filterForm);
  const params = new URLSearchParams();
  for (const [key, value] of formData.entries()) {
    if (value) {
      params.set(key, value);
    }
  }
  if (sortKeyInput?.value) {
    params.set("sort", sortKeyInput.value);
  }
  if (sortDirInput?.value) {
    params.set("dir", sortDirInput.value);
  }
  return params;
};

const updateSortIndicators = () => {
  if (!sortKeyInput || !sortDirInput) {
    return;
  }
  const activeKey = sortKeyInput.value;
  const isAsc = sortDirInput.value === "asc";
  sortableHeaders.forEach((header) => {
    const isActive = header.dataset.sort === activeKey;
    header.classList.toggle("is-active", isActive);
    header.classList.toggle("is-asc", isActive && isAsc);
    header.classList.toggle("is-desc", isActive && !isAsc);
  });
};

const setChipSelection = (group, value) => {
  if (group === "estado" && estadoInput) {
    estadoInput.value = estadoInput.value === value ? "" : value;
  }
  if (group === "resultado" && resultadoInput) {
    resultadoInput.value = resultadoInput.value === value ? "" : value;
  }
  chipButtons.forEach((button) => {
    if (button.dataset.chipGroup !== group) {
      return;
    }
    const isActive =
      (group === "estado" && estadoInput?.value === button.dataset.chipValue) ||
      (group === "resultado" && resultadoInput?.value === button.dataset.chipValue);
    button.classList.toggle("is-active", isActive);
  });
};

let filterTimer = null;
const applyFilters = () => {
  if (!refreshCard) {
    return;
  }
  const baseUrl = refreshCard.dataset.refreshBaseUrl || refreshCard.dataset.refreshUrl;
  if (!baseUrl) {
    return;
  }
  const params = buildFilterParams();
  params.delete("page");
  const nextUrl = params.toString()
    ? `${baseUrl}?${params.toString()}`
    : baseUrl;
  refreshCard.dataset.refreshUrl = nextUrl;
  refreshCard.dataset.autoRefresh = "true";
  refreshTable();
  updateSortIndicators();
};

const scheduleFilterApply = () => {
  clearTimeout(filterTimer);
  filterTimer = setTimeout(applyFilters, 400);
};

if (filterForm) {
  filterForm.addEventListener("submit", (event) => {
    event.preventDefault();
    applyFilters();
    if (filterDrawer) {
      filterDrawer.classList.remove("is-open");
      filterDrawer.setAttribute("aria-hidden", "true");
    }
  });
  filterForm.querySelectorAll("input, select").forEach((input) => {
    if (input.type === "hidden") {
      return;
    }
    const handler = input.tagName === "SELECT" ? applyFilters : scheduleFilterApply;
    input.addEventListener("input", handler);
    input.addEventListener("change", handler);
  });
}

const clearCachedDateInputs = () => {
  if (!dateFromInput && !dateToInput) {
    return;
  }
  const params = new URLSearchParams(window.location.search);
  if (params.has("f_date_from") || params.has("f_date_to")) {
    return;
  }
  if (dateFromInput) {
    dateFromInput.value = "";
  }
  if (dateToInput) {
    dateToInput.value = "";
  }
};

if (filterForm) {
  window.requestAnimationFrame(clearCachedDateInputs);
}

if (filterClearBtn && filterForm) {
  filterClearBtn.addEventListener("click", () => {
    filterForm.reset();
    if (queryInput) {
      queryInput.value = "";
    }
    if (dateFromInput) {
      dateFromInput.value = "";
    }
    if (dateToInput) {
      dateToInput.value = "";
    }
    if (estadoInput) {
      estadoInput.value = "";
    }
    if (resultadoInput) {
      resultadoInput.value = "";
    }
    if (sortDirInput) {
      sortDirInput.value = "desc";
    }
    if (sortKeyInput) {
      sortKeyInput.value = "fecha";
    }
    chipButtons.forEach((button) => {
      button.classList.remove("is-active");
    });
    updateSortIndicators();
    applyFilters();
  });
}

if (sortableHeaders.length && sortKeyInput && sortDirInput) {
  updateSortIndicators();
  sortableHeaders.forEach((header) => {
    header.addEventListener("click", () => {
      const nextKey = header.dataset.sort;
      if (!nextKey) {
        return;
      }
      if (sortKeyInput.value === nextKey) {
        sortDirInput.value = sortDirInput.value === "asc" ? "desc" : "asc";
      } else {
        sortKeyInput.value = nextKey;
        sortDirInput.value = "desc";
      }
      updateSortIndicators();
      applyFilters();
    });
  });
}

if (chipButtons.length) {
  chipButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const group = button.dataset.chipGroup;
      const value = button.dataset.chipValue;
      if (!group || !value) {
        return;
      }
      setChipSelection(group, value);
      applyFilters();
    });
  });
  if (estadoInput?.value) {
    setChipSelection("estado", estadoInput.value);
  }
  if (resultadoInput?.value) {
    setChipSelection("resultado", resultadoInput.value);
  }
}

if (filterOpenBtn && filterDrawer) {
  filterOpenBtn.addEventListener("click", () => {
    filterDrawer.classList.add("is-open");
    filterDrawer.setAttribute("aria-hidden", "false");
  });
}

if (filterDrawer) {
  filterDrawer.addEventListener("click", (event) => {
    if (event.target.closest("[data-filter-close]")) {
      filterDrawer.classList.remove("is-open");
      filterDrawer.setAttribute("aria-hidden", "true");
    }
  });
}

const updatePaginationState = (payload) => {
  if (!payload) {
    return;
  }
  if (payload.page !== undefined) {
    currentPage = Number.parseInt(payload.page, 10) || 1;
  }
  if (payload.total_pages !== undefined) {
    currentTotalPages = Number.parseInt(payload.total_pages, 10) || 1;
  }
};

const handlePaginationClick = (event) => {
  const button = event.target.closest("[data-page-action]");
  if (!button || button.disabled) {
    return;
  }
  const action = button.dataset.pageAction;
  let nextPage = currentPage;
  if (action === "prev") {
    nextPage = Math.max(1, currentPage - 1);
  }
  if (action === "next") {
    nextPage = Math.min(currentTotalPages, currentPage + 1);
  }
  const params = buildFilterParams();
  params.set("page", String(nextPage));
  const baseUrl = refreshCard?.dataset.refreshBaseUrl || refreshCard?.dataset.refreshUrl;
  if (!baseUrl || !refreshCard) {
    return;
  }
  refreshCard.dataset.refreshUrl = `${baseUrl}?${params.toString()}`;
  refreshCard.dataset.autoRefresh = "true";
  refreshTable();
};

const initPaginationState = () => {
  const pagination =
    refreshPaginationTop?.querySelector(".pagination") ||
    refreshPagination?.querySelector(".pagination");
  if (!pagination) {
    return;
  }
  const pageAttr = pagination.getAttribute("data-page");
  const totalAttr = pagination.getAttribute("data-total-pages");
  if (pageAttr) {
    currentPage = Number.parseInt(pageAttr, 10) || currentPage;
  }
  if (totalAttr) {
    currentTotalPages = Number.parseInt(totalAttr, 10) || currentTotalPages;
  }
};

if (refreshPagination) {
  refreshPagination.addEventListener("click", handlePaginationClick);
}
if (refreshPaginationTop) {
  refreshPaginationTop.addEventListener("click", handlePaginationClick);
}
initPaginationState();

const sessionStatusSection = document.querySelector("[data-session-status-url]");
const sessionStatusContent = document.querySelector("#rpa-session-status");
let lastSessionPayload = null;

const tableCard = document.querySelector(".table-card");
let lastScrollY = window.scrollY;

const handleTableAnchor = (event) => {
  if (!tableCard) {
    return;
  }
  const trigger = event.target.closest("button, a, th.sortable");
  if (!trigger) {
    return;
  }
  tableCard.classList.add("is-sticky");
  tableCard.scrollIntoView({ behavior: "smooth", block: "start" });
};

if (tableCard) {
  tableCard.addEventListener("click", handleTableAnchor);
  window.addEventListener("scroll", () => {
    const currentY = window.scrollY;
    if (currentY < lastScrollY && tableCard.classList.contains("is-sticky")) {
      tableCard.classList.remove("is-sticky");
    }
    lastScrollY = currentY;
  });
}

const formatCountdown = (totalSeconds) => {
  if (!Number.isFinite(totalSeconds) || totalSeconds <= 0) {
    return "00:00";
  }
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.floor(totalSeconds % 60);
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
};

const renderSessionStatus = (payload) => {
  if (!sessionStatusSection || !sessionStatusContent) {
    return;
  }
  const now = Math.floor(Date.now() / 1000);
  const state = payload?.state || "none";
  let message = "";

  if (state === "running") {
    message = "Sesión activa: procesando consulta.";
  } else if (state === "active") {
    const remaining = (payload.active_until || 0) - now;
    if (remaining > 0) {
      message = `Sesión activa (cierra en ${formatCountdown(remaining)}).`;
    }
  } else if (state === "cooldown") {
    const remaining = (payload.cooldown_until || 0) - now;
    if (remaining > 0) {
      message = `Espera de inactividad (reanuda en ${formatCountdown(remaining)}).`;
    }
  }

  if (!message) {
    sessionStatusSection.classList.remove("is-visible");
    sessionStatusContent.textContent = "";
    return;
  }

  sessionStatusSection.classList.add("is-visible");
  sessionStatusContent.textContent = message;
};

const updateSessionStatus = async () => {
  if (!sessionStatusSection) {
    return;
  }
  const statusUrl = sessionStatusSection.dataset.sessionStatusUrl;
  if (!statusUrl) {
    return;
  }
  try {
    const response = await fetch(statusUrl, { cache: "no-store" });
    if (!response.ok) {
      throw new Error("status failed");
    }
    const payload = await safeJson(response);
    lastSessionPayload = payload;
    renderSessionStatus(payload);
  } catch (error) {
    lastSessionPayload = { state: "none" };
    renderSessionStatus(lastSessionPayload);
  }
};

if (sessionStatusSection) {
  updateSessionStatus();
  setInterval(updateSessionStatus, 5000);
  setInterval(() => {
    if (lastSessionPayload) {
      renderSessionStatus(lastSessionPayload);
    }
  }, 1000);
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
    info.innerHTML = `<div class="upload-list__name">${file.name}</div><div class="upload-list__meta">${formatBytes(file.size)}</div>`;
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
      refreshImgTable();
    } catch (error) {
      showToast(error.message);
      setGenerateLoading(false);
    }
  });
}

let imgRefreshTimer = null;
const refreshImgTable = async () => {
  if (!imgRefreshCard || !imgTableBody) {
    return;
  }
  const url = imgRefreshCard.dataset.imgRefreshUrl;
  const interval = Number.parseInt(
    imgRefreshCard.dataset.imgRefreshInterval || "5000",
    10
  );
  if (!url || Number.isNaN(interval)) {
    return;
  }
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) {
      throw new Error("refresh failed");
    }
    const payload = await safeJson(response);
    imgTableBody.innerHTML = payload.html;
    if (payload.has_pending) {
      imgRefreshTimer = setTimeout(refreshImgTable, interval);
    } else {
      imgRefreshTimer = null;
    }
  } catch (error) {
    imgRefreshTimer = setTimeout(refreshImgTable, interval);
  }
};

if (imgRefreshCard && imgTableBody) {
  refreshImgTable();
}
