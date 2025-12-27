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
    if (payload.has_pending) {
      refreshTimerId = setTimeout(refreshTable, interval);
    }
  } catch (error) {
    refreshTimerId = setTimeout(refreshTable, interval);
  }
};

if (refreshCard && refreshCard.dataset.autoRefresh === "true") {
  refreshTimerId = setTimeout(refreshTable, 2000);
}
