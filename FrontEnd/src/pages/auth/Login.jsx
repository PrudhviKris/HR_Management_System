import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { Eye, EyeOff } from 'lucide-react'
import { useAuth } from '../../auth/AuthContext'
import { errorMessage } from '../../api/client'
import { Field, Spinner } from '../../components/ui'
import AuthShell from './AuthShell'

const DEMO = [
  { label: 'Admin', email: 'admin@example.com', password: 'Admin@123' },
  { label: 'HR', email: 'hr@example.com', password: 'Hr@12345' },
  { label: 'Employee', email: 'rahul.verma@example.com', password: 'Employee@123' },
]

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState(null)
  const [show, setShow] = useState(false)
  const { register, handleSubmit, setValue, formState: { errors, isSubmitting } } = useForm()

  const onSubmit = async ({ email, password }) => {
    setError(null)
    try {
      const user = await login(email, password)
      navigate(user.must_change_password ? '/change-password' : location.state?.from?.pathname || '/', { replace: true })
    } catch (err) {
      setError(errorMessage(err, 'Unable to sign in'))
    }
  }

  return (
    <AuthShell title="Welcome back" subtitle="Sign in to your HRMS account">
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
        {error && <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700" role="alert">{error}</div>}
        <Field label="Email" error={errors.email?.message}>
          <input className="input" type="email" autoComplete="username" autoFocus
            {...register('email', { required: 'Email is required', pattern: { value: /^\S+@\S+\.\S+$/, message: 'Enter a valid email' } })} />
        </Field>
        <Field label="Password" error={errors.password?.message}>
          <div className="relative">
            <input className="input pr-10" type={show ? 'text' : 'password'} autoComplete="current-password"
              {...register('password', { required: 'Password is required' })} />
            <button type="button" className="absolute inset-y-0 right-0 px-3 text-slate-400" onClick={() => setShow((s) => !s)} aria-label="Toggle password visibility">
              {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </Field>
        <div className="flex justify-end">
          <Link to="/forgot-password" className="text-sm text-brand-600 hover:underline">Forgot password?</Link>
        </div>
        <button className="btn-primary w-full" disabled={isSubmitting}>
          {isSubmitting && <Spinner className="h-4 w-4 text-white" />} Sign in
        </button>
      </form>
      <div className="mt-8 rounded-lg border border-dashed border-slate-300 p-3">
        <p className="mb-2 text-xs font-medium text-slate-500">Demo accounts (click to fill)</p>
        <div className="flex gap-2">
          {DEMO.map((d) => (
            <button key={d.label} type="button" className="btn-secondary btn-sm flex-1"
              onClick={() => { setValue('email', d.email); setValue('password', d.password) }}>
              {d.label}
            </button>
          ))}
        </div>
      </div>
    </AuthShell>
  )
}
