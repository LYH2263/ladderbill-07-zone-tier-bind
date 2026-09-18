async function parseError(r) {
  const text = await r.text()
  let data = null
  try { data = JSON.parse(text) } catch { /* non-json body */ }
  const detail = data?.detail
  const message = typeof detail === 'string'
    ? detail
    : (detail?.error || text || `HTTP ${r.status}`)
  const err = new Error(message)
  err.status = r.status
  err.data = data
  return err
}

export async function getJSON(path) {
  const r = await fetch(path)
  if (!r.ok) throw await parseError(r)
  return r.json()
}
export async function sendJSON(method, path, body) {
  const r = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!r.ok) throw await parseError(r)
  if (r.status === 204) return null
  return r.json()
}
export const postJSON = (path, body) => sendJSON('POST', path, body)
export const putJSON = (path, body) => sendJSON('PUT', path, body)
export const delJSON = (path) => sendJSON('DELETE', path)
