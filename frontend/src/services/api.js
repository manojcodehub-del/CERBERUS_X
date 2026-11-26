const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

export async function api(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, options)
  } catch {
    throw new Error('Cannot reach the local CERBERUS-X API. Check that the backend is running.')
  }
  if (response.status === 204) return null
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(payload?.error?.message || payload?.detail?.message || `API returned HTTP ${response.status}`)
  }
  return payload
}

export function sourceLocation(item = {}) {
  const parts = []
  if (item.page_number != null) parts.push(`Page ${item.page_number}`)
  if (item.sheet_name) parts.push(`Sheet ${item.sheet_name}`)
  if (item.row_number != null) parts.push(`Row ${item.row_number}`)
  if (item.cell_coordinate) parts.push(item.cell_coordinate)
  if (item.paragraph_index != null) parts.push(`Paragraph ${item.paragraph_index}`)
  if (item.table_index != null) parts.push(`Table ${item.table_index}`)
  return parts.join(' · ') || 'Location not provided by source'
}

export function pretty(value = '') {
  return String(value).replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export async function downloadApiFile(path, filename) {
  let response
  try { response = await fetch(`${API_BASE}${path}`) }
  catch { throw new Error('Cannot reach the local CERBERUS-X API. Check that the backend is running.') }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(payload?.error?.message || payload?.detail?.message || `API returned HTTP ${response.status}`)
  }
  const objectUrl = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = objectUrl; anchor.download = filename; anchor.hidden = true
  document.body.append(anchor); anchor.click(); anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
}
