import { useState } from 'react'
import toast from 'react-hot-toast'
import { Download, ShieldCheck } from 'lucide-react'
import { downloadFile, errorMessage } from '../../api/client'
import { useApi } from '../../lib/hooks'
import { fmtUtc } from '../../lib/format'
import { Card, Modal, PageHeader, Pagination, Spinner, Table } from '../../components/ui'

export default function AuditLogs() {
  const [q, setQ] = useState({ action: '', actor: '', search: '', date_from: '', date_to: '', page: 1 })
  const params = Object.fromEntries(Object.entries({ ...q, page_size: 25 }).filter(([, v]) => v !== ''))
  const { data, isLoading } = useApi(['audit', params], '/audit-logs', params, { placeholderData: (p) => p })
  const { data: actions } = useApi('audit-actions', '/audit-logs/actions')
  const [open, setOpen] = useState(null)
  const set = (k) => (e) => setQ({ ...q, [k]: e.target.value, page: 1 })
  const { page, ...exportParams } = params // eslint-disable-line no-unused-vars

  return (
    <>
      <PageHeader title="Audit logs" subtitle="Read-only, append-only trail of every critical action"
        actions={<button className="btn-secondary" onClick={() => downloadFile('/audit-logs/export', exportParams, 'audit_logs.csv').catch((e) => toast.error(errorMessage(e)))}><Download className="h-4 w-4" /> Export CSV</button>} />
      <Card bodyClass="p-0">
        <div className="flex flex-wrap gap-3 border-b border-slate-100 p-4">
          <select className="input w-56" value={q.action} onChange={set('action')}>
            <option value="">All actions</option>{actions?.map((a) => <option key={a}>{a}</option>)}
          </select>
          <input className="input w-48" placeholder="Actor email" value={q.actor} onChange={set('actor')} />
          <input className="input w-56" placeholder="Search description" value={q.search} onChange={set('search')} />
          <input type="date" className="input w-40" value={q.date_from} onChange={set('date_from')} />
          <input type="date" className="input w-40" value={q.date_to} onChange={set('date_to')} />
        </div>
        {isLoading ? <div className="flex justify-center py-10"><Spinner /></div> : (
          <>
            <Table rows={data.items} onRowClick={setOpen} empty={{ icon: ShieldCheck, title: 'No audit entries match' }} columns={[
              { key: 'created_at', label: 'Time', render: (r) => <span className="text-xs">{fmtUtc(r.created_at)}</span> },
              { key: 'actor_email', label: 'Actor', render: (r) => r.actor_email || 'system' },
              { key: 'action', label: 'Action', render: (r) => <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{r.action}</code> },
              { key: 'description', label: 'Description', tdClass: 'max-w-lg truncate', render: (r) => <span title={r.description}>{r.description}</span> },
              { key: 'ip_address', label: 'IP' },
            ]} />
            <Pagination page={data.page} pages={data.pages} total={data.total} onChange={(p) => setQ({ ...q, page: p })} />
          </>
        )}
      </Card>
      <Modal open={!!open} onClose={() => setOpen(null)} size="lg" title={`Audit entry #${open?.id}`}>
        {open && (
          <dl className="space-y-3 text-sm">
            {[['Time', fmtUtc(open.created_at)], ['Actor', open.actor_email || 'system'], ['Action', open.action], ['Entity', open.entity_type ? `${open.entity_type} #${open.entity_id}` : '—'],
              ['Description', open.description], ['IP address', open.ip_address], ['User agent', open.user_agent]].map(([k, v]) => (
              <div key={k} className="grid grid-cols-4 gap-2"><dt className="text-slate-500">{k}</dt><dd className="col-span-3 break-words">{v || '—'}</dd></div>
            ))}
            {open.changes && (
              <div><dt className="mb-1 text-slate-500">Changes</dt>
                <pre className="max-h-72 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">{JSON.stringify(open.changes, null, 2)}</pre></div>
            )}
          </dl>
        )}
      </Modal>
    </>
  )
}
