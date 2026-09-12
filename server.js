const express = require('express');
const cors = require('cors');
const multer = require('multer');
const AdmZip = require('adm-zip');
const webdav = require('webdav-server').v2;
const fs = require('fs');
const path = require('path');
const os = require('os');
const http = require('http');

// Load or initialize config
const CONFIG_PATH = path.join(__dirname, 'config.json');
let config = {
  port: 3000,
  username: 'admin',
  password: 'codecloud123',
  storageDir: './storage'
};

if (fs.existsSync(CONFIG_PATH)) {
  try {
    const loaded = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
    config = { ...config, ...loaded };
  } catch (err) {
    console.error('Error reading config.json, using defaults:', err.message);
  }
}

const STORAGE_ROOT = path.resolve(__dirname, config.storageDir);
if (!fs.existsSync(STORAGE_ROOT)) {
  fs.mkdirSync(STORAGE_ROOT, { recursive: true });
}

// Helper: Save config
function saveConfig() {
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2), 'utf8');
}

// Helper: Verify path stays inside STORAGE_ROOT
function safePath(subPath) {
  const normalized = path.normalize(subPath || '').replace(/^(\.\.[\/\\])+/, '');
  const resolved = path.resolve(STORAGE_ROOT, normalized);
  if (!resolved.startsWith(STORAGE_ROOT)) {
    throw new Error('Access denied: Path traversal attempted.');
  }
  return resolved;
}

// -------------------------------------------------------------
// Initialize WebDAV Server
// -------------------------------------------------------------
let userManager = new webdav.SimpleUserManager();
let currentUser = userManager.addUser(config.username, config.password, false);
let privilegeManager = new webdav.SimplePathPrivilegeManager();
privilegeManager.setRights(currentUser, '/', ['all']);

const davServer = new webdav.WebDAVServer({
  httpAuthentication: new webdav.HTTPBasicAuthentication(userManager, 'CodeCloud WebDAV'),
  privilegeManager: privilegeManager
});

davServer.setFileSystem('/', new webdav.PhysicalFileSystem(STORAGE_ROOT), (success) => {
  if (!success) {
    console.error('Failed to mount PhysicalFileSystem for WebDAV!');
  } else {
    console.log('WebDAV PhysicalFileSystem mounted successfully at', STORAGE_ROOT);
  }
});

function updateWebDavUser(username, password) {
  userManager = new webdav.SimpleUserManager();
  currentUser = userManager.addUser(username, password, false);
  privilegeManager = new webdav.SimplePathPrivilegeManager();
  privilegeManager.setRights(currentUser, '/', ['all']);
  davServer.options.httpAuthentication = new webdav.HTTPBasicAuthentication(userManager, 'CodeCloud WebDAV');
  davServer.options.privilegeManager = privilegeManager;
}

// -------------------------------------------------------------
// Initialize Express App
// -------------------------------------------------------------
const app = express();

app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

// Mount WebDAV handler before API/Static middleware
app.use(webdav.extensions.express('/webdav', davServer));

// Upload configuration using multer
const uploadDir = path.join(__dirname, 'temp_uploads');
if (!fs.existsSync(uploadDir)) {
  fs.mkdirSync(uploadDir, { recursive: true });
}
const upload = multer({ dest: uploadDir });

// -------------------------------------------------------------
// Auth Middleware for Web Dashboard & REST API
// -------------------------------------------------------------
function requireAuth(req, res, next) {
  // Check Authorization header (Basic or Bearer)
  const authHeader = req.headers.authorization;
  if (authHeader) {
    if (authHeader.startsWith('Basic ')) {
      const creds = Buffer.from(authHeader.substring(6), 'base64').toString('utf8').split(':');
      if (creds[0] === config.username && creds[1] === config.password) {
        return next();
      }
    } else if (authHeader.startsWith('Bearer ')) {
      const token = authHeader.substring(7);
      const expectedToken = Buffer.from(`${config.username}:${config.password}`).toString('base64');
      if (token === expectedToken) {
        return next();
      }
    }
  }

  // Check URL query param token (?token=...)
  if (req.query.token) {
    const expectedToken = Buffer.from(`${config.username}:${config.password}`).toString('base64');
    if (req.query.token === expectedToken) {
      return next();
    }
  }

  return res.status(401).json({ error: 'Unauthorized. Please login.' });
}

// -------------------------------------------------------------
// REST API Routes
// -------------------------------------------------------------

