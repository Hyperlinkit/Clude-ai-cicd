// public/js/main.js

document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('action-btn');

  if (btn) {
    btn.addEventListener('click', handleAction);
  }
});

async function handleAction() {
  try {
    const response = await fetch('/api/hello');
    if (!response.ok) throw new Error(`HTTP error: ${response.status}`);
    const data = await response.json();
    alert(data.message);
  } catch (err) {
    console.error('Request failed:', err);
  }
}
