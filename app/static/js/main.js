const flashMessages = document.querySelectorAll(".flash");
flashMessages.forEach((message) => {
  setTimeout(() => {
    message.style.opacity = "0";
    message.style.transform = "translateY(-6px)";
  }, 3500);
});

const uppercaseInputs = document.querySelectorAll("input[data-uppercase='true']");
uppercaseInputs.forEach((input) => {
  input.addEventListener("input", () => {
    const cursor = input.selectionStart;
    input.value = input.value.toUpperCase();
    if (cursor !== null) {
      input.setSelectionRange(cursor, cursor);
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
