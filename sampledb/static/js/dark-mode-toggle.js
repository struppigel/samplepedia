// Dark mode toggle functionality
const key = "adminlte-dark";
const body = document.body;
const toggle = document.getElementById("darkToggle");
const darkIcon = document.getElementById("darkIcon");
const lightIcon = document.getElementById("lightIcon");
const darkModeText = document.getElementById("darkModeText");

function updateIcon() {
  if (body.classList.contains("dark-mode")) {
    darkIcon.style.display = "none";
    lightIcon.style.display = "inline-block";
    if (darkModeText) darkModeText.textContent = "Light";
  } else {
    darkIcon.style.display = "inline-block";
    lightIcon.style.display = "none";
    if (darkModeText) darkModeText.textContent = "Dark";
  }
}

// Update icon on page load
updateIcon();

if (toggle) {
  toggle.onclick = function (e) {
    e.preventDefault();
    body.classList.toggle("dark-mode");
    localStorage.setItem(
      key,
      body.classList.contains("dark-mode") ? "on" : "off"
    );
    updateIcon();
  };
}
