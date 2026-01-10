// Dark mode toggle functionality
const key = "adminlte-dark";

const hljsTheme = document.getElementById("hljsTheme");
const hljsDark = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css";
const hljsLight = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css";


function updateHighlightTheme(isDark) {
  if (hljsTheme) {
    hljsTheme.href = isDark ? hljsDark : hljsLight;
  }
}

function updateIcon() {
  const body = document.body;
  const darkIcon = document.getElementById("darkIcon");
  const lightIcon = document.getElementById("lightIcon");
  const darkModeText = document.getElementById("darkModeText");
  
  if (!darkIcon || !lightIcon || !darkModeText) return;
  
  if (body.classList.contains("dark-mode")) {
    darkIcon.style.display = "none";
    lightIcon.style.display = "inline-block";
    darkModeText.textContent = "Light";
  } else {
    darkIcon.style.display = "inline-block";
    lightIcon.style.display = "none";
    darkModeText.textContent = "Dark";
  }
}

// Wait for DOM to be ready
document.addEventListener("DOMContentLoaded", function() {
  const body = document.body;
  const toggle = document.getElementById("darkToggle");
  
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
      updateHighlightTheme(body.classList.contains("dark-mode"));
    };
  }
});
