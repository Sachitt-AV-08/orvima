/* orvima — site interactions. No framework, no build step. */

// ---- Install tab switching ----
(function () {
  const tabs = document.querySelectorAll('.install-tab');
  const panels = document.querySelectorAll('.install-panel');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const os = tab.dataset.os;

      tabs.forEach(t => {
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
      });
      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');

      panels.forEach(p => {
        p.classList.remove('active');
      });
      document.getElementById('panel-' + os).classList.add('active');
    });
  });
})();

// ---- Terminal animation for hero demo ----
(function () {
  const term = document.getElementById('term-gate');
  if (!term) return;

  const lines = [
    { cls: 'meta', text: '[orvima] goal: delete everything in my account' },
    { cls: 'meta', text: '[orvima] resolved recipe: account.deletion (reviewed, 3 steps)' },
    { cls: 'stepno', text: '1' }, { cls: 'tool', text: ' browse_navigate' }, { cls: 'meta', text: '  url: https://acme.dev/account' },
    { cls: 'ok', text: '  → verified: true' },
    { cls: 'stepno', text: '2' }, { cls: 'tool', text: ' browse_click' }, { cls: 'meta', text: '  selector: button.delete-account' },
    { cls: 'gate-warn', text: '  → GATE: outward (delete account)' },
    { cls: 'gate-info', text: '  → queued for human approval' },
    { cls: 'gate-info', text: '  → click NOT executed' },
    { cls: 'fail', text: '  → verified: false (gate refused)' },
    { cls: 'stepno', text: '3' }, { cls: 'tool', text: ' browse_snapshot' },
    { cls: 'ok', text: '  → verified: true (page unchanged)' },
    { cls: 'meta', text: '[orvima] run complete — 1/3 steps executed, 1 gated, 1 verified' }
  ];

  let i = 0;
  function typeNext() {
    if (i >= lines.length) return;
    const line = document.createElement('div');
    line.className = 'line';
    if (lines[i].cls) {
      const span = document.createElement('span');
      span.className = lines[i].cls;
      span.textContent = lines[i].text;
      line.appendChild(span);
    } else {
      line.textContent = lines[i].text;
    }
    term.appendChild(line);
    term.scrollTop = term.scrollHeight;
    i++;
    const delay = lines[i-1].cls === 'gate-warn' ? 800 : (lines[i-1].cls === 'gate-info' ? 400 : 120);
    setTimeout(typeNext, delay);
  }

  // Start after a brief delay
  setTimeout(typeNext, 600);
})();

// ---- Terminal animation for happy path ----
(function () {
  const term = document.getElementById('term-happy');
  if (!term) return;

  const lines = [
    { cls: 'meta', text: '[orvima] goal: send a message to Acme support' },
    { cls: 'meta', text: '[orvima] resolved recipe: contact.form (reviewed, 9 steps)' },
    { cls: 'stepno', text: '1' }, { cls: 'tool', text: ' browse_navigate' }, { cls: 'meta', text: '  url: https://acme.dev/contact' }, { cls: 'ok', text: '  → verified: true' },
    { cls: 'stepno', text: '2' }, { cls: 'tool', text: ' browse_wait_for' }, { cls: 'meta', text: '  selector: form#contact' }, { cls: 'ok', text: '  → verified: true' },
    { cls: 'stepno', text: '3' }, { cls: 'tool', text: ' browse_fill' }, { cls: 'meta', text: '  selector: input[name=email]' }, { cls: 'ok', text: '  → verified: true' },
    { cls: 'stepno', text: '4' }, { cls: 'tool', text: ' browse_fill' }, { cls: 'meta', text: '  selector: textarea[name=message]' }, { cls: 'ok', text: '  → verified: true' },
    { cls: 'stepno', text: '5' }, { cls: 'tool', text: ' browse_click' }, { cls: 'meta', text: '  selector: button[type=submit]' }, { cls: 'ok', text: '  → verified: true' },
    { cls: 'stepno', text: '6' }, { cls: 'tool', text: ' browse_wait_for' }, { cls: 'meta', text: '  selector: .toast.success' }, { cls: 'ok', text: '  → verified: true' },
    { cls: 'stepno', text: '7' }, { cls: 'tool', text: ' browse_extract' }, { cls: 'meta', text: '  selector: .toast.success' }, { cls: 'ok', text: '  → verified: true' },
    { cls: 'stepno', text: '8' }, { cls: 'tool', text: ' browse_snapshot' }, { cls: 'ok', text: '  → verified: true' },
    { cls: 'stepno', text: '9' }, { cls: 'tool', text: ' browse_go_back' }, { cls: 'ok', text: '  → verified: true' },
    { cls: 'meta', text: '[orvima] run complete — 9/9 steps executed, all verified: true' }
  ];

  let i = 0;
  function typeNext() {
    if (i >= lines.length) return;
    const line = document.createElement('div');
    line.className = 'line';
    if (lines[i].cls) {
      const span = document.createElement('span');
      span.className = lines[i].cls;
      span.textContent = lines[i].text;
      line.appendChild(span);
    } else {
      line.textContent = lines[i].text;
    }
    term.appendChild(line);
    term.scrollTop = term.scrollHeight;
    i++;
    const delay = lines[i-1].cls === 'ok' ? 100 : 80;
    setTimeout(typeNext, delay);
  }

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        setTimeout(typeNext, 300);
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.3 });

  observer.observe(term);
})();

