import { useEffect, useState } from 'react'
import { Clock, LogIn, LogOut } from 'lucide-react'
import { api } from '../api/client'
import { useAction, useApi } from '../lib/hooks'
import { fmtTime } from '../lib/format'
import { Spinner, StatusBadge } from './ui'

function useNow() {
  const [now, setNow] = useState(new Date())
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 30_000); return () => clearInterval(t) }, [])
  return now
}

export default function CheckInWidget({ onLeave }) {
  const now = useNow()
  const { data: rec, isLoading } = useApi('attendance-today', '/attendance/today')
  const inv = ['attendance-today', 'dash-employee', 'my-attendance', 'dash-admin']
  const checkIn = useAction(() => api.post('/attendance/check-in'), { success: 'Checked in. Have a great day!', invalidate: inv })
  const checkOut = useAction(() => api.post('/attendance/check-out'), { success: 'Checked out. See you tomorrow!', invalidate: inv })

  const workedMin = rec?.check_in && !rec.check_out ? Math.max(0, Math.round((now - new Date(rec.check_in)) / 60000)) : rec?.work_minutes || 0
  const busy = checkIn.isPending || checkOut.isPending

  return (
    <div className="card flex flex-wrap items-center gap-5 p-5">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-brand-50 text-brand-600"><Clock className="h-6 w-6" /></div>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
          {now.toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })}
        </p>
        <p className="text-2xl font-semibold text-slate-900">{now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}</p>
        <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
          {isLoading ? <Spinner className="h-4 w-4" /> : rec ? (
            <>
              <span>In: <b className="text-slate-700">{fmtTime(rec.check_in)}</b></span>
              <span>Out: <b className="text-slate-700">{rec.check_out ? fmtTime(rec.check_out) : '—'}</b></span>
              <span>Worked: <b className="text-slate-700">{Math.floor(workedMin / 60)}h {workedMin % 60}m</b></span>
              {rec.is_late && <StatusBadge status="pending" label="Late" />}
              {rec.check_out && <StatusBadge status={rec.status} />}
            </>
          ) : onLeave ? <span>You're on approved leave today.</span> : <span>You haven't checked in yet.</span>}
        </div>
      </div>
      {!rec && !onLeave && (
        <button className="btn-success px-5 py-2.5" onClick={() => checkIn.mutate()} disabled={busy || isLoading}>
          {busy ? <Spinner className="h-4 w-4 text-white" /> : <LogIn className="h-4 w-4" />} Check in
        </button>
      )}
      {rec && !rec.check_out && (
        <button className="btn-danger px-5 py-2.5" onClick={() => checkOut.mutate()} disabled={busy}>
          {busy ? <Spinner className="h-4 w-4 text-white" /> : <LogOut className="h-4 w-4" />} Check out
        </button>
      )}
    </div>
  )
}
