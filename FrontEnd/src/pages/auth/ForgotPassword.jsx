import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { api, errorMessage } from '../../api/client'
import { Field, Spinner } from '../../components/ui'
import AuthShell from './AuthShell'

export default function ForgotPassword() {
  const [done, setDone] = useState(null)
  const [error, setError] = useState(null)
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm()

  const onSubmit = async ({ email }) => {
    setError(null)
    try {
      const { data } = await api.post('/auth/forgot-password', { email })
      setDone(data.message)
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <AuthShell title="Reset your password" subtitle="We'll email you a secure link to set a new password.">
      {done ? (
        <div className="rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{done}</div>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          {error && <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}
          <Field label="Email" error={errors.email?.message}>
            <input className="input" type="email" autoFocus {...register('email', { required: 'Email is required' })} />
          </Field>
          <button className="btn-primary w-full" disabled={isSubmitting}>
            {isSubmitting && <Spinner className="h-4 w-4 text-white" />} Send reset link
          </button>
        </form>
      )}
      <p className="mt-6 text-center text-sm"><Link to="/login" className="text-brand-600 hover:underline">Back to sign in</Link></p>
    </AuthShell>
  )
}
