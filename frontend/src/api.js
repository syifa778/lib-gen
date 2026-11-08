const API_BASE = import.meta.env.VITE_API_URL || '/api'

export class ApiError extends Error {
  constructor(error, message, status) {
    super(message)
    this.name = 'ApiError'
    this.error = error
    this.status = status
  }
}

async function parseBody(res) {
  const text = await res.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return { message: text }
  }
}

async function request(path, options = {}) {
  let res
  try {
    res = await fetch(`${API_BASE}${path}`, options)
  } catch (err) {
    throw new ApiError(
      'unreachable',
      'Backend is unreachable. Start the FastAPI server on port 8000.',
      0,
    )
  }

  const body = await parseBody(res)
  if (!res.ok) {
    if (res.status === 502 || res.status === 503) {
      throw new ApiError(
        'unreachable',
        'Backend is unreachable. Start the FastAPI server on port 8000.',
        res.status,
      )
    }
    throw new ApiError(
      body?.error || 'request_failed',
      body?.message || `Request failed (${res.status})`,
      res.status,
    )
  }
  return body
}

export const api = {
  health() {
    return request('/health')
  },

  listDocuments() {
    return request('/documents')
  },

  getDocument(id) {
    return request(`/documents/${id}`)
  },

  uploadDocument(file) {
    const body = new FormData()
    body.append('file', file)
    return request('/documents', { method: 'POST', body })
  },

  search(query, k) {
    return request('/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, k }),
    })
  },

  listProjects() {
    return request('/projects')
  },

  getProject(id) {
    return request(`/projects/${id}`)
  },

  createProject(payload) {
    return request('/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  },

  patchProject(id, payload) {
    return request(`/projects/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  },

  deleteProject(id) {
    return request(`/projects/${id}`, { method: 'DELETE' })
  },

  chat(projectId, message) {
    return request(`/projects/${projectId}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    })
  },
}
