import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, Search, Users } from 'lucide-react'
import { useAuth } from '../../auth/AuthContext'
import { useApi, useDepartments } from '../../lib/hooks'
import { fmtDate, titleCase } from '../../lib/format'
import { Avatar, Card, ErrorState, PageHeader, Pagination, Spinner, StatusBadge, Table } from '../../components/ui'

export default function EmployeeList() {
  const { can } = useAuth()
  const navigate = useNavigate()
  const [filters, setFilters] = useState({ search: '', department_id: '', status: 'active', page: 1 })
  const params = Object.fromEntries(Object.entries({ ...filters, page_size: 15 }).filter(([, v]) => v !== ''))
  const { data, isLoading, error, refetch } = useApi(['employees', params], '/employees', params, { placeholderData: (p) => p })
  const { data: depts } = useDepartments()
  const set = (k) => (e) => setFilters((f) => ({ ...f, [k]: e.target.value, page: 1 }))

  return (
    <>
      <PageHeader
        title="Employees"
        subtitle="Directory of everyone in the organisation"
        actions={can('employee:create', 'salary:manage') && <Link to="/employees/new" className="btn-primary"><Plus className="h-4 w-4" /> Add employee</Link>}
      />
      <Card bodyClass="p-0">
        <div className="flex flex-wrap gap-3 border-b border-slate-100 p-4">
          <div className="relative min-w-56 flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input className="input pl-9" placeholder="Search name, ID, email or phone" value={filters.search} onChange={set('search')} />
          </div>
          <select className="input w-48" value={filters.department_id} onChange={set('department_id')}>
            <option value="">All departments</option>
            {depts?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          <select className="input w-36" value={filters.status} onChange={set('status')}>
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
        {isLoading ? <div className="flex justify-center py-12"><Spinner /></div> : error ? <ErrorState error={error} onRetry={refetch} /> : (
          <>
            <Table
              onRowClick={(r) => navigate(`/employees/${r.id}`)}
              empty={{ icon: Users, title: 'No employees found', message: 'Try changing the filters.' }}
              rows={data.items}
              columns={[
                { key: 'name', label: 'Employee', render: (r) => (
                  <div className="flex items-center gap-3">
                    <Avatar name={r.full_name} />
                    <div><p className="font-medium text-slate-900">{r.full_name}</p><p className="text-xs text-slate-500">{r.email}</p></div>
                  </div>
                ) },
                { key: 'employee_code', label: 'ID' },
                { key: 'department_name', label: 'Department' },
                { key: 'designation_title', label: 'Designation' },
                { key: 'role', label: 'Role' },
                { key: 'employment_type', label: 'Type', render: (r) => titleCase(r.employment_type) },
                { key: 'date_of_joining', label: 'Joined', render: (r) => fmtDate(r.date_of_joining) },
                { key: 'status', label: 'Status', render: (r) => <StatusBadge status={r.status} /> },
              ]}
            />
            <Pagination page={data.page} pages={data.pages} total={data.total} onChange={(page) => setFilters((f) => ({ ...f, page }))} />
          </>
        )}
      </Card>
    </>
  )
}
