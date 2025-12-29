// Dark mode initialization - must run before page renders
(function() {
  const key = "adminlte-dark";
  if (localStorage.getItem(key) === "on") {
    document.body.classList.add("dark-mode");
  }
})();
