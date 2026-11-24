import { useEffect, useState } from 'react'
import { Eye, RotateCw, Save } from 'lucide-react'
import { api } from '../../api/client'
import { useAction, useApi } from '../../lib/hooks'
import { fmtUtc } from '../../lib/format'
import { Card, Field, Modal, PageHeader, Pagination, Spinner, StatusBadge, Table, Tabs } from '../../components/ui'

function Templates() {
  const { data: templates, isLoading } = useApi('email-templates', '/email-templates')
  const [sel, setSel] = useState(null)
  const [form, setForm] = useState(null)
  const [preview, setPreview] = useState(null)
  useEffect(() => { if (templates && !sel) setSel(templates[0]?.id) }, [templates, sel])
  const current = templates?.find((t) => t.id === sel)
  useEffect(() => { if (current) setForm({ subject: current.subject, body_html: current.body_html, is_active: current.is_active }) }, [current])
  const save = useAction(() => api.put(`/email-templates/${sel}`, form), { success: 'Template saved', invalidate: ['email-templates'] })
  const doPreview = useAction(() => api.post(`/email-templates/${sel}/preview`, { subject: form.subject, body_html: form.body_html }).then((r) => r.data), { onSuccess: setPreview })
  if (isLoading) return <div className="flex justify-center py-10"><Spinner /></div>
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Card title="Templates" bodyClass="p-2">
        {templates.map((t) => (
          <button key={t.id} onClick={() => setSel(t.id)} className={`block w-full rounded-lg px-3 py-2 text-left ${t.id === sel ? 'bg-brand-50' : 'hover:bg-slate-50'}`}>
            <p className="text-sm font-medium text-slate-800">{t.name} {!t.is_active && <StatusBadge status="inactive" label="off" />}</p>
            <p className="text-xs text-slate-500">{t.description}</p>
          </button>
        ))}
      </Card>
      {current && form && (
        <Card title={current.name} className="lg:col-span-2" actions={
          <div className="flex gap-2">
            <button className="btn-secondary btn-sm" onClick={() => doPreview.mutate()}><Eye className="h-3.5 w-3.5" /> Preview</button>
            <button className="btn-primary btn-sm" disabled={save.isPending} onClick={() => save.mutate()}><Save className="h-3.5 w-3.5" /> Save</button>
          </div>}>
          <div className="space-y-4">
            <p className="text-xs text-slate-500">Jinja2 syntax (rendered in a sandbox, values auto-escaped). Variables: <code className="text-slate-700">{current.variables}</code>, <code>company_name</code>, <code>app_url</code></p>
            <Field label="Subject"><input className="input font-mono text-xs" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} /></Field>
            <Field label="HTML body"><textarea className="input min-h-72 font-mono text-xs" value={form.body_html} onChange={(e) => setForm({ ...form, body_html: e.target.value })} /></Field>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} /> Enabled (disabled templates are not sent)</label>
          </div>
        </Card>
      )}
      <Modal open={!!preview} onClose={() => setPreview(null)} size="lg" title={preview?.subject}>
        {/* sandboxed iframe: template HTML cannot run scripts or touch the app */}
        <iframe title="preview" sandbox="" srcDoc={preview?.html} className="h-[60vh] w-full rounded-lg border border-slate-200" />
      </Modal>
    </div>
  )
}

function Logs() {
  const [q, setQ] = useState({ status: '', recipient: '', page: 1 })
  const params = Object.fromEntries(Object.entries({ ...q, page_size: 20 }).filter(([, v]) => v !== ''))
  const { data, isLoading } = useApi(['email-logs', params], '/email-logs', params, { placeholderData: (p) => p })
  const [openId, setOpenId] = useState(null)
  const { data: detail } = useApi(['email-log', openId], `/email-logs/${openId}`, null, { enabled: !!openId })
  const resend = useAction((id) => api.post(`/email-logs/${id}/resend`), { success: 'Email re-queued', invalidate: ['email-logs'] })
  return (
    <Card bodyClass="p-0">
      <div className="flex flex-wrap gap-3 border-b border-slate-100 p-4">
        <input className="input w-64" placeholder="Recipient" value={q.recipient} onChange={(e) => setQ({ ...q, recipient: e.target.value, page: 1 })} />
        <select className="input w-40" value={q.status} onChange={(e) => setQ({ ...q, status: e.target.value, page: 1 })}>
          <option value="">Any status</option>{['logged', 'queued', 'sent', 'failed'].map((s) => <option key={s}>{s}</option>)}
        </select>
        <p className="ml-auto self-center text-xs text-slate-500"><b>logged</b> = rendered &amp; stored (SMTP not configured) · secrets in links are redacted</p>
      </div>
      {isLoading ? <div className="flex justify-center py-10"><Spinner /></div> : (
        <>
          <Table rows={data.items} onRowClick={(r) => setOpenId(r.id)} columns={[
            { key: 'created_at', label: 'Time', render: (r) => fmtUtc(r.created_at) },
            { key: 'recipient', label: 'To' },
            { key: 'subject', label: 'Subject', tdClass: 'max-w-sm truncate' },
            { key: 'template_code', label: 'Template', render: (r) => <code className="text-xs">{r.template_code}</code> },
            { key: 'status', label: 'Status', render: (r) => <span title={r.error_message || ''}><StatusBadge status={r.status} /></span> },
            { key: 'act', label: '', tdClass: 'text-right', render: (r) => r.status === 'failed' && <button className="btn-ghost btn-sm" onClick={(e) => { e.stopPropagation(); resend.mutate(r.id) }}><RotateCw className="h-3.5 w-3.5" /> Resend</button> },
          ]} />
          <Pagination page={data.page} pages={data.pages} total={data.total} onChange={(page) => setQ({ ...q, page })} />
        </>
      )}
      <Modal open={!!openId} onClose={() => setOpenId(null)} size="lg" title={detail?.subject || 'Email'}>
        {detail && (
          <>
            <p className="mb-3 text-xs text-slate-500">To {detail.recipient} · {fmtUtc(detail.created_at)} · <StatusBadge status={detail.status} /> {detail.error_message}</p>
            <iframe title="email" sandbox="" srcDoc={detail.body_html} className="h-[60vh] w-full rounded-lg border border-slate-200" />
          </>
        )}
      </Modal>
    </Card>
  )
}

export default function EmailCenter() {
  const [tab, setTab] = useState('logs')
  return (
    <>
      <PageHeader title="Email center" subtitle="Notification templates and the delivery log" />
      <Tabs value={tab} onChange={setTab} tabs={[{ value: 'logs', label: 'Email log' }, { value: 'templates', label: 'Templates' }]} />
      {tab === 'logs' ? <Logs /> : <Templates />}
    </>
  )
}
