import { useState } from 'react'
import { useDepartments } from '../../lib/hooks'
import { fmtDate } from '../../lib/format'
import { PageHeader, StatusBadge, Tabs } from '../../components/ui'
import CrudSection from '../../components/CrudSection'

const req = { required: 'Required' }
const activeBadge = (r) => <StatusBadge status={r.is_active ? 'active' : 'inactive'} />

export default function Organization() {
  const [tab, setTab] = useState('departments')
  const [year, setYear] = useState(new Date().getFullYear())
  const { data: depts } = useDepartments()
  return (
    <>
      <PageHeader title="Organization" subtitle="Departments, designations and the holiday calendar" />
      <Tabs value={tab} onChange={setTab} tabs={[{ value: 'departments', label: 'Departments' }, { value: 'designations', label: 'Designations' }, { value: 'holidays', label: 'Holidays' }]} />
      {tab === 'departments' && (
        <CrudSection title="Departments" url="/departments" queryKey="departments"
          columns={[
            { key: 'name', label: 'Name', render: (r) => <span className="font-medium text-slate-800">{r.name}</span> },
            { key: 'code', label: 'Code' }, { key: 'description', label: 'Description' },
            { key: 'employee_count', label: 'Active employees' }, { key: 'is_active', label: 'Status', render: activeBadge },
          ]}
          fields={[
            { name: 'name', label: 'Name', rules: req, half: true }, { name: 'code', label: 'Code', rules: req, half: true },
            { name: 'description', label: 'Description' }, { name: 'is_active', label: 'Active', type: 'checkbox', default: true },
          ]}
          toBody={(v) => ({ ...v, description: v.description || null })} />
      )}
      {tab === 'designations' && (
        <CrudSection title="Designations" url="/designations" queryKey="designations"
          columns={[
            { key: 'title', label: 'Title', render: (r) => <span className="font-medium text-slate-800">{r.title}</span> },
            { key: 'department_name', label: 'Department' }, { key: 'description', label: 'Description' },
            { key: 'is_active', label: 'Status', render: activeBadge },
          ]}
          fields={[
            { name: 'title', label: 'Title', rules: req },
            { name: 'department_id', label: 'Department', type: 'select', options: depts?.map((d) => ({ value: d.id, label: d.name })) },
            { name: 'description', label: 'Description' }, { name: 'is_active', label: 'Active', type: 'checkbox', default: true },
          ]}
          toBody={(v) => ({ ...v, department_id: v.department_id ? Number(v.department_id) : null, description: v.description || null })} />
      )}
      {tab === 'holidays' && (
        <>
          <div className="mb-4 flex items-center gap-2 text-sm">
            <span className="text-slate-500">Year</span>
            <select className="input w-28" value={year} onChange={(e) => setYear(Number(e.target.value))}>
              {[year - 1, year, year + 1].map((y) => <option key={y}>{y}</option>)}
            </select>
            <span className="text-xs text-slate-400">Mandatory holidays are excluded from working days for attendance, leave and payroll.</span>
          </div>
          <CrudSection title="Holidays" url="/holidays" queryKey="holidays" params={{ year }}
            columns={[
              { key: 'holiday_date', label: 'Date', render: (r) => fmtDate(r.holiday_date, 'EEE, dd MMM yyyy') },
              { key: 'name', label: 'Holiday', render: (r) => <span className="font-medium text-slate-800">{r.name}</span> },
              { key: 'is_optional', label: 'Type', render: (r) => <StatusBadge status={r.is_optional ? 'pending' : 'locked'} label={r.is_optional ? 'Optional' : 'Mandatory'} /> },
            ]}
            fields={[
              { name: 'holiday_date', label: 'Date', type: 'date', rules: req, half: true }, { name: 'name', label: 'Name', rules: req, half: true },
              { name: 'is_optional', label: 'Optional (restricted) holiday: still a working day', type: 'checkbox' },
            ]} />
        </>
      )}
    </>
  )
}
