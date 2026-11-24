import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { KeyRound, Pencil, Plus, UserCheck, UserX } from 'lucide-react'
import { api } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { useAction, useApi } from '../../lib/hooks'
import { fmtDate, fmtDateTime, money, titleCase } from '../../lib/format'
import { Avatar, Card, ConfirmDialog, ErrorState, Field, Modal, PageLoader, StatusBadge, Table, Tabs } from '../../components/ui'
import AttendanceCalendar, { MonthPicker, SummaryStrip } from '../../components/AttendanceCalendar'
import DocumentsPanel from '../../components/DocumentsPanel'
import PayslipView from '../../components/PayslipView'

const Info = ({ label, value }) => (
  <div><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-0.5 text-sm font-medium text-slate-800">{value || '—'}</dd></div>
)

export function ProfileOverview({ e }) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card title="Personal">
        <dl className="grid grid-cols-2 gap-4">
          <Info label="Email" value={e.email} /><Info label="Phone" value={e.phone} />
          <Info label="Date of birth" value={fmtDate(e.date_of_birth)} /><Info label="Gender" value={titleCase(e.gender)} />
          <div className="col-span-2"><Info label="Address" value={e.address} /></div>
          <Info label="Emergency contact" value={e.emergency_contact_name} /><Info label="Emergency phone" value={e.emergency_contact_phone} />
        </dl>
      </Card>
      <Card title="Employment">
        <dl className="grid grid-cols-2 gap-4">
          <Info label="Department" value={e.department_name} /><Info label="Designation" value={e.designation_title} />
          <Info label="Manager" value={e.manager_name} /><Info label="Joined" value={fmtDate(e.date_of_joining)} />
          <Info label="Employment type" value={titleCase(e.employment_type)} /><Info label="Location" value={e.work_location} />
          <Info label="System role" value={e.role} /><Info label="Last login" value={fmtDateTime(e.last_login_at)} />
          {e.exit_date && <><Info label="Exit date" value={fmtDate(e.exit_date)} /><Info label="Exit reason" value={e.exit_reason} /></>}
        </dl>
      </Card>
      <Card title="Bank & statutory">
        <dl className="grid grid-cols-2 gap-4">
          <Info label="Bank" value={e.bank_name} /><Info label="Account" value={e.bank_account_number} />
          <Info label="IFSC" value={e.ifsc_code} /><Info label="PAN" value={e.pan_number} />
        </dl>
      </Card>
    </div>
  )
}

function SalaryTab({ id, canManage }) {
  const { data, isLoading } = useApi(['salary', id], `/employees/${id}/salary`)
  const [open, setOpen] = useState(false)
  const { register, handleSubmit, reset } = useForm()
  const save = useAction((b) => api.post(`/employees/${id}/salary`, b), { success: 'Salary revised', invalidate: [['salary', id]], onSuccess: () => { setOpen(false); reset() } })
  if (isLoading) return <PageLoader />
  const cur = data[0]
  const submit = (v) => {
    const b = { ...v }
    ;['basic', 'hra', 'conveyance_allowance', 'medical_allowance', 'special_allowance', 'tds_monthly'].forEach((k) => { b[k] = Number(b[k] || 0) })
    if (!b.effective_from) delete b.effective_from
    save.mutate(b)
  }
  return (
    <div className="space-y-6">
      {cur && (
        <Card title={`Current structure · effective ${fmtDate(cur.effective_from)}`} actions={canManage && <button className="btn-primary btn-sm" onClick={() => { reset({ ...cur, effective_from: '' }); setOpen(true) }}><Plus className="h-3.5 w-3.5" /> Revise</button>}>
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Info label="Basic" value={money(cur.basic)} /><Info label="HRA" value={money(cur.hra)} />
            <Info label="Conveyance" value={money(cur.conveyance_allowance)} /><Info label="Medical" value={money(cur.medical_allowance)} />
            <Info label="Special" value={money(cur.special_allowance)} /><Info label="TDS / month" value={money(cur.tds_monthly)} />
            <Info label="Gross / month" value={money(cur.gross_monthly)} /><Info label="Annual CTC" value={money(cur.annual_ctc)} />
            <Info label="PF" value={cur.pf_applicable ? 'Applicable' : 'No'} /><Info label="Professional tax" value={cur.professional_tax_applicable ? 'Applicable' : 'No'} />
          </dl>
        </Card>
      )}
      <Card title="Revision history" bodyClass="p-0">
        <Table rows={data} columns={[
          { key: 'effective_from', label: 'Effective', render: (r) => fmtDate(r.effective_from) },
          { key: 'basic', label: 'Basic', render: (r) => money(r.basic) },
          { key: 'gross_monthly', label: 'Gross / month', render: (r) => money(r.gross_monthly) },
          { key: 'annual_ctc', label: 'CTC', render: (r) => money(r.annual_ctc) },
          { key: 'remarks', label: 'Remarks' },
          { key: 'created_at', label: 'Recorded', render: (r) => fmtDateTime(r.created_at) },
        ]} />
      </Card>
      <Modal open={open} onClose={() => setOpen(false)} title="Revise salary" footer={<button className="btn-primary" onClick={handleSubmit(submit)} disabled={save.isPending}>Save revision</button>}>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Effective from" hint="Defaults to today"><input type="date" className="input" {...register('effective_from')} /></Field>
          {['basic', 'hra', 'conveyance_allowance', 'medical_allowance', 'special_allowance', 'tds_monthly'].map((k) => (
            <Field key={k} label={titleCase(k)}><input type="number" min="0" step="0.01" className="input" {...register(k)} /></Field>
          ))}
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" {...register('pf_applicable')} /> PF applicable</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" {...register('professional_tax_applicable')} /> PT applicable</label>
          <Field label="Remarks" className="col-span-2"><input className="input" {...register('remarks')} /></Field>
        </div>
      </Modal>
    </div>
  )
}

