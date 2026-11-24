import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { useAction, useApi } from '../../lib/hooks'
import { titleCase } from '../../lib/format'
import { Card, Field, PageHeader, PageLoader } from '../../components/ui'

const GROUPS = {
  Company: ['company_name', 'company_address'],
  Attendance: ['office_start_time', 'late_grace_minutes', 'full_day_hours', 'half_day_hours'],
  Payroll: ['pf_rate_percent', 'professional_tax_amount', 'professional_tax_threshold'],
}

export default function SettingsPage() {
  const { data, isLoading } = useApi('settings', '/settings')
  const [values, setValues] = useState({})
  useEffect(() => { if (data) setValues(Object.fromEntries(data.map((s) => [s.key, s.value]))) }, [data])
  const save = useAction(() => api.put('/settings', { values }), { success: 'Settings saved', invalidate: ['settings'] })
  if (isLoading) return <PageLoader />
  const meta = Object.fromEntries(data.map((s) => [s.key, s]))
  return (
    <div className="max-w-3xl space-y-6">
      <PageHeader title="System settings" subtitle="Changes apply to new calculations; locked payroll is never affected."
        actions={<button className="btn-primary" disabled={save.isPending} onClick={() => save.mutate()}>Save settings</button>} />
      {Object.entries(GROUPS).map(([group, keys]) => (
        <Card key={group} title={group}>
          <div className="grid gap-4 sm:grid-cols-2">
            {keys.map((k) => (
              <Field key={k} label={titleCase(k)} hint={meta[k]?.description} className={k === 'company_address' ? 'sm:col-span-2' : ''}>
                <input className="input" type={meta[k]?.type === 'time' ? 'time' : meta[k]?.type === 'str' ? 'text' : 'number'} step="any"
                  value={values[k] ?? ''} onChange={(e) => setValues({ ...values, [k]: e.target.value })} />
              </Field>
            ))}
          </div>
        </Card>
      ))}
    </div>
  )
}
