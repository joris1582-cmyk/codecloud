// CodeCloud Frontend Application Controller
(function() {
  'use strict';

  // --- STATE ---
  const state = {
    user: 'admin',
    token: localStorage.getItem('codecloud_token') || btoa('admin:codecloud123'),
    projects: [],
    currentProject: '',
    currentTree: null,
    openTabs: [], // { path, name, language, model, isUnsaved }
    activeTabPath: null,
    monacoInstance: null,
    editorInstance: null,
    connectInfo: null,
    smartFilter: true
  };

  // --- DOM ELEMENTS ---
  const el = {
    navTabs: document.getElementById('navTabs'),
    tabContents: document.querySelectorAll('.tab-content'),
    serverStatusChip: document.getElementById('serverStatusChip'),
    statusServerIp: document.getElementById('statusServerIp'),
    headerMountQuickBtn: document.getElementById('headerMountQuickBtn'),
    authBtn: document.getElementById('authBtn'),
    authBtnLabel: document.getElementById('authBtnLabel'),

    // Studio View
    projectSelect: document.getElementById('projectSelect'),
    btnNewProject: document.getElementById('btnNewProject'),
    btnNewFile: document.getElementById('btnNewFile'),
    btnNewFolder: document.getElementById('btnNewFolder'),
    btnRefreshTree: document.getElementById('btnRefreshTree'),
    treeSearchInput: document.getElementById('treeSearchInput'),
    fileTree: document.getElementById('fileTree'),
    editorTabsBar: document.getElementById('editorTabsBar'),
    tabsList: document.getElementById('tabsList'),
    editorBreadcrumbs: document.getElementById('editorBreadcrumbs'),
    editorLanguageBadge: document.getElementById('editorLanguageBadge'),
    btnSaveFile: document.getElementById('btnSaveFile'),
    monacoContainer: document.getElementById('monacoEditorContainer'),
    emptyEditorPlaceholder: document.getElementById('emptyEditorPlaceholder'),
    statusCursor: document.getElementById('statusCursor'),
    statusFileSize: document.getElementById('statusFileSize'),
    statusEncoding: document.getElementById('statusEncoding'),
    drivePathLabel: document.getElementById('drivePathLabel'),

    // Upload View
    dropzone: document.getElementById('dropzone'),
    folderInput: document.getElementById('folderInput'),
    zipInput: document.getElementById('zipInput'),
    smartFilterToggle: document.getElementById('smartFilterToggle'),
    uploadProgressCard: document.getElementById('uploadProgressCard'),
    uploadSpinner: document.getElementById('uploadSpinner'),
    progressTitle: document.getElementById('progressTitle'),
    progressPercentage: document.getElementById('progressPercentage'),
    progressBarFill: document.getElementById('progressBarFill'),
    progressFileCount: document.getElementById('progressFileCount'),
    progressStatus: document.getElementById('progressStatus'),
    workspacesList: document.getElementById('workspacesList'),
    btnRefreshWorkspacesList: document.getElementById('btnRefreshWorkspacesList'),

    // Mount View
    osTabs: document.querySelectorAll('.os-tab'),
    osContents: document.querySelectorAll('.os-content'),
    cmdWindowsNetUse: document.getElementById('cmdWindowsNetUse'),
    cmdMacFinder: document.getElementById('cmdMacFinder'),
    cmdLinuxMount: document.getElementById('cmdLinuxMount'),
    cmdCloudflareTunnel: document.getElementById('cmdCloudflareTunnel'),
    webdavFolderUrl: document.getElementById('webdavFolderUrl'),

    // Settings View
    settingsForm: document.getElementById('settingsForm'),
    settingUsername: document.getElementById('settingUsername'),
    settingPassword: document.getElementById('settingPassword'),
    settingPort: document.getElementById('settingPort'),
    btnRefreshStats: document.getElementById('btnRefreshStats'),
    statWorkspaces: document.getElementById('statWorkspaces'),
    statFiles: document.getElementById('statFiles'),
    statSizeMB: document.getElementById('statSizeMB'),
    statStoragePath: document.getElementById('statStoragePath'),

    // Modals
    loginModal: document.getElementById('loginModal'),
    loginForm: document.getElementById('loginForm'),
    loginUsername: document.getElementById('loginUsername'),
    loginPassword: document.getElementById('loginPassword'),
    loginError: document.getElementById('loginError'),

    promptModal: document.getElementById('promptModal'),
    promptModalTitle: document.getElementById('promptModalTitle'),
    promptModalLabel: document.getElementById('promptModalLabel'),
    promptModalInput: document.getElementById('promptModalInput'),
    promptModalCancel: document.getElementById('promptModalCancel'),
    promptModalConfirm: document.getElementById('promptModalConfirm'),

    toastContainer: document.getElementById('toastContainer')
  };

  // --- TOAST NOTIFICATIONS ---
  function showToast(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '❌';
    toast.innerHTML = `<span>${icon}</span> <span>${escapeHtml(message)}</span>`;
    el.toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(12px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // --- API HELPER ---
  async function api(endpoint, options = {}) {
    options.headers = options.headers || {};
    if (state.token) {
      options.headers['Authorization'] = `Bearer ${state.token}`;
    }

    try {
      const res = await fetch(endpoint, options);
      if (res.status === 401) {
        showLoginModal();
        throw new Error('Authentication required');
      }
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(errorData.error || `HTTP error ${res.status}`);
      }
      return await res.json();
    } catch (err) {
      throw err;
    }
  }

  // --- AUTH & LOGIN MODAL ---
  function showLoginModal() {
    el.loginModal.style.display = 'flex';
    el.loginError.style.display = 'none';
  }

  function hideLoginModal() {
    el.loginModal.style.display = 'none';
  }

  el.loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = el.loginUsername.value.trim();
    const password = el.loginPassword.value.trim();

    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();
      if (data.success) {
        state.token = data.token;
        state.user = data.username;
        localStorage.setItem('codecloud_token', data.token);
        el.authBtnLabel.innerText = data.username;
        hideLoginModal();
        showToast('Logged in successfully', 'success');
        initializeApp();
      } else {
        el.loginError.innerText = data.error || 'Login failed';
        el.loginError.style.display = 'block';
      }
    } catch (err) {
      el.loginError.innerText = err.message;
      el.loginError.style.display = 'block';
    }
  });

  el.authBtn.addEventListener('click', () => {
    showLoginModal();
  });

  // --- NAVIGATION TABS ---
  el.navTabs.addEventListener('click', (e) => {
    const tabBtn = e.target.closest('.nav-tab');
    if (!tabBtn) return;

    const targetTabId = tabBtn.dataset.tab;
    document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
    tabBtn.classList.add('active');

    el.tabContents.forEach(tc => {
      if (tc.id === targetTabId) {
        tc.classList.add('active');
        if (targetTabId === 'studio-tab' && state.editorInstance) {
          state.editorInstance.layout();
        }
        if (targetTabId === 'settings-tab') {
          loadStats();
        }
      } else {
        tc.classList.remove('active');
      }
    });
  });

  // OS Guide Tabs in Mount View
  el.osTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      el.osTabs.forEach(t => t.classList.remove('active'));
      el.osContents.forEach(c => c.classList.remove('active'));
      tab.classList.add('active');
      const osName = tab.dataset.os;
      const targetContent = document.getElementById(`os-${osName}`);
      if (targetContent) targetContent.classList.add('active');
    });
  });

  // Quick Copy Z: Mount button in header
  el.headerMountQuickBtn.addEventListener('click', () => {
    if (state.connectInfo && state.connectInfo.commands.windowsNetUse) {
      navigator.clipboard.writeText(state.connectInfo.commands.windowsNetUse);
      showToast('Copied Windows Z: Mount command to clipboard!', 'success');
    }
  });

  // Universal Copy Buttons
  document.addEventListener('click', (e) => {
    const copyBtn = e.target.closest('.btn-copy, .btn-copy-sm');
    if (!copyBtn) return;

    const targetId = copyBtn.dataset.target;
    if (targetId) {
      const targetEl = document.getElementById(targetId);
      if (targetEl) {
        navigator.clipboard.writeText(targetEl.innerText.trim());
        const originalText = copyBtn.innerHTML;
        copyBtn.innerHTML = '✓ Copied!';
        setTimeout(() => { copyBtn.innerHTML = originalText; }, 1800);
        showToast('Copied to clipboard!', 'success');
      }
    }
  });

  // --- PROMPT MODAL HELPER ---
  let promptResolve = null;
  function showPrompt(title, label, defaultValue = '') {
    return new Promise((resolve) => {
      promptResolve = resolve;
      el.promptModalTitle.innerText = title;
      el.promptModalLabel.innerText = label;
      el.promptModalInput.value = defaultValue;
      el.promptModal.style.display = 'flex';
      el.promptModalInput.focus();
    });
  }

  el.promptModalConfirm.addEventListener('click', () => {
    const val = el.promptModalInput.value.trim();
    el.promptModal.style.display = 'none';
    if (promptResolve) promptResolve(val);
  });
  el.promptModalCancel.addEventListener('click', () => {
    el.promptModal.style.display = 'none';
    if (promptResolve) promptResolve(null);
  });
  el.promptModalInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') el.promptModalConfirm.click();
    if (e.key === 'Escape') el.promptModalCancel.click();
  });

  // --- MONACO EDITOR INITIALIZATION ---
  function initMonaco() {
    if (typeof require === 'undefined') {
      console.warn('Monaco loader not loaded yet, retrying in 500ms...');
      setTimeout(initMonaco, 500);
      return;
    }

    require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs' } });
    require(['vs/editor/editor.main'], function() {
      state.monacoInstance = monaco;

      // Create Monaco editor
      state.editorInstance = monaco.editor.create(el.monacoContainer, {
        value: '',
        language: 'plaintext',
        theme: 'vs-dark',
        automaticLayout: true,
        fontSize: 13.5,
        fontFamily: "'JetBrains Mono', Consolas, Menlo, monospace",
        minimap: { enabled: true, maxColumn: 80 },
        scrollBeyondLastLine: false,
        cursorSmoothCaretAnimation: 'on',
        smoothScrolling: true,
        tabSize: 2,
        renderWhitespace: 'selection',
        lineNumbers: 'on',
        renderLineHighlight: 'all',
        roundedSelection: true
      });

      // Cursor position change event
      state.editorInstance.onDidChangeCursorPosition((e) => {
        el.statusCursor.innerText = `Ln ${e.position.lineNumber}, Col ${e.position.column}`;
      });

      // Document edit change event -> mark tab unsaved
      state.editorInstance.onDidChangeModelContent(() => {
        const activeTab = state.openTabs.find(t => t.path === state.activeTabPath);
        if (activeTab) {
          const currentVal = state.editorInstance.getValue();
          if (currentVal !== activeTab.originalContent) {
            activeTab.isUnsaved = true;
          } else {
            activeTab.isUnsaved = false;
          }
          renderTabs();
        }
      });

      // Keyboard shortcut Ctrl+S
      state.editorInstance.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
        saveCurrentFile();
      });

      // Global window resize
      window.addEventListener('resize', () => {
        if (state.editorInstance) state.editorInstance.layout();
      });

      console.log('Monaco Editor initialized successfully.');
    });
  }

  // Language mapping
  function getLanguageFromFilename(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const map = {
      'js': 'javascript',
      'mjs': 'javascript',
      'cjs': 'javascript',
      'ts': 'typescript',
      'jsx': 'javascript',
      'tsx': 'typescript',
      'html': 'html',
      'htm': 'html',
      'css': 'css',
      'scss': 'scss',
      'less': 'less',
      'json': 'json',
      'py': 'python',
      'md': 'markdown',
      'c': 'c',
      'cpp': 'cpp',
      'h': 'cpp',
      'hpp': 'cpp',
      'java': 'java',
      'rs': 'rust',
      'go': 'go',
      'sh': 'shell',
      'bash': 'shell',
      'bat': 'bat',
      'ps1': 'powershell',
      'sql': 'sql',
      'xml': 'xml',
      'svg': 'xml',
      'yaml': 'yaml',
      'yml': 'yaml',
      'txt': 'plaintext'
    };
    return map[ext] || 'plaintext';
  }

  // --- PROJECT WORKSPACES ---
  async function loadProjects() {
    try {
      const data = await api('/api/projects');
      state.projects = data.projects || [];

      // Update workspace dropdown
      el.projectSelect.innerHTML = '';
      if (state.projects.length === 0) {
        el.projectSelect.innerHTML = '<option value="">No projects yet</option>';
        state.currentProject = '';
        renderEmptyTree();
        return;
      }

      state.projects.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.name;
        opt.textContent = `${p.name} (${p.fileCount} files)`;
        el.projectSelect.appendChild(opt);
      });

      if (!state.currentProject || !state.projects.find(p => p.name === state.currentProject)) {
        state.currentProject = state.projects[0].name;
      }

      el.projectSelect.value = state.currentProject;
      el.drivePathLabel.innerText = `Z:\\${state.currentProject}`;

      // Render workspaces list in Upload view
      renderWorkspacesList();

      // Load file tree for current workspace
      await loadTree(state.currentProject);
    } catch (err) {
      console.error('Failed to load projects:', err);
    }
  }

  el.projectSelect.addEventListener('change', async (e) => {
    state.currentProject = e.target.value;
    el.drivePathLabel.innerText = `Z:\\${state.currentProject}`;
    await loadTree(state.currentProject);
  });

  // Create new project button
  el.btnNewProject.addEventListener('click', async () => {
    const name = await showPrompt('New Workspace Folder', 'Enter project / workspace name:', 'My-Code-Project');
    if (!name) return;

    try {
      await api('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      });
      showToast(`Created workspace "${name}"`, 'success');
      state.currentProject = name;
      await loadProjects();
    } catch (err) {
      showToast(err.message, 'error');
    }
  });

  // --- FILE TREE ---
  async function loadTree(projectPath) {
    if (!projectPath) {
      renderEmptyTree();
      return;
    }

    try {
      const data = await api(`/api/tree?path=${encodeURIComponent(projectPath)}`);
      state.currentTree = data.tree;
      renderTree(state.currentTree);
    } catch (err) {
      renderEmptyTree(`Error loading tree: ${err.message}`);
    }
  }

  function renderEmptyTree(msg = 'Workspace is empty. Create a file or upload a folder.') {
    el.fileTree.innerHTML = `<div class="tree-empty-msg">${escapeHtml(msg)}</div>`;
  }

  function renderTree(tree) {
    if (!tree) {
      renderEmptyTree();
      return;
    }

    el.fileTree.innerHTML = '';
    const container = document.createElement('div');
    container.className = 'tree-root';

    if (tree.children && tree.children.length > 0) {
      tree.children.forEach(child => {
        container.appendChild(createTreeNodeElement(child));
      });
    } else {
      renderEmptyTree('No files in this project yet.');
      return;
    }

    el.fileTree.appendChild(container);
  }

  function createTreeNodeElement(node) {
    const nodeEl = document.createElement('div');
    nodeEl.className = 'tree-node';

    const row = document.createElement('div');
    row.className = 'node-row';
    row.dataset.path = node.path;
    row.dataset.isDir = node.isDirectory ? 'true' : 'false';

    if (node.isDirectory) {
      row.innerHTML = `
        <span class="node-arrow">▶</span>
        <span class="node-icon folder">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
        </span>
        <span class="node-name">${escapeHtml(node.name)}</span>
        <div class="node-actions-hover">
          <button class="node-action-btn btn-del" title="Delete Folder">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
      `;

      const childrenContainer = document.createElement('div');
      childrenContainer.className = 'tree-children';

      if (node.children && node.children.length > 0) {
        node.children.forEach(c => childrenContainer.appendChild(createTreeNodeElement(c)));
      }

      row.addEventListener('click', (e) => {
        if (e.target.closest('.node-action-btn')) return;
        row.classList.toggle('open');
        childrenContainer.classList.toggle('open');
      });

      // Delete folder action
      row.querySelector('.btn-del').addEventListener('click', async (e) => {
        e.stopPropagation();
        if (confirm(`Delete folder "${node.name}" and all its contents?`)) {
          try {
            await api(`/api/item?path=${encodeURIComponent(node.path)}`, { method: 'DELETE' });
            showToast(`Deleted "${node.name}"`, 'success');
            await loadTree(state.currentProject);
          } catch (err) {
            showToast(err.message, 'error');
          }
        }
      });

      nodeEl.appendChild(row);
      nodeEl.appendChild(childrenContainer);
    } else {
      // File Node
      const ext = node.name.split('.').pop().toLowerCase();
      row.innerHTML = `
        <span class="node-arrow"></span>
        <span class="node-icon file ${ext}">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        </span>
        <span class="node-name">${escapeHtml(node.name)}</span>
        <div class="node-actions-hover">
          <button class="node-action-btn btn-del" title="Delete File">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
      `;

      row.addEventListener('click', (e) => {
        if (e.target.closest('.node-action-btn')) return;
        document.querySelectorAll('.node-row').forEach(r => r.classList.remove('active'));
        row.classList.add('active');
        openFile(node.path, node.name);
      });

      row.querySelector('.btn-del').addEventListener('click', async (e) => {
        e.stopPropagation();
        if (confirm(`Delete file "${node.name}"?`)) {
          try {
            await api(`/api/item?path=${encodeURIComponent(node.path)}`, { method: 'DELETE' });
            showToast(`Deleted "${node.name}"`, 'success');
            closeTab(node.path);
            await loadTree(state.currentProject);
          } catch (err) {
            showToast(err.message, 'error');
          }
        }
      });

      nodeEl.appendChild(row);
    }

    return nodeEl;
  }

  // Tree filter search
  el.treeSearchInput.addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase().trim();
    const rows = el.fileTree.querySelectorAll('.node-row');
    rows.forEach(r => {
      const name = r.querySelector('.node-name').innerText.toLowerCase();
      if (!q || name.includes(q)) {
        r.style.display = 'flex';
      } else {
        r.style.display = 'none';
      }
    });
  });

  // Tree Toolbar Actions
  el.btnRefreshTree.addEventListener('click', () => {
    loadTree(state.currentProject);
    showToast('File tree refreshed', 'info');
  });

  el.btnNewFile.addEventListener('click', async () => {
    if (!state.currentProject) return showToast('Please select or create a project first', 'error');
    const filename = await showPrompt('New File', 'Enter file name (e.g. script.js or src/test.py):', 'index.js');
    if (!filename) return;

    const fullRelPath = `${state.currentProject}/${filename.replace(/^[\/\\]+/, '')}`;
    try {
      await api('/api/new-item', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: fullRelPath, isDirectory: false })
      });
      showToast(`Created file "${filename}"`, 'success');
      await loadTree(state.currentProject);
      openFile(fullRelPath, filename.split('/').pop());
    } catch (err) {
      showToast(err.message, 'error');
    }
  });

  el.btnNewFolder.addEventListener('click', async () => {
    if (!state.currentProject) return showToast('Please select or create a project first', 'error');
    const folderName = await showPrompt('New Folder', 'Enter folder name (e.g. components or utils):', 'components');
    if (!folderName) return;

    const fullRelPath = `${state.currentProject}/${folderName.replace(/^[\/\\]+/, '')}`;
    try {
      await api('/api/new-item', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: fullRelPath, isDirectory: true })
      });
      showToast(`Created folder "${folderName}"`, 'success');
      await loadTree(state.currentProject);
    } catch (err) {
      showToast(err.message, 'error');
    }
  });

  // --- EDITOR & TABS ---
  async function openFile(filePath, fileName) {
    // Check if already open
    const existing = state.openTabs.find(t => t.path === filePath);
    if (existing) {
      setActiveTab(filePath);
      return;
    }

    try {
      const data = await api(`/api/file?path=${encodeURIComponent(filePath)}`);
      const language = getLanguageFromFilename(fileName);

      let model;
      if (state.monacoInstance) {
        const uri = state.monacoInstance.Uri.parse(`file:///${filePath}`);
        model = state.monacoInstance.editor.getModel(uri) ||
                state.monacoInstance.editor.createModel(data.content, language, uri);
      }

      const tab = {
        path: filePath,
        name: fileName,
        content: data.content,
        originalContent: data.content,
        language: language,
        model: model,
        isUnsaved: false
      };

      state.openTabs.push(tab);
      renderTabs();
      setActiveTab(filePath);

      el.emptyEditorPlaceholder.style.display = 'none';
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  function setActiveTab(filePath) {
    state.activeTabPath = filePath;
    const tab = state.openTabs.find(t => t.path === filePath);
    if (!tab) return;

    renderTabs();

    if (state.editorInstance && tab.model) {
      state.editorInstance.setModel(tab.model);
    }

    // Update breadcrumbs
    const parts = filePath.split('/');
    el.editorBreadcrumbs.innerHTML = parts.map((part, idx) => {
      const isLast = idx === parts.length - 1;
      return `<span class="crumb ${isLast ? 'active' : ''}">${escapeHtml(part)}</span>`;
    }).join(' <span style="color:var(--text-muted)">/</span> ');

    // Update language badge & status bar
    el.editorLanguageBadge.innerText = tab.language;
    el.statusFileSize.innerText = `${(tab.content.length / 1024).toFixed(1)} KB`;
    el.drivePathLabel.innerText = `Z:\\${filePath.replace(/\//g, '\\')}`;
  }

  function closeTab(filePath) {
    const idx = state.openTabs.findIndex(t => t.path === filePath);
    if (idx === -1) return;

    const tab = state.openTabs[idx];
    if (tab.isUnsaved) {
      if (!confirm(`"${tab.name}" has unsaved changes. Close anyway?`)) return;
    }

    if (tab.model) {
      tab.model.dispose();
    }

    state.openTabs.splice(idx, 1);

    if (state.activeTabPath === filePath) {
      if (state.openTabs.length > 0) {
        const nextTab = state.openTabs[Math.max(0, idx - 1)];
        setActiveTab(nextTab.path);
      } else {
        state.activeTabPath = null;
        if (state.editorInstance) {
          state.editorInstance.setModel(null);
        }
        el.emptyEditorPlaceholder.style.display = 'flex';
        el.editorBreadcrumbs.innerHTML = '<span class="crumb root">Workspace</span>';
        el.editorLanguageBadge.innerText = 'plaintext';
      }
    }

    renderTabs();
  }

  function renderTabs() {
    el.tabsList.innerHTML = '';
    state.openTabs.forEach(tab => {
      const tabEl = document.createElement('div');
      tabEl.className = `editor-tab ${tab.path === state.activeTabPath ? 'active' : ''} ${tab.isUnsaved ? 'unsaved' : ''}`;
      tabEl.innerHTML = `
        <span class="tab-name">${escapeHtml(tab.name)}</span>
        <span class="tab-unsaved-dot"></span>
        <span class="tab-close-btn" title="Close">✕</span>
      `;

      tabEl.addEventListener('click', (e) => {
        if (e.target.closest('.tab-close-btn')) {
          e.stopPropagation();
          closeTab(tab.path);
        } else {
          setActiveTab(tab.path);
        }
      });

      el.tabsList.appendChild(tabEl);
    });
  }

  async function saveCurrentFile() {
    const activeTab = state.openTabs.find(t => t.path === state.activeTabPath);
    if (!activeTab || !state.editorInstance) return;

    const content = state.editorInstance.getValue();
    try {
      await api('/api/file', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: activeTab.path, content })
      });

      activeTab.content = content;
      activeTab.originalContent = content;
      activeTab.isUnsaved = false;
      renderTabs();
      showToast(`Saved "${activeTab.name}" to server!`, 'success');
    } catch (err) {
      showToast(`Failed to save: ${err.message}`, 'error');
    }
  }

  el.btnSaveFile.addEventListener('click', saveCurrentFile);

  // Global Ctrl+S listener
  window.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      saveCurrentFile();
    }
  });

  // --- UPLOAD CONTROLLER (FOLDERS & ZIP) ---
  el.smartFilterToggle.addEventListener('change', (e) => {
    state.smartFilter = e.target.checked;
  });

  // Helper to determine if path should be skipped
  function shouldSkipPath(relPath) {
    if (!state.smartFilter) return false;
    const parts = relPath.split(/[\/\\]/);
    const ignoreList = ['node_modules', '.git', '.next', '.cache', 'dist', 'build', '__pycache__', '.idea', '.vscode'];
    return parts.some(p => ignoreList.includes(p));
  }

  // Drag and Drop Events on Dropzone
  ['dragenter', 'dragover'].forEach(name => {
    el.dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      el.dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    el.dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      el.dropzone.classList.remove('dragover');
    });
  });

  el.dropzone.addEventListener('drop', async (e) => {
    const items = e.dataTransfer.items;
    if (!items || items.length === 0) return;

    // Check if user dropped a zip file directly
    if (e.dataTransfer.files && e.dataTransfer.files.length === 1 && e.dataTransfer.files[0].name.endsWith('.zip')) {
      handleZipUpload(e.dataTransfer.files[0]);
      return;
    }

    // Traverse directory tree entries
    const filesToUpload = [];
    showUploadProgress(true, 'Scanning dropped folder...');

    const entries = [];
    for (let i = 0; i < items.length; i++) {
      const entry = items[i].webkitGetAsEntry ? items[i].webkitGetAsEntry() : null;
      if (entry) entries.push(entry);
    }

    for (const entry of entries) {
      await traverseEntry(entry, '', filesToUpload);
    }

    if (filesToUpload.length === 0) {
      showUploadProgress(false);
      showToast('No eligible files found to upload', 'info');
      return;
    }

    // Determine target project folder name from top-level dropped folder
    let targetProject = state.currentProject || 'Uploaded-Project';
    if (entries.length === 1 && entries[0].isDirectory) {
      targetProject = entries[0].name;
    }

    await executeBatchUpload(filesToUpload, targetProject);
  });

  async function traverseEntry(entry, currentPath, result) {
    if (entry.isFile) {
      const relPath = currentPath ? `${currentPath}/${entry.name}` : entry.name;
      if (!shouldSkipPath(relPath)) {
        const file = await new Promise((resolve) => entry.file(resolve));
        result.push({ file, relPath });
      }
    } else if (entry.isDirectory) {
      const dirPath = currentPath ? `${currentPath}/${entry.name}` : entry.name;
      if (!shouldSkipPath(dirPath)) {
        const dirReader = entry.createReader();
        const readEntries = async () => {
          const entries = await new Promise((resolve) => dirReader.readEntries(resolve));
          if (entries.length > 0) {
            for (const sub of entries) {
              await traverseEntry(sub, dirPath, result);
            }
            await readEntries(); // Continue reading in batches of 100
          }
        };
        await readEntries();
      }
    }
  }

  // Folder input picker
  el.folderInput.addEventListener('change', async (e) => {
    const fileList = Array.from(e.target.files);
    if (fileList.length === 0) return;

    const filesToUpload = [];
    let topFolder = '';

    fileList.forEach(file => {
      const relPath = file.webkitRelativePath || file.name;
      if (!topFolder && file.webkitRelativePath) {
        topFolder = file.webkitRelativePath.split('/')[0];
      }
      if (!shouldSkipPath(relPath)) {
        filesToUpload.push({ file, relPath });
      }
    });

    const targetProject = topFolder || state.currentProject || 'Project';
    await executeBatchUpload(filesToUpload, targetProject);
    el.folderInput.value = '';
  });

  // ZIP input picker
  el.zipInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
      handleZipUpload(file);
    }
    el.zipInput.value = '';
  });

  async function handleZipUpload(zipFile) {
    showUploadProgress(true, `Uploading & extracting "${zipFile.name}"...`);
    updateProgress(50, `Unzipping on server...`, '1 / 1 files');

    const formData = new FormData();
    formData.append('zipFile', zipFile);
    formData.append('targetProject', zipFile.name.replace(/\.zip$/i, ''));

    try {
      const res = await fetch('/api/upload-zip', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${state.token}` },
        body: formData
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to upload zip');

      updateProgress(100, 'Complete!', '1 / 1 files');
      showToast(`Extracted project "${data.project}" successfully!`, 'success');
      setTimeout(() => showUploadProgress(false), 1200);

      state.currentProject = data.project;
      await loadProjects();
    } catch (err) {
      showUploadProgress(false);
      showToast(err.message, 'error');
    }
  }

  // Execute multi-file batch upload in chunks
  async function executeBatchUpload(filesToUpload, targetProject) {
    const totalFiles = filesToUpload.length;
    showUploadProgress(true, `Uploading project "${targetProject}"...`);

    const CHUNK_SIZE = 50; // 50 files per chunk
    let uploadedCount = 0;

    for (let i = 0; i < totalFiles; i += CHUNK_SIZE) {
      const chunk = filesToUpload.slice(i, i + CHUNK_SIZE);
      const formData = new FormData();
      formData.append('targetProject', targetProject);

      const paths = [];
      chunk.forEach(item => {
        formData.append('files', item.file);
        // Strip top-level directory if it matches targetProject
        let cleanRelPath = item.relPath;
        if (cleanRelPath.startsWith(`${targetProject}/`)) {
          cleanRelPath = cleanRelPath.substring(targetProject.length + 1);
        }
        paths.push(cleanRelPath);
      });
      formData.append('paths', JSON.stringify(paths));

      try {
        const res = await fetch('/api/upload', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${state.token}` },
          body: formData
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({ error: res.statusText }));
          throw new Error(errData.error);
        }

        uploadedCount += chunk.length;
        const pct = Math.round((uploadedCount / totalFiles) * 100);
        updateProgress(pct, `Uploading...`, `${uploadedCount} / ${totalFiles} files`);
      } catch (err) {
        showUploadProgress(false);
        showToast(`Upload failed: ${err.message}`, 'error');
        return;
      }
    }

    updateProgress(100, 'All files uploaded!', `${totalFiles} / ${totalFiles} files`);
    showToast(`Successfully uploaded "${targetProject}" (${totalFiles} files)!`, 'success');
    setTimeout(() => showUploadProgress(false), 1200);

    state.currentProject = targetProject;
    await loadProjects();
  }

  function showUploadProgress(show, title = '') {
    el.uploadProgressCard.style.display = show ? 'block' : 'none';
    if (title) el.progressTitle.innerText = title;
  }

  function updateProgress(percentage, statusText, fileCountText) {
    el.progressBarFill.style.width = `${percentage}%`;
    el.progressPercentage.innerText = `${percentage}%`;
    if (statusText) el.progressStatus.innerText = statusText;
    if (fileCountText) el.progressFileCount.innerText = fileCountText;
  }

  // Workspaces list rendering in upload view
  function renderWorkspacesList() {
    el.workspacesList.innerHTML = '';
    if (state.projects.length === 0) {
      el.workspacesList.innerHTML = '<div style="color:var(--text-muted);font-size:12px;padding:8px;">No projects yet.</div>';
      return;
    }

    state.projects.forEach(p => {
      const item = document.createElement('div');
      item.className = 'workspace-item';
      const sizeMB = (p.totalBytes / (1024 * 1024)).toFixed(2);
      item.innerHTML = `
        <div class="ws-info">
          <span class="ws-name">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" color="#f59e0b"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            ${escapeHtml(p.name)}
          </span>
          <span class="ws-meta">${p.fileCount} files • ${sizeMB} MB • Drive: <code>Z:\\${escapeHtml(p.name)}</code></span>
        </div>
        <div class="ws-actions">
          <button class="btn btn-sm btn-outline btn-download" title="Download ZIP">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          </button>
          <button class="btn btn-sm btn-outline btn-del" style="color:#ef4444" title="Delete">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
      `;

      item.querySelector('.btn-download').addEventListener('click', () => {
        window.location.href = `/api/download-zip?project=${encodeURIComponent(p.name)}&token=${state.token}`;
      });

      item.querySelector('.btn-del').addEventListener('click', async () => {
        if (confirm(`Are you sure you want to permanently delete project "${p.name}"?`)) {
          try {
            await api(`/api/projects/${encodeURIComponent(p.name)}`, { method: 'DELETE' });
            showToast(`Deleted "${p.name}"`, 'success');
            await loadProjects();
          } catch (err) {
            showToast(err.message, 'error');
          }
        }
      });

      el.workspacesList.appendChild(item);
    });
  }

  el.btnRefreshWorkspacesList.addEventListener('click', loadProjects);

  // --- CONNECT INFO & MOUNT GUIDE ---
  async function loadConnectInfo() {
    try {
      const data = await api('/api/connect-info');
      state.connectInfo = data;

      el.statusServerIp.innerText = `Online: ${data.primaryIp}:${data.port}`;
      if (el.cmdWindowsNetUse) el.cmdWindowsNetUse.innerText = data.commands.windowsNetUse;
      if (el.cmdMacFinder) el.cmdMacFinder.innerText = data.commands.macFinder;
      if (el.cmdLinuxMount) el.cmdLinuxMount.innerText = data.commands.linuxMount;
      if (el.cmdCloudflareTunnel) el.cmdCloudflareTunnel.innerText = data.commands.cloudflareTunnel;
      if (el.webdavFolderUrl) el.webdavFolderUrl.innerText = data.webdavLocalUrl;

      // Settings fields
      el.settingUsername.value = data.username;
      el.settingPort.value = data.port;
    } catch (err) {
      console.error('Failed to load connect info:', err);
    }
  }

  // --- SETTINGS & STATS ---
  el.settingsForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = el.settingUsername.value.trim();
    const password = el.settingPassword.value.trim();
    const port = el.settingPort.value.trim();

    try {
      const data = await api('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password: password || undefined, port })
      });

      if (data.success) {
        state.token = data.token;
        state.user = data.username;
        localStorage.setItem('codecloud_token', data.token);
        el.authBtnLabel.innerText = data.username;
        showToast('Settings saved successfully!', 'success');
        await loadConnectInfo();
      }
    } catch (err) {
      showToast(err.message, 'error');
    }
  });

  async function loadStats() {
    try {
      const stats = await api('/api/stats');
      el.statWorkspaces.innerText = state.projects.length;
      el.statFiles.innerText = stats.totalFiles;
      el.statSizeMB.innerText = `${stats.totalSizeMB} MB`;
      el.statStoragePath.innerText = stats.storagePath;
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  }

  el.btnRefreshStats.addEventListener('click', loadStats);

  // --- INITIALIZE APPLICATION ---
  async function initializeApp() {
    initMonaco();
    await loadConnectInfo();
    await loadProjects();
    await loadStats();
  }

  // Start
  initializeApp();

})();
