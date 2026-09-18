async function request(path, options = {}) {
  const r = await fetch(path, options)
  if (!r.ok) throw new ApiError(r.status, await r.text())
  return r.json()
}

export class ApiError extends Error {
  constructor(status, text) {
    super(text)
    this.status = status
    try {
      this.detail = JSON.parse(text)?.detail
    } catch {
      this.detail = null
    }
  }
}

export async function getJSON(path) {
  return request(path)
}
export async function postJSON(path, body) {
  return request(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
}
export async function putJSON(path, body) {
  return request(path, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
}
export async function patchJSON(path, body) {
  return request(path, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
}
