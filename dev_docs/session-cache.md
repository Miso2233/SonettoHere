# 前端会话缓存（localStorage）机制

## 概述

前端使用 `localStorage` 缓存每条会话的聊天记录（`ChatTurn[]`），使得页面刷新后能恢复历史对话。缓存 key 格式为 `sonetto_turns_<session_id>`，值是对 `ChatTurn[]` 的 `JSON.stringify`。

---

## 数据流总览

```
服务端 WebSocket
      │
      ▼
handleEventForChannel()
      │
      ├─ answer / done 事件
      │      ▼
      │   ch.turns.push(turn)
      │      ▼
      │   persistTurns(sid)
      │      ▼
      │   saveTurnsToStorage(sid, snapshot)    ← 写入 localStorage
      │
      ├─ sub_session_created
      │      ▼
      │   switchSession(subId)  →  触发 watch
      │                               ▼
      │                           persistTurns(oldId)    ← 切换前写入
      │
      └─ ...

模块加载时：
  turnsCache = loadAllTurnsFromStorage()    ← 读取全部 localStorage

页面初始化：
  initIfNeeded() → sessionId.value = stored
      ▼
  watch(sessionId) fires
      ▼
  cached = turnsCache.get(newId)           ← 从内存 Map 读取
  if (cached && ch.turns.length === 0)
    ch.turns.push(...cached)               ← 恢复到响应式通道
      ▼
  cleanupOrphanedCaches()                  ← 清理孤儿缓存
```

---

## localStorage key

