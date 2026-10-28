/* ============================================================
   ACADEMIX — Dashboard JavaScript Core
   Trung tâm Anh ngữ | Nhóm 10 QLQTKD
   ============================================================ */

'use strict';

// ─── 1. QUẢN LÝ THEME (LIGHT / DARK MODE) ────────────────────
const ThemeManager = (() => {
  const KEY = 'academix_theme';
  const root = document.documentElement;

  function apply(theme) {
    root.setAttribute('data-theme', theme);
    localStorage.setItem(KEY, theme);
    const icon = document.getElementById('theme-icon');
    if (icon) icon.textContent = theme === 'dark' ? '☀️' : '🌙';
    
    // Đồng bộ nút Sun/Moon trong Capsule Pill Toggle
    const sunBtn = document.getElementById('theme-sun-btn');
    const moonBtn = document.getElementById('theme-moon-btn');
    if (sunBtn && moonBtn) {
      if (theme === 'dark') {
        moonBtn.classList.add('active');
        sunBtn.classList.remove('active');
      } else {
        sunBtn.classList.add('active');
        moonBtn.classList.remove('active');
      }
    }
  }

  function toggle() {
    const cur = root.getAttribute('data-theme') || 'light';
    apply(cur === 'dark' ? 'light' : 'dark');
  }

  function init() {
    apply(localStorage.getItem(KEY) || 'light');
  }

  return { init, toggle };
})();

// ─── 2. TOAST NOTIFICATIONS ──────────────────────────────────
const Toast = (() => {
  let stack = null;

  function getStack() {
    if (!stack) {
      stack = document.getElementById('toast-stack');
      if (!stack) {
        stack = document.createElement('div');
        stack.id = 'toast-stack';
        stack.className = 'toast-stack';
        document.body.appendChild(stack);
      }
    }
    return stack;
  }

  function show(msg, type = 'info', duration = 3500) {
    const icons = { info: 'ℹ️', success: '✅', warning: '⚠️', error: '❌', ai: '✦' };
    const s = getStack();
    const t = document.createElement('div');
    t.className = 'toast';
    t.innerHTML = `
      <span class="toast-icon" style="font-size: 16px;">${icons[type] || icons.info}</span>
      <span class="toast-msg" style="font-size: 13px;">${msg}</span>
    `;
    s.appendChild(t);

    setTimeout(() => {
      t.classList.add('out');
      setTimeout(() => t.remove(), 350);
    }, duration);
  }

  return { show };
})();

// ─── 3. SIDEBAR DI ĐỘNG TOGGLE ───────────────────────────────
function toggleSidebar() {
  const sb = document.getElementById('sidebar');
  if (sb) sb.classList.toggle('open');
}

// ─── 4. ĐÁNH DẤU MENU ACTIVE ─────────────────────────────────
function setActiveNav() {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-item').forEach(item => {
    const href = item.getAttribute('data-href') || item.getAttribute('href');
    if (href && path.startsWith(href) && href !== '/' && href !== '#') {
      item.classList.add('active');
    }
  });
}

// ─── 5. BỘ CHUYỂN TAB (TAB SWITCHER HIỆN ĐẠI ĐỒNG BỘ) ─────────
function initTabs() {
  document.querySelectorAll('[data-tab-group]').forEach(group => {
    const id = group.dataset.tabGroup;
    const tabs = group.querySelectorAll(`[data-tab="${id}"]`);
    const panels = group.querySelectorAll(`[data-tab-panel="${id}"]`);

    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        const target = tab.dataset.tabTarget;
        // Bỏ active trên toàn bộ tabs thuộc group
        tabs.forEach(t => t.classList.remove('active'));
        // Ẩn tất cả panels
        panels.forEach(p => p.style.display = 'none');
        // Kích hoạt tất cả tabs có cùng target (đồng bộ cả Hero Cards và Segmented Pills)
        group.querySelectorAll(`[data-tab="${id}"][data-tab-target="${target}"]`).forEach(t => t.classList.add('active'));
        // Hiển thị panel tương ứng
        const panel = group.querySelector(`[data-tab-panel="${id}"][data-panel="${target}"]`);
        if (panel) panel.style.display = 'block';
      });
    });
  });
}

