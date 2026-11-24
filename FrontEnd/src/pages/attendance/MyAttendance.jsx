import { useState } from 'react'
import { useApi } from '../../lib/hooks'
import { Card, PageHeader } from '../../components/ui'
import AttendanceCalendar, { MonthPicker, SummaryStrip } from '../../components/AttendanceCalendar'
import CheckInWidget from '../../components/CheckInWidget'

export default function MyAttendance() {
  const t = new Date()
  const [ym, setYm] = useState({ year: t.getFullYear(), month: t.getMonth() + 1 })
  const { data, isLoading } = useApi(['my-attendance', ym], '/attendance/me', ym)
  return (
    <div className="space-y-6">
      <PageHeader title="My attendance" subtitle="Daily check-ins, working hours and monthly summary" />
      <CheckInWidget />
      {data && <SummaryStrip s={data.summary} />}
      <Card title="Calendar" actions={<MonthPicker {...ym} onChange={(year, month) => setYm({ year, month })} />}>
        <AttendanceCalendar data={data} loading={isLoading} />
      </Card>
    </div>
  )
}
