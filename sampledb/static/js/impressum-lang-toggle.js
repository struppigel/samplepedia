// Language toggle functionality for impressum page
const langKey = "impressum-lang";

function setLanguage(lang) {
  const contentDe = document.getElementById("content-de");
  const contentEn = document.getElementById("content-en");
  const titleDe = document.getElementById("title-de");
  const titleEn = document.getElementById("title-en");
  const langDe = document.getElementById("langDe");
  const langEn = document.getElementById("langEn");
  
  if (lang === "en") {
    if (contentDe) contentDe.style.display = "none";
    if (contentEn) contentEn.style.display = "block";
    if (titleDe) titleDe.style.display = "none";
    if (titleEn) titleEn.style.display = "block";
    if (langDe) langDe.style.display = "inline-block";
    if (langEn) langEn.style.display = "none";
  } else {
    if (contentDe) contentDe.style.display = "block";
    if (contentEn) contentEn.style.display = "none";
    if (titleDe) titleDe.style.display = "block";
    if (titleEn) titleEn.style.display = "none";
    if (langDe) langDe.style.display = "none";
    if (langEn) langEn.style.display = "inline-block";
  }
  localStorage.setItem(langKey, lang);
}

// Wait for DOM to be ready
document.addEventListener("DOMContentLoaded", function() {
  const toggle = document.getElementById("langToggle");
  
  // Load saved language preference or default to German
  const savedLang = localStorage.getItem(langKey) || "de";
  setLanguage(savedLang);

  // Toggle language on button click
  if (toggle) {
    toggle.onclick = function (e) {
      e.preventDefault();
      const currentLang = localStorage.getItem(langKey) || "de";
      const newLang = currentLang === "de" ? "en" : "de";
      setLanguage(newLang);
    };
  }
});
