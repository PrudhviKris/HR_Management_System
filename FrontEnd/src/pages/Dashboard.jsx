import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { CalendarClock, CalendarDays, Clock, PartyPopper, UserCheck, Users, Wallet } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { useApi } from '../lib/hooks'
import { fmtDate, fmtUtc, money, money0, number } from '../lib/format'
import { AXIS, GRID, SERIES, TOOLTIP } from '../lib/chart'
import { Card, EmptyState, ErrorState, PageHeader, PageLoader, StatCard, StatusBadge } from '../components/ui'
import CheckInWidget from '../components/CheckInWidget'

function Holidays({ items }) {
  return (
    <Card title="Upcoming holidays">
      {items?.length ? (
        <ul className="space-y-3">
          {items.map((h) => (
            <li key={h.date} className="flex items-center gap-3">
              <div className="flex h-10 w-10 flex-col items-center justify-center rounded-lg bg-brand-50 text-brand-700">
                <span className="text-[10px] font-semibold uppercase leading-none">{fmtDate(h.date, 'MMM')}</span>
                <span className="text-sm font-bold leading-none">{fmtDate(h.date, 'd')}</span>
              </div>
              <div>
                <p className="text-sm font-medium text-slate-800">{h.name}</p>
                <p className="text-xs text-slate-500">{fmtDate(h.date, 'EEEE')}{h.is_optional ? ' · Optional' : ''}</p>
              </div>
            </li>
          ))}
        </ul>
      ) : <EmptyState icon={PartyPopper} title="No upcoming holidays" />}
    </Card>
  )
}

function AdminDashboard() {
  const { hasEmployee, user } = useAuth()
  const { data, isLoading, error, refetch } = useApi('dash-admin', '/dashboard/admin')
  if (isLoading) return <PageLoader />
  if (error) return <ErrorState error={error} onRetry={refetch} />
  const { employees, attendance_today: att, leave, payroll } = data
  const trend = data.attendance_trend.map((d) => ({ ...d, label: fmtDate(d.date, 'dd MMM') }))

  return (
    <div className="space-y-6">
      <PageHeader title={`Welcome, ${user.full_name.split(' ')[0]}`} subtitle="Organisation overview for today" />
      {hasEmployee && <CheckInWidget />}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Active employees" value={employees.active} icon={Users} hint={`${employees.inactive} inactive · ${employees.new_this_month} joined this month`} />
        <StatCard label="Present today" value={`${att.present}/${att.total}`} icon={UserCheck} tone="green" hint={`${att.rate}% · ${att.late} late · ${att.on_leave} on leave`} />
        <StatCard label="Pending leave" value={leave.pending} icon={CalendarClock} tone="amber" hint={`${number(leave.approved_days_this_month)} leave days approved this month`} />
        <StatCard label="Last payroll" value={payroll.last_run ? money0(payroll.last_run.total_net) : '—'} icon={Wallet} tone="purple"
          hint={payroll.last_run ? `${payroll.last_run.period} · ${payroll.last_run.status}` : 'No payroll yet'} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Attendance, last 10 working days" className="lg:col-span-2">
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={trend} barGap={2} margin={{ left: -20, right: 8 }}>
                <CartesianGrid {...GRID} />
                <XAxis dataKey="label" {...AXIS} />
                <YAxis allowDecimals={false} {...AXIS} />
                <Tooltip {...TOOLTIP} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                <Bar isAnimationActive={false} dataKey="present" name="Present" fill={SERIES[0]} radius={[4, 4, 0, 0]} maxBarSize={18} />
                <Bar isAnimationActive={false} dataKey="on_leave" name="On leave" fill={SERIES[1]} radius={[4, 4, 0, 0]} maxBarSize={18} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Headcount by department">
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={employees.by_department} layout="vertical" margin={{ left: 10, right: 16 }}>
                <CartesianGrid {...GRID} horizontal={false} vertical />
                <XAxis type="number" allowDecimals={false} {...AXIS} />
                <YAxis type="category" dataKey="department" width={110} {...AXIS} />
                <Tooltip {...TOOLTIP} />
                <Bar isAnimationActive={false} dataKey="count" name="Employees" fill={SERIES[0]} radius={[0, 4, 4, 0]} maxBarSize={16} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Payroll trend" className="lg:col-span-2" actions={<Link to="/payroll" className="text-xs text-brand-600 hover:underline">Open payroll</Link>}>
          {payroll.trend.length ? (
            <div className="h-64">
              <ResponsiveContainer>
                <LineChart data={payroll.trend} margin={{ left: 10, right: 16 }}>
                  <CartesianGrid {...GRID} />
                  <XAxis dataKey="period" {...AXIS} />
                  <YAxis {...AXIS} tickFormatter={(v) => `₹${Math.round(v / 1000)}k`} />
                  <Tooltip {...TOOLTIP} formatter={(v) => money(v)} cursor={{ stroke: '#94a3b8' }} />
                  <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                  <Line isAnimationActive={false} dataKey="total_gross" name="Gross" stroke={SERIES[0]} strokeWidth={2} dot={{ r: 4 }} />
                  <Line isAnimationActive={false} dataKey="total_net" name="Net payout" stroke={SERIES[1]} strokeWidth={2} dot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : <EmptyState title="No payroll runs yet" />}
        </Card>
        <Card title="Pending leave requests" bodyClass="p-0" actions={<Link to="/leaves/approvals" className="text-xs text-brand-600 hover:underline">Review all</Link>}>
          {leave.recent_pending.length ? (
            <ul className="divide-y divide-slate-100">
              {leave.recent_pending.map((r) => (
                <li key={r.id} className="px-5 py-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-slate-800">{r.employee_name}</p>
                    <span className="text-xs text-slate-500">{r.total_days} d</span>
                  </div>
                  <p className="text-xs text-slate-500">{r.leave_type} · {fmtDate(r.start_date, 'dd MMM')} – {fmtDate(r.end_date, 'dd MMM')}</p>
                </li>
              ))}
            </ul>
          ) : <EmptyState icon={CalendarDays} title="No pending requests" />}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Recent activity" className="lg:col-span-2" bodyClass="p-0" actions={data.recent_activity.length > 0 && <Link to="/audit" className="text-xs text-brand-600 hover:underline">Audit log</Link>}>
          <ul className="divide-y divide-slate-100">
            {data.recent_activity.map((a) => (
              <li key={a.id} className="flex items-start justify-between gap-4 px-5 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm text-slate-700">{a.description}</p>
                  <p className="text-xs text-slate-400">{a.actor || 'system'} · <code>{a.action}</code></p>
                </div>
                <span className="shrink-0 text-xs text-slate-400">{fmtUtc(a.created_at)}</span>
              </li>
            ))}
          </ul>
        </Card>
        <Holidays items={data.upcoming_holidays} />
      </div>
    </div>
  )
}

function EmployeeDashboard() {
  const { user } = useAuth()
  const { data, isLoading, error, refetch } = useApi('dash-employee', '/dashboard/employee')
  if (isLoading) return <PageLoader />
  if (error) return <ErrorState error={error} onRetry={refetch} />
  const m = data.month_summary
  return (
    <div className="space-y-6">
      <PageHeader title={`Hello, ${user.full_name.split(' ')[0]} 👋`} subtitle={`${user.employee.employee_code} · Here's your month at a glance`} />
      <CheckInWidget onLeave={data.today.on_leave} />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Present this month" value={`${number(m.present_days)} d`} icon={UserCheck} tone="green" hint={`of ${m.counted_days} working days so far`} />
        <StatCard label="Hours worked" value={number(m.total_hours)} icon={Clock} tone="blue" hint={`avg ${m.avg_hours} h/day · ${m.late_days} late`} />
        <StatCard label="Leave / LOP" value={`${number(m.paid_leave_days)} / ${number(m.lop_days)}`} icon={CalendarDays} tone="amber" hint="paid leave days / loss-of-pay days" />
        <StatCard label="Latest net pay" value={data.latest_payslip ? money0(data.latest_payslip.net_salary) : '—'} icon={Wallet} tone="purple"
          hint={data.latest_payslip ? `${data.latest_payslip.period} · ${data.latest_payslip.payment_status}` : 'No payslip yet'} />
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Leave balance" className="lg:col-span-2" actions={<Link to="/my/leaves" className="text-xs text-brand-600 hover:underline">Apply for leave</Link>}>
          <div className="grid gap-4 sm:grid-cols-2">
            {data.leave_balances.filter((b) => b.leave_type_id).map((b) => (
              <div key={b.code} className="rounded-lg border border-slate-200 p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-slate-700">{b.leave_type}</p>
                  <span className="text-xs text-slate-500">{b.used} used{b.pending ? ` · ${b.pending} pending` : ''}</span>
                </div>
                <p className="mt-1 text-2xl font-semibold text-slate-900">{number(b.available)}<span className="text-sm font-normal text-slate-500"> / {number(b.total)} days</span></p>
                <div className="mt-2 h-1.5 rounded-full bg-slate-100">
                  <div className="h-1.5 rounded-full" style={{ width: `${b.total ? Math.min(100, (b.available / b.total) * 100) : 0}%`, background: SERIES[0] }} />
                </div>
              </div>
            ))}
          </div>
        </Card>
        <Holidays items={data.upcoming_holidays} />
      </div>
      <Card title="Recent leave requests" bodyClass="p-0">
        {data.recent_leaves.length ? (
          <ul className="divide-y divide-slate-100">
            {data.recent_leaves.map((r) => (
              <li key={r.id} className="flex items-center justify-between px-5 py-3">
                <div>
                  <p className="text-sm font-medium text-slate-800">{r.leave_type} · {r.total_days} day(s)</p>
                  <p className="text-xs text-slate-500">{fmtDate(r.start_date)} – {fmtDate(r.end_date)}</p>
                </div>
                <StatusBadge status={r.status} />
              </li>
            ))}
          </ul>
        ) : <EmptyState title="No leave requests yet" />}
      </Card>
    </div>
  )
}

export default function Dashboard() {
  const { can, hasEmployee } = useAuth()
  if (can('dashboard:admin')) return <AdminDashboard />
  if (hasEmployee) return <EmployeeDashboard />
  return <EmptyState title="Welcome" message="Your account has no dashboard widgets assigned." />
}
