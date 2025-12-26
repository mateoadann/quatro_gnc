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
