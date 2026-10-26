export type PendingOutlineNotification = {jobId: string; projectId: string; target?: 'ppt'}

export const outlineNotificationStorageKey = 'edu-video:outline-job-notification'
export const outlineNotificationEvent = 'edu-video:outline-job-pending'
const completedNotificationKey = 'edu-video:completed-job-notifications'
function completedJobIds(): string[] {
  try { const ids:unknown=JSON.parse(sessionStorage.getItem(completedNotificationKey)??'[]');return Array.isArray(ids)?ids.filter((id):id is string=>typeof id==='string'):[] }
  catch { return [] }
}

function isPendingOutlineNotification(value: unknown): value is PendingOutlineNotification {
  if (!value || typeof value !== 'object') return false
  const parsed = value as Partial<PendingOutlineNotification>
  return typeof parsed.jobId === 'string' && typeof parsed.projectId === 'string' && (parsed.target === undefined || parsed.target === 'ppt')
}

export function readPendingOutlineNotifications(): PendingOutlineNotification[] {
  try {
    const value = sessionStorage.getItem(outlineNotificationStorageKey)
    if (!value) return []
    const parsed = JSON.parse(value) as unknown
    // Migrate the earlier single-object format without dropping an in-flight task.
    if (Array.isArray(parsed)) return parsed.filter(isPendingOutlineNotification)
    return isPendingOutlineNotification(parsed) ? [parsed] : []
  } catch {
    return []
  }
}

function writePendingOutlineNotifications(values: PendingOutlineNotification[]) {
  try {
    if (values.length === 0) sessionStorage.removeItem(outlineNotificationStorageKey)
    else sessionStorage.setItem(outlineNotificationStorageKey, JSON.stringify(values))
  } catch { /* storage may be unavailable */ }
}

export function addPendingOutlineNotification(value: PendingOutlineNotification) {
  if (!isPendingOutlineNotification(value) || completedJobIds().includes(value.jobId)) return
  const values = readPendingOutlineNotifications().filter(item => item.jobId !== value.jobId)
  values.push(value)
  writePendingOutlineNotifications(values)
  try { window.dispatchEvent(new Event(outlineNotificationEvent)) } catch { /* window may be unavailable */ }
}

export function removePendingOutlineNotification(jobId: string) {
  try { sessionStorage.setItem(completedNotificationKey,JSON.stringify([...new Set([...completedJobIds(),jobId])])) } catch { /* storage may be unavailable */ }
  writePendingOutlineNotifications(readPendingOutlineNotifications().filter(item => item.jobId !== jobId))
}

export function clearPendingOutlineNotifications() {
  try { sessionStorage.removeItem(completedNotificationKey) } catch { /* storage may be unavailable */ }
  writePendingOutlineNotifications([])
}

// Compatibility aliases for callers created before notifications became a queue.
export function readPendingOutlineNotification(): PendingOutlineNotification | null {
  return readPendingOutlineNotifications()[0] ?? null
}
export const setPendingOutlineNotification = addPendingOutlineNotification
export const clearPendingOutlineNotification = clearPendingOutlineNotifications
