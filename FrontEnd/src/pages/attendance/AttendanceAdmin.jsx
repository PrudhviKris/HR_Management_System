import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Pencil, Plus } from 'lucide-react'
import { api } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { useAction, useApi, useDepartments } from '../../lib/hooks'
import { fmtDate, fmtTime, isoDate, number } from '../../lib/format'
import { Card, ErrorState, Field, Modal, PageHeader, Spinner, StatusBadge, Table, Tabs } from '../../components/ui'
import AttendanceCalendar, { MonthPicker, SummaryStrip } from '../../components/AttendanceCalendar'

const STATES = { present: 'Present', half_day: 'Half day', checked_in: 'Checked in', missed_checkout: 'No check-out', on_leave: 'On leave', not_checked_in: 'Not checked in', absent: 'Absent', off: 'Off' }

export function OverrideModal({ target, onClose }) {
  const { register, handleSubmit, formState: { errors } } = useForm({
    values: target && {
      check_in: target.check_in ? fmtDate(target.check_in, "yyyy-MM-dd'T'HH:mm") : `${target.work_date}T09:30`,
      check_out: target.check_out ? fmtDate(target.check_out, "yyyy-MM-dd'T'HH:mm") : `${target.work_date}T18:30`,
      status: '', reason: '',
    },
  })
  const save = useAction((b) => api.post('/attendance/override', b), {
    success: 'Attendance corrected', invalidate: ['attendance-daily', 'attendance-summary', 'emp-attendance', 'my-attendance'], onSuccess: onClose,
  })
  if (!target) return null
  const submit = (v) => save.mutate({
    employee_id: target.employee_id, work_date: target.work_date, reason: v.reason, status: v.status || null,
    check_in: v.status === 'absent' ? null : v.check_in || null, check_out: v.status === 'absent' ? null : v.check_out || null,
  })
  return (
    <Modal open onClose={onClose} title={`Correct attendance · ${target.employee_name}`} footer={<button className="btn-primary" disabled={save.isPending} onClick={handleSubmit(submit)}>Save correction</button>}>
      <p className="mb-4 text-sm text-slate-500">Date: <b>{fmtDate(target.work_date)}</b>. Corrections are audited and blocked once payroll for the month is locked.</p>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Check-in"><input type="datetime-local" className="input" {...register('check_in')} /></Field>
        <Field label="Check-out"><input type="datetime-local" className="input" {...register('check_out')} /></Field>
        <Field label="Status" className="col-span-2" hint="Leave on 'Auto' to derive from worked hours">
          <select className="input" {...register('status')}>
            <option value="">Auto (from hours)</option><option value="present">Present</option><option value="half_day">Half day</option><option value="absent">Absent</option>
          </select>
        </Field>
        <Field label="Reason *" className="col-span-2" error={errors.reason?.message}>
          <input className="input" placeholder="e.g. Biometric device offline" {...register('reason', { required: 'A reason is required', minLength: { value: 5, message: 'At least 5 characters' } })} />
        </Field>
      </div>
    </Modal>
  )
}