// Login
app.post('/api/login', (req, res) => {
  const { username, password } = req.body;
  if (username === config.username && password === config.password) {
    const token = Buffer.from(`${username}:${password}`).toString('base64');
    return res.json({ success: true, token, username });
  }
  return res.status(401).json({ error: 'Invalid username or password' });
});

// System / Connection Information
app.get('/api/connect-info', (req, res) => {
  const networkInterfaces = os.networkInterfaces();
  const localIps = [];

  for (const name of Object.keys(networkInterfaces)) {
    for (const net of networkInterfaces[name]) {
      if (net.family === 'IPv4' && !net.internal) {
        localIps.push(net.address);
      }
    }
  }

  const primaryIp = localIps[0] || '127.0.0.1';
  const port = config.port;

  res.json({
    localIps,
    primaryIp,
    port,
    username: config.username,
    webdavLocalUrl: `http://${primaryIp}:${port}/webdav`,
    commands: {
      windowsNetUse: `net use Z: http://${primaryIp}:${port}/webdav /user:${config.username} ${config.password} /persistent:yes`,
      windowsRemove: `net use Z: /delete /y`,
      macFinder: `http://${primaryIp}:${port}/webdav`,
      linuxMount: `sudo mount -t davfs http://${primaryIp}:${port}/webdav /mnt/codecloud -o username=${config.username}`,
      cloudflareTunnel: `npx -y cloudflared tunnel --url http://localhost:${port}`
    }
  });
});

