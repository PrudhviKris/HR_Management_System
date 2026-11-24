import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import clsx from 'clsx'
import {
  BarChart3, Bell, Building2, CalendarCheck, CalendarDays, ClipboardCheck, FileText, KeyRound, LayoutDashboard,
  LogOut, Mail, Menu, Settings, ShieldCheck, User, Users, Wallet, X, ScrollText, Tags,
} from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { useAction, useApi } from '../lib/hooks'
import { api } from '../api/client'
import { fmtDateTime } from '../lib/format'
import { Avatar } from './ui'

function useNav() {
  const { can, hasEmployee } = useAuth()
  const sections = [
    { items: [{ to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true }] },
    hasEmployee && {
      title: 'My workspace',
      items: [
        can('attendance:self') && { to: '/my/attendance', label: 'My Attendance', icon: CalendarCheck },
        can('leave:apply') && { to: '/my/leaves', label: 'My Leaves', icon: CalendarDays },
        can('payslip:self') && { to: '/my/payslips', label: 'My Payslips', icon: FileText },
        { to: '/profile', label: 'My Profile', icon: User },
      ],
    },
    {
      title: 'Management',
      items: [
        can('employee:view') && { to: '/employees', label: 'Employees', icon: Users },
        can('attendance:view') && { to: '/attendance', label: 'Attendance', icon: ClipboardCheck },
        can('leave:view') && { to: '/leaves', label: 'Leave Requests', icon: CalendarDays },
        can('payroll:view') && { to: '/payroll', label: 'Payroll', icon: Wallet },
        can('reports:view') && { to: '/reports', label: 'Reports', icon: BarChart3 },
      ],
    },
    {
      title: 'Administration',
      items: [
        can('org:manage') && { to: '/admin/organization', label: 'Organization', icon: Building2 },
        can('leave:configure') && { to: '/admin/leave-types', label: 'Leave Types', icon: Tags },
        can('role:manage') && { to: '/admin/roles', label: 'Roles & Users', icon: ShieldCheck },
        can('notification:manage') && { to: '/admin/emails', label: 'Email Center', icon: Mail },
        can('settings:manage') && { to: '/admin/settings', label: 'Settings', icon: Settings },
        can('audit:view') && { to: '/audit', label: 'Audit Logs', icon: ScrollText },
      ],
    },
  ]
  return sections.filter(Boolean).map((s) => ({ ...s, items: s.items.filter(Boolean) })).filter((s) => s.items.length)
}

