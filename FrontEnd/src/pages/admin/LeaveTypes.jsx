import { useForm } from 'react-hook-form'
import { api } from '../../api/client'
import { useAction, useApi, useLeaveTypes } from '../../lib/hooks'
import { Card, Field, PageHeader, StatusBadge } from '../../components/ui'
import CrudSection from '../../components/CrudSection'

function BalanceAdjuster() {
  const { data: types } = useLeaveTypes()
  const { data: emps } = useApi(['employees', 'all-active'], '/employees', { status: 'active', page_size: 100 })
  const { register, handleSubmit, watch } = useForm({ defaultValues: { year: new Date().getFullYear() } })
  const [empId, year] = watch(['employee_id', 'year'])
  const { data: bal } = useApi(['balances', empId, year], `/leaves/balances/${empId}`, { year }, { enabled: !!empId })
  const adjust = useAction((b) => api.post('/leaves/balances/adjust', b), { success: 'Balance updated', invalidate: ['balances'] })
  return (
    <Card title="Adjust an employee's leave allocation">
      <form className="grid gap-3 sm:grid-cols-6" onSubmit={handleSubmit((v) => adjust.mutate({ ...v, employee_id: Number(v.employee_id), leave_type_id: Number(v.leave_type_id), year: Number(v.year), allocated: Number(v.allocated) }))}>
        <Field label="Employee" className="sm:col-span-2"><select className="input" {...register('employee_id', { required: true })}><option value="">Select…</option>{emps?.items.map((e) => <option key={e.id} value={e.id}>{e.full_name} ({e.employee_code})</option>)}</select></Field>
        <Field label="Leave type"><select className="input" {...register('leave_type_id', { required: true })}>{types?.filter((t) => t.is_paid).map((t) => <option key={t.id} value={t.id}>{t.code}</option>)}</select></Field>
        <Field label="Year"><input type="number" className="input" {...register('year')} /></Field>
        <Field label="New allocation"><input type="number" step="0.5" min="0" className="input" {...register('allocated', { required: true })} /></Field>
        <Field label="Reason"><input className="input" {...register('reason', { required: true, minLength: 5 })} /></Field>
        <div className="sm:col-span-6 flex items-center justify-between">
          <div className="flex flex-wrap gap-3 text-xs text-slate-500">
            {bal?.filter((b) => b.leave_type_id).map((b) => <span key={b.code}><b>{b.code}</b>: {b.allocated} allocated + {b.carried_forward} carried, {b.used} used, {b.available} left</span>)}
          </div>
          <button className="btn-primary" disabled={adjust.isPending}>Update allocation</button>
        </div>
      </form>
    </Card>
  )
}

export default function LeaveTypes() {
  return (
    <div className="space-y-6">
      <PageHeader title="Leave types" subtitle="Configure leave categories, annual quotas and carry-forward" />
      <CrudSection title="Leave types" url="/leaves/types" queryKey="leave-types" canDelete={false} invalidate={['my-balances']}
        columns={[
          { key: 'name', label: 'Name', render: (r) => <span className="flex items-center gap-2 font-medium text-slate-800"><span className="h-2.5 w-2.5 rounded-full" style={{ background: r.color }} />{r.name}</span> },
          { key: 'code', label: 'Code' },
          { key: 'annual_quota', label: 'Annual quota', render: (r) => (r.is_paid ? `${r.annual_quota} days` : '—') },
          { key: 'is_paid', label: 'Paid', render: (r) => <StatusBadge status={r.is_paid ? 'approved' : 'rejected'} label={r.is_paid ? 'Paid' : 'Unpaid (LOP)'} /> },
          { key: 'carry_forward', label: 'Carry forward', render: (r) => (r.carry_forward ? `Up to ${r.max_carry_forward} d` : 'No') },
          { key: 'is_active', label: 'Status', render: (r) => <StatusBadge status={r.is_active ? 'active' : 'inactive'} /> },
        ]}
        fields={[
          { name: 'name', label: 'Name', rules: { required: 'Required' }, half: true },
          { name: 'code', label: 'Code', rules: { required: 'Required' }, half: true },
          { name: 'annual_quota', label: 'Annual quota (days)', type: 'number', step: '0.5', half: true, default: 0 },
          { name: 'color', label: 'Colour', type: 'color', half: true, default: '#6366f1' },
          { name: 'is_paid', label: 'Paid leave (unpaid types are fully Loss of Pay)', type: 'checkbox', default: true },
          { name: 'carry_forward', label: 'Allow carry forward to next year', type: 'checkbox' },
          { name: 'max_carry_forward', label: 'Max carry forward (days)', type: 'number', step: '0.5', half: true, default: 0 },
          { name: 'description', label: 'Description' },
          { name: 'is_active', label: 'Active', type: 'checkbox', default: true },
        ]}
        toBody={(v) => ({ ...v, annual_quota: Number(v.annual_quota || 0), max_carry_forward: Number(v.max_carry_forward || 0), description: v.description || null })} />
      <BalanceAdjuster />
    </div>
  )
}
