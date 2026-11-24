import clsx from 'clsx'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { MONTHS, fmtTime, number } from '../lib/format'
import { Spinner } from './ui'

const KIND = {
  present: { label: 'Present', cls: 'bg-emerald-50 border-emerald-200 text-emerald-800' },
  half_day: { label: 'Half day', cls: 'bg-amber-50 border-amber-200 text-amber-800' },
  missed_checkout: { label: 'No check-out', cls: 'bg-amber-50 border-amber-200 text-amber-800' },
  checked_in: { label: 'Checked in', cls: 'bg-sky-50 border-sky-200 text-sky-800' },
  absent: { label: 'Absent (LOP)', cls: 'bg-rose-50 border-rose-200 text-rose-800' },
  leave: { label: 'On leave', cls: 'bg-violet-50 border-violet-200 text-violet-800' },
  holiday: { label: 'Holiday', cls: 'bg-slate-100 border-slate-200 text-slate-500' },
  weekend: { label: 'Weekend', cls: 'bg-white border-slate-100 text-slate-400' },
  future: { label: '', cls: 'bg-white border-slate-100 text-slate-400' },
  not_employed: { label: '—', cls: 'bg-white border-slate-100 text-slate-300' },
}

export function MonthPicker({ year, month, onChange }) {
  const shift = (n) => {
    const d = new Date(year, month - 1 + n, 1)
    onChange(d.getFullYear(), d.getMonth() + 1)
  }
  return (
    <div className="flex items-center gap-2">
      <button className="btn-secondary btn-sm" onClick={() => shift(-1)} aria-label="Previous month"><ChevronLeft className="h-4 w-4" /></button>
      <span className="w-36 text-center text-sm font-medium">{MONTHS[month - 1]} {year}</span>
      <button className="btn-secondary btn-sm" onClick={() => shift(1)} aria-label="Next month"><ChevronRight className="h-4 w-4" /></button>
    </div>
  )
}

export function SummaryStrip({ s }) {
  const items = [
    ['Working days', s.counted_days], ['Present', number(s.present_days)], ['Half days', s.half_days],
    ['Paid leave', number(s.paid_leave_days)], ['Absent', number(s.absent_days)], ['LOP days', number(s.lop_days)],
    ['Late', s.late_days], ['Hours', number(s.total_hours)],
  ]
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
      {items.map(([k, v]) => (
        <div key={k} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
          <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">{k}</p>
          <p className="text-lg font-semibold text-slate-900">{v}</p>
        </div>
      ))}
    </div>
  )
}

export default function AttendanceCalendar({ data, loading, onDayClick }) {
  if (loading || !data) return <div className="flex justify-center py-16"><Spinner /></div>
  const first = new Date(data.days[0].date)
  const offset = (first.getDay() + 6) % 7 // Monday-first grid
  return (
    <div>
      <div className="grid grid-cols-7 gap-1.5 text-center text-[11px] font-semibold uppercase text-slate-400">
        {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d) => <div key={d} className="py-1">{d}</div>)}
      </div>
      <div className="grid grid-cols-7 gap-1.5">
        {Array.from({ length: offset }).map((_, i) => <div key={`pad${i}`} />)}
        {data.days.map((d) => {
          const k = KIND[d.kind] || KIND.future
          const clickable = onDayClick && !['weekend', 'future', 'not_employed'].includes(d.kind)
          return (
            <button
              key={d.date}
              type="button"
              disabled={!clickable}
              onClick={() => clickable && onDayClick(d)}
              className={clsx('min-h-20 rounded-lg border p-1.5 text-left text-[11px] transition', k.cls, clickable && 'hover:ring-2 hover:ring-brand-500/30')}
              title={d.check_in ? `${fmtTime(d.check_in)} – ${d.check_out ? fmtTime(d.check_out) : '…'}` : k.label}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold">{Number(d.date.slice(8))}</span>
                {d.is_overridden && <span className="rounded bg-white/70 px-1 text-[9px] font-semibold text-slate-500" title="Corrected by HR">EDIT</span>}
              </div>
              <div className="mt-1 leading-tight">
                <p className="font-medium">{d.leave_type ? `${k.label === 'On leave' ? '' : k.label + ' · '}${d.leave_type}` : k.label}</p>
                {d.check_in && <p className="opacity-80">{fmtTime(d.check_in)}–{d.check_out ? fmtTime(d.check_out) : '…'}</p>}
                {d.work_hours > 0 && <p className="opacity-80">{d.work_hours} h{d.is_late ? ' · late' : ''}</p>}
              </div>
            </button>
          )
        })}
      </div>
      <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-500">
        {['present', 'half_day', 'leave', 'absent', 'holiday'].map((k) => (
          <span key={k} className="flex items-center gap-1.5"><span className={clsx('h-3 w-3 rounded border', KIND[k].cls)} />{KIND[k].label}</span>
        ))}
      </div>
    </div>
  )
}