function Sidebar({ open, onClose }) {
  const nav = useNav()
  return (
    <>
      <div className={clsx('fixed inset-0 z-30 bg-slate-900/40 lg:hidden', open ? 'block' : 'hidden')} onClick={onClose} />
      <aside className={clsx(
        'fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-slate-900 text-slate-300 transition-transform lg:translate-x-0',
        open ? 'translate-x-0' : '-translate-x-full',
      )}>
        <div className="flex h-16 items-center gap-2.5 px-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">H</div>
          <div>
            <p className="text-sm font-semibold text-white">HRMS</p>
            <p className="text-[11px] text-slate-400">People &amp; Payroll</p>
          </div>
          <button className="ml-auto text-slate-400 lg:hidden" onClick={onClose} aria-label="Close menu"><X className="h-5 w-5" /></button>
        </div>
        <nav className="flex-1 space-y-5 overflow-y-auto px-3 pb-6 pt-2">
          {nav.map((section, i) => (
            <div key={i}>
              {section.title && <p className="mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">{section.title}</p>}
              <div className="space-y-0.5">
                {section.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    onClick={onClose}
                    className={({ isActive }) => clsx(
                      'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition',
                      isActive ? 'bg-brand-600 text-white' : 'hover:bg-slate-800 hover:text-white',
                    )}
                  >
                    <item.icon className="h-4 w-4" />
                    {item.label}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>
      </aside>
    </>
  )
}

function useClickOutside(ref, onOutside) {
  useEffect(() => {
    const h = (e) => ref.current && !ref.current.contains(e.target) && onOutside()
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [ref, onOutside])
}

function NotificationBell() {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const navigate = useNavigate()
  useClickOutside(ref, () => setOpen(false))
  const { data: count } = useApi('notif-count', '/notifications/unread-count', null, { refetchInterval: 60_000 })
  const { data } = useApi(['notifications'], '/notifications', { page_size: 8 }, { enabled: open })
  const readAll = useAction(() => api.post('/notifications/read-all'), { invalidate: ['notif-count', 'notifications'] })
  const readOne = useAction((id) => api.post(`/notifications/${id}/read`), { invalidate: ['notif-count', 'notifications'] })

  return (
    <div className="relative" ref={ref}>
      <button className="btn-ghost relative p-2" onClick={() => setOpen((o) => !o)} aria-label="Notifications">
        <Bell className="h-5 w-5" />
        {count?.count > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-semibold text-white">
            {count.count > 9 ? '9+' : count.count}
          </span>
        )}
      </button>
      {open && (
        <div className="card absolute right-0 z-50 mt-2 w-80 overflow-hidden">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
            <p className="text-sm font-semibold">Notifications</p>
            <button className="text-xs text-brand-600 hover:underline" onClick={() => readAll.mutate()}>Mark all read</button>
          </div>
          <div className="max-h-96 divide-y divide-slate-100 overflow-y-auto">
            {data?.items?.length ? data.items.map((n) => (
              <button
                key={n.id}
                className={clsx('block w-full px-4 py-3 text-left hover:bg-slate-50', !n.is_read && 'bg-brand-50/40')}
                onClick={() => { if (!n.is_read) readOne.mutate(n.id); setOpen(false); if (n.link) navigate(n.link) }}
              >
                <p className="text-sm font-medium text-slate-800">{n.title}</p>
                <p className="mt-0.5 text-xs text-slate-500">{n.message}</p>
                <p className="mt-1 text-[11px] text-slate-400">{fmtDateTime(n.created_at)}</p>
              </button>
            )) : <p className="px-4 py-8 text-center text-sm text-slate-500">You're all caught up</p>}
          </div>
        </div>
      )}
    </div>
  )
}

function UserMenu() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const navigate = useNavigate()
  useClickOutside(ref, () => setOpen(false))
  return (
    <div className="relative" ref={ref}>
      <button className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 hover:bg-slate-100" onClick={() => setOpen((o) => !o)}>
        <Avatar name={user.full_name} />
        <div className="hidden text-left sm:block">
          <p className="text-sm font-medium leading-tight text-slate-800">{user.full_name}</p>
          <p className="text-xs leading-tight text-slate-500">{user.role}{user.employee ? ` · ${user.employee.employee_code}` : ''}</p>
        </div>
      </button>
      {open && (
        <div className="card absolute right-0 z-50 mt-2 w-52 py-1">
          {user.employee && (
            <Link to="/profile" className="flex items-center gap-2 px-4 py-2 text-sm hover:bg-slate-50" onClick={() => setOpen(false)}>
              <User className="h-4 w-4" /> My profile
            </Link>
          )}
          <Link to="/change-password" className="flex items-center gap-2 px-4 py-2 text-sm hover:bg-slate-50" onClick={() => setOpen(false)}>
            <KeyRound className="h-4 w-4" /> Change password
          </Link>
          <button className="flex w-full items-center gap-2 px-4 py-2 text-sm text-rose-600 hover:bg-slate-50" onClick={async () => { await logout(); navigate('/login') }}>
            <LogOut className="h-4 w-4" /> Sign out
          </button>
        </div>
      )}
    </div>
  )
}

export default function Layout() {
  const [open, setOpen] = useState(false)
  const location = useLocation()
  useEffect(() => { window.scrollTo(0, 0) }, [location.pathname])
  return (
    <div className="min-h-full lg:bg-[linear-gradient(to_right,var(--color-slate-900)_16rem,transparent_16rem)]">
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur sm:px-6">
          <button className="btn-ghost p-2 lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><Menu className="h-5 w-5" /></button>
          <div className="ml-auto flex items-center gap-2">
            <NotificationBell />
            <UserMenu />
          </div>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
