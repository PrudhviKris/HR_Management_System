import { format, parseISO } from 'date-fns'

const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 })
const inr0 = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })
const num = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 })

export const money = (v) => (v == null ? '—' : inr.format(v))
export const money0 = (v) => (v == null ? '—' : inr0.format(v))
export const number = (v) => (v == null ? '—' : num.format(v))

const toDate = (v) => (v instanceof Date ? v : typeof v === 'string' ? parseISO(v) : null)

export const fmtDate = (v, f = 'dd MMM yyyy') => {
  const d = v && toDate(v)
  return d && !isNaN(d) ? format(d, f) : '—'
}
// Event timestamps (created/approved/locked...) are stored in UTC -> shown in the viewer's local time.
const utc = (v) => new Date(/Z|[+-]\d\d:\d\d$/.test(v) ? v : `${v}Z`)
export const fmtDateTime = (v) => (v ? fmtDate(utc(v), 'dd MMM yyyy, HH:mm') : '—')
export const fmtUtc = (v) => (v ? fmtDate(utc(v), 'dd MMM yyyy, HH:mm:ss') : '—')
// Attendance check-in/out are office wall-clock times (no time zone) -> shown as-is.
export const fmtTime = (v) => fmtDate(v, 'HH:mm')

export const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

export const titleCase = (s) => (s || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

export const isoDate = (d) => format(d, 'yyyy-MM-dd')

export function initials(name = '') {
  return name.split(' ').filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join('')
}
