import { useEffect, useRef } from 'react'

function formatTime(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

export function StatusBadge({ status }) {
  return <span className={`badge ${status}`}>{status}</span>
}

export function EmptyState({ title, children }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  )
}

export function ChipStrip({
  docs,
  ariaLabel,
  activeId,
  onNameClick,
  onRemove,
  emptyLabel,
  showStatus = false,
}) {
  const stripRef = useRef(null)
  const many = docs.length > 1

  useEffect(() => {
    if (!activeId || !stripRef.current) return
    const activeChip = stripRef.current.querySelector('.chip.active')
    activeChip?.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' })
  }, [activeId])

  function scroll(delta) {
    stripRef.current?.scrollBy({ left: delta, behavior: 'smooth' })
  }

  return (
    <div className="chip-row">
      {many ? (
        <button
          className="chip-nav"
          type="button"
          aria-label="Previous PDFs"
          onClick={() => scroll(-200)}
        >
          ‹
        </button>
      ) : null}
      <div className="chip-scroller" ref={stripRef} role="region" aria-label={ariaLabel} tabIndex={0}>
        {docs.length === 0 ? (
          emptyLabel ? <span className="muted">{emptyLabel}</span> : null
        ) : (
          docs.map((doc) => (
            <span className={`chip ${activeId === doc.id ? 'active' : ''}`} key={doc.id}>
              {onNameClick ? (
                <button
                  type="button"
                  className="chip-name"
                  title={doc.filename}
                  onClick={() => onNameClick(doc)}
                >
                  {doc.filename}
                  {showStatus && doc.status && doc.status !== 'ready' ? ` (${doc.status})` : ''}
                </button>
              ) : (
                <span className="chip-name" title={doc.filename}>
                  {doc.filename}
                  {showStatus && doc.status && doc.status !== 'ready' ? ` (${doc.status})` : ''}
                </span>
              )}
              {onRemove ? (
                <button type="button" aria-label={`Remove ${doc.filename}`} onClick={() => onRemove(doc)}>
                  ×
                </button>
              ) : null}
            </span>
          ))
        )}
      </div>
      {many ? (
        <button className="chip-nav" type="button" aria-label="Next PDFs" onClick={() => scroll(200)}>
          ›
        </button>
      ) : null}
    </div>
  )
}

export function DocumentCard({
  doc,
  selected,
  onToggle,
  selectable = true,
  extra,
}) {
  const ready = doc.status === 'ready'
  return (
    <article className={`catalog-card ${doc.status === 'failed' ? 'failed' : ''}`}>
      <input
        type="checkbox"
        checked={selected}
        disabled={!selectable || !ready}
        onChange={() => onToggle(doc.id)}
        aria-label={`Select ${doc.filename}`}
      />
      <div className="catalog-card-body">
        <h4 className="doc-title" title={doc.filename}>
          {doc.filename}
        </h4>
        <p className="meta">
          {doc.page_count != null ? `${doc.page_count} pages · ` : ''}
          {formatTime(doc.created_at)}
          {doc.error ? ` · ${doc.error}` : ''}
        </p>
        {extra}
      </div>
      <StatusBadge status={doc.status} />
    </article>
  )
}
