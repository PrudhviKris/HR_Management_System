import { useEffect, useMemo } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import toast from 'react-hot-toast'
import { api, errorMessage } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { useApi, useDepartments, useDesignations } from '../../lib/hooks'
import { money } from '../../lib/format'
import { Card, Field, PageHeader, PageLoader, Spinner } from '../../components/ui'

const clean = (obj) => Object.fromEntries(Object.entries(obj).map(([k, v]) => [k, v === '' ? null : v]))
const PERSONAL = ['first_name', 'last_name', 'email', 'phone', 'date_of_birth', 'gender', 'address', 'emergency_contact_name', 'emergency_contact_phone']
const JOB = ['department_id', 'designation_id', 'manager_id', 'date_of_joining', 'employment_type', 'work_location']
const BANK = ['bank_name', 'bank_account_number', 'ifsc_code', 'pan_number']

export default function EmployeeForm() {
  const { id } = useParams()
  const editing = !!id
  const navigate = useNavigate()
  const { can } = useAuth()
  const { data: existing, isLoading } = useApi(['employee', id], `/employees/${id}`, null, { enabled: editing })
  const { data: depts } = useDepartments()
  const { data: desigs } = useDesignations()
  const { data: managers } = useApi(['employees', 'managers'], '/employees', { status: 'active', page_size: 100 })
  const { data: roles } = useApi('roles', '/roles')
  const { register, handleSubmit, reset, watch, setError, formState: { errors, isSubmitting } } = useForm({
    defaultValues: { employment_type: 'full_time', salary: { pf_applicable: true, professional_tax_applicable: true, hra: 0, conveyance_allowance: 1600, medical_allowance: 1250, special_allowance: 0, tds_monthly: 0 } },
  })

  useEffect(() => {
    if (existing) reset(Object.fromEntries(Object.entries(existing).map(([k, v]) => [k, v ?? ''])))
  }, [existing, reset])

  const deptId = watch('department_id')
  const filteredDesigs = useMemo(() => (desigs || []).filter((d) => d.is_active && (!deptId || !d.department_id || String(d.department_id) === String(deptId))), [desigs, deptId])
  const s = watch('salary') || {}
  const gross = ['basic', 'hra', 'conveyance_allowance', 'medical_allowance', 'special_allowance'].reduce((a, k) => a + (Number(s[k]) || 0), 0)

  const onSubmit = async (v) => {
    const body = clean(Object.fromEntries([...PERSONAL, ...JOB, ...BANK].map((k) => [k, v[k]])))
    ;['department_id', 'designation_id', 'manager_id'].forEach((k) => { body[k] = body[k] ? Number(body[k]) : null })
    try {
      if (editing) {
        await api.put(`/employees/${id}`, body)
        toast.success('Employee updated')
        navigate(`/employees/${id}`)
      } else {
        const salary = clean(v.salary)
        ;['basic', 'hra', 'conveyance_allowance', 'medical_allowance', 'special_allowance', 'tds_monthly'].forEach((k) => { salary[k] = Number(salary[k] || 0) })
        const { data } = await api.post('/employees', { ...body, salary, role_id: v.role_id ? Number(v.role_id) : null, password: v.password || null })
        toast.success(`${data.full_name} onboarded as ${data.employee_code}`)
        navigate(`/employees/${data.id}`)
      }
    } catch (err) {
      const details = err.response?.data?.error?.details
      if (Array.isArray(details)) details.forEach((d) => d.field && setError(d.field, { message: d.message }))
      toast.error(errorMessage(err))
    }
  }

  if (editing && isLoading) return <PageLoader />
  const req = { required: 'Required' }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-6">
      <PageHeader
        title={editing ? `Edit ${existing?.full_name}` : 'Onboard employee'}
        subtitle={editing ? existing?.employee_code : 'Creates the login account, profile, salary structure and leave balances, and sends a welcome email.'}
        actions={<>
          <button type="button" className="btn-secondary" onClick={() => navigate(-1)}>Cancel</button>
          <button className="btn-primary" disabled={isSubmitting}>{isSubmitting && <Spinner className="h-4 w-4 text-white" />} {editing ? 'Save changes' : 'Create employee'}</button>
        </>}
      />

      <Card title="Personal details">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="First name *" error={errors.first_name?.message}><input className="input" {...register('first_name', req)} /></Field>
          <Field label="Last name *" error={errors.last_name?.message}><input className="input" {...register('last_name', req)} /></Field>
          <Field label="Work email *" error={errors.email?.message}><input className="input" type="email" {...register('email', { ...req, pattern: { value: /^\S+@\S+\.\S+$/, message: 'Invalid email' } })} /></Field>
          <Field label="Phone" error={errors.phone?.message}><input className="input" placeholder="+91 98765 43210" {...register('phone')} /></Field>
          <Field label="Date of birth" error={errors.date_of_birth?.message}><input className="input" type="date" {...register('date_of_birth')} /></Field>
          <Field label="Gender" error={errors.gender?.message}>
            <select className="input" {...register('gender')}><option value="">—</option><option value="male">Male</option><option value="female">Female</option><option value="other">Other</option></select>
          </Field>
          <Field label="Address" className="sm:col-span-2 lg:col-span-3" error={errors.address?.message}><input className="input" {...register('address')} /></Field>
          <Field label="Emergency contact name"><input className="input" {...register('emergency_contact_name')} /></Field>
          <Field label="Emergency contact phone" error={errors.emergency_contact_phone?.message}><input className="input" {...register('emergency_contact_phone')} /></Field>
        </div>
      </Card>

      <Card title="Job details">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Department" error={errors.department_id?.message}>
            <select className="input" {...register('department_id')}><option value="">—</option>{depts?.filter((d) => d.is_active || String(d.id) === String(existing?.department_id)).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select>
          </Field>
          <Field label="Designation" error={errors.designation_id?.message}>
            <select className="input" {...register('designation_id')}><option value="">—</option>{filteredDesigs.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}</select>
          </Field>
          <Field label="Reporting manager" error={errors.manager_id?.message}>
            <select className="input" {...register('manager_id')}><option value="">—</option>{managers?.items?.filter((m) => String(m.id) !== String(id)).map((m) => <option key={m.id} value={m.id}>{m.full_name} ({m.employee_code})</option>)}</select>
          </Field>
          <Field label="Date of joining *" error={errors.date_of_joining?.message}><input className="input" type="date" {...register('date_of_joining', req)} /></Field>
          <Field label="Employment type">
            <select className="input" {...register('employment_type')}><option value="full_time">Full time</option><option value="part_time">Part time</option><option value="contract">Contract</option><option value="intern">Intern</option></select>
          </Field>
          <Field label="Work location"><input className="input" {...register('work_location')} /></Field>
          {!editing && (
            <>
              <Field label="System role" hint="Defaults to Employee">
                <select className="input" {...register('role_id')}><option value="">Employee</option>{roles?.filter((r) => r.name !== 'Employee' && (r.name !== 'Admin' || can('role:manage'))).map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select>
              </Field>
              <Field label="Initial password (optional)" className="lg:col-span-2" error={errors.password?.message}
                hint="Leave empty to email a secure set-password link. If set, the employee must change it at first login.">
                <input className="input" type="password" autoComplete="new-password" {...register('password', { validate: (v) => !v || (v.length >= 8 && /[a-z]/.test(v) && /[A-Z]/.test(v) && /\d/.test(v)) || '8+ chars with upper, lower and a digit' })} />
              </Field>
            </>
          )}
        </div>
      </Card>

      <Card title="Bank & statutory">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Bank name"><input className="input" {...register('bank_name')} /></Field>
          <Field label="Account number" error={errors.bank_account_number?.message}><input className="input" inputMode="numeric" {...register('bank_account_number', { pattern: { value: /^\d{6,20}$/, message: '6–20 digits' } })} /></Field>
          <Field label="IFSC" error={errors.ifsc_code?.message}><input className="input uppercase" placeholder="HDFC0001234" {...register('ifsc_code', { pattern: { value: /^[A-Za-z]{4}0[A-Za-z0-9]{6}$/, message: 'Invalid IFSC' } })} /></Field>
          <Field label="PAN" error={errors.pan_number?.message}><input className="input uppercase" placeholder="ABCDE1234F" {...register('pan_number', { pattern: { value: /^[A-Za-z]{5}\d{4}[A-Za-z]$/, message: 'Invalid PAN' } })} /></Field>
        </div>
      </Card>

      {!editing && (
        <Card title="Salary structure (monthly)" actions={<span className="text-sm text-slate-500">Gross: <b className="text-slate-800">{money(gross)}</b> · CTC: <b className="text-slate-800">{money(gross * 12)}</b>/yr</span>}>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[['basic', 'Basic *'], ['hra', 'HRA'], ['conveyance_allowance', 'Conveyance'], ['medical_allowance', 'Medical'], ['special_allowance', 'Special allowance'], ['tds_monthly', 'Income tax (TDS) / month']].map(([k, label]) => (
              <Field key={k} label={label} error={errors.salary?.[k]?.message}>
                <input className="input" type="number" min="0" step="0.01" {...register(`salary.${k}`, k === 'basic' ? { required: 'Required', min: { value: 1, message: 'Must be > 0' } } : { min: { value: 0, message: '≥ 0' } })} />
              </Field>
            ))}
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" {...register('salary.pf_applicable')} /> Provident fund applicable</label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" {...register('salary.professional_tax_applicable')} /> Professional tax applicable</label>
          </div>
        </Card>
      )}
    </form>
  )
}
