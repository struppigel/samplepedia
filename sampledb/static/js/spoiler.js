// Simple spoiler reveal (no animation)
document.addEventListener("click", function (e) {
  const el = e.target.closest(".spoiler");
  if (el && !el.classList.contains('revealed')) {
    el.classList.add('revealed');
  }
});
