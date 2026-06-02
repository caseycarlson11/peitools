/**
 * PEI Tools — Visual Edit Mode
 * Adds a floating Edit button for logged-in users.
 * Click Edit → click any text → type → Save → updates the template file.
 */
(function () {
  'use strict';

  let editActive = false;
  let changes    = [];   // [{selector, oldText, newText}]
  let activeEl   = null;

  // --- Build UI ---
  const bar = document.createElement('div');
  bar.id = 'pei-editbar';
  bar.innerHTML = `
    <button id="pei-edit-btn"  title="Toggle edit mode">&#9998; Edit Page</button>
    <button id="pei-save-btn"  title="Save changes" style="display:none">&#10003; Save</button>
    <button id="pei-cancel-btn" title="Cancel"       style="display:none">&#10007; Cancel</button>
    <span   id="pei-edit-hint" style="display:none">Click any text to edit it</span>
  `;

  const style = document.createElement('style');
  style.textContent = `
    #pei-editbar {
      position: fixed; bottom: 20px; right: 20px; z-index: 9999;
      display: flex; align-items: center; gap: 8px;
      background: #111d30; border: 1px solid rgba(96,180,240,0.4);
      border-radius: 10px; padding: 8px 12px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.5);
      font-family: 'Inter', sans-serif;
    }
    #pei-editbar button {
      padding: 6px 14px; border-radius: 7px; border: none; cursor: pointer;
      font-size: 0.78rem; font-weight: 700;
    }
    #pei-edit-btn   { background: #1e64c8; color: white; }
    #pei-save-btn   { background: #16a34a; color: white; }
    #pei-cancel-btn { background: rgba(255,255,255,0.1); color: white; }
    #pei-edit-hint  { font-size: 0.72rem; color: rgba(255,255,255,0.45); }

    /* Preserve ALL styling — only show a subtle outline indicator */
    body.pei-edit-mode [data-pei-editable] {
      font: inherit !important;
      color: inherit !important;
      background: inherit !important;
      letter-spacing: inherit !important;
      text-transform: inherit !important;
    }
    body.pei-edit-mode [data-pei-editable]:hover {
      outline: 2px dashed #60b4f0;
      outline-offset: 3px;
      cursor: text;
    }
    body.pei-edit-mode [data-pei-editable]:focus {
      outline: 2px solid #60b4f0;
      outline-offset: 3px;
    }
  `;

  document.head.appendChild(style);
  document.addEventListener('DOMContentLoaded', () => {
    document.body.appendChild(bar);
    init();
  });

  function init() {
    document.getElementById('pei-edit-btn').addEventListener('click', toggleEdit);
    document.getElementById('pei-save-btn').addEventListener('click', saveChanges);
    document.getElementById('pei-cancel-btn').addEventListener('click', cancelEdit);
  }

  // --- Mark editable elements ---
  function markEditable() {
    const tags = ['h1','h2','h3','h4','h5','p','span','a','button','li','label','td','th','div'];
    document.querySelectorAll(tags.join(',')).forEach(el => {
      // Skip our own editbar
      if (el.closest('#pei-editbar')) return;
      // ONLY mark pure text nodes — no child elements allowed.
      // This prevents editing colored spans that would lose their styling.
      if (el.childElementCount > 0) return;
      const text = el.innerText ? el.innerText.trim() : '';
      if (!text || text.length < 2) return;
      el.dataset.peiEditable = 'true';
      el.dataset.peiOriginal  = text;
      el.contentEditable = 'true';
      el.spellcheck = false;
    });
  }

  function unmarkEditable() {
    document.querySelectorAll('[data-pei-editable]').forEach(el => {
      el.removeAttribute('data-pei-editable');
      el.removeAttribute('data-pei-original');
      el.contentEditable = 'false';
    });
  }

  // --- Toggle ---
  function toggleEdit() {
    editActive = !editActive;
    changes = [];

    const btn    = document.getElementById('pei-edit-btn');
    const save   = document.getElementById('pei-save-btn');
    const cancel = document.getElementById('pei-cancel-btn');
    const hint   = document.getElementById('pei-edit-hint');

    if (editActive) {
      document.body.classList.add('pei-edit-mode');
      markEditable();
      btn.textContent    = 'Editing...';
      btn.style.background = 'rgba(255,255,255,0.1)';
      btn.style.color = 'rgba(255,255,255,0.5)';
      save.style.display   = 'inline-block';
      cancel.style.display = 'inline-block';
      hint.style.display   = 'inline';
    } else {
      cancelEdit();
    }
  }

  function cancelEdit() {
    // Restore original text for any changed elements
    document.querySelectorAll('[data-pei-editable]').forEach(el => {
      if (el.dataset.peiOriginal !== undefined) {
        el.innerText = el.dataset.peiOriginal;
      }
    });
    exitEditMode();
  }

  function exitEditMode() {
    editActive = false;
    changes    = [];
    document.body.classList.remove('pei-edit-mode');
    unmarkEditable();

    const btn    = document.getElementById('pei-edit-btn');
    const save   = document.getElementById('pei-save-btn');
    const cancel = document.getElementById('pei-cancel-btn');
    const hint   = document.getElementById('pei-edit-hint');

    btn.textContent    = '✎ Edit Page';
    btn.style.background = '#1e64c8';
    btn.style.color = 'white';
    save.style.display   = 'none';
    cancel.style.display = 'none';
    hint.style.display   = 'none';
  }

  // --- Save ---
  async function saveChanges() {
    // Collect changed elements
    const edits = [];
    document.querySelectorAll('[data-pei-editable]').forEach(el => {
      const orig = el.dataset.peiOriginal || '';
      const curr = el.innerText.trim();
      if (curr !== orig && orig.length > 0) {
        edits.push({ old_text: orig, new_text: curr });
      }
    });

    if (edits.length === 0) {
      showToast('No changes to save.');
      exitEditMode();
      return;
    }

    // Get current template name from body data attribute or page URL
    const template = document.body.dataset.template || '';

    try {
      const res = await fetch('/admin/save-page-edits', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template, edits })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Save failed');
      showToast(`Saved ${data.updated} change${data.updated === 1 ? '' : 's'}`);
      exitEditMode();
    } catch(e) {
      showToast('Error: ' + e.message, true);
    }
  }

  function showToast(msg, isError) {
    let t = document.getElementById('pei-toast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'pei-toast';
      t.style.cssText = `position:fixed;bottom:80px;right:20px;z-index:9999;
        padding:8px 16px;border-radius:8px;font-size:0.8rem;font-weight:600;
        font-family:'Inter',sans-serif;transition:opacity 0.3s;`;
      document.body.appendChild(t);
    }
    t.textContent    = msg;
    t.style.background = isError ? '#b91c1c' : '#16a34a';
    t.style.color    = 'white';
    t.style.opacity  = '1';
    setTimeout(() => { t.style.opacity = '0'; }, 2500);
  }
})();
