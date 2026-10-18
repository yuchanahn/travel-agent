'use strict';
// Apply before styles paint, including when localStorage is unavailable.
let savedTheme = 'dark';
try { savedTheme = localStorage.getItem('travel-agent-theme') || 'dark'; } catch { }
document.documentElement.dataset.theme = savedTheme === 'light' ? 'light' : 'dark';
function toggleTheme() {
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem('travel-agent-theme', theme); } catch { }
  updateThemeButton();
}
function updateThemeButton() {
  const button = document.getElementById('theme-toggle');
  const dark = document.documentElement.dataset.theme === 'dark';
  button.textContent = dark ? '☀ 라이트' : '☾ 다크';
  button.setAttribute('aria-label', dark ? '라이트 모드로 전환' : '다크 모드로 전환');
  button.setAttribute('aria-pressed', String(dark));
}
