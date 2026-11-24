import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { ArrowLeft, Banknote, Lock, RefreshCw, Trash2, X } from 'lucide-react'
import { api } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { useAction, useApi } from '../../lib/hooks'
import { fmtDateTime, money } from '../../lib/format'
import { Card, ConfirmDialog, ErrorState, Field, PageHeader, PageLoader, StatCard, StatusBadge, Table } from '../../components/ui'
import PayslipView from '../../components/PayslipView'

function AdjustmentEditor({ slip, onChanged }) {
  const { register, handleSubmit, reset, formState: { errors } } = useForm({ defaultValues: { kind: 'earning' } })
  const add = useAction((b) => api.post(`/payroll/payslips/${slip.id}/adjustments`, b).then((r) => r.data), { success: 'Adjustment added', onSuccess: (d) => { reset({ kind: 'earning' }); onChanged(d) } })
  const remove = useAction((aid) => api.delete(`/payroll/payslips/${slip.id}/adjustments/${aid}`).then((r) => r.data), { success: 'Adjustment removed', onSuccess: onChanged })
  return (
    <div className="mt-5 border-t border-slate-100 pt-4">
      <p className="mb-2 text-sm font-semibold">Manual adjustments</p>
      {slip.adjustments.map((a) => (
        <div key={a.id} className="mb-2 flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
          <span><StatusBadge status={a.kind === 'earning' ? 'approved' : 'rejected'} label={a.kind} /> <b className="ml-1">{a.label}</b> · {money(a.amount)} <span className="text-xs text-slate-500">— {a.reason}</span></span>
          <button className="btn-ghost btn-sm" onClick={() => remove.mutate(a.id)} aria-label="Remove"><X className="h-3.5 w-3.5" /></button>
        </div>
      ))}
      <form onSubmit={handleSubmit((v) => add.mutate({ ...v, amount: Number(v.amount) }))} className="grid grid-cols-2 gap-3 sm:grid-cols-5" noValidate>
        <select className="input" {...register('kind')}><option value="earning">Earning (+)</option><option value="deduction">Deduction (−)</option></select>
        <input className="input" placeholder="Label" {...register('label', { required: true, minLength: 2 })} />
        <input className="input" type="number" step="0.01" min="0" placeholder="Amount" {...register('amount', { required: true, min: 0.01 })} />
        <input className="input" placeholder="Reason" {...register('reason', { required: true, minLength: 5 })} />
        <button className="btn-primary" disabled={add.isPending}>Add</button>
      </form>
      {Object.keys(errors).length > 0 && <p className="mt-1 text-xs text-rose-600">Label, positive amount and a reason (5+ chars) are required.</p>}
    </div>
  )
}

