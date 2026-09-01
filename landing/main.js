const revealObserver = new IntersectionObserver((entries) => entries.forEach((entry) => entry.isIntersecting && entry.target.classList.add('visible')), { threshold: 0.12 });
document.querySelectorAll('.reveal').forEach((element) => revealObserver.observe(element));
document.querySelectorAll('[data-count]').forEach((element) => {
  const target = Number(element.dataset.count);
  let current = 0;
  const tick = () => { current = Math.min(target, current + Math.ceil(target / 30)); element.textContent = current + (target === 85 ? '%' : ''); if (current < target) requestAnimationFrame(tick); };
  const observer = new IntersectionObserver(([entry]) => { if (entry.isIntersecting) { tick(); observer.disconnect(); } });
  observer.observe(element);
});
document.getElementById('stress').addEventListener('click', () => {
  document.getElementById('moisture').textContent = '15%';
  document.getElementById('moisture-bar').style.width = '15%';
  document.getElementById('moisture-bar').style.background = '#ff786e';
  const alert = document.getElementById('mock-alert');
  alert.textContent = '⚠ Stress detected · Irrigation recommended';
  alert.style.color = '#ff786e';
});
