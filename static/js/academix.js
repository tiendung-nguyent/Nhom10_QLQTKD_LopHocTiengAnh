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
  let lastToastMsg = '';
  let lastToastTime = 0;

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
    if (!msg) return;
    const now = Date.now();
    const s = getStack();

    // 1. Chặn trùng lặp: Nếu thông báo cùng nội dung đang hiển thị trên màn hình -> Không tạo thêm
    const activeToasts = Array.from(s.querySelectorAll('.toast:not(.out)'));
    const isAlreadyShowing = activeToasts.some(t => {
      const msgEl = t.querySelector('.toast-msg');
      return msgEl && msgEl.textContent.trim() === String(msg).trim();
    });
    if (isAlreadyShowing) {
      return;
    }

    // 2. Chặn gọi trùng lặp liên tục trong khoảng thời gian cooldown (3.5s)
    if (msg === lastToastMsg && (now - lastToastTime) < Math.max(duration, 3500)) {
      return;
    }
    lastToastMsg = msg;
    lastToastTime = now;

    const icons = { info: 'ℹ️', success: '✅', warning: '⚠️', error: '❌', ai: '✦' };
    const t = document.createElement('div');
    t.className = 'toast';
    t.style.cursor = 'pointer';
    t.title = 'Bấm để tắt thông báo này';
    t.innerHTML = `
      <span class="toast-icon" style="font-size: 16px;">${icons[type] || icons.info}</span>
      <span class="toast-msg" style="font-size: 13px;">${msg}</span>
    `;
    s.appendChild(t);

    // Tự động tắt sau thời gian duration (chỉ hiện 1 lần rồi biến mất)
    const timer = setTimeout(() => {
      t.classList.add('out');
      setTimeout(() => t.remove(), 350);
    }, duration);

    // Bấm vào toast để đóng ngay lập tức
    t.onclick = () => {
      clearTimeout(timer);
      t.classList.add('out');
      setTimeout(() => t.remove(), 200);
    };
  }

  function clear() {
    const s = document.getElementById('toast-stack');
    if (s) {
      s.innerHTML = '';
    }
    lastToastMsg = '';
    lastToastTime = 0;
  }

  return { show, clear };
})();

// ─── 3. SIDEBAR DI ĐỘNG TOGGLE ───────────────────────────────
function toggleSidebar() {
  if (window.innerWidth <= 768) {
    const sb = document.getElementById('sidebar');
    if (sb) sb.classList.toggle('open');
  } else {
    document.body.classList.toggle('sidebar-collapsed');
    const isCollapsed = document.body.classList.contains('sidebar-collapsed');
    try {
      localStorage.setItem('sidebar_collapsed', isCollapsed ? '1' : '0');
    } catch(e) {}
  }
}

// Khởi tạo trạng thái sidebar thu gọn trên desktop nếu đã lưu trước đó
document.addEventListener('DOMContentLoaded', function() {
  try {
    if (window.innerWidth > 768 && localStorage.getItem('sidebar_collapsed') === '1') {
      document.body.classList.add('sidebar-collapsed');
    }
  } catch(e) {}
});

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


/**
 * Sap xep danh sach bang theo thoi gian (Toggle: Moi nhat <-> Cu nhat)
 * Tu dong dao chieu va cap nhat lai cot STT (1, 2, 3...)
 */
function toggleTableSortTime(tableId, btnElement, timeColIndex) {
  const table = document.getElementById(tableId);
  if (!table) return;
  const tbody = table.querySelector('tbody');
  if (!tbody) return;
  const rows = Array.from(tbody.querySelectorAll('tr')).filter(r => !r.querySelector('td[colspan]'));
  if (rows.length < 2) return;

  const isDesc = table.dataset.sortOrder !== 'asc';
  const newOrder = isDesc ? 'asc' : 'desc';
  table.dataset.sortOrder = newOrder;

  rows.sort((a, b) => {
    let tA = a.dataset.timestamp ? parseFloat(a.dataset.timestamp) : 0;
    let tB = b.dataset.timestamp ? parseFloat(b.dataset.timestamp) : 0;

    if (!tA || !tB) {
      const idx = (typeof timeColIndex === 'number') ? timeColIndex : 1;
      const textA = a.cells[idx] ? a.cells[idx].innerText.trim() : '';
      const textB = b.cells[idx] ? b.cells[idx].innerText.trim() : '';
      tA = Date.parse(textA) || 0;
      tB = Date.parse(textB) || 0;
    }

    return newOrder === 'asc' ? tA - tB : tB - tA;
  });

  rows.forEach(r => tbody.appendChild(r));

  rows.forEach((r, idx) => {
    const sttCell = r.querySelector('.stt-cell');
    if (sttCell) {
      sttCell.textContent = idx + 1;
    }
  });

  const sortBtn = btnElement || document.querySelector('[data-target-table="' + tableId + '"]');
  if (sortBtn) {
    const sortText = sortBtn.querySelector('.sort-text');
    const sortIcon = sortBtn.querySelector('i');
    if (newOrder === 'asc') {
      if (sortText) sortText.textContent = 'Xa nhất trước (Cũ → Mới)';
      if (sortIcon) sortIcon.className = 'fa-solid fa-arrow-up-wide-short';
      sortBtn.style.borderColor = 'var(--accent-purple)';
      sortBtn.style.color = 'var(--accent-purple)';
      sortBtn.style.background = 'rgba(139, 92, 246, 0.08)';
    } else {
      if (sortText) sortText.textContent = 'Gần nhất trước (Mới → Cũ)';
      if (sortIcon) sortIcon.className = 'fa-solid fa-arrow-down-wide-short';
      sortBtn.style.borderColor = '';
      sortBtn.style.color = '';
      sortBtn.style.background = '';
    }
  }


}
window.toggleTableSortTime = toggleTableSortTime;


function toggleTimelineSort(timelineId, btnElement) {
  const container = document.getElementById(timelineId);
  if (!container) return;
  const items = Array.from(container.querySelectorAll('.timeline-item'));
  if (items.length < 2) return;

  const isDesc = container.dataset.sortOrder !== 'asc';
  const newOrder = isDesc ? 'asc' : 'desc';
  container.dataset.sortOrder = newOrder;

  items.sort((a, b) => {
    const tA = parseFloat(a.dataset.timestamp) || 0;
    const tB = parseFloat(b.dataset.timestamp) || 0;
    return newOrder === 'asc' ? tA - tB : tB - tA;
  });

  items.forEach(item => container.appendChild(item));

  items.forEach((item, idx) => {
    const badge = item.querySelector('.timeline-stt-badge');
    if (badge) badge.textContent = '#' + (idx + 1);
  });

  if (btnElement) {
    const text = btnElement.querySelector('.sort-text');
    const icon = btnElement.querySelector('i');
    if (newOrder === 'asc') {
      if (text) text.textContent = 'Xa nhất trước (Cũ → Mới)';
      if (icon) icon.className = 'fa-solid fa-arrow-up-wide-short';
      btnElement.style.borderColor = 'var(--accent-purple)';
      btnElement.style.color = 'var(--accent-purple)';
    } else {
      if (text) text.textContent = 'Gần nhất trước (Mới → Cũ)';
      if (icon) icon.className = 'fa-solid fa-arrow-down-wide-short';
      btnElement.style.borderColor = '';
      btnElement.style.color = '';
    }
  }


}
window.toggleTimelineSort = toggleTimelineSort;