function AttendanceTab({ id }) {
  const t = new Date()
  const [ym, setYm] = useState({ year: t.getFullYear(), month: t.getMonth() + 1 })
  const { data, isLoading } = useApi(['emp-attendance', id, ym], `/attendance/employees/${id}`, ym)
  return (
    <Card title="Attendance" actions={<MonthPicker {...ym} onChange={(year, month) => setYm({ year, month })} />}>
      {data && <div className="mb-5"><SummaryStrip s={data.summary} /></div>}
      <AttendanceCalendar data={data} loading={isLoading} />
    </Card>
  )
}

function LeaveTab({ id }) {
  const { data: bal } = useApi(['balances', id], `/leaves/balances/${id}`)
  const { data } = useApi(['leaves', { employee_id: id }], '/leaves', { employee_id: id, page_size: 50 })
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {bal?.map((b) => (
          <div key={b.code} className="card p-4">
            <p className="text-sm text-slate-500">{b.leave_type}</p>
            <p className="text-xl font-semibold">{b.leave_type_id ? `${b.available} / ${b.total}` : b.used}</p>
            <p className="text-xs text-slate-400">{b.leave_type_id ? `${b.used} used · ${b.pending} pending` : 'days this year'}</p>
          </div>
        ))}
      </div>
      <Card title="Leave history" bodyClass="p-0">
        <Table rows={data?.items} columns={[
          { key: 'leave_type', label: 'Type' },
          { key: 'dates', label: 'Dates', render: (r) => `${fmtDate(r.start_date)} – ${fmtDate(r.end_date)}` },
          { key: 'total_days', label: 'Days' }, { key: 'lop_days', label: 'LOP' },
          { key: 'status', label: 'Status', render: (r) => <StatusBadge status={r.status} /> },
          { key: 'reviewed_by_name', label: 'Reviewed by' },
        ]} />
      </Card>
    </div>
  )
}

function PayslipsTab({ id }) {
  const { data } = useApi(['payslips', { employee_id: id }], '/payroll/payslips', { employee_id: id, page_size: 24 })
  const [view, setView] = useState(null)
  return (
    <Card title="Payslips" bodyClass="p-0">
      <Table rows={data?.items} onRowClick={setView} columns={[
        { key: 'period', label: 'Period' }, { key: 'paid_days', label: 'Paid days' }, { key: 'lop_days', label: 'LOP' },
        { key: 'gross_earnings', label: 'Gross', render: (r) => money(r.gross_earnings) },
        { key: 'net_salary', label: 'Net', render: (r) => <b>{money(r.net_salary)}</b> },
        { key: 'run_status', label: 'Payroll', render: (r) => <StatusBadge status={r.run_status} /> },
        { key: 'payment_status', label: 'Payment', render: (r) => <StatusBadge status={r.payment_status} /> },
      ]} />
      <PayslipView slip={view} onClose={() => setView(null)} />
    </Card>
  )
}

