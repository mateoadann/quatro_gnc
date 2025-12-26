const flashMessages = document.querySelectorAll(".flash");
flashMessages.forEach((message) => {
  setTimeout(() => {
    message.style.opacity = "0";
    message.style.transform = "translateY(-6px)";
  }, 3500);
});
