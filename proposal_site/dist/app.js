/**
 * USM Orientation Operations Proposal Site - Client App
 * Handles:
 * - Contenteditable synchronization with localStorage
 * - Canonical Reset functionality
 * - Print / Export PDF triggers
 * - Visual editing indicator
 * - Edit mode toggle
 */

(function () {
  'use strict';

  const STORAGE_KEY = 'usm_proposal_content_v1';
  let isDirty = false;

  // Cache of canonical HTML content taken upon initial load
  const canonicalMap = {};

  function initApp() {
    const editableElements = document.querySelectorAll('[data-editable-id]');
    
    // 1. Store canonical text/html
    editableElements.forEach(el => {
      const id = el.getAttribute('data-editable-id');
      if (id && canonicalMap[id] === undefined) {
        canonicalMap[id] = el.innerHTML;
      }
    });

    // 2. Load stored edits from localStorage if present
    loadStoredEdits(editableElements);

    // 3. Attach input listeners for live saving
    editableElements.forEach(el => {
      el.addEventListener('input', () => {
        markDirty();
        debounceSave();
      });
      el.addEventListener('blur', () => {
        saveEdits();
      });
    });

    // 4. Attach toolbar buttons (supporting both ID conventions: btn-* and *Btn)
    const btnReset = document.getElementById('btn-reset') || document.getElementById('resetBtn');
    if (btnReset) {
      btnReset.addEventListener('click', () => handleReset(false));
    }

    const btnPrint = document.getElementById('btn-print') || document.getElementById('printBtn');
    if (btnPrint) {
      btnPrint.addEventListener('click', () => {
        window.print();
      });
    }

    const btnSave = document.getElementById('btn-save') || document.getElementById('saveBtn');
    if (btnSave) {
      btnSave.addEventListener('click', () => {
        saveEdits();
        updateStatusPill('Saved to LocalStorage', true);
      });
    }

    // Attach edit mode toggle button
    const btnEditToggle = document.getElementById('btn-edit-toggle') || document.getElementById('editToggle');
    let isEditMode = true;
    if (btnEditToggle) {
      btnEditToggle.addEventListener('click', () => {
        isEditMode = !isEditMode;
        setEditMode(isEditMode);
      });
    }

    // Attach export data button if present
    const btnExportData = document.getElementById('btn-export-data') || document.getElementById('exportBtn');
    if (btnExportData) {
      btnExportData.addEventListener('click', exportEditsJson);
    }

    updateStatusPill('Ready (Canonical / Stored)', false);
  }

  function setEditMode(enabled) {
    const allEditables = document.querySelectorAll('[data-editable-id], .narrative');
    allEditables.forEach(el => {
      el.setAttribute('contenteditable', enabled ? 'true' : 'false');
    });
    const toggle = document.getElementById('btn-edit-toggle') || document.getElementById('editToggle');
    if (toggle) {
      toggle.textContent = enabled ? 'Lock Edit Mode' : 'Enable Edit Mode';
    }
    updateStatusPill(enabled ? 'Edit Mode Active' : 'Document Locked (Read Only)', false);
  }

  function loadStoredEdits(elements) {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const data = JSON.parse(raw);
      if (typeof data !== 'object' || data === null) return;

      const targetElements = elements || document.querySelectorAll('[data-editable-id]');
      targetElements.forEach(el => {
        const id = el.getAttribute('data-editable-id');
        if (id && data[id] !== undefined) {
          el.innerHTML = data[id];
        }
      });
      updateStatusPill('Loaded edits from storage', true);
    } catch (e) {
      console.warn('Failed to load stored edits:', e);
    }
  }

  let saveTimeout = null;
  function debounceSave() {
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(() => {
      saveEdits();
    }, 800);
  }

  function saveEdits() {
    const elements = document.querySelectorAll('[data-editable-id]');
    const data = {};
    elements.forEach(el => {
      const id = el.getAttribute('data-editable-id');
      if (id) {
        data[id] = el.innerHTML;
      }
    });
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      isDirty = false;
      updateStatusPill('All changes saved', true);
    } catch (e) {
      console.error('Storage error:', e);
      updateStatusPill('Save error (quota/private)', false);
    }
  }

  function handleReset(force = false) {
    const shouldConfirm = !force && !window.__USM_SKIP_CONFIRM__;
    if (shouldConfirm && typeof window.confirm === 'function') {
      const confirmed = window.confirm('Reset all edits back to canonical document defaults? This cannot be undone.');
      if (!confirmed) return;
    }

    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {
      console.warn('Failed to clear storage:', e);
    }

    const elements = document.querySelectorAll('[data-editable-id]');
    elements.forEach(el => {
      const id = el.getAttribute('data-editable-id');
      if (id && canonicalMap[id] !== undefined) {
        el.innerHTML = canonicalMap[id];
      }
    });

    isDirty = false;
    updateStatusPill('Reset to canonical defaults', true);
  }

  function markDirty() {
    isDirty = true;
    updateStatusPill('Unsaved edits...', false);
  }

  function updateStatusPill(text, isSaved) {
    const pill = document.getElementById('status-pill');
    if (!pill) return;
    pill.textContent = text;
    if (isSaved) {
      pill.classList.add('saved');
    } else {
      pill.classList.remove('saved');
    }
  }

  function exportEditsJson() {
    const elements = document.querySelectorAll('[data-editable-id]');
    const data = {};
    elements.forEach(el => {
      const id = el.getAttribute('data-editable-id');
      if (id) {
        data[id] = el.innerHTML;
      }
    });
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'usm-transit-proposal-edits.json';
    a.click();
    URL.revokeObjectURL(url);
  }

  // Expose hooks for testing and verification
  window.UsmProposalApp = {
    getStorageKey: () => STORAGE_KEY,
    getCanonicalMap: () => canonicalMap,
    saveEdits: saveEdits,
    loadStoredEdits: loadStoredEdits,
    resetToCanonical: (force = true) => handleReset(force),
    exportEditsJson: exportEditsJson,
    isDirty: () => isDirty,
    setEditMode: setEditMode,
    initApp: initApp
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
  } else {
    initApp();
  }
})();