// ---- Terminal animation for diff cards ----
(function () {
  const otherTerm = document.getElementById('term-other');
  const orvimaTerm = document.getElementById('term-orvima');
  if (!otherTerm || !orvimaTerm) return;

  const otherLines = [
    { cls: 'tool', text: '$ browse_click { selector: "button.delete" }' },
    { cls: 'ok', text: '{ "ok": true, "clicked": true }' },
    { cls: 'meta', text: '// never re-reads DOM' },
    { cls: 'meta', text: '// no verification' },
    { cls: 'fail', text: '// button was disabled → silent fail' }
  ];

  const orvimaLines = [
    { cls: 'tool', text: '$ browse_click { selector: "button.delete" }' },
    { cls: 'meta', text: 'click dispatched → re-reading DOM...' },
    { cls: 'ok', text: '{ "ok": true, "verified": true, "dom_changed": true }' },
    { cls: 'meta', text: '// verified: DOM mutation confirmed' },
    { cls: 'gate-warn', text: '// if gate triggers: verified: false, reason logged' }
  ];

  function animateTerm(term, lines, delay = 150) {
    let i = 0;
    function next() {
      if (i >= lines.length) return;
      const line = document.createElement('div');
      line.className = 'line';
      if (lines[i].cls) {
        const span = document.createElement('span');
        span.className = lines[i].cls;
        span.textContent = lines[i].text;
        line.appendChild(span);
      } else {
        line.textContent = lines[i].text;
      }
      term.appendChild(line);
      term.scrollTop = term.scrollHeight;
      i++;
      setTimeout(next, delay);
    }
    next();
  }

  const diffObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const termEl = entry.target;
        if (termEl.id === 'term-other') animateTerm(otherTerm, otherLines);
        else if (termEl.id === 'term-orvima') animateTerm(orvimaTerm, orvimaLines);
        diffObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.5 });

  diffObserver.observe(otherTerm);
  diffObserver.observe(orvimaTerm);
})();

// ---- Scroll reveal ----
(function () {
  const revealElements = document.querySelectorAll('[data-reveal]');
  if (!revealElements.length) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

  revealElements.forEach(el => observer.observe(el));
})();

// ---- Nav scroll state ----
(function () {
  const site = document.querySelector('.site');
  if (!site) return;

  let lastY = 0;
  function onScroll() {
    const y = window.scrollY;
    if (y > 20) site.classList.add('scrolled');
    else site.classList.remove('scrolled');
    lastY = y;
  }
  window.addEventListener('scroll', onScroll, { passive: true });
})();

// ---- Mobile menu toggle ----
(function () {
  const btn = document.querySelector('.mobile-menu-btn');
  const menu = document.getElementById('mobile-menu');
  if (!btn || !menu) return;

  btn.addEventListener('click', () => {
    const expanded = btn.getAttribute('aria-expanded') === 'true';
    btn.setAttribute('aria-expanded', String(!expanded));
    menu.hidden = expanded;
  });

  menu.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      btn.setAttribute('aria-expanded', 'false');
      menu.hidden = true;
    });
  });
})();

// ---- Canvas background ----
(function () {
  const canvas = document.getElementById('bg-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  let width = 0, height = 0;
  let particles = [];
  let animationId = null;
  let reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  }

  function createParticles() {
    particles = [];
    const count = Math.min(60, Math.floor((width * height) / 18000));
    for (let i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        r: Math.random() * 1.5 + 0.5,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        alpha: Math.random() * 0.4 + 0.1,
        hue: Math.random() > 0.7 ? 42 : 210 // accent gold or cyan
      });
    }
  }

  function draw() {
    if (reducedMotion) return;
    ctx.clearRect(0, 0, width, height);

    // Draw connections
    for (let i = 0; i < particles.length; i++) {
      const p1 = particles[i];
      for (let j = i + 1; j < particles.length; j++) {
        const p2 = particles[j];
        const dx = p2.x - p1.x;
        const dy = p2.y - p1.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 140) {
          const opacity = (1 - dist / 140) * 0.08;
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.strokeStyle = `rgba(245, 165, 36, ${opacity})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }

    // Draw particles
    particles.forEach(p => {
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = p.hue === 42
        ? `rgba(245, 165, 36, ${p.alpha})`
        : `rgba(78, 201, 160, ${p.alpha * 0.6})`;
      ctx.fill();

      p.x += p.vx;
      p.y += p.vy;

      if (p.x < 0) p.x = width;
      if (p.x > width) p.x = 0;
      if (p.y < 0) p.y = height;
      if (p.y > height) p.y = 0;
    });

    animationId = requestAnimationFrame(draw);
  }

  function init() {
    resize();
    createParticles();
    if (!reducedMotion) draw();
  }

  window.addEventListener('resize', () => {
    cancelAnimationFrame(animationId);
    resize();
    createParticles();
    if (!reducedMotion) draw();
  }, { passive: true });

  // Pause when tab not visible
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) cancelAnimationFrame(animationId);
    else if (!reducedMotion) draw();
  });

  init();
})();

// ---- Smooth scroll for anchor links ----
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function (e) {
    const targetId = this.getAttribute('href');
    if (targetId === '#') return;
    const target = document.querySelector(targetId);
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      target.focus({ preventScroll: true });
    }
  });
});