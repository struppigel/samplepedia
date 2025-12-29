// Spoiler reveal functionality
document.addEventListener("click", function (e) {
  const el = e.target.closest(".spoiler");
  if (el) el.classList.toggle("revealed");
});
