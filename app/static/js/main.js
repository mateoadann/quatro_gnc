const flashMessages = document.querySelectorAll(".flash");
flashMessages.forEach((message) => {
  setTimeout(() => {
    message.classList.add("dismissed");
    setTimeout(() => {
      message.remove();
    }, 250);
  }, 3500);
});

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
      isPassword ? "Ocultar contrasena" : "Mostrar contrasena"
    );
    button.setAttribute("aria-pressed", isPassword ? "true" : "false");
  });
});

const refreshCard = document.querySelector("[data-refresh-url]");
const refreshBody = document.querySelector("#rpa-table-body");
const refreshPagination = document.querySelector("#rpa-pagination");
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
    const payload = await response.json();
    refreshBody.innerHTML = payload.html;
    if (refreshPagination && payload.pagination !== undefined) {
      refreshPagination.innerHTML = payload.pagination;
    }
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

const createOptimisticRow = (patente, placeholderId) => {
  const row = document.createElement("tr");
  row.dataset.placeholderId = placeholderId;
  row.classList.add("pending-row");
  row.innerHTML = `
    <td>${new Date().toLocaleString("es-AR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })}</td>
    <td>${patente}</td>
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

const rpaForm = document.querySelector("form.form-grid");
if (rpaForm) {
  rpaForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(rpaForm);
    const patente = formData.get("patente") || "";
    const placeholderId = `pending-${Date.now()}`;
    if (refreshBody) {
      const row = createOptimisticRow(patente, placeholderId);
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
      const payload = await response.json();
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
      ensureTableRefresh();
      rpaForm.reset();
    } catch (error) {
      const placeholder = refreshBody?.querySelector(
        `[data-placeholder-id="${placeholderId}"]`
      );
      if (placeholder) {
        placeholder.remove();
      }
      window.alert(error.message);
    }
  });
}

if (refreshBody) {
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
      const statusCell = row.querySelector("td:nth-child(3)");
      if (statusCell) {
        statusCell.innerHTML = '<span class="badge en-proceso">en proceso</span>';
      }
      const resultCell = row.querySelector("td:nth-child(4)");
      if (resultCell) {
        resultCell.textContent = "-";
      }
      const detailCell = row.querySelector("td:nth-child(5)");
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
      const payload = await response.json();
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
      window.alert(error.message);
    }
  });
}

const sessionStatusSection = document.querySelector("[data-session-status-url]");
const sessionStatusContent = document.querySelector("#rpa-session-status");
let lastSessionPayload = null;

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
    const payload = await response.json();
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
