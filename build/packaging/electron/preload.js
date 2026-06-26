/**
 * SonettoHere Desktop — Preload Script
 *
 * 通过 contextBridge 安全地向渲染进程暴露 Electron API，
 * 不启用 nodeIntegration 以保持安全。
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  /** 后端就绪事件，返回监听端口 */
  onBackendReady: (callback) => {
    const handler = (_event, port) => callback(port);
    ipcRenderer.on('backend-ready', handler);
    // 返回清理函数
    return () => ipcRenderer.removeListener('backend-ready', handler);
  },

  /** 后端崩溃事件 */
  onBackendCrashed: (callback) => {
    const handler = (_event, msg) => callback(msg);
    ipcRenderer.on('backend-crashed', handler);
    return () => ipcRenderer.removeListener('backend-crashed', handler);
  },

  /** 请求重启后端 */
  restartBackend: () => ipcRenderer.invoke('restart-backend'),

  /** 获取当前后端端口 */
  getBackendPort: () => ipcRenderer.invoke('get-backend-port'),

  /** 平台信息 */
  platform: process.platform,
});
