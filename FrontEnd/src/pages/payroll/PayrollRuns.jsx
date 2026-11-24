import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Calculator } from 'lucide-react'
import { api } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { useAction, useApi } from '../../lib/hooks'
import { MONTHS, fmtDateTime, money } from '../../lib/format'
import { Card, Field, Modal, PageHeader, Pagination, Spinner, StatusBadge, Table } from '../../components/ui'

export default function PayrollRuns() {
  const { can } = useAuth()
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [open, setOpen] = useState(false)
  const prev = new Date(new Date().getFullYear(), new Date().getMonth() - 1, 1)
  const [form, setForm] = useState({ year: prev.getFullYear(), month: prev.getMonth() + 1, notes: '' })
  const { data, isLoading } = useApi(['payroll-runs', page], '/payroll/runs', { page, page_size: 12 })
  const gen = useAction((b) => api.post('/payroll/runs', b).then((r) => r.data), {
    success: (d) => `Payroll generated for ${d.run.period}${d.warnings.length ? ` (${d.warnings.length} warning(s))` : ''}`,
    invalidate: ['payroll-runs', 'dash-admin'],
    onSuccess: (d) => navigate(`/payroll/${d.run.id}`),
  })
  const years = [prev.getFullYear() - 1, prev.getFullYear(), new Date().getFullYear()].filter((v, i, a) => a.indexOf(v) === i)

  return (
    <>
      <PageHeader title="Payroll" subtitle="Generate monthly salaries, review, lock and credit"
        actions={can('payroll:process') && <button className="btn-primary" onClick={() => setOpen(true)}><Calculator className="h-4 w-4" /> Run payroll</button>} />
      <Card bodyClass="p-0">
        {isLoading ? <div className="flex justify-center py-10"><Spinner /></div> : (
          <>
            <Table rows={data.items} onRowClick={(r) => navigate(`/payroll/${r.id}`)}
              empty={{ icon: Calculator, title: 'No payroll runs yet', message: 'Run payroll for a completed month to get started.' }}
              columns={[
                { key: 'period', label: 'Period', render: (r) => <span className="font-medium text-slate-900">{r.period}</span> },
                { key: 'status', label: 'Status', render: (r) => <StatusBadge status={r.status} /> },
                { key: 'employee_count', label: 'Employees' }, { key: 'working_days', label: 'Working days' },
                { key: 'total_gross', label: 'Gross', render: (r) => money(r.total_gross) },
                { key: 'total_deductions', label: 'Deductions', render: (r) => money(r.total_deductions) },
                { key: 'total_net', label: 'Net payout', render: (r) => <b>{money(r.total_net)}</b> },
                { key: 'when', label: 'Last action', render: (r) => <span className="text-xs text-slate-500">{r.paid_at ? `Paid ${fmtDateTime(r.paid_at)}` : r.locked_at ? `Locked ${fmtDateTime(r.locked_at)}` : `Generated ${fmtDateTime(r.generated_at)}`}</span> },
              ]} />
            <Pagination page={data.page} pages={data.pages} total={data.total} onChange={setPage} />
          </>
        )}
      </Card>
      <Modal open={open} onClose={() => setOpen(false)} title="Run payroll"
        footer={<button className="btn-primary" disabled={gen.isPending} onClick={() => gen.mutate({ ...form, notes: form.notes || null })}>{gen.isPending && <Spinner className="h-4 w-4 text-white" />} Generate</button>}>
        <p className="mb-4 text-sm text-slate-500">Salaries are calculated from attendance and approved leave. Unexplained absences and LOP leave are deducted automatically. The run stays in <b>draft</b> until you lock it.</p>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Month"><select className="input" value={form.month} onChange={(e) => setForm({ ...form, month: Number(e.target.value) })}>{MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select></Field>
          <Field label="Year"><select className="input" value={form.year} onChange={(e) => setForm({ ...form, year: Number(e.target.value) })}>{years.map((y) => <option key={y}>{y}</option>)}</select></Field>
          <Field label="Notes" className="col-span-2"><input className="input" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></Field>
        </div>
      </Modal>
    </>
  )
}
