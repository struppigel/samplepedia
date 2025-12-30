// Language toggle functionality for impressum page
const langKey = "impressum-lang";
const toggle = document.getElementById("langToggle");
const contentDe = document.getElementById("content-de");
const contentEn = document.getElementById("content-en");
const langDe = document.getElementById("langDe");
const langEn = document.getElementById("langEn");

function setLanguage(lang) {
  if (lang === "en") {
    contentDe.style.display = "none";
    contentEn.style.display = "block";
    langDe.style.display = "inline-block";
    langEn.style.display = "none";
  } else {
    contentDe.style.display = "block";
    contentEn.style.display = "none";
    langDe.style.display = "none";
    langEn.style.display = "inline-block";
  }
  localStorage.setItem(langKey, lang);
}

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