// ─── LIVE DATE DISPLAY ───────────────────────────────────────
function initLiveDate() {
  const dateEl = document.getElementById('header-live-date');
  if (dateEl) {
    const now = new Date();
    const options = { day: 'numeric', month: 'long', year: 'numeric' };
    try {
      dateEl.textContent = now.toLocaleDateString('vi-VN', options);
    } catch (e) {
      dateEl.textContent = now.toLocaleDateString('en-GB', options);
    }
  }
}

// ─── 6. BỘ LỰA CHỌN CÂU HỎI TRẮC NGHIỆM ─────────────────────
function initMCQOptions() {
  document.querySelectorAll('.option-item').forEach(item => {
    item.addEventListener('click', () => {
      const group = item.closest('.option-list');
      if (!group) return;
      group.querySelectorAll('.option-item').forEach(i => i.classList.remove('selected'));
      item.classList.add('selected');
      const radio = item.querySelector('input[type="radio"]');
      if (radio) radio.checked = true;
    });
  });
}

// ─── 7. ANIMATION CONIC SCORE RINGS ──────────────────────────
function animateScoreRings() {
  document.querySelectorAll('.score-ring').forEach(ring => {
    const pct = parseFloat(ring.dataset.pct || 72);
    let cur = 0;
    const step = pct / 50;
    const iv = setInterval(() => {
      cur = Math.min(cur + step, pct);
      ring.style.setProperty('--pct', cur.toFixed(1));
      if (cur >= pct) clearInterval(iv);
    }, 16);
  });
}

// ─── 8. ANIMATION CRITERIA PROGRESS BARS ─────────────────────
function animateBars() {
  document.querySelectorAll('.criterion-fill, .bar-fill, .capacity-fill').forEach(bar => {
    const w = bar.dataset.width || bar.style.width || '0%';
    bar.style.width = '0%';
    setTimeout(() => { bar.style.width = w; }, 200);
  });
}

// ─── 9. WEB AUDIO RECORDER API CHO SPEAKING ──────────────────
const AudioRecorder = (() => {
  let mediaRecorder = null;
  let audioChunks = [];
  let timerInterval = null;
  let seconds = 0;
  let stream = null;

  function formatTime(s) {
    const m = Math.floor(s / 60);
    return `${String(m).padStart(2,'0')}:${String(s % 60).padStart(2,'0')}`;
  }

  async function start(opts = {}) {
    const btn   = document.getElementById(opts.btnId || 'record-btn');
    const timer = document.getElementById(opts.timerId || 'timer-display');
    const wave  = document.getElementById(opts.waveId || 'audio-wave');
    const area  = document.getElementById(opts.areaId || 'recorder-area');
    const label = document.getElementById(opts.labelId || 'record-label');

    if (!btn) return;

    btn.addEventListener('click', async () => {
      if (!mediaRecorder || mediaRecorder.state === 'inactive') {
        // Bắt đầu ghi âm
        try {
          stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          mediaRecorder = new MediaRecorder(stream);
          audioChunks = [];
          seconds = 0;

          mediaRecorder.ondataavailable = e => {
            if (e.data.size > 0) audioChunks.push(e.data);
          };

          mediaRecorder.onstop = () => {
            const blob = new Blob(audioChunks, { type: 'audio/webm' });
            const url = URL.createObjectURL(blob);
            const preview = document.getElementById('audio-preview');
            const previewWrapper = document.getElementById('preview-wrapper');
            if (preview && previewWrapper) {
              preview.src = url;
              previewWrapper.style.display = 'block';
            }

            const input = document.getElementById('audio-input');
            if (input) {
              const file = new File([blob], 'candidate_speaking.webm', { type: 'audio/webm' });
              const dt = new DataTransfer();
              dt.items.add(file);
              input.files = dt.files;
            }

            if (area) area.classList.remove('recording');
            if (wave) wave.style.display = 'none';
            if (label) label.textContent = 'Đã hoàn tất ghi âm! Bạn có thể nghe lại bên dưới.';
            btn.innerHTML = '🎙️';
            btn.className = 'record-btn idle';
            Toast.show('Ghi âm hoàn tất! Hãy nghe lại trước khi nộp.', 'success');

            if (stream) stream.getTracks().forEach(t => t.stop());
          };

          mediaRecorder.start(100);
          btn.innerHTML = '⏹️';
          btn.className = 'record-btn active';
          if (area) area.classList.add('recording');
          if (wave) wave.style.display = 'flex';
          if (label) label.textContent = 'Đang ghi âm bài nói… Nhấn ⏹️ để dừng lại';
          if (timer) { timer.textContent = '00:00'; timer.style.display = 'block'; }

          timerInterval = setInterval(() => {
            seconds++;
            if (timer) timer.textContent = formatTime(seconds);
            if (seconds >= 180) stopRecording(); // Giới hạn 3 phút
          }, 1000);

        } catch (err) {
          // Fallback giả lập nếu trình duyệt chặn mic
          Toast.show('Microphone chưa bật, đang kích hoạt bộ ghi âm mô phỏng...', 'info');
          simulateRecording(btn, timer, wave, area, label);
        }
      } else {
        stopRecording();
      }
    });

    function stopRecording() {
      if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
      }
      clearInterval(timerInterval);
    }

    function simulateRecording(btn, timer, wave, area, label) {
      seconds = 0;
      btn.innerHTML = '⏹️';
      btn.className = 'record-btn active';
      if (area) area.classList.add('recording');
      if (wave) wave.style.display = 'flex';
      if (label) label.textContent = 'Đang thu âm mô phỏng… Nhấn ⏹️ để hoàn tất';
      if (timer) { timer.textContent = '00:00'; timer.style.display = 'block'; }

      timerInterval = setInterval(() => {
        seconds++;
        if (timer) timer.textContent = formatTime(seconds);
        if (seconds >= 15) {
          clearInterval(timerInterval);
          btn.innerHTML = '🎙️';
          btn.className = 'record-btn idle';
          if (area) area.classList.remove('recording');
          if (wave) wave.style.display = 'none';
          if (label) label.textContent = 'Đã hoàn tất ghi âm mô phỏng! Sẵn sàng nộp cho AI.';
          const previewWrapper = document.getElementById('preview-wrapper');
          if (previewWrapper) previewWrapper.style.display = 'block';
          Toast.show('Đã hoàn thành ghi âm mô phỏng!', 'success');
        }
      }, 1000);
    }
  }

  return { start };
})();

