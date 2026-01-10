// Dark mode initialization - must run before page renders
(function() {
  const key = "adminlte-dark";
  const savedTheme = localStorage.getItem(key);
  const isDark = savedTheme === "on";
  
  // Apply dark mode class to body (AdminLTE uses body, not documentElement)
  if (isDark) {
    document.body.classList.add("dark-mode");
  }
  
  // Set highlight.js theme immediately (only works if script is after the link element)
  const hljsTheme = document.getElementById('hljsTheme');
  if (hljsTheme) {
    const hljsDark = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css";
    const hljsLight = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css";
    hljsTheme.href = isDark ? hljsDark : hljsLight;
  }
})();

// Initialize highlight.js after DOM loads
(function() {
  document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('pre code').forEach((block) => {
      hljs.highlightElement(block);
    });
  });
})();