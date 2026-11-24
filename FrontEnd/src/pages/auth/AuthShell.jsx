import { CalendarCheck, FileText, ShieldCheck, Wallet } from 'lucide-react'

export default function AuthShell({ title, subtitle, children }) {
  return (
    <div className="flex min-h-full">
      <div className="hidden w-1/2 flex-col justify-between bg-gradient-to-br from-brand-700 via-brand-600 to-indigo-500 p-12 text-white lg:flex">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/15 font-bold">H</div>
          <span className="text-lg font-semibold">HRMS</span>
        </div>
        <div>
          <h2 className="text-3xl font-semibold leading-tight">People, attendance and payroll<br />in one secure place.</h2>
          <div className="mt-8 grid grid-cols-2 gap-4 text-sm text-indigo-100">
            {[[CalendarCheck, 'Attendance & leave'], [Wallet, 'Payroll processing'], [FileText, 'PDF salary slips'], [ShieldCheck, 'Role-based access']].map(([Icon, t]) => (
              <div key={t} className="flex items-center gap-2"><Icon className="h-4 w-4" />{t}</div>
            ))}
          </div>
        </div>
        <p className="text-xs text-indigo-200">© {new Date().getFullYear()} HRMS</p>
      </div>
      <div className="flex flex-1 items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
          <div className="mt-8">{children}</div>
        </div>
      </div>
    </div>
  )
}
