import { useRef, useState } from 'react'
import { Download, FileText, Trash2, Upload } from 'lucide-react'
import toast from 'react-hot-toast'
import { useQueryClient } from '@tanstack/react-query'
import { api, downloadFile, errorMessage } from '../api/client'
import { useAction, useApi } from '../lib/hooks'
import { fmtDateTime } from '../lib/format'
import { Card, ConfirmDialog, Spinner, Table } from './ui'

const TYPES = ['ID Proof', 'Address Proof', 'PAN Card', 'Offer Letter', 'Educational Certificate', 'Experience Letter', 'Bank Proof', 'Other']
const size = (b) => (b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.ceil(b / 1024)} KB`)

/** base: '/employees/12' (HR) or '/me' (self service) */
export default function DocumentsPanel({ base, canUpload = true, canDelete = false }) {
  const { data, isLoading } = useApi(['documents', base], `${base}/documents`)
  const qc = useQueryClient()
  const [type, setType] = useState(TYPES[0])
  const [uploading, setUploading] = useState(false)
  const [toDelete, setToDelete] = useState(null)
  const fileRef = useRef(null)
  const del = useAction((id) => api.delete(`${base}/documents/${id}`), { success: 'Document deleted', invalidate: [['documents', base]], onSuccess: () => setToDelete(null) })

  const upload = async (file) => {
    if (!file) return
    if (file.size > 5 * 1024 * 1024) return toast.error('File exceeds the 5 MB limit')
    const fd = new FormData()
    fd.append('document_type', type)
    fd.append('file', file)
    setUploading(true)
    try {
      await api.post(`${base}/documents`, fd)
      toast.success('Document uploaded')
      qc.invalidateQueries({ queryKey: ['documents', base] })
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setUploading(false)
      fileRef.current.value = ''
    }
  }

  return (
    <Card
      title="Documents"
      bodyClass="p-0"
      actions={canUpload && (
        <div className="flex items-center gap-2">
          <select className="input py-1.5 text-xs" value={type} onChange={(e) => setType(e.target.value)}>{TYPES.map((t) => <option key={t}>{t}</option>)}</select>
          <input ref={fileRef} type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.docx" onChange={(e) => upload(e.target.files[0])} />
          <button className="btn-primary btn-sm" onClick={() => fileRef.current.click()} disabled={uploading}>
            {uploading ? <Spinner className="h-3.5 w-3.5 text-white" /> : <Upload className="h-3.5 w-3.5" />} Upload
          </button>
        </div>
      )}
    >
      {isLoading ? <div className="flex justify-center py-8"><Spinner /></div> : (
        <Table
          rows={data}
          empty={{ icon: FileText, title: 'No documents uploaded', message: 'PDF, PNG, JPG or DOCX up to 5 MB.' }}
          columns={[
            { key: 'original_filename', label: 'File', render: (d) => <span className="font-medium text-slate-800">{d.original_filename}</span> },
            { key: 'document_type', label: 'Type' },
            { key: 'size_bytes', label: 'Size', render: (d) => size(d.size_bytes) },
            { key: 'uploaded', label: 'Uploaded', render: (d) => <span>{fmtDateTime(d.uploaded_at)}<span className="text-slate-400"> · {d.uploaded_by_name}</span></span> },
            { key: 'actions', label: '', tdClass: 'text-right', render: (d) => (
              <div className="flex justify-end gap-1">
                <button className="btn-ghost btn-sm" onClick={() => downloadFile(`${base}/documents/${d.id}/download`).catch((e) => toast.error(errorMessage(e)))} aria-label="Download"><Download className="h-4 w-4" /></button>
                {canDelete && <button className="btn-ghost btn-sm text-rose-600" onClick={() => setToDelete(d)} aria-label="Delete"><Trash2 className="h-4 w-4" /></button>}
              </div>
            ) },
          ]}
        />
      )}
      <ConfirmDialog open={!!toDelete} title="Delete document" tone="danger" confirmLabel="Delete" busy={del.isPending}
        message={`Permanently delete "${toDelete?.original_filename}"?`} onClose={() => setToDelete(null)} onConfirm={() => del.mutate(toDelete.id)} />
    </Card>
  )
}
