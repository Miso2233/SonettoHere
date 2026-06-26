/**
 * SonettoHere Desktop — Electron 主进程
 *
 * 职责：
 *   1. 管理后端 FastAPI 子进程（启动/停止/重启）
 *   2. 自动检测可用端口
 *   3. 创建 BrowserWindow 加载前端
 *   4. 崩溃守护（自动重启后端）
 */

const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const net = require('net');
const http = require('http');

const isDev = process.argv.includes('--dev');

// ── 配置 ──────────────────────────────────────────────────

const BACKEND_PORT_RANGE = { start: 8000, end: 8010 };
const HEALTH_CHECK_INTERVAL = 800;    // ms 轮询间隔
const HEALTH_CHECK_TIMEOUT = 3000;    // ms 单次超时
const MAX_RESTART_RETRIES = 3;
const RESTART_COOLDOWN_MS = 60_000;   // 重置重试计数的时间窗口

// ── 状态 ──────────────────────────────────────────────────

let backendProcess = null;
let backendPort = BACKEND_PORT_RANGE.start;
let restartCount = 0;
let firstRestartTime = 0;
let mainWindow = null;
let isQuitting = false;

// ── 工具函数 ──────────────────────────────────────────────

/** 获取平台对应的数据目录 */
function getDataDir() {
  if (isDev) {
    // 开发模式：使用项目根目录
    return path.resolve(__dirname, '..', '..', '..');
  }
  // 生产模式：使用 Electron 的 userData 目录
  return app.getPath('userData');
}

/** 获取后端可执行文件路径 */
function getBackendConfig() {
  if (isDev) {
    const python = process.platform === 'win32'
      ? path.resolve(__dirname, '..', '..', '..', '.venv', 'Scripts', 'python.exe')
      : path.resolve(__dirname, '..', '..', '..', '.venv', 'bin', 'python3');
    const mainPy = path.resolve(__dirname, '..', '..', '..', 'main.py');
    return { command: python, args: [mainPy] };
  }
  // 生产：使用 extraResources 中的 PyInstaller 可执行文件
  const resourcesPath = process.resourcesPath;
  const ext = process.platform === 'win32' ? '.exe' : '';
  return {
    command: path.join(resourcesPath, 'backend', `sonettohere-backend${ext}`),
    args: [],
  };
}

/** 检测可用端口 */
async function findAvailablePort(start, end) {
  for (let port = start; port <= end; port++) {
    try {
      await new Promise((resolve, reject) => {
        const server = net.createServer();
        server.once('error', reject);
        server.listen(port, '127.0.0.1', () => {
          server.close(() => resolve());
        });
      });
      return port;
    } catch {
      continue; // 端口被占用，尝试下一个
    }
  }
  throw new Error(`无法找到可用端口 (${start}-${end})`);
}

/** 等待后端健康检查通过 */
async function waitForBackend(port, maxRetries = 20) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      await new Promise((resolve, reject) => {
        const req = http.get(`http://127.0.0.1:${port}/api/health`, { timeout: HEALTH_CHECK_TIMEOUT }, (res) => {
          if (res.statusCode === 200) resolve();
          else reject(new Error(`status ${res.statusCode}`));
        });
        req.once('error', reject);
        req.once('timeout', () => { req.destroy(); reject(new Error('timeout')); });
      });
      return true;
    } catch {
      await new Promise(r => setTimeout(r, HEALTH_CHECK_INTERVAL));
    }
  }
  throw new Error(`后端在 ${port} 端口未能启动`);
}

/** 记录后端日志 */
function logBackend(data) {
  const lines = data.toString().trim().split('\n');
  for (const line of lines) {
    console.log(`[backend] ${line}`);
  }
}

// ── 后端生命周期 ──────────────────────────────────────────

async function startBackend() {
  if (isQuitting) return;

  try {
    backendPort = await findAvailablePort(BACKEND_PORT_RANGE.start, BACKEND_PORT_RANGE.end);
  } catch (err) {
    console.error('[electron] 端口检测失败:', err.message);
    return;
  }

  const { command, args } = getBackendConfig();
  const env = {
    ...process.env,
    SONETTO_HOME: getDataDir(),
    SONETTO_PORT: String(backendPort),
  };

  console.log(`[electron] 启动后端: ${command} ${args.join(' ')}`);
  console.log(`[electron] 端口: ${backendPort}, 数据目录: ${env.SONETTO_HOME}`);

  backendProcess = spawn(command, args, { env, stdio: ['ignore', 'pipe', 'pipe'] });

  backendProcess.stdout.on('data', logBackend);
  backendProcess.stderr.on('data', logBackend);

  backendProcess.on('exit', (code, signal) => {
    console.log(`[electron] 后端退出 (code=${code}, signal=${signal})`);
    backendProcess = null;

    if (isQuitting) return;

    // 崩溃重启逻辑
    const now = Date.now();
    if (now - firstRestartTime > RESTART_COOLDOWN_MS) {
      restartCount = 0;
      firstRestartTime = now;
    }
    restartCount++;
    if (restartCount > MAX_RESTART_RETRIES) {
      console.error(`[electron] 后端在 ${RESTART_COOLDOWN_MS / 1000}s 内崩溃 ${MAX_RESTART_RETRIES} 次，停止重试`);
      if (mainWindow) {
        mainWindow.webContents.send('backend-crashed', '后端多次崩溃，请检查日志后重启应用');
      }
      return;
    }
    if (restartCount === 1) firstRestartTime = now;

    console.log(`[electron] 后端将在 2s 后重启 (重试 ${restartCount}/${MAX_RESTART_RETRIES})`);
    setTimeout(() => startBackend(), 2000);
  });

  try {
    await waitForBackend(backendPort);
    console.log('[electron] 后端就绪');
    if (mainWindow) {
      mainWindow.webContents.send('backend-ready', backendPort);
    }
  } catch (err) {
    console.error('[electron] 后端启动失败:', err.message);
  }
}

function stopBackend() {
  if (backendProcess) {
    console.log('[electron] 停止后端...');
    if (process.platform === 'win32') {
      // Windows 上 spawn 的进程需要杀死进程树
      spawn('taskkill', ['/pid', String(backendProcess.pid), '/f', '/t']);
    } else {
      backendProcess.kill('SIGTERM');
    }
    backendProcess = null;
  }
}

// ── 窗口管理 ──────────────────────────────────────────────

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    show: false,
    title: 'SonettoHere',
  });

  if (isDev) {
    // 开发模式：加载 Vite dev server
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    // 生产模式：加载内嵌的静态文件
    const frontendPath = path.resolve(__dirname, '..', '..', '..', 'web', 'dist', 'index.html');
    mainWindow.loadFile(frontendPath);
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// ── IPC 处理 ──────────────────────────────────────────────

ipcMain.handle('restart-backend', async () => {
  console.log('[electron] 收到重启请求');
  stopBackend();
  await startBackend();
  return backendPort;
});

ipcMain.handle('get-backend-port', () => {
  return backendPort;
});

// ── 应用生命周期 ──────────────────────────────────────────

app.whenReady().then(async () => {
  createWindow();
  await startBackend();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  isQuitting = true;
  stopBackend();
});