// Get Projects List
app.get('/api/projects', requireAuth, (req, res) => {
  try {
    const entries = fs.readdirSync(STORAGE_ROOT, { withFileTypes: true });
    const projects = [];

    for (const entry of entries) {
      if (entry.isDirectory()) {
        const projPath = path.join(STORAGE_ROOT, entry.name);
        const stats = fs.statSync(projPath);

        // Count files inside
        let fileCount = 0;
        let totalBytes = 0;

        function walk(dir) {
          try {
            const list = fs.readdirSync(dir, { withFileTypes: true });
            for (const item of list) {
              if (item.name === '.git' || item.name === 'node_modules') continue;
              const full = path.join(dir, item.name);
              if (item.isDirectory()) {
                walk(full);
              } else {
                fileCount++;
                try {
                  totalBytes += fs.statSync(full).size;
                } catch (e) {}
              }
            }
          } catch (e) {}
        }
        walk(projPath);

        projects.push({
          name: entry.name,
          modified: stats.mtime,
          fileCount,
          totalBytes
        });
      }
    }

    res.json({ projects });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Create new project / folder
app.post('/api/projects', requireAuth, (req, res) => {
  try {
    const { name } = req.body;
    if (!name || typeof name !== 'string') {
      return res.status(400).json({ error: 'Invalid project name' });
    }
    const cleanName = name.trim().replace(/[^a-zA-Z0-9_\-\.\s]/g, '');
    if (!cleanName) {
      return res.status(400).json({ error: 'Project name contains invalid characters' });
    }
    const targetDir = path.join(STORAGE_ROOT, cleanName);
    if (fs.existsSync(targetDir)) {
      return res.status(400).json({ error: 'Project or folder already exists' });
    }
    fs.mkdirSync(targetDir, { recursive: true });
    res.json({ success: true, name: cleanName });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Delete Project
app.delete('/api/projects/:name', requireAuth, (req, res) => {
  try {
    const targetDir = safePath(req.params.name);
    if (!fs.existsSync(targetDir)) {
      return res.status(404).json({ error: 'Project not found' });
    }
    fs.rmSync(targetDir, { recursive: true, force: true });
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Get File Tree for a Project or Root
app.get('/api/tree', requireAuth, (req, res) => {
  try {
    const subPath = req.query.path || '';
    const rootPath = safePath(subPath);

    function buildTree(dirPath, relativeToRoot = '') {
      if (!fs.existsSync(dirPath)) return null;
      const stats = fs.statSync(dirPath);
      const name = path.basename(dirPath);

      if (!stats.isDirectory()) {
        return {
          name,
          path: relativeToRoot.replace(/\\/g, '/'),
          isDirectory: false,
          size: stats.size,
          modified: stats.mtime
        };
      }

      const children = [];
      const items = fs.readdirSync(dirPath, { withFileTypes: true });

      // Sort directories first, then alphabetically
      items.sort((a, b) => {
        if (a.isDirectory() && !b.isDirectory()) return -1;
        if (!a.isDirectory() && b.isDirectory()) return 1;
        return a.name.localeCompare(b.name);
      });

      for (const item of items) {
        // Skip huge build caches in default tree to keep browser blazing fast
        if (item.name === '.git' && !req.query.showHidden) continue;

        const childFull = path.join(dirPath, item.name);
        const childRel = relativeToRoot ? path.join(relativeToRoot, item.name) : item.name;

        if (item.isDirectory()) {
          children.push(buildTree(childFull, childRel));
        } else {
          try {
            const childStat = fs.statSync(childFull);
            children.push({
              name: item.name,
              path: childRel.replace(/\\/g, '/'),
              isDirectory: false,
              size: childStat.size,
              modified: childStat.mtime
            });
          } catch (e) {}
        }
      }

      return {
        name,
        path: relativeToRoot.replace(/\\/g, '/'),
        isDirectory: true,
        children
      };
    }

    const tree = buildTree(rootPath, subPath);
    res.json({ tree });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Get File Content
app.get('/api/file', requireAuth, (req, res) => {
  try {
    const filePath = safePath(req.query.path);
    if (!fs.existsSync(filePath)) {
      return res.status(404).json({ error: 'File not found' });
    }
    const stat = fs.statSync(filePath);
    if (stat.isDirectory()) {
      return res.status(400).json({ error: 'Path is a directory, not a file' });
    }

    // Limit web-editor load to 5MB to avoid freezing
    if (stat.size > 5 * 1024 * 1024) {
      return res.status(400).json({
        error: 'File is too large to open in browser editor (>5MB). Please open via your mounted network drive.'
      });
    }

    const content = fs.readFileSync(filePath, 'utf8');
    res.json({
      path: req.query.path,
      name: path.basename(filePath),
      size: stat.size,
      modified: stat.mtime,
      content
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Save File Content
app.put('/api/file', requireAuth, (req, res) => {
  try {
    const { path: relPath, content } = req.body;
    if (!relPath || typeof content !== 'string') {
      return res.status(400).json({ error: 'Invalid file payload' });
    }
    const filePath = safePath(relPath);
    const parentDir = path.dirname(filePath);
    if (!fs.existsSync(parentDir)) {
      fs.mkdirSync(parentDir, { recursive: true });
    }
    fs.writeFileSync(filePath, content, 'utf8');
    res.json({ success: true, path: relPath, size: Buffer.byteLength(content, 'utf8') });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Create new file or folder
app.post('/api/new-item', requireAuth, (req, res) => {
  try {
    const { path: relPath, isDirectory } = req.body;
    if (!relPath) return res.status(400).json({ error: 'Path is required' });
    const fullPath = safePath(relPath);

    if (fs.existsSync(fullPath)) {
      return res.status(400).json({ error: 'Item already exists' });
    }

    if (isDirectory) {
      fs.mkdirSync(fullPath, { recursive: true });
    } else {
      const parentDir = path.dirname(fullPath);
      if (!fs.existsSync(parentDir)) {
        fs.mkdirSync(parentDir, { recursive: true });
      }
      fs.writeFileSync(fullPath, '', 'utf8');
    }

    res.json({ success: true, path: relPath });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Delete specific item (file or directory)
app.delete('/api/item', requireAuth, (req, res) => {
  try {
    const relPath = req.query.path;
    if (!relPath) return res.status(400).json({ error: 'Path is required' });
    const fullPath = safePath(relPath);

    if (!fs.existsSync(fullPath)) {
      return res.status(404).json({ error: 'Item not found' });
    }

    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) {
      fs.rmSync(fullPath, { recursive: true, force: true });
    } else {
      fs.unlinkSync(fullPath);
    }

    res.json({ success: true, path: relPath });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Multi-file & Folder Upload
app.post('/api/upload', requireAuth, upload.array('files'), (req, res) => {
  try {
    const files = req.files || [];
    const targetProject = req.body.targetProject || '';
    let relativePaths = req.body.paths || [];

    if (typeof relativePaths === 'string') {
      try {
        relativePaths = JSON.parse(relativePaths);
      } catch (e) {
        relativePaths = [relativePaths];
      }
    }

    let savedCount = 0;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const relPath = relativePaths[i] || file.originalname;

      // Clean path
      const cleanedRelPath = relPath.replace(/^[\/\\]+/, '');
      const fullDestination = safePath(path.join(targetProject, cleanedRelPath));
      const parentDir = path.dirname(fullDestination);

      if (!fs.existsSync(parentDir)) {
        fs.mkdirSync(parentDir, { recursive: true });
      }

      // Move uploaded temp file to destination
      fs.copyFileSync(file.path, fullDestination);
      fs.unlinkSync(file.path);
      savedCount++;
    }

    res.json({ success: true, uploadedCount: savedCount });
  } catch (err) {
    // Cleanup any lingering temp files
    if (req.files) {
      for (const file of req.files) {
        try { fs.unlinkSync(file.path); } catch (e) {}
      }
    }
    res.status(500).json({ error: err.message });
  }
});

// ZIP Archive Upload with auto-extract
app.post('/api/upload-zip', requireAuth, upload.single('zipFile'), (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No ZIP file provided' });
    }

    const targetProject = req.body.targetProject || path.parse(req.file.originalname).name;
    const destDir = safePath(targetProject);

    if (!fs.existsSync(destDir)) {
      fs.mkdirSync(destDir, { recursive: true });
    }

    const zip = new AdmZip(req.file.path);
    zip.extractAllTo(destDir, true);

    // Clean up uploaded zip
    fs.unlinkSync(req.file.path);

    res.json({ success: true, project: targetProject });
  } catch (err) {
    if (req.file && fs.existsSync(req.file.path)) {
      try { fs.unlinkSync(req.file.path); } catch (e) {}
    }
    res.status(500).json({ error: err.message });
  }
});

// Download Project as ZIP
app.get('/api/download-zip', requireAuth, (req, res) => {
  try {
    const relPath = req.query.project;
    if (!relPath) return res.status(400).json({ error: 'Project name is required' });
    const fullPath = safePath(relPath);

    if (!fs.existsSync(fullPath)) {
      return res.status(404).json({ error: 'Project not found' });
    }

    const zip = new AdmZip();
    zip.addLocalFolder(fullPath);
    const buffer = zip.toBuffer();

    res.set({
      'Content-Type': 'application/zip',
      'Content-Disposition': `attachment; filename="${path.basename(fullPath)}.zip"`,
      'Content-Length': buffer.length
    });
    res.send(buffer);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Update Settings / Credentials
app.post('/api/settings', requireAuth, (req, res) => {
  try {
    const { username, password, port } = req.body;
    let changed = false;

    if (username && typeof username === 'string' && username.trim()) {
      config.username = username.trim();
      changed = true;
    }
    if (password && typeof password === 'string' && password.trim()) {
      config.password = password.trim();
      changed = true;
    }
    if (port && Number(port) > 0 && Number(port) <= 65535) {
      config.port = Number(port);
      changed = true;
    }

    if (changed) {
      saveConfig();
      updateWebDavUser(config.username, config.password);
    }

    const newToken = Buffer.from(`${config.username}:${config.password}`).toString('base64');
    res.json({ success: true, username: config.username, token: newToken });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Storage Disk Stats
app.get('/api/stats', requireAuth, (req, res) => {
  try {
    let totalFiles = 0;
    let totalSize = 0;

    function scan(dir) {
      try {
        const items = fs.readdirSync(dir, { withFileTypes: true });
        for (const item of items) {
          const full = path.join(dir, item.name);
          if (item.isDirectory()) {
            scan(full);
          } else {
            totalFiles++;
            try {
              totalSize += fs.statSync(full).size;
            } catch (e) {}
          }
        }
      } catch (e) {}
    }
    scan(STORAGE_ROOT);

    res.json({
      totalFiles,
      totalSize,
      totalSizeMB: (totalSize / (1024 * 1024)).toFixed(2),
      storagePath: STORAGE_ROOT
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Serve frontend static files
app.use(express.static(path.join(__dirname, 'public')));

// SPA Fallback for any unhandled route
app.use((req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Start Server
const PORT = process.env.PORT || config.port || 3050;
const serverInstance = app.listen(PORT, '0.0.0.0', () => {
  console.log(`=======================================================`);
  console.log(`🚀 CodeCloud (Document Hoster) is running!`);
  console.log(`💻 Web Dashboard: http://localhost:${PORT}`);
  console.log(`📂 WebDAV Endpoint: http://localhost:${PORT}/webdav`);
  console.log(`🔐 Default Login: ${config.username} / ${config.password}`);
  console.log(`=======================================================`);
});

serverInstance.on('error', (err) => {
  if (err.code === 'EADDRINUSE') {
    console.error(`Port ${PORT} is in use. Please stop the conflicting process or change the port in config.json.`);
  } else {
    console.error('Server error:', err);
  }
});