export default function EmployeeDetail() {
  const { id } = useParams()
  const { can, user } = useAuth()
  const [tab, setTab] = useState('overview')
  const [confirm, setConfirm] = useState(null)
  const [reason, setReason] = useState('')
  const [exitDate, setExitDate] = useState('')
  const { data: e, isLoading, error, refetch } = useApi(['employee', id], `/employees/${id}`)
  const inv = [['employee', id], 'employees']
  const deactivate = useAction(() => api.post(`/employees/${id}/deactivate`, { reason, exit_date: exitDate || null }), { success: 'Employee deactivated', invalidate: inv, onSuccess: () => setConfirm(null) })
  const activate = useAction(() => api.post(`/employees/${id}/activate`), { success: 'Employee reactivated', invalidate: inv, onSuccess: () => setConfirm(null) })
  const reset = useAction(() => api.post(`/employees/${id}/send-password-reset`), { success: 'Password reset link emailed', onSuccess: () => setConfirm(null) })

  if (isLoading) return <PageLoader />
  if (error) return <ErrorState error={error} onRetry={refetch} />
  const isSelf = e.user_id === user.id
  const tabs = [
    { value: 'overview', label: 'Overview' },
    can('salary:view') && { value: 'salary', label: 'Salary' },
    { value: 'documents', label: 'Documents' },
    can('attendance:view') && { value: 'attendance', label: 'Attendance' },
    can('leave:view') && { value: 'leave', label: 'Leave' },
    can('payroll:view') && { value: 'payslips', label: 'Payslips' },
  ].filter(Boolean)

  return (
    <>
      <div className="card mb-6 flex flex-wrap items-center gap-4 p-5">
        <Avatar name={e.full_name} className="h-14 w-14 text-lg" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold text-slate-900">{e.full_name}</h1>
            <StatusBadge status={e.status} />
          </div>
          <p className="text-sm text-slate-500">{e.employee_code} · {e.designation_title || 'No designation'} · {e.department_name || 'No department'}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {can('employee:update') && <Link to={`/employees/${id}/edit`} className="btn-secondary"><Pencil className="h-4 w-4" /> Edit</Link>}
          {can('employee:update') && e.status === 'active' && <button className="btn-secondary" onClick={() => setConfirm('reset')}><KeyRound className="h-4 w-4" /> Send reset link</button>}
          {can('employee:deactivate') && !isSelf && (e.status === 'active'
            ? <button className="btn-danger" onClick={() => setConfirm('deactivate')}><UserX className="h-4 w-4" /> Deactivate</button>
            : <button className="btn-success" onClick={() => setConfirm('activate')}><UserCheck className="h-4 w-4" /> Reactivate</button>)}
        </div>
      </div>
      <Tabs tabs={tabs} value={tab} onChange={setTab} />
      {tab === 'overview' && <ProfileOverview e={e} />}
      {tab === 'salary' && <SalaryTab id={id} canManage={can('salary:manage')} />}
      {tab === 'documents' && <DocumentsPanel base={`/employees/${id}`} canUpload={can('document:manage')} canDelete={can('document:manage')} />}
      {tab === 'attendance' && <AttendanceTab id={id} />}
      {tab === 'leave' && <LeaveTab id={id} />}
      {tab === 'payslips' && <PayslipsTab id={id} />}

      <ConfirmDialog open={confirm === 'deactivate'} title={`Deactivate ${e.full_name}?`} tone="danger" confirmLabel="Deactivate"
        message="Login will be blocked, active sessions revoked and pending leave requests cancelled. All history is kept."
        busy={deactivate.isPending} onClose={() => setConfirm(null)} onConfirm={() => deactivate.mutate()}>
        <div className="mt-4 space-y-3">
          <Field label="Exit date" hint="Defaults to today"><input type="date" className="input" value={exitDate} onChange={(ev) => setExitDate(ev.target.value)} /></Field>
          <Field label="Reason *"><input className="input" value={reason} onChange={(ev) => setReason(ev.target.value)} placeholder="e.g. Resigned" /></Field>
        </div>
      </ConfirmDialog>
      <ConfirmDialog open={confirm === 'activate'} title={`Reactivate ${e.full_name}?`} message="The employee will be able to sign in again." busy={activate.isPending} onClose={() => setConfirm(null)} onConfirm={() => activate.mutate()} />
      <ConfirmDialog open={confirm === 'reset'} title="Send password reset link?" message={`A secure link will be emailed to ${e.email}.`} busy={reset.isPending} onClose={() => setConfirm(null)} onConfirm={() => reset.mutate()} />
    </>
  )
}
