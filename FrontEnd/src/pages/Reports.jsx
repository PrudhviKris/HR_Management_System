import { useState } from 'react'
import toast from 'react-hot-toast'
import { Download, FileSpreadsheet, FileText, Play } from 'lucide-react'
import { downloadFile, errorMessage } from '../api/client'
import { useApi, useDepartments, useLeaveTypes } from '../lib/hooks'
import { MONTHS, fmtDate, fmtDateTime, isoDate, titleCase } from '../lib/format'
import { Card, ErrorState, Field, PageHeader, Spinner, Table, Tabs } from '../components/ui'

const today = new Date()
const firstOfMonth = isoDate(new Date(today.getFullYear(), today.getMonth(), 1))
const REPORTS = {
  attendance: { label: 'Attendance summary', url: '/reports/attendance' },
  'attendance-daily': { label: 'Daily attendance log', url: '/reports/attendance/daily' },
  leave: { label: 'Leave report', url: '/reports/leave' },
  payroll: { label: 'Payroll summary', url: '/reports/payroll' },
}

function cell(v) {
  if (v == null || v === '') return '—'
  if (typeof v === 'boolean') return v ? 'Yes' : 'No'
  if (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(v)) return fmtDateTime(v)
  if (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v)) return fmtDate(v)
  if (typeof v === 'number') return v.toLocaleString('en-IN', { maximumFractionDigits: 2 })
  return v
}

export default function Reports() {
  const [type, setType] = useState('attendance')
  const { data: depts } = useDepartments()
  const { data: types } = useLeaveTypes()
  const prev = new Date(today.getFullYear(), today.getMonth() - 1, 1)
  const [f, setF] = useState({
    date_from: firstOfMonth, date_to: isoDate(today), department_id: '', status: '', leave_type_id: '',
    from_year: today.getFullYear(), from_month: 1, to_year: prev.getFullYear(), to_month: prev.getMonth() + 1,
  })
  const [applied, setApplied] = useState(null)
  const params = (filters) => {
    const keys = type === 'payroll' ? ['from_year', 'from_month', 'to_year', 'to_month', 'department_id']
      : type === 'leave' ? ['date_from', 'date_to', 'department_id', 'status', 'leave_type_id'] : ['date_from', 'date_to', 'department_id']
    return Object.fromEntries(keys.map((k) => [k, filters[k]]).filter(([, v]) => v !== ''))
  }
  const q = applied && { ...params(applied) }
  const { data, isFetching, error, refetch } = useApi(['report', type, q], REPORTS[type].url, q, { enabled: !!applied })
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  const exp = (format) => downloadFile(REPORTS[type].url, { ...params(f), format }, `${type}.${format}`).catch((e) => toast.error(errorMessage(e, 'Export failed')))

  return (
    <>
      <PageHeader title="Reports & analytics" subtitle="Filter by date and department, then export to CSV or PDF" />
      <Tabs value={type} onChange={(t) => { setType(t); setApplied(null) }} tabs={Object.entries(REPORTS).map(([value, r]) => ({ value, label: r.label }))} />
      <Card className="mb-6">
        <div className="flex flex-wrap items-end gap-3">
          {type === 'payroll' ? (
            <>
              <Field label="From"><div className="flex gap-2">
                <select className="input w-32" value={f.from_month} onChange={set('from_month')}>{MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select>
                <input type="number" className="input w-24" value={f.from_year} onChange={set('from_year')} />
              </div></Field>
              <Field label="To"><div className="flex gap-2">
                <select className="input w-32" value={f.to_month} onChange={set('to_month')}>{MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select>
                <input type="number" className="input w-24" value={f.to_year} onChange={set('to_year')} />
              </div></Field>
            </>
          ) : (
            <>
              <Field label="From"><input type="date" className="input" value={f.date_from} onChange={set('date_from')} /></Field>
              <Field label="To"><input type="date" className="input" value={f.date_to} onChange={set('date_to')} /></Field>
            </>
          )}
          <Field label="Department">
            <select className="input w-48" value={f.department_id} onChange={set('department_id')}>
              <option value="">All departments</option>{depts?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </Field>
          {type === 'leave' && (
            <>
              <Field label="Status"><select className="input w-36" value={f.status} onChange={set('status')}><option value="">Any</option>{['pending', 'approved', 'rejected', 'cancelled'].map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}</select></Field>
              <Field label="Leave type"><select className="input w-40" value={f.leave_type_id} onChange={set('leave_type_id')}><option value="">Any</option>{types?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></Field>
            </>
          )}
          <button className="btn-primary" onClick={() => { setApplied({ ...f }); if (applied) refetch() }}><Play className="h-4 w-4" /> Run report</button>
          <div className="ml-auto flex gap-2">
            <button className="btn-secondary" onClick={() => exp('csv')}><FileSpreadsheet className="h-4 w-4" /> CSV</button>
            <button className="btn-secondary" onClick={() => exp('pdf')}><FileText className="h-4 w-4" /> PDF</button>
          </div>
        </div>
      </Card>
      {applied && (
        <Card title={data?.title} bodyClass="p-0" actions={data && <span className="text-xs text-slate-500">{data.rows.length} rows</span>}>
          {isFetching ? <div className="flex justify-center py-10"><Spinner /></div> : error ? <ErrorState error={error} /> : data && (
            <>
              {data.summary?.length > 0 && (
                <div className="grid gap-3 border-b border-slate-100 p-4 sm:grid-cols-2 lg:grid-cols-4">
                  {data.summary.map((s) => (
                    <div key={s.leave_type} className="rounded-lg border border-slate-200 p-3 text-sm">
                      <p className="font-medium">{s.leave_type}</p>
                      <p className="text-xs text-slate-500">{s.requests} requests · {s.approved_days} approved days · {s.pending_days} pending · {s.lop_days} LOP</p>
                    </div>
                  ))}
                </div>
              )}
              <Table rows={data.totals ? [...data.rows, { ...data.totals, __total: true }] : data.rows}
                empty={{ icon: Download, title: 'No data for the selected filters' }}
                columns={data.columns.map((c) => ({ key: c.key, label: c.label, render: (r) => r.__total ? <b>{cell(r[c.key])}</b> : cell(r[c.key]) }))} />
            </>
          )}
        </Card>
      )}
    </>
  )
}
