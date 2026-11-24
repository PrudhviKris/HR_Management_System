import { useEffect } from 'react'
import clsx from 'clsx'
import { AlertTriangle, ChevronLeft, ChevronRight, Inbox, Loader2, X } from 'lucide-react'
import { titleCase } from '../../lib/format'

export function Spinner({ className }) {
  return <Loader2 className={clsx('animate-spin text-brand-600', className || 'h-5 w-5')} />
}

export function PageLoader() {
  return (
    <div className="flex h-64 items-center justify-center">
      <Spinner className="h-8 w-8" />
    </div>
  )
}

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function Card({ title, actions, children, className, bodyClass }) {
  return (
    <div className={clsx('card', className)}>
      {(title || actions) && (
        <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-5 py-3">
          <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
          {actions}
        </div>
      )}
      <div className={clsx(bodyClass ?? 'p-5')}>{children}</div>
    </div>
  )
}

const TONES = {
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  red: 'bg-rose-50 text-rose-700 ring-rose-600/20',
  amber: 'bg-amber-50 text-amber-700 ring-amber-600/20',
  blue: 'bg-sky-50 text-sky-700 ring-sky-600/20',
  indigo: 'bg-brand-50 text-brand-700 ring-brand-600/20',
  gray: 'bg-slate-100 text-slate-600 ring-slate-500/20',
  purple: 'bg-violet-50 text-violet-700 ring-violet-600/20',
}

const STATUS_TONE = {
  active: 'green', approved: 'green', present: 'green', paid: 'green', credited: 'green', sent: 'green',
  inactive: 'gray', cancelled: 'gray', draft: 'amber', pending: 'amber', half_day: 'amber', logged: 'blue',
  queued: 'blue', locked: 'indigo', checked_in: 'blue', rejected: 'red', absent: 'red', failed: 'red',
  on_leave: 'purple', leave: 'purple', not_checked_in: 'gray', missed_checkout: 'amber', off: 'gray',
}

export function Badge({ tone = 'gray', children, className }) {
  return (
    <span className={clsx('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset', TONES[tone], className)}>
      {children}
    </span>
  )
}

export function StatusBadge({ status, label }) {
  return <Badge tone={STATUS_TONE[status] || 'gray'}>{label || titleCase(status)}</Badge>
}

export function StatCard({ label, value, icon: Icon, tone = 'indigo', hint }) {
  const tones = {
    indigo: 'bg-brand-50 text-brand-600', green: 'bg-emerald-50 text-emerald-600', amber: 'bg-amber-50 text-amber-600',
    red: 'bg-rose-50 text-rose-600', blue: 'bg-sky-50 text-sky-600', purple: 'bg-violet-50 text-violet-600',
  }
  return (
    <div className="card flex items-center gap-4 p-5">
      {Icon && (
        <div className={clsx('flex h-11 w-11 shrink-0 items-center justify-center rounded-lg', tones[tone])}>
          <Icon className="h-5 w-5" />
        </div>
      )}
      <div className="min-w-0">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
        <p className="mt-0.5 truncate text-2xl font-semibold text-slate-900">{value}</p>
        {hint && <p className="truncate text-xs text-slate-500">{hint}</p>}
      </div>
    </div>
  )
}

export function EmptyState({ title = 'Nothing here yet', message, icon: Icon = Inbox, action }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <Icon className="h-10 w-10 text-slate-300" />
      <p className="mt-3 text-sm font-medium text-slate-700">{title}</p>
      {message && <p className="mt-1 max-w-sm text-sm text-slate-500">{message}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorState({ error, onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <AlertTriangle className="h-10 w-10 text-rose-400" />
      <p className="mt-3 text-sm text-slate-700">{error?.response?.data?.error?.message || 'Failed to load data'}</p>
      {onRetry && <button className="btn-secondary btn-sm mt-3" onClick={onRetry}>Retry</button>}
    </div>
  )
}

export function Modal({ open, onClose, title, children, footer, size = 'md' }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e) => e.key === 'Escape' && onClose?.()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  if (!open) return null
  const widths = { sm: 'max-w-md', md: 'max-w-lg', lg: 'max-w-2xl', xl: 'max-w-4xl' }
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 sm:p-8" onMouseDown={onClose}>
      <div className={clsx('card my-auto w-full', widths[size])} onMouseDown={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
          <h3 className="text-base font-semibold text-slate-900">{title}</h3>
          <button className="btn-ghost btn-sm" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-slate-100 px-5 py-3">{footer}</div>}
      </div>
    </div>
  )
}

export function ConfirmDialog({ open, title, message, confirmLabel = 'Confirm', tone = 'primary', onConfirm, onClose, busy, children }) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      size="sm"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose} disabled={busy}>Cancel</button>
          <button className={tone === 'danger' ? 'btn-danger' : 'btn-primary'} onClick={onConfirm} disabled={busy}>
            {busy && <Spinner className="h-4 w-4 text-white" />} {confirmLabel}
          </button>
        </>
      }
    >
      <p className="text-sm text-slate-600">{message}</p>
      {children}
    </Modal>
  )
}

export function Pagination({ page, pages, total, onChange }) {
  if (!total) return null
  return (
    <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-sm text-slate-500">
      <span>{total} record{total === 1 ? '' : 's'}</span>
      <div className="flex items-center gap-2">
        <button className="btn-secondary btn-sm" disabled={page <= 1} onClick={() => onChange(page - 1)} aria-label="Previous page">
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span>Page {page} of {Math.max(pages, 1)}</span>
        <button className="btn-secondary btn-sm" disabled={page >= pages} onClick={() => onChange(page + 1)} aria-label="Next page">
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

export function Field({ label, error, children, hint, className }) {
  return (
    <label className={clsx('block', className)}>
      {label && <span className="label">{label}</span>}
      {children}
      {error ? <span className="mt-1 block text-xs text-rose-600">{error}</span> : hint && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}
    </label>
  )
}

export function Table({ columns, rows, empty, rowKey = 'id', onRowClick }) {
  if (!rows?.length) return <EmptyState {...(empty || {})} />
  return (
    <div className="overflow-x-auto">
      <table className="table">
        <thead>
          <tr>{columns.map((c) => <th key={c.key} className={c.thClass}>{c.label}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {rows.map((r, i) => (
            <tr key={r[rowKey] ?? i} onClick={onRowClick ? () => onRowClick(r) : undefined} className={onRowClick ? 'cursor-pointer' : ''}>
              {columns.map((c) => <td key={c.key} className={c.tdClass}>{c.render ? c.render(r) : r[c.key] ?? '—'}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Tabs({ tabs, value, onChange }) {
  return (
    <div className="mb-5 flex gap-1 overflow-x-auto border-b border-slate-200">
      {tabs.map((t) => (
        <button key={t.value} className={clsx('tab whitespace-nowrap', value === t.value && 'tab-active')} onClick={() => onChange(t.value)}>
          {t.label}
        </button>
      ))}
    </div>
  )
}

export function Avatar({ name, className }) {
  const initials = (name || '?').split(' ').filter(Boolean).slice(0, 2).map((p) => p[0]).join('').toUpperCase()
  return (
    <span className={clsx('inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700', className)}>
      {initials}
    </span>
  )
}
