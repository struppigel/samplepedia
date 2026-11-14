/**
 * Cloudflare Turnstile (samples/_turnstile.html, loaded before the widget by _turnstile_script.html)
 * Enables a form's submit button once its challenge is solved: the widget names the
 * callback (data-callback="spTurnstileSolved") and the button to enable (data-submit-button).
 */

// Global: Turnstile looks the callback up by name
function spTurnstileSolved() {
  document.querySelectorAll('.cf-turnstile[data-submit-button]').forEach(function (widget) {
    const button = document.getElementById(widget.dataset.submitButton);
    if (button) {
      button.disabled = false;
    }
  });
}

// Fallback in case the challenge was solved without the callback firing
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.cf-turnstile[data-submit-button]').forEach(function (widget) {
    function solved() {
      const response = widget.querySelector('input[name="cf-turnstile-response"]');
      return Boolean(response && response.value);
    }
    if (solved()) {
      spTurnstileSolved();
      return;
    }
    const observer = new MutationObserver(function () {
      if (solved()) {
        spTurnstileSolved();
        observer.disconnect();
      }
    });
    observer.observe(widget, { childList: true, subtree: true });
  });
});
