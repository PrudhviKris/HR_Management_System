import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { AlertTriangle, CalendarPlus } from 'lucide-react'
import { api } from '../../api/client'
import { useAction, useApi, useLeaveTypes } from '../../lib/hooks'
import { fmtDate, fmtDateTime, number } from '../../lib/format'
import { Card, ConfirmDialog, Field, Modal, PageHeader, Pagination, Spinner, StatusBadge, Table } from '../../components/ui'

function ApplyModal({ open, onClose }) {
  const { data: types } = useLeaveTypes()
  const { register, handleSubmit, watch, reset, setValue, formState: { errors } } = useForm({ defaultValues: { is_half_day: false } })
  const [preview, setPreview] = useState(null)
  const [pvError, setPvError] = useState(null)
  const v = watch()
  const apply = useAction((b) => api.post('/leaves', b), {
    success: 'Leave request submitted', invalidate: ['my-leaves', 'my-balances', 'dash-employee'], onSuccess: () => { reset(); setPreview(null); onClose() },
  })

  useEffect(() => { if (v.is_half_day && v.start_date) setValue('end_date', v.start_date) }, [v.is_half_day, v.start_date, setValue])

  useEffect(() => {
    if (!v.leave_type_id || !v.start_date || !v.end_date) { setPreview(null); return }
    const t = setTimeout(() => {
      api.post('/leaves/preview', { leave_type_id: Number(v.leave_type_id), start_date: v.start_date, end_date: v.end_date, is_half_day: !!v.is_half_day })
        .then((r) => { setPreview(r.data); setPvError(null) })
        .catch((e) => { setPreview(null); setPvError(e.response?.data?.error?.message) })
    }, 250)
    return () => clearTimeout(t)
  }, [v.leave_type_id, v.start_date, v.end_date, v.is_half_day])

  const submit = (f) => apply.mutate({ ...f, leave_type_id: Number(f.leave_type_id), is_half_day: !!f.is_half_day })
  const active = types?.filter((t) => t.is_active) || []
  return (
    <Modal open={open} onClose={onClose} title="Apply for leave"
      footer={<button className="btn-primary" disabled={apply.isPending} onClick={handleSubmit(submit)}>{apply.isPending && <Spinner className="h-4 w-4 text-white" />} Submit request</button>}>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Leave type *" className="col-span-2" error={errors.leave_type_id?.message}>
          <select className="input" {...register('leave_type_id', { required: 'Choose a leave type' })}>
            <option value="">Select…</option>
            {active.map((t) => <option key={t.id} value={t.id}>{t.name}{!t.is_paid ? ' (unpaid)' : ''}</option>)}
          </select>
        </Field>
        <Field label="From *" error={errors.start_date?.message}><input type="date" className="input" {...register('start_date', { required: 'Required' })} /></Field>
        <Field label="To *" error={errors.end_date?.message}><input type="date" className="input" disabled={v.is_half_day} {...register('end_date', { required: 'Required' })} /></Field>
        <label className="col-span-2 flex items-center gap-2 text-sm"><input type="checkbox" {...register('is_half_day')} /> Half day (single date)</label>
        <Field label="Reason *" className="col-span-2" error={errors.reason?.message}>
          <textarea rows={3} className="input" {...register('reason', { required: 'Required', minLength: { value: 5, message: 'At least 5 characters' } })} />
        </Field>
      </div>
      {pvError && <p className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{pvError}</p>}
      {preview && (
        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
          <div className="grid grid-cols-3 gap-3 text-center">
            <div><p className="text-xs text-slate-500">Working days</p><p className="font-semibold">{number(preview.total_days)}</p></div>
            <div><p className="text-xs text-slate-500">Available balance</p><p className="font-semibold">{number(preview.available_balance)}</p></div>
            <div><p className="text-xs text-slate-500">Paid / LOP</p><p className="font-semibold">{number(preview.paid_days)} / <span className={preview.lop_days > 0 ? 'text-rose-600' : ''}>{number(preview.lop_days)}</span></p></div>
          </div>
          {preview.lop_days > 0 && (
            <p className="mt-3 flex items-start gap-2 text-xs text-amber-700"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              {number(preview.lop_days)} day(s) exceed your balance and will be treated as Loss of Pay (deducted from salary) if approved.</p>
          )}
          {preview.total_days === 0 && <p className="mt-2 text-xs text-rose-600">The selected dates fall on weekends/holidays.</p>}
        </div>
      )}
    </Modal>
  )
}

