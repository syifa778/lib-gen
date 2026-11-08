import { useEffect, useRef, useState } from 'react'
import { ChipStrip, EmptyState } from './ui'

function pdfUrl(docId) {
  return `/api/documents/${docId}/file`
}

export default function ProjectView({
  projects,
  active,
  documents,
  onOpen,
  onCreateFromSelection,
  canCreate,
  onRename,
  onDelete,
  onDetach,
  onChat,
  chatting,
}) {
  const [draft, setDraft] = useState('')
  const [name, setName] = useState(active?.name || '')
  const [preview, setPreview] = useState(null)
  const bottomRef = useRef(null)
  const docsById = Object.fromEntries(documents.map((d) => [d.id, d]))
  const selectedDocs = (active?.document_ids || []).map((id) => docsById[id]).filter(Boolean)

  useEffect(() => {
    setDraft('')
    setName(active?.name || '')
    setPreview(null)
  }, [active?.id, active?.name])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' })
  }, [active?.messages?.length, chatting])

  function sendDraft(text) {
    const message = (text ?? draft).trim()
    if (!message || chatting || !selectedDocs.length) return
    onChat(message)
    setDraft('')
  }

  function openPreview(docId, filename) {
    if (!docId) return
    setPreview({ id: docId, filename: filename || docsById[docId]?.filename || 'PDF' })
  }

  return (
    <div className={`projects-layout ${preview ? 'with-preview' : ''}`}>
      <aside className="project-list">
        {projects.length === 0 ? (
          <EmptyState title="No projects">Select ready documents in Library or Related, then create a Project.</EmptyState>
        ) : (
          projects.map((p) => (
            <button
              key={p.id}
              type="button"
              className={`project-item ${active?.id === p.id ? 'active' : ''}`}
              onClick={() => onOpen(p.id)}
            >
              <strong>{p.name}</strong>
              <span className="meta">{p.document_ids?.length || 0} documents</span>
            </button>
          ))
        )}
        <div className="project-list-actions">
          <button className="btn btn-ghost" type="button" disabled={!canCreate} onClick={onCreateFromSelection}>
            New project from selection
          </button>
        </div>
      </aside>

      {!active ? (
        <div className="selection-empty">
          <EmptyState title="Open a Project">Chat is scoped to the documents saved on that Project, not the last search.</EmptyState>
        </div>
      ) : (
        <div className={`project-workspace ${preview ? 'has-preview' : ''}`}>
          <section className="chat-panel">
            <header className="chat-head">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                onBlur={() => {
                  if (name.trim() && name.trim() !== active.name) onRename(active.id, name.trim())
                }}
                aria-label="Project name"
              />
              <button className="btn btn-danger" type="button" onClick={() => onDelete(active.id)}>
                Delete
              </button>
            </header>
            <ChipStrip
              docs={selectedDocs}
              ariaLabel="Project PDFs"
              activeId={preview?.id}
              onNameClick={(doc) => openPreview(doc.id, doc.filename)}
              onRemove={(doc) => onDetach(doc.id)}
              emptyLabel="No documents on this Project. Attach a selection before chatting."
            />
            <div className="messages">
              {(active.messages || []).length === 0 ? (
                <p className="muted">Ask something that can be answered from the selected files. Enter sends; Shift+Enter adds a line.</p>
              ) : (
                active.messages.map((m) => (
                  <div key={m.id} className={`bubble ${m.role}`}>
                    <p className="bubble-text">{m.content}</p>
                    {m.citations?.length ? (
                      <ul className="citations">
                        {m.citations.map((c, i) => (
                          <li key={`${c.document_id}-${i}`}>
                            <button type="button" onClick={() => openPreview(c.document_id, c.document_name)}>
                              {c.document_name}
                              {c.page != null ? ` p.${c.page}` : ''}
                            </button>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                ))
              )}
              <div ref={bottomRef} />
            </div>
            <form
              className="composer"
              onSubmit={(e) => {
                e.preventDefault()
                const field = e.currentTarget.querySelector('textarea')
                sendDraft(field?.value)
              }}
            >
              <textarea
                rows={1}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    sendDraft(e.currentTarget.value)
                  }
                }}
                placeholder={selectedDocs.length ? 'Ask the Project…' : 'Attach documents to enable chat'}
                disabled={!selectedDocs.length || chatting}
                aria-label="Prompt"
              />
              <button
                className="btn btn-primary"
                type="submit"
                disabled={!selectedDocs.length || chatting || !draft.trim()}
              >
                {chatting ? '…' : 'Send'}
              </button>
            </form>
          </section>

          {preview ? (
            <aside className="pdf-preview">
              <header className="pdf-preview-head">
                <h3>{preview.filename}</h3>
                <div className="pdf-preview-actions">
                  <a className="btn btn-ghost" href={pdfUrl(preview.id)} target="_blank" rel="noreferrer">
                    Open
                  </a>
                  <button className="btn btn-ghost" type="button" onClick={() => setPreview(null)}>
                    Close
                  </button>
                </div>
              </header>
              <iframe title={`Preview ${preview.filename}`} src={pdfUrl(preview.id)} />
            </aside>
          ) : null}
        </div>
      )}
    </div>
  )
}
