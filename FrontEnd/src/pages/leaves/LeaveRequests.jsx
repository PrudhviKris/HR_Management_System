import { useState } from 'react'
import { Check, X } from 'lucide-react'
import { api } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { useAction, useApi, useDepartments, useLeaveTypes } from '../../lib/hooks'
import { fmtDate, fmtDateTime } from '../../lib/format'
import { Card, Field, Modal, PageHeader, Pagination, Spinner, StatusBadge, Table, Tabs } from '../../components/ui'

export default function LeaveRequests({ initialStatus = '' }) {
  const { can, user } = useAuth()
  const [status, setStatus] = useState(initialStatus)
  const [filters, setFilters] = useState({ department_id: '', leave_type_id: '', page: 1 })
  const [decision, setDecision] = useState(null) // {req, action}
  const [comment, setComment] = useState('')
  const { data: depts } = useDepartments()
  const { data: types } = useLeaveTypes()
  const params = Object.fromEntries(Object.entries({ ...filters, status, page_size: 15 }).filter(([, v]) => v !== ''))
  const { data, isLoading } = useApi(['leaves', params], '/leaves', params, { placeholderData: (p) => p })
  const decide = useAction(
    ({ req, action }) => api.post(`/leaves/${req.id}/${action}`, { comment: comment || null }),
    { success: (_, { action }) => `Request ${action === 'approve' ? 'approved' : 'rejected'}`, invalidate: ['leaves', 'dash-admin', 'notif-count'], onSuccess: () => { setDecision(null); setComment('') } },
  )
  const set = (k) => (e) => setFilters((f) => ({ ...f, [k]: e.target.value, page: 1 }))
  const canReview = (r) => can('leave:approve') && r.status === 'pending' && r.employee_id !== user.employee?.id

  return (
    <>
      <PageHeader title="Leave requests" subtitle="Review, approve or reject employee leave" />
      <Tabs value={status} onChange={(s) => { setStatus(s); setFilters((f) => ({ ...f, page: 1 })) }}
        tabs={[{ value: 'pending', label: 'Pending' }, { value: 'approved', label: 'Approved' }, { value: 'rejected', label: 'Rejected' }, { value: 'cancelled', label: 'Cancelled' }, { value: '', label: 'All' }]} />
      <Card bodyClass="p-0">
        <div className="flex flex-wrap gap-3 border-b border-slate-100 p-4">
          <select className="input w-48" value={filters.department_id} onChange={set('department_id')}>
            <option value="">All departments</option>{depts?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          <select className="input w-44" value={filters.leave_type_id} onChange={set('leave_type_id')}>
            <option value="">All leave types</option>{types?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        </div>
        {isLoading ? <div className="flex justify-center py-10"><Spinner /></div> : (
          <>
            <Table rows={data.items} empty={{ title: status === 'pending' ? 'No pending requests' : 'No requests found', message: status === 'pending' ? 'All caught up!' : undefined }} columns={[
              { key: 'employee_name', label: 'Employee', render: (r) => <div><p className="font-medium text-slate-800">{r.employee_name}</p><p className="text-xs text-slate-500">{r.employee_code} · {r.department_name || '—'}</p></div> },
              { key: 'leave_type', label: 'Type', render: (r) => <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full" style={{ background: r.leave_type_color }} />{r.leave_type}</span> },
              { key: 'dates', label: 'Dates', render: (r) => `${fmtDate(r.start_date)}${r.start_date !== r.end_date ? ` – ${fmtDate(r.end_date)}` : ''}${r.is_half_day ? ' (½)' : ''}` },
              { key: 'total_days', label: 'Days' },
              { key: 'lop_days', label: 'LOP', render: (r) => <span className={r.lop_days > 0 ? 'font-semibold text-rose-600' : ''}>{r.lop_days}</span> },
              { key: 'reason', label: 'Reason', tdClass: 'max-w-56 truncate', render: (r) => <span title={r.reason}>{r.reason}</span> },
              { key: 'status', label: 'Status', render: (r) => <StatusBadge status={r.status} /> },
              { key: 'applied_at', label: 'Applied', render: (r) => fmtDateTime(r.applied_at) },
              { key: 'act', label: '', tdClass: 'text-right', render: (r) => canReview(r) ? (
                <div className="flex justify-end gap-1">
                  <button className="btn-success btn-sm" onClick={() => setDecision({ req: r, action: 'approve' })}><Check className="h-3.5 w-3.5" /> Approve</button>
                  <button className="btn-secondary btn-sm" onClick={() => setDecision({ req: r, action: 'reject' })}><X className="h-3.5 w-3.5" /> Reject</button>
                </div>
              ) : r.reviewed_by_name ? <span className="text-xs text-slate-400">by {r.reviewed_by_name}</span> : null },
            ]} />
            <Pagination page={data.page} pages={data.pages} total={data.total} onChange={(page) => setFilters((f) => ({ ...f, page }))} />
          </>
        )}
      </Card>
      <Modal open={!!decision} onClose={() => setDecision(null)} title={decision?.action === 'approve' ? 'Approve leave' : 'Reject leave'}
        footer={<button className={decision?.action === 'approve' ? 'btn-success' : 'btn-danger'} disabled={decide.isPending || (decision?.action === 'reject' && comment.trim().length < 3)}
          onClick={() => decide.mutate(decision)}>{decide.isPending && <Spinner className="h-4 w-4 text-white" />} {decision?.action === 'approve' ? 'Approve' : 'Reject'}</button>}>
        {decision && (
          <div className="space-y-4">
            <div className="rounded-lg bg-slate-50 p-3 text-sm">
              <p><b>{decision.req.employee_name}</b> · {decision.req.leave_type}</p>
              <p className="text-slate-600">{fmtDate(decision.req.start_date)} – {fmtDate(decision.req.end_date)} · {decision.req.total_days} working day(s)</p>
              <p className="mt-1 text-slate-600">“{decision.req.reason}”</p>
              {decision.action === 'approve' && decision.req.lop_days > 0 && (
                <p className="mt-2 text-xs text-amber-700">Estimated {decision.req.lop_days} day(s) Loss of Pay: the balance is insufficient. The final split is recalculated on approval.</p>
              )}
            </div>
            <Field label={decision.action === 'reject' ? 'Reason for rejection *' : 'Comment (optional)'}>
              <textarea className="input" rows={3} value={comment} onChange={(e) => setComment(e.target.value)} />
            </Field>
          </div>
        )}
      </Modal>
    </>
  )
}