export default function MyLeaves() {
  const [open, setOpen] = useState(false)
  const [page, setPage] = useState(1)
  const [cancel, setCancel] = useState(null)
  const { data: bal } = useApi('my-balances', '/leaves/balances/me')
  const { data, isLoading } = useApi(['my-leaves', page], '/leaves/me', { page, page_size: 10 })
  const doCancel = useAction((id) => api.post(`/leaves/${id}/cancel`), { success: 'Request cancelled', invalidate: ['my-leaves', 'my-balances'], onSuccess: () => setCancel(null) })
  const today = new Date().toISOString().slice(0, 10)

  return (
    <div className="space-y-6">
      <PageHeader title="My leaves" subtitle="Balances, applications and history"
        actions={<button className="btn-primary" onClick={() => setOpen(true)}><CalendarPlus className="h-4 w-4" /> Apply for leave</button>} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {bal?.map((b) => (
          <div key={b.code} className="card p-4" style={{ borderTop: `3px solid ${b.color}` }}>
            <p className="text-sm font-medium text-slate-600">{b.leave_type}</p>
            {b.leave_type_id ? (
              <>
                <p className="mt-1 text-2xl font-semibold">{number(b.available)}<span className="text-sm font-normal text-slate-500"> / {number(b.total)}</span></p>
                <p className="text-xs text-slate-500">{number(b.used)} used · {number(b.pending)} pending{b.carried_forward > 0 ? ` · ${b.carried_forward} carried` : ''}</p>
              </>
            ) : (
              <><p className="mt-1 text-2xl font-semibold">{number(b.used)}</p><p className="text-xs text-slate-500">loss-of-pay days this year</p></>
            )}
          </div>
        ))}
      </div>
      <Card title="My requests" bodyClass="p-0">
        {isLoading ? <div className="flex justify-center py-10"><Spinner /></div> : (
          <>
            <Table rows={data.items} empty={{ title: 'No leave requests yet', message: 'Apply for leave to see it here.' }} columns={[
              { key: 'leave_type', label: 'Type', render: (r) => <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full" style={{ background: r.leave_type_color }} />{r.leave_type}</span> },
              { key: 'dates', label: 'Dates', render: (r) => `${fmtDate(r.start_date)}${r.start_date !== r.end_date ? ` – ${fmtDate(r.end_date)}` : ''}${r.is_half_day ? ' (½)' : ''}` },
              { key: 'total_days', label: 'Days' },
              { key: 'lop_days', label: 'LOP', render: (r) => <span className={r.lop_days > 0 ? 'text-rose-600' : ''}>{r.lop_days}</span> },
              { key: 'status', label: 'Status', render: (r) => <StatusBadge status={r.status} /> },
              { key: 'review', label: 'Review', render: (r) => r.reviewed_by_name ? <span className="text-xs">{r.reviewed_by_name}{r.review_comment ? `: “${r.review_comment}”` : ''}</span> : '—', tdClass: 'max-w-xs truncate' },
              { key: 'applied_at', label: 'Applied', render: (r) => fmtDateTime(r.applied_at) },
              { key: 'act', label: '', tdClass: 'text-right', render: (r) => (r.status === 'pending' || (r.status === 'approved' && r.start_date > today)) && (
                <button className="btn-ghost btn-sm text-rose-600" onClick={() => setCancel(r)}>Cancel</button>
              ) },
            ]} />
            <Pagination page={data.page} pages={data.pages} total={data.total} onChange={setPage} />
          </>
        )}
      </Card>
      <ApplyModal open={open} onClose={() => setOpen(false)} />
      <ConfirmDialog open={!!cancel} title="Cancel leave request?" confirmLabel="Cancel request" tone="danger" busy={doCancel.isPending}
        message={cancel?.status === 'approved' ? 'Your leave balance will be restored.' : 'The request will be withdrawn.'}
        onClose={() => setCancel(null)} onConfirm={() => doCancel.mutate(cancel.id)} />
    </div>
  )
}