// ─── 10. MODAL HELPERS ───────────────────────────────────────
function openModal(id)  { document.getElementById(id)?.classList.add('show'); }
function closeModal(id) { document.getElementById(id)?.classList.remove('show'); }

// ─── 11. KHỞI TẠO TẤT CẢ MODULE KHI DOM SẴN SÀNG ─────────────
document.addEventListener('DOMContentLoaded', () => {
  ThemeManager.init();
  setActiveNav();
  initLiveDate();
  initTabs();
  initMCQOptions();
  animateScoreRings();
  animateBars();

  // Nút Theme Toggle
  const themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) themeBtn.addEventListener('click', ThemeManager.toggle);

  // Nút Mobile Menu Sidebar
  const menuBtn = document.getElementById('menu-toggle');
  if (menuBtn) {
    menuBtn.style.display = window.innerWidth <= 768 ? 'flex' : 'none';
    menuBtn.addEventListener('click', toggleSidebar);
    window.addEventListener('resize', () => {
      menuBtn.style.display = window.innerWidth <= 768 ? 'flex' : 'none';
    });
  }

  // Khởi động Audio Recorder nếu có trên trang
  if (document.getElementById('record-btn')) {
    AudioRecorder.start({
      btnId: 'record-btn',
      timerId: 'timer-display',
      waveId: 'audio-wave',
      areaId: 'recorder-area',
      labelId: 'record-label',
    });
  }

  // Dropdown Thông báo Top Header
  const notifBtn = document.getElementById('notif-btn');
  const notifPopover = document.getElementById('notif-popover');
  if (notifBtn && notifPopover) {
    notifBtn.addEventListener('click', e => {
      e.stopPropagation();
      notifPopover.classList.toggle('show');
      document.getElementById('user-dropdown')?.classList.remove('show');
    });
  }

  // Dropdown Avatar Người dùng Top Header
  const userAvatarBtn = document.getElementById('user-avatar-btn');
  const userDropdown = document.getElementById('user-dropdown');
  if (userAvatarBtn && userDropdown) {
    userAvatarBtn.addEventListener('click', e => {
      e.stopPropagation();
      userDropdown.classList.toggle('show');
      notifPopover?.classList.remove('show');
    });
  }

  // Đóng các dropdown khi click ra ngoài
  document.addEventListener('click', () => {
    notifPopover?.classList.remove('show');
    userDropdown?.classList.remove('show');
  });

  // Modal overlay click outside để đóng
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', e => {
      if (e.target === overlay) overlay.classList.remove('show');
    });
  });
});
