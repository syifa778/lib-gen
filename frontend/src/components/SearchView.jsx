import { K_MAX, K_MIN } from '../constants'
import { DocumentCard, EmptyState } from './ui'

export default function SearchView({
  query,
  k,
  onQuery,
  onK,
  onSearch,
  busy,
  results,
  documents,
  selectedIds,
  onToggle,
}) {
  const browsing = results === null
  const list = browsing ? documents : results

  return (
    <>
      <form
        className="search-bar"
        onSubmit={(e) => {
          e.preventDefault()
          onSearch()
        }}
      >
        <label className="field">
          <span>Query</span>
          <input
            value={query}
            onChange={(e) => onQuery(e.target.value)}
            placeholder="What are you looking for?"
          />
        </label>
        <label className="k-field">
          <span>k</span>
          <input
            type="number"
            min={K_MIN}
            max={K_MAX}
            value={k}
            onChange={(e) => onK(Number(e.target.value))}
          />
        </label>
        <button className="btn btn-primary" type="submit" disabled={busy || !query.trim()}>
          {busy ? 'Finding…' : 'Find related'}
        </button>
      </form>
      <p className="muted">
        {browsing
          ? `All ${documents.length} PDF${documents.length === 1 ? '' : 's'} in the library. Swipe or scroll the list. Run a query to rank the k most related.`
          : `Showing the ${list.length} most related of ${documents.length}. Relatedness is not certainty. Leave this tab to return to the full library.`}
      </p>

      {list.length === 0 ? (
        browsing ? (
          <EmptyState title="No documents yet">
            Upload PDFs in Library first. Then you can pick from the full list or rank by relatedness.
          </EmptyState>
        ) : (
          <EmptyState title="No related documents">
            Nothing in the ready library matched this query. Try different wording or ingest more PDFs.
          </EmptyState>
        )
      ) : (
        <div className="doc-scroller" role="region" aria-label="PDF list" tabIndex={0}>
          {list.map((doc) => (
            <DocumentCard
              key={doc.id}
              doc={doc}
              selected={selectedIds.has(doc.id)}
              onToggle={onToggle}
              extra={
                browsing ? null : (
                  <>
                    <p className="score">relatedness {doc.score?.toFixed?.(3) ?? doc.score}</p>
                    {doc.snippet ? <p className="snippet">{doc.snippet}</p> : null}
                  </>
                )
              }
            />
          ))}
        </div>
      )}
    </>
  )
}