function Daily() {
  const { can } = useAuth()
  const [day, setDay] = useState(isoDate(new Date()))
  const [dept, setDept] = useState('')
  const [target, setTarget] = useState(null)
  const { data: depts } = useDepartments()
  const params = { day, ...(dept && { department_id: dept }) }
  const { data, isLoading, error, refetch } = useApi(['attendance-daily', params], '/attendance/daily', params)
  return (
    <Card bodyClass="p-0">
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 p-4">
        <input type="date" className="input w-44" value={day} max={isoDate(new Date())} onChange={(e) => setDay(e.target.value)} />
        <select className="input w-48" value={dept} onChange={(e) => setDept(e.target.value)}>
          <option value="">All departments</option>{depts?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        {data && (
          <div className="ml-auto flex flex-wrap gap-2 text-xs">
            {Object.entries(data.counts).filter(([, v]) => v).map(([k, v]) => <StatusBadge key={k} status={k} label={`${k === 'late' ? 'Late' : STATES[k] || k}: ${v}`} />)}
          </div>
        )}
      </div>
      {isLoading ? <div className="flex justify-center py-12"><Spinner /></div> : error ? <ErrorState error={error} onRetry={refetch} /> : (
        <>
          {!data.is_working_day && <p className="bg-slate-50 px-4 py-2 text-xs text-slate-500">This is a weekend or holiday.</p>}
          <Table rowKey="employee_id" rows={data.rows} columns={[
            { key: 'employee_name', label: 'Employee', render: (r) => <div><p className="font-medium text-slate-800">{r.employee_name}</p><p className="text-xs text-slate-500">{r.employee_code}</p></div> },
            { key: 'department_name', label: 'Department' },
            { key: 'in', label: 'Check-in', render: (r) => r.attendance ? <span>{fmtTime(r.attendance.check_in)}{r.attendance.is_late && <span className="ml-1 text-xs text-amber-600">late</span>}</span> : '—' },
            { key: 'out', label: 'Check-out', render: (r) => fmtTime(r.attendance?.check_out) },
            { key: 'hours', label: 'Hours', render: (r) => (r.attendance?.work_hours ? number(r.attendance.work_hours) : '—') },
            { key: 'state', label: 'Status', render: (r) => <span className="flex items-center gap-1.5"><StatusBadge status={r.state} label={STATES[r.state]} />{r.attendance?.is_overridden && <span className="text-[10px] text-slate-400" title={r.attendance.override_reason}>edited</span>}</span> },
            can('attendance:override') && { key: 'act', label: '', tdClass: 'text-right', render: (r) => (
              <button className="btn-ghost btn-sm" onClick={() => setTarget({ employee_id: r.employee_id, employee_name: r.employee_name, work_date: day, check_in: r.attendance?.check_in, check_out: r.attendance?.check_out })}>
                {r.attendance ? <Pencil className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />} {r.attendance ? 'Correct' : 'Add'}
              </button>
            ) },
          ].filter(Boolean)} />
        </>
      )}
      <OverrideModal target={target} onClose={() => setTarget(null)} />
    </Card>
  )
}

function Monthly() {
  const { can } = useAuth()
  const t = new Date()
  const [ym, setYm] = useState({ year: t.getFullYear(), month: t.getMonth() + 1 })
  const [dept, setDept] = useState('')
  const [emp, setEmp] = useState(null)
  const [target, setTarget] = useState(null)
  const { data: depts } = useDepartments()
  const params = { ...ym, ...(dept && { department_id: dept }) }
  const { data, isLoading } = useApi(['attendance-summary', params], '/attendance/summary', params)
  const { data: cal, isLoading: calLoading } = useApi(['emp-attendance', emp?.employee_id, ym], `/attendance/employees/${emp?.employee_id}`, ym, { enabled: !!emp })
  return (
    <Card bodyClass="p-0">
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 p-4">
        <MonthPicker {...ym} onChange={(year, month) => setYm({ year, month })} />
        <select className="input w-48" value={dept} onChange={(e) => setDept(e.target.value)}>
          <option value="">All departments</option>{depts?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <p className="ml-auto text-xs text-slate-500">Click a row to see the day-by-day calendar</p>
      </div>
      {isLoading ? <div className="flex justify-center py-12"><Spinner /></div> : (
        <Table rowKey="employee_id" rows={data} onRowClick={setEmp} columns={[
          { key: 'employee_name', label: 'Employee', render: (r) => <div><p className="font-medium text-slate-800">{r.employee_name}</p><p className="text-xs text-slate-500">{r.employee_code} · {r.department_name}</p></div> },
          { key: 'counted_days', label: 'Working' }, { key: 'present_days', label: 'Present' }, { key: 'half_days', label: 'Half' },
          { key: 'paid_leave_days', label: 'Leave' }, { key: 'absent_days', label: 'Absent' },
          { key: 'lop_days', label: 'LOP', render: (r) => <span className={r.lop_days > 0 ? 'font-semibold text-rose-600' : ''}>{r.lop_days}</span> },
          { key: 'late_days', label: 'Late' }, { key: 'total_hours', label: 'Hours' }, { key: 'avg_hours', label: 'Avg h' },
          { key: 'attendance_pct', label: 'Att. %', render: (r) => (r.attendance_pct == null ? '—' : `${r.attendance_pct}%`) },
        ]} />
      )}
      <Modal open={!!emp} onClose={() => setEmp(null)} size="xl" title={`${emp?.employee_name} · ${fmtDate(`${ym.year}-${String(ym.month).padStart(2, '0')}-01`, 'MMMM yyyy')}`}>
        {cal && <div className="mb-4"><SummaryStrip s={cal.summary} /></div>}
        <AttendanceCalendar data={cal} loading={calLoading}
          onDayClick={can('attendance:override') ? (d) => setTarget({ employee_id: emp.employee_id, employee_name: emp.employee_name, work_date: d.date, check_in: d.check_in, check_out: d.check_out }) : undefined} />
      </Modal>
      <OverrideModal target={target} onClose={() => setTarget(null)} />
    </Card>
  )
}

export default function AttendanceAdmin() {
  const [tab, setTab] = useState('daily')
  return (
    <>
      <PageHeader title="Attendance" subtitle="Live daily board, monthly summaries and corrections" />
      <Tabs value={tab} onChange={setTab} tabs={[{ value: 'daily', label: 'Daily board' }, { value: 'monthly', label: 'Monthly summary' }]} />
      {tab === 'daily' ? <Daily /> : <Monthly />}
    </>
  )
}