| 常量 | 值 | 来源 |
|------|-----|------|
| `TURNS_KEY_PREFIX` | `sonetto_turns_` | [useChat.ts:5](web/src/composables/useChat.ts#L5) |
| `STORAGE_KEY` | `sonetto_session_id` | [useSession.ts:6](web/src/composables/useSession.ts#L6) |

- 缓存 key: `sonetto_turns_<session_id>`（如 `sonetto_turns_550e8400e29b41d4a716446655440000`）
- 当前会话 ID key: `sonetto_session_id`（值仅为 UUID 字符串，不包含前缀）

---

## 读时机（Read）

### 模块加载时全量读取

**位置**: [useChat.ts:8-32](web/src/composables/useChat.ts#L8-L32) `loadAllTurnsFromStorage()`

在 `useChat.ts` 模块首次被 import 时调用，遍历 `localStorage` 中所有以 `sonetto_turns_` 开头的键，反序列化后存入模块级 `turnsCache: Map<string, ChatTurn[]>`。

```typescript
const turnsCache = loadAllTurnsFromStorage()    // 模块级，仅执行一次
```

### 会话切换 / 初始化时从缓存恢复

**位置**: [useChat.ts:393-422](web/src/composables/useChat.ts#L393-L422) `watch(sessionId, ..., { immediate: true })`

在以下两种场景触发：
1. **页面初始化** — `initIfNeeded()` 从 `sonetto_session_id` 恢复会话 ID，watch 以 `{ immediate: true }` 触发
2. **用户切换会话** — 点击侧边栏会话 → `switchSession(id)` → `sessionId.value = id` → watch 触发

恢复逻辑：
```typescript
const cached = turnsCache.get(newId)
const ch = getOrCreateChannel(newId)
if (cached && ch.turns.length === 0) {
  ch.turns.push(...cached)   // 将缓存数据推入响应式通道
}
```

> **注意**: `turnsCache.get(newId)` 查找失败意味着该会话从未被持久化（或缓存已被删除）。此时通道将保持空数组，页面显示空白。

---

## 写时机（Write）

### 1. 轮次完成时（`done` 事件）

**位置**: [useChat.ts:299-336](web/src/composables/useChat.ts#L299-L336)

WebSocket 接收到 `done` 事件后，将 `ch.currentTurn` 移入 `ch.turns` 并持久化：

- **非 `becameAnswer` 分支**: 立即执行 `persistTurns(sid)`（同步）
- **`becameAnswer` 分支**: 延迟 ~420ms 后执行 `persistTurns(sid)`（`nextTick` + `setTimeout(420)`）

```typescript
function persistTurns(sid: string) {
  const snapshot = [...ch.turns]
  turnsCache.set(sid, snapshot)           // 更新内存缓存
  saveTurnsToStorage(sid, snapshot)       // 写入 localStorage
}
```

### 2. 会话切换时

**位置**: [useChat.ts:397-399](web/src/composables/useChat.ts#L397-L399)

watch 中切换会话前，先持久化旧会话：
```typescript
if (oldId) persistTurns(oldId)
```

### 3. 子 Agent 切回主会话时

**位置**: [useChat.ts:333-335](web/src/composables/useChat.ts#L333-L335)

子 Agent 完成后 500ms 自动切回主会话，触发步骤 2 的持久化。

### 写入函数

**位置**: [useChat.ts:34-51](web/src/composables/useChat.ts#L34-L51) `saveTurnsToStorage()`

```typescript
function saveTurnsToStorage(sid: string, data: ChatTurn[]) {
  const serialized = JSON.stringify(data)
  localStorage.setItem(TURNS_KEY_PREFIX + sid, serialized)
}
```

> **注意**: `JSON.stringify` 异常或 `localStorage` 配额超限会导致写入失败。新版已添加错误日志。

---

## 删时机（Delete）

### 1. 用户删除会话

**位置**: [useSession.ts:70-85](web/src/composables/useSession.ts#L70-L85) `deleteSession()`

```typescript
async function deleteSession(id: string) {
  await api.deleteSession(id)
  disconnectSession(id)
  removeTurnsFromStorage(id)      // 删除 localStorage 条目
  // ...
}
```

### 2. 孤儿缓存清理

**位置**: [useSession.ts:92-114](web/src/composables/useSession.ts#L92-L114) `cleanupOrphanedCaches()`

在 `initIfNeeded()` 获取后端会话列表后执行。删除所有 `sonetto_turns_*` 中后端已不存在的会话缓存。

### 删除函数

**位置**: [useChat.ts:53-55](web/src/composables/useChat.ts#L53-L55) `removeTurnsFromStorage()`

```typescript
export function removeTurnsFromStorage(sid: string) {
  localStorage.removeItem(TURNS_KEY_PREFIX + sid)
}
```

---

## 时序图

```
页面加载
  │
  ├─ useChat 模块加载
  │     └─ turnsCache = loadAllTurnsFromStorage()    ← 读所有 localStorage
  │
  ├─ useSession().initIfNeeded()
  │     ├─ localStorage.getItem('sonetto_session_id') ← 读存储的 sessionId
  │     ├─ api.getSession(stored)                     ← 验证后端存在
  │     └─ sessionId.value = stored
  │
  ├─ watch(sessionId) fires (immediate)
  │     ├─ persistTurns(oldId)                        ← 写旧会话缓存
  │     ├─ ensureConnected(newId)
  │     ├─ turnsCache.get(newId)                      ← 读内存缓存
  │     └─ ch.turns.push(...cached)                   ← 恢复通道
  │
  └─ cleanupOrphanedCaches()                          ← 删孤儿缓存

对话中
  │
  ├─ 用户发送消息
  │     └─ send() → WebSocket
  │
  └─ 服务端推送 done 事件
        ├─ ch.turns.push(turn)
        └─ persistTurns(sid)                          ← 写 localStorage

切换会话 / 删除会话
  │
  ├─ switchSession(id)
  │     ├─ watch 触发
  │     │   ├─ persistTurns(oldId)                    ← 写旧会话缓存
  │     │   └─ 恢复新会话的缓存                        ← 读缓存
  │     └─ localStorage.setItem('sonetto_session_id') ← 写 sessionId
  │
  └─ deleteSession(id)
        └─ removeTurnsFromStorage(id)                  ← 删 localStorage 条目
```

---

## 关键文件

| 文件 | 职责 |
|------|------|
| [web/src/composables/useChat.ts](web/src/composables/useChat.ts) | 缓存读写函数、WebSocket 事件处理、watch 恢复逻辑、`turnsCache` 内存缓存 |
| [web/src/composables/useSession.ts](web/src/composables/useSession.ts) | 会话 CRUD、`initIfNeeded` 初始化、孤儿缓存清理 |

## 关键函数

| 函数 | 位置 | 触发时机 |
|------|------|----------|
| `loadAllTurnsFromStorage()` | [useChat.ts:8](web/src/composables/useChat.ts#L8) | 模块加载时 |
| `saveTurnsToStorage()` | [useChat.ts:34](web/src/composables/useChat.ts#L34) | 轮次完成、会话切换 |
| `persistTurns()` | [useChat.ts:122](web/src/composables/useChat.ts#L122) | 更新内存缓存 + 调用 `saveTurnsToStorage` |
| `removeTurnsFromStorage()` | [useChat.ts:53](web/src/composables/useChat.ts#L53) | 删除会话 |
| `cleanupOrphanedCaches()` | [useSession.ts:92](web/src/composables/useSession.ts#L92) | 页面初始化完成时 |
