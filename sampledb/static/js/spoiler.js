// Decryption animation for spoilers
const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+-=[]{}|;:,.<>?';

function decryptText(element) {
  const textEl = element.querySelector('.spoiler-text');
  const originalHTML = textEl.innerHTML;
  
  // Extract text content without HTML tags
  const tempDiv = document.createElement('div');
  tempDiv.innerHTML = originalHTML;
  const originalText = tempDiv.textContent || tempDiv.innerText;
  
  if (element.classList.contains('revealed')) return;
  
  element.classList.add('decrypting');
  
  let iteration = 0;
  const totalIterations = 20;
  const textLength = originalText.length;
  
  const interval = setInterval(() => {
    let scrambled = '';
    
    for (let i = 0; i < textLength; i++) {
      if (originalText[i] === ' ' || originalText[i] === '\n') {
        scrambled += originalText[i];
      } else if (i < (textLength * iteration) / totalIterations) {
        scrambled += originalText[i];
      } else {
        scrambled += chars[Math.floor(Math.random() * chars.length)];
      }
    }
    
    textEl.textContent = scrambled;
    
    iteration++;
    
    if (iteration > totalIterations) {
      clearInterval(interval);
      textEl.innerHTML = originalHTML;
      element.classList.remove('decrypting');
      element.classList.add('revealed');
    }
  }, 40);
}

document.addEventListener("click", function (e) {
  const el = e.target.closest(".spoiler");
  if (el && !el.classList.contains('revealed') && !el.classList.contains('decrypting')) {
    decryptText(el);
  }
});