export default function PayrollRunDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { can } = useAuth()
  const [confirm, setConfirm] = useState(null)
  const [viewId, setViewId] = useState(null)
  const { data: run, isLoading, error, refetch } = useApi(['payroll-run', id], `/payroll/runs/${id}`)
  const inv = [['payroll-run', id], 'payroll-runs', 'dash-admin']
  const done = () => setConfirm(null)
  const regen = useAction(() => api.post(`/payroll/runs/${id}/regenerate`).then((r) => r.data), { success: (d) => `Recalculated${d.warnings.length ? ` · ${d.warnings.join('; ')}` : ''}`, invalidate: inv, onSuccess: done })
  const lock = useAction(() => api.post(`/payroll/runs/${id}/lock`), { success: 'Payroll locked · payslips generated and emailed', invalidate: inv, onSuccess: done })
  const credit = useAction(() => api.post(`/payroll/runs/${id}/credit`).then((r) => r.data), { success: (d) => `${d.credited} salaries credited${d.failed.length ? `, ${d.failed.length} failed` : ''}`, invalidate: inv, onSuccess: done })
  const discard = useAction(() => api.delete(`/payroll/runs/${id}`), { success: 'Draft discarded', invalidate: ['payroll-runs'], onSuccess: () => navigate('/payroll') })

  if (isLoading) return <PageLoader />
  if (error) return <ErrorState error={error} onRetry={refetch} />
  const draft = run.status === 'draft'
  const proc = can('payroll:process')
  const viewing = run.payslips.find((s) => s.id === viewId)
  const busy = regen.isPending || lock.isPending || credit.isPending || discard.isPending

  return (
    <>
      <Link to="/payroll" className="mb-3 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"><ArrowLeft className="h-4 w-4" /> All payroll runs</Link>
      <PageHeader
        title={<span className="flex items-center gap-3">Payroll · {run.period} <StatusBadge status={run.status} /></span>}
        subtitle={[run.generated_at && `Generated ${fmtDateTime(run.generated_at)} by ${run.generated_by_name}`, run.locked_at && `locked ${fmtDateTime(run.locked_at)} by ${run.locked_by_name}`, run.paid_at && `credited ${fmtDateTime(run.paid_at)}`].filter(Boolean).join(' · ')}
        actions={proc && (
          <>
            {draft && <button className="btn-secondary" onClick={() => setConfirm('discard')}><Trash2 className="h-4 w-4" /> Discard</button>}
            {draft && <button className="btn-secondary" onClick={() => setConfirm('regen')}><RefreshCw className="h-4 w-4" /> Recalculate</button>}
            {draft && <button className="btn-primary" onClick={() => setConfirm('lock')}><Lock className="h-4 w-4" /> Lock &amp; generate payslips</button>}
            {run.status === 'locked' && <button className="btn-success" onClick={() => setConfirm('credit')}><Banknote className="h-4 w-4" /> Credit salaries</button>}
          </>
        )}
      />
      {draft && <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">This payroll is a <b>draft</b>. Review payslips and add manual adjustments, then lock it. Locking freezes attendance, leave and salary data for {run.period}.</div>}
      {run.notes && <p className="mb-4 text-sm text-slate-500">Notes: {run.notes}</p>}
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Employees" value={run.employee_count} hint={`${run.working_days} working days`} />
        <StatCard label="Gross" value={money(run.total_gross)} tone="blue" />
        <StatCard label="Deductions" value={money(run.total_deductions)} tone="amber" />
        <StatCard label="Net payout" value={money(run.total_net)} tone="green" hint={Object.entries(run.payment_summary).map(([k, v]) => `${v} ${k}`).join(' · ')} />
      </div>
      <Card title="Payslips" bodyClass="p-0">
        <Table rows={run.payslips} onRowClick={(s) => setViewId(s.id)} columns={[
          { key: 'employee_name', label: 'Employee', render: (s) => <div><p className="font-medium text-slate-800">{s.employee_name}</p><p className="text-xs text-slate-500">{s.employee_code} · {s.department_name}</p></div> },
          { key: 'eligible_days', label: 'Eligible' }, { key: 'paid_days', label: 'Paid days' },
          { key: 'lop_days', label: 'LOP', render: (s) => <span className={s.lop_days > 0 ? 'font-semibold text-rose-600' : ''}>{s.lop_days}</span> },
          { key: 'gross_earnings', label: 'Gross', render: (s) => money(s.gross_earnings) },
          { key: 'lop_deduction', label: 'LOP ded.', render: (s) => money(s.lop_deduction) },
          { key: 'total_deductions', label: 'Deductions', render: (s) => money(s.total_deductions) },
          { key: 'net_salary', label: 'Net', render: (s) => <b>{money(s.net_salary)}</b> },
          { key: 'adj', label: 'Adj.', render: (s) => s.adjustments.length ? <StatusBadge status="locked" label={`${s.adjustments.length}`} /> : '' },
          { key: 'payment_status', label: 'Payment', render: (s) => <span title={s.transaction_ref || ''}><StatusBadge status={s.payment_status} /></span> },
        ]} />
      </Card>
      {viewing && (
        <PayslipView slip={viewing} onClose={() => setViewId(null)}
          footerExtra={draft && <span className="mr-auto self-center text-xs text-slate-400">PDF is a draft preview</span>}>
          {draft && can('payroll:adjust') && <AdjustmentEditor slip={viewing} onChanged={() => refetch()} />}
        </PayslipView>
      )}
      <ConfirmDialog open={confirm === 'lock'} title={`Lock payroll for ${run.period}?`} confirmLabel="Lock payroll" busy={busy} onClose={done} onConfirm={() => lock.mutate()}
        message="Payslip PDFs will be generated and emailed to every employee. Attendance, leave, holidays and salaries for this month can no longer be changed." />
      <ConfirmDialog open={confirm === 'credit'} title="Credit salaries?" confirmLabel="Credit now" busy={busy} onClose={done} onConfirm={() => credit.mutate()}
        message={`Simulates a bank transfer of ${money(run.total_net)} to ${run.employee_count} employees (no real payment). Employees without bank details will be marked failed.`} />
      <ConfirmDialog open={confirm === 'regen'} title="Recalculate payroll?" confirmLabel="Recalculate" busy={busy} onClose={done} onConfirm={() => regen.mutate()}
        message="Salaries are recomputed from the latest attendance, leave and salary data. Manual adjustments are kept." />
      <ConfirmDialog open={confirm === 'discard'} title="Discard draft?" tone="danger" confirmLabel="Discard" busy={busy} onClose={done} onConfirm={() => discard.mutate()}
        message="The draft run and its payslips (including adjustments) will be deleted." />
    </>
  )
}
