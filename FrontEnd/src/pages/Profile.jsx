import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Pencil } from 'lucide-react'
import { api } from '../api/client'
import { useAction, useApi } from '../lib/hooks'
import { fmtDate, money } from '../lib/format'
import { Avatar, Card, ErrorState, Field, Modal, PageLoader, StatusBadge } from '../components/ui'
import DocumentsPanel from '../components/DocumentsPanel'
import { ProfileOverview } from './employees/EmployeeDetail'

export default function Profile() {
  const { data: e, isLoading, error, refetch } = useApi('my-profile', '/me/profile')
  const { data: salary } = useApi('my-salary', '/me/salary')
  const [edit, setEdit] = useState(false)
  const { register, handleSubmit, reset } = useForm()
  const save = useAction((b) => api.put('/me/profile', b), { success: 'Contact details updated', invalidate: ['my-profile'], onSuccess: () => setEdit(false) })
  if (isLoading) return <PageLoader />
  if (error) return <ErrorState error={error} onRetry={refetch} />

  return (
    <div className="space-y-6">
      <div className="card flex flex-wrap items-center gap-4 p-5">
        <Avatar name={e.full_name} className="h-14 w-14 text-lg" />
        <div className="flex-1">
          <div className="flex items-center gap-2"><h1 className="text-xl font-semibold">{e.full_name}</h1><StatusBadge status={e.status} /></div>
          <p className="text-sm text-slate-500">{e.employee_code} · {e.designation_title} · {e.department_name} · joined {fmtDate(e.date_of_joining)}</p>
        </div>
        <button className="btn-secondary" onClick={() => { reset({ phone: e.phone || '', address: e.address || '', emergency_contact_name: e.emergency_contact_name || '', emergency_contact_phone: e.emergency_contact_phone || '' }); setEdit(true) }}>
          <Pencil className="h-4 w-4" /> Edit contact details
        </button>
      </div>
      <ProfileOverview e={e} />
      {salary && (
        <Card title={`My salary structure (effective ${fmtDate(salary.effective_from)})`}>
          <div className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            {[['Basic', salary.basic], ['HRA', salary.hra], ['Conveyance', salary.conveyance_allowance], ['Medical', salary.medical_allowance],
              ['Special', salary.special_allowance], ['Gross / month', salary.gross_monthly], ['Annual CTC', salary.annual_ctc], ['TDS / month', salary.tds_monthly]].map(([k, v]) => (
              <div key={k}><p className="text-xs text-slate-500">{k}</p><p className="font-medium">{money(v)}</p></div>
            ))}
          </div>
        </Card>
      )}
      <DocumentsPanel base="/me" canUpload />
      <Modal open={edit} onClose={() => setEdit(false)} title="Edit contact details"
        footer={<button className="btn-primary" disabled={save.isPending} onClick={handleSubmit((v) => save.mutate(v))}>Save</button>}>
        <p className="mb-4 text-xs text-slate-500">Job, bank and salary details are managed by HR.</p>
        <div className="space-y-4">
          <Field label="Phone"><input className="input" {...register('phone')} /></Field>
          <Field label="Address"><textarea className="input" rows={2} {...register('address')} /></Field>
          <Field label="Emergency contact name"><input className="input" {...register('emergency_contact_name')} /></Field>
          <Field label="Emergency contact phone"><input className="input" {...register('emergency_contact_phone')} /></Field>
        </div>
      </Modal>
    </div>
  )
}
