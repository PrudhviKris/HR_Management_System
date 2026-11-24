import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { api, errorMessage } from '../../api/client'
import { Field, Spinner } from '../../components/ui'
import AuthShell from './AuthShell'
import { passwordRules } from './passwordRules'

export default function ResetPassword() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const [done, setDone] = useState(false)
  const [error, setError] = useState(null)
  const { register, handleSubmit, watch, formState: { errors, isSubmitting } } = useForm()

  const onSubmit = async ({ password }) => {
    setError(null)
    try {
      await api.post('/auth/reset-password', { token, new_password: password })
      setDone(true)
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <AuthShell title="Set a new password" subtitle="Use at least 8 characters with upper & lower case letters and a number.">
      {!token ? (
        <div className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">This link is missing its token. Please use the link from your email.</div>
      ) : done ? (
        <div className="space-y-4">
          <div className="rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-700">Your password has been set.</div>
          <Link to="/login" className="btn-primary w-full">Continue to sign in</Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          {error && <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}
          <Field label="New password" error={errors.password?.message}>
            <input className="input" type="password" autoComplete="new-password" {...register('password', passwordRules)} />
          </Field>
          <Field label="Confirm password" error={errors.confirm?.message}>
            <input className="input" type="password" autoComplete="new-password"
              {...register('confirm', { validate: (v) => v === watch('password') || 'Passwords do not match' })} />
          </Field>
          <button className="btn-primary w-full" disabled={isSubmitting}>
            {isSubmitting && <Spinner className="h-4 w-4 text-white" />} Save password
          </button>
        </form>
      )}
    </AuthShell>
  )
}
