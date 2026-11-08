import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, ApiError } from './api'
import LibraryView from './components/LibraryView'
import ProjectView from './components/ProjectView'
import SearchView from './components/SearchView'
import { ChipStrip } from './components/ui'
import { K_DEFAULT, K_MAX, K_MIN, POLL_MS, VIEWS } from './constants'

const COPY = {
  library: {
    title: 'Library',
    lede: 'Ingest PDFs. Only ready documents can be searched or used in a Project.',
  },
  search: {
    title: 'Related',
    lede: 'Browse every PDF, or rank the k most related, then tick a subset to save onto a Project.',
  },
  projects: {
    title: 'Projects',
    lede: 'A Project is the chat workspace. The assistant may use only its saved selection.',
  },
}

function errorMessage(err) {
  if (err instanceof ApiError) return err.message
  return err?.message || 'Something went wrong.'
}

export default function App() {
  const [view, setView] = useState('library')
  const [health, setHealth] = useState(null)
  const [banner, setBanner] = useState('')
  const [documents, setDocuments] = useState([])
  const [projects, setProjects] = useState([])
  const [active, setActive] = useState(null)
  const [selectedIds, setSelectedIds] = useState(() => new Set())
  const [query, setQuery] = useState('')
  const [k, setK] = useState(K_DEFAULT)
  const [results, setResults] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [searching, setSearching] = useState(false)
  const [chatting, setChatting] = useState(false)

  const readyIds = useMemo(
    () => new Set(documents.filter((d) => d.status === 'ready').map((d) => d.id)),
    [documents],
  )
  const selectedReady = useMemo(
    () => [...selectedIds].filter((id) => readyIds.has(id)),
    [selectedIds, readyIds],
  )

  const refreshDocuments = useCallback(async () => {
    const data = await api.listDocuments()
    setDocuments(data.documents || data)
  }, [])

  const refreshProjects = useCallback(async () => {
    const data = await api.listProjects()
    setProjects(data.projects || data)
  }, [])

  const loadAll = useCallback(async () => {
    try {
      const h = await api.health()
      setHealth(h)
      await Promise.all([refreshDocuments(), refreshProjects()])
      setBanner('')
    } catch (err) {
      setHealth(null)
      setBanner(errorMessage(err))
    }
  }, [refreshDocuments, refreshProjects])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  useEffect(() => {
    if (health) return undefined
    const timer = setInterval(() => {
      loadAll()
    }, 4000)
    return () => clearInterval(timer)
  }, [health, loadAll])

  useEffect(() => {
    const pending = documents.some((d) => d.status && !['ready', 'failed'].includes(d.status))
    if (!pending) return undefined
    const timer = setInterval(() => {
      refreshDocuments().catch((err) => setBanner(errorMessage(err)))
    }, POLL_MS)
    return () => clearInterval(timer)
  }, [documents, refreshDocuments])

  function goToView(next) {
    if (next !== view && (view === 'search' || next === 'search')) {
      setQuery('')
      setResults(null)
      setSearching(false)
    }
    setView(next)
  }

  function toggleSelected(id) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function handleUpload(files) {
    setUploading(true)
    setBanner('')
    try {
      for (const file of files) {
        await api.uploadDocument(file)
      }
      await refreshDocuments()
    } catch (err) {
      setBanner(errorMessage(err))
      await refreshDocuments().catch(() => {})
    } finally {
      setUploading(false)
    }
  }

  async function handleSearch() {
    const nextK = Math.min(K_MAX, Math.max(K_MIN, Number(k) || K_DEFAULT))
    setK(nextK)
    setSearching(true)
    setBanner('')
    try {
      const data = await api.search(query.trim(), nextK)
      setResults(data.documents || [])
    } catch (err) {
      setBanner(errorMessage(err))
    } finally {
      setSearching(false)
    }
  }

  async function openProject(id) {
    try {
      const project = await api.getProject(id)
      setActive(project)
      goToView('projects')
    } catch (err) {
      setBanner(errorMessage(err))
    }
  }

  async function createFromSelection() {
    if (!selectedReady.length) return
    const name = `Project ${projects.length + 1}`
    try {
      const project = await api.createProject({ name, document_ids: selectedReady })
      setSelectedIds(new Set())
      await refreshProjects()
      setActive(project)
      goToView('projects')
    } catch (err) {
      setBanner(errorMessage(err))
    }
  }

  async function renameProject(id, name) {
    try {
      const project = await api.patchProject(id, { name })
      setActive(project)
      await refreshProjects()
    } catch (err) {
      setBanner(errorMessage(err))
    }
  }

  async function deleteProject(id) {
    if (!window.confirm('Delete this Project? Chat history will be removed.')) return
    try {
      await api.deleteProject(id)
      setActive(null)
      await refreshProjects()
    } catch (err) {
      setBanner(errorMessage(err))
    }
  }

  async function addToActive() {
    if (!active || !selectedReady.length) return
    const document_ids = [...new Set([...(active.document_ids || []), ...selectedReady])]
    try {
      const project = await api.patchProject(active.id, { document_ids })
      setActive(project)
      setSelectedIds(new Set())
      await refreshProjects()
      goToView('projects')
    } catch (err) {
      setBanner(errorMessage(err))
    }
  }

  async function detachDocument(docId) {
    if (!active) return
    const document_ids = active.document_ids.filter((id) => id !== docId)
    try {
      const project = await api.patchProject(active.id, { document_ids })
      setActive(project)
      await refreshProjects()
    } catch (err) {
      setBanner(errorMessage(err))
    }
  }

  async function sendChat(message) {
    if (!active) return
    setChatting(true)
    setBanner('')
    const optimistic = {
      id: `local-${Date.now()}`,
      role: 'user',
      content: message,
      citations: [],
    }
    setActive((prev) => ({ ...prev, messages: [...(prev.messages || []), optimistic] }))
    try {
      const reply = await api.chat(active.id, message)
      const project = await api.getProject(active.id)
      setActive(project)
      return reply
    } catch (err) {
      setBanner(errorMessage(err))
      const project = await api.getProject(active.id).catch(() => null)
      if (project) setActive(project)
    } finally {
      setChatting(false)
    }
  }

  const selectedDocs = documents.filter((d) => selectedIds.has(d.id))
  const copy = COPY[view]

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <h1>Lib Gen</h1>
          <p>Library, retrieval, then Project chat — never the whole corpus by accident.</p>
        </div>
        <nav className="nav">
          {VIEWS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={view === item.id ? 'active' : ''}
              onClick={() => goToView(item.id)}
            >
              <span className="label">{item.label}</span>
              <span className="hint">{item.hint}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-meta">
          <div className="health">
            <span className={`dot ${health ? '' : 'down'}`} />
            {health ? 'Backend connected' : 'Backend offline'}
          </div>
          <div className="counts">
            {documents.length} documents · {projects.length} projects
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h2>{copy.title}</h2>
            <p className="lede">{copy.lede}</p>
          </div>
        </header>
        <div className="content">
          {banner ? <div className="banner">{banner}</div> : null}
          {view === 'library' ? (
            <LibraryView
              documents={documents}
              selectedIds={selectedIds}
              onToggle={toggleSelected}
              onUpload={handleUpload}
              busy={uploading}
            />
          ) : null}
          {view === 'search' ? (
            <SearchView
              query={query}
              k={k}
              onQuery={setQuery}
              onK={setK}
              onSearch={handleSearch}
              busy={searching}
              results={results}
              documents={documents}
              selectedIds={selectedIds}
              onToggle={toggleSelected}
            />
          ) : null}
          {view === 'projects' ? (
            <ProjectView
              projects={projects}
              active={active}
              documents={documents}
              onOpen={openProject}
              onCreateFromSelection={createFromSelection}
              canCreate={selectedReady.length > 0}
              onRename={renameProject}
              onDelete={deleteProject}
              onDetach={detachDocument}
              onChat={sendChat}
              chatting={chatting}
            />
          ) : null}
        </div>
        {selectedDocs.length ? (
          <div className="dock">
            <div className="dock-selection">
              <strong>{selectedReady.length} ready selected</strong>
              <ChipStrip
                docs={selectedDocs}
                ariaLabel="Selected documents"
                onRemove={(doc) => toggleSelected(doc.id)}
                showStatus
              />
            </div>
            <div className="dock-actions">
              {active ? (
                <button className="btn btn-ghost" type="button" disabled={!selectedReady.length} onClick={addToActive}>
                  Add to Project
                </button>
              ) : null}
              <button className="btn btn-primary" type="button" disabled={!selectedReady.length} onClick={createFromSelection}>
                Create Project
              </button>
            </div>
          </div>
        ) : null}
      </main>
    </div>
  )
}
