import { useRef, useState } from 'react'
import { UPLOAD_MAX_BYTES } from '../constants'
import { DocumentCard, EmptyState } from './ui'

export default function LibraryView({ documents, selectedIds, onToggle, onUpload, busy }) {
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)
  const [localError, setLocalError] = useState('')

  function takeFiles(fileList) {
    const files = [...fileList]
    const pdfs = files.filter((f) => f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf'))
    if (pdfs.length !== files.length) {
      setLocalError('Only PDF files can be ingested.')
    } else {
      setLocalError('')
    }
    const accepted = pdfs.filter((f) => f.size <= UPLOAD_MAX_BYTES)
    if (accepted.length !== pdfs.length) {
      setLocalError('Each PDF must be 25 MB or smaller.')
    }
    if (accepted.length) onUpload(accepted)
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <>
      <div
        className={`dropzone ${dragging ? 'dragging' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          takeFiles(e.dataTransfer.files)
        }}
      >
        <h3>Drop PDFs into the library</h3>
        <p>Files are stored by the backend, then extracted and embedded. Ready documents can be searched or added to a Project.</p>
        <input
          ref={inputRef}
          className="file-input"
          type="file"
          accept="application/pdf,.pdf"
          multiple
          onChange={(e) => takeFiles(e.target.files)}
        />
        <button className="btn btn-primary" type="button" disabled={busy} onClick={() => inputRef.current?.click()}>
          {busy ? 'Uploading…' : 'Choose PDFs'}
        </button>
        {localError ? <p className="meta">{localError}</p> : null}
      </div>

      {documents.length === 0 ? (
        <EmptyState title="No documents yet">Upload a PDF to start the library. Related and chat stay empty until something is ready.</EmptyState>
      ) : (
        <div className="card-list">
          {documents.map((doc) => (
            <DocumentCard
              key={doc.id}
              doc={doc}
              selected={selectedIds.has(doc.id)}
              onToggle={onToggle}
            />
          ))}
        </div>
      )}
    </>
  )
}
