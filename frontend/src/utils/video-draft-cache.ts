export type VideoDraftData = {
  prompt: string
  title: string
  values: Record<string, unknown>
}

type FileRecord = { key: string; files: File[] }

const memoryFiles = new Map<string, File[]>()
let database: Promise<IDBDatabase | null> | undefined

function openDatabase() {
  if (database) return database
  if (typeof indexedDB === 'undefined') {
    database = Promise.resolve(null)
    return database
  }
  database = new Promise((resolve) => {
    const request = indexedDB.open('edu-video-local-cache', 1)
    request.onupgradeneeded = () => request.result.createObjectStore('files', { keyPath: 'key' })
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => resolve(null)
  })
  return database
}

export function readVideoDraft(key: string): VideoDraftData | null {
  try {
    const value = localStorage.getItem(`edu-video:draft:${key}`)
    return value ? JSON.parse(value) as VideoDraftData : null
  } catch {
    return null
  }
}

export function writeVideoDraft(key: string, data: VideoDraftData) {
  try { localStorage.setItem(`edu-video:draft:${key}`, JSON.stringify(data)) } catch { /* storage may be unavailable */ }
}

export function clearVideoDraft(key: string) {
  try { localStorage.removeItem(`edu-video:draft:${key}`) } catch { /* storage may be unavailable */ }
}

export async function clearPendingFiles(key: string) {
  memoryFiles.delete(key)
  const db = await openDatabase()
  if (!db) return
  await new Promise<void>((resolve) => {
    const request = db.transaction('files', 'readwrite').objectStore('files').delete(key)
    request.onsuccess = request.onerror = () => resolve()
  })
}

export async function clearAllVideoDraftCache() {
  try {
    for (let index = localStorage.length - 1; index >= 0; index -= 1) {
      const key = localStorage.key(index)
      if (key?.startsWith('edu-video:draft:')) localStorage.removeItem(key)
    }
  } catch { /* storage may be unavailable */ }
  memoryFiles.clear()
  const db = await openDatabase()
  if (!db) return
  await new Promise<void>((resolve) => {
    const request = db.transaction('files', 'readwrite').objectStore('files').clear()
    request.onsuccess = request.onerror = () => resolve()
  })
}

export async function readPendingFiles(key: string): Promise<File[]> {
  if (memoryFiles.has(key)) return memoryFiles.get(key) ?? []
  const db = await openDatabase()
  if (!db) return []
  return new Promise((resolve) => {
    const request = db.transaction('files', 'readonly').objectStore('files').get(key)
    request.onsuccess = () => {
      const files = (request.result as FileRecord | undefined)?.files ?? []
      memoryFiles.set(key, files)
      resolve(files)
    }
    request.onerror = () => resolve([])
  })
}

export async function writePendingFiles(key: string, files: File[]) {
  memoryFiles.set(key, files)
  try {
    const db = await openDatabase()
    if (!db) return
    await new Promise<void>((resolve) => {
      const request = db.transaction('files', 'readwrite').objectStore('files').put({ key, files } satisfies FileRecord)
      request.onsuccess = request.onerror = () => resolve()
    })
  } catch {
    // 本地缓存只是辅助恢复，不能阻断已经完成的项目或素材保存。
  }
}

export async function moveVideoDraft(from: string, to: string) {
  const data = readVideoDraft(from)
  if (data) writeVideoDraft(to, data)
  const files = await readPendingFiles(from)
  if (files.length) await writePendingFiles(to, files)
  if (from !== to) {
    clearVideoDraft(from)
    memoryFiles.delete(from)
    const db = await openDatabase()
    if (db) await new Promise<void>((resolve) => {
      const request = db.transaction('files', 'readwrite').objectStore('files').delete(from)
      request.onsuccess = request.onerror = () => resolve()
    })
  }
}
