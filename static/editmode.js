/**
 * PEI Tools -- DevTools Edit Mode
 * localhost only. User edits freely with Inspect Element.
 * Save captures the full page HTML and writes it back to the template file.
 */
(function () {
  'use strict';

  if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') return;

  const template = document.body.dataset.template || '';

  // --- Build the floating bar ---
  const bar = document.createElement('div');
  bar.id = 'pei-bar';
  bar.style.cssText = `
    position: fixed; bottom: 20px; right: 20px; z-index: 999999;
    display: flex; align-items: center; gap: 8px;
    background: #111d30; border: 1px solid rgba(96,180,240,0.4);
    border-radius: 10px; padding: 8px 14px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.6);
    font-family: 'Inter', sans-serif; font-size: 0.78rem;
  `;
  bar.innerHTML = `
    <span style="color:rgba(255,255,255,0.4);font-size:0.72rem;">localhost</span>
    <div style="width:1px;height:20px;background:rgba(255,255,255,0.1)"></div>
    <span style="color:rgba(255,255,255,0.35);font-size:0.72rem;">
      Edit with Inspect Element, then Save
    </span>
    <button id="pei-deploy" style="
      padding:6px 16px;border-radius:7px;border:none;cursor:pointer;
      background:#16a34a;color:white;font-weight:700;font-size:0.78rem;
    ">&#8593; Deploy to Live</button>
    <button id="pei-reset" style="
      padding:6px 12px;border-radius:7px;border:none;cursor:pointer;
      background:rgba(255,255,255,0.08);color:rgba(255,255,255,0.5);
      font-weight:600;font-size:0.78rem;
    ">Reset</button>
  `;

  document.addEventListener('DOMContentLoaded', () => {
    document.body.appendChild(bar);
    document.getElementById('pei-deploy').addEventListener('click', deployToLive);
    document.getElementById('pei-reset').addEventListener('click', () => {
      if (confirm('Reload page and discard all unsaved changes?')) location.reload();
    });
  });

  // --- Capture full page HTML, strip injected scripts/bar ---
  function getCleanHTML() {
    const clone = document.documentElement.cloneNode(true);

    // Remove our editmode bar
    const bar = clone.querySelector('#pei-bar');
    if (bar) bar.remove();
    const toast = clone.querySelector('#pei-toast');
    if (toast) toast.remove();

    // Remove injected editmode scripts (not in the original template)
    clone.querySelectorAll('script').forEach(s => {
      if (s.src && s.src.includes('editmode.js')) s.remove();
      if (s.textContent && s.textContent.includes('pei-bar')) s.remove();
      if (s.textContent && s.textContent.includes('_rendered_template')) s.remove();
    });

    return clone.outerHTML;
  }

  // --- Deploy to live site ---
  async function deployToLive() {
    if (!confirm('Push all local changes to peitools.com?')) return;
    const btn = document.getElementById('pei-deploy');
    btn.textContent = 'Deploying...';
    btn.disabled = true;
    try {
      const res  = await fetch('/admin/deploy', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Deploy failed');
      showToast(data.message || 'Deployed!', true);
    } catch(e) {
      showToast('Error: ' + e.message, false);
    } finally {
      btn.textContent = '↑ Deploy to Live';
      btn.disabled = false;
    }
  }

  // --- Save (kept for compatibility) ---
  async function saveChanges() {
    if (!template) {
      showToast('No template name set on this page.', false);
      return;
    }

    const btn = document.getElementById('pei-save');
    btn.textContent = 'Saving...';
    btn.disabled = true;

    try {
      const html = getCleanHTML();
      const tmpl = document.body.dataset.template || template;

      if (!tmpl) {
        showToast('No template name found — cannot save.', false);
        btn.textContent = 'Save Changes'; btn.disabled = false;
        return;
      }

      const res = await fetch('/admin/save-page-edits', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template: tmpl, full_html: html })
      });

      const text = await res.text();
      let data;
      try { data = JSON.parse(text); }
      catch(e) {
        // Server returned HTML — show status and first 120 chars
        showToast('Server error ' + res.status + ': ' + text.slice(0, 120), false);
        return;
      }

      if (!res.ok) throw new Error(data.error || 'Save failed');
      showToast('Saved to ' + tmpl, true);
    } catch (e) {
      showToast('Error: ' + e.message, false);
    } finally {
      btn.textContent = 'Save Changes';
      btn.disabled = false;
    }
  }

  // --- Toast ---
  function showToast(msg, success) {
    let t = document.getElementById('pei-toast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'pei-toast';
      t.style.cssText = `position:fixed;bottom:80px;right:20px;z-index:999999;
        padding:9px 18px;border-radius:8px;font-size:0.8rem;font-weight:600;
        font-family:'Inter',sans-serif;transition:opacity 0.3s;pointer-events:none;`;
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.style.background = success ? '#16a34a' : '#b91c1c';
    t.style.color = 'white';
    t.style.opacity = '1';
    clearTimeout(t._timer);
    t._timer = setTimeout(() => t.style.opacity = '0', 3000);
  }

})();
