# 🚀 CodeCloud - Remote Code Hoster & Virtual Drive

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/joris1582-cmyk/codecloud)

> **Access and edit large code projects from home directly on your school laptop in *any code editor* without downloading the whole repository onto your laptop!**

---

## 🌟 Why This Solves Your Problem

When coding at home on large projects (full-stack web apps, big datasets, projects with thousands of files), downloading them on school Wi-Fi or on a school laptop is slow, takes up precious laptop storage, and causes sync headaches.

**CodeCloud solves this with two powerful methods:**

1. **Virtual Network Drive (`Z:\`) - Open in ANY Editor**:
   - Uses native **WebDAV** built into Windows, macOS, and Linux.
   - When mounted, the remote folder appears on your laptop as a local drive (`Z:\`).
   - You can open **VS Code, Sublime Text, Notepad++, IntelliJ, Cursor, or Vim** on your laptop and choose `File -> Open Folder -> Z:\Welcome-Project`.
   - **Zero pre-downloading**: The OS streams directory listings and only downloads individual files on-demand when you click them. When you press `Ctrl+S`, it writes directly back to your server!
   - No special software needs to be installed on your school laptop.

2. **In-Browser Monaco Code Studio**:
   - If your school laptop is locked down or blocks network drive mapping, you can open CodeCloud in **Google Chrome / Microsoft Edge** and get a full VS Code-grade editor with syntax highlighting, search, and multi-tab editing.

---

## ⚡ Quick Start

### 1. Start CodeCloud at Home
Double-click `start.bat` or run:
```bash
node server.js
```
Open your browser to: **`http://localhost:3000`**
- **Default Username:** `admin`
- **Default Password:** `codecloud123`

---

## 💻 How to Open in ANY Code Editor at School (Without Downloading)

### Method A: Windows 1-Command Mount (PowerShell or CMD)
On your laptop, press `Win + R`, type `cmd`, and run:
```cmd
net use Z: http://YOUR-HOME-IP:3000/webdav /user:admin codecloud123 /persistent:yes
```
*(If connecting over the internet via Cloudflare Tunnel, replace the URL with your `https://...trycloudflare.com/webdav` address)*.

Now open your favorite editor:
- **VS Code**: Run `code Z:\` or `File -> Open Folder -> This PC -> Z:\`
- **Sublime Text**: `File -> Open Folder... -> Z:\`
- **Notepad++**: `File -> Open Folder as Workspace -> Z:\`
- **JetBrains (PyCharm, WebStorm, etc.)**: `File -> Open -> Z:\`

To disconnect / unmount when finished:
```cmd
net use Z: /delete /y
```

### Method B: macOS Finder
1. Press `Command ⌘ + K` in Finder.
2. Enter: `http://YOUR-HOME-IP:3000/webdav`
3. Enter credentials and click **Connect**.
4. Open the mounted `/Volumes/webdav` drive in your editor.

### Method C: Linux
```bash
sudo mount -t davfs http://YOUR-HOME-IP:3000/webdav /mnt/codecloud -o username=admin
```

---

## 🌐 Connecting from School Over the Internet (Zero Port Forwarding)

Your home Wi-Fi router usually blocks incoming connections from school. To bypass this for **free** without any router port forwarding:

1. On your home PC, double-click **`tunnel-helper.bat`** (or run `npx cloudflared tunnel --url http://localhost:3000`).
2. Cloudflare will give you a free, public HTTPS address like:
   `https://random-words-1234.trycloudflare.com`
3. From your school laptop, map the network drive using that link:
   ```cmd
   net use Z: https://random-words-1234.trycloudflare.com/webdav /user:admin codecloud123
   ```
4. Because Cloudflare provides official HTTPS/SSL, Windows connects natively with zero configuration!

---

## 📁 Uploading Folders from Home
1. Go to `http://localhost:3000` and switch to the **Upload Projects** tab.
2. Drag and drop any code folder or `.zip` file into the dropzone.
3. Keep the **Smart Filter** toggled on to automatically skip bulky directories (`node_modules`, `.git`, `.cache`, `dist`) and save bandwidth and disk space!

---

## 🛠️ Architecture & Tech Stack
- **WebDAV RFC 4918 v2 Engine**: Streams files on-demand directly into the operating system filesystem.
- **Node.js & Express**: High-throughput REST API and streaming multipart upload handlers.
- **Monaco Editor**: The open-source code editor that powers Visual Studio Code.
- **Responsive Glassmorphic UI**: Dark theme, real-time file tree, multi-tab editing, live save (`Ctrl+S`).
