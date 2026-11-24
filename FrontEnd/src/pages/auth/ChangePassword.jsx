import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import toast from 'react-hot-toast'
import { api, errorMessage } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { Card, Field, PageHeader, Spinner } from '../../components/ui'
import { passwordRules } from './passwordRules'

export default function ChangePassword() {
  const { user, applyTokenResponse } = useAuth()
  const navigate = useNavigate()
  const { register, handleSubmit, watch, setError, formState: { errors, isSubmitting } } = useForm()

  const onSubmit = async ({ current, password }) => {
    try {
      const { data } = await api.post('/auth/change-password', { current_password: current, new_password: password })
      applyTokenResponse(data)
      toast.success('Password changed. Other sessions were signed out.')
      navigate('/')
    } catch (err) {
      setError('current', { message: errorMessage(err) })
    }
  }

  return (
    <div className="max-w-lg">
      <PageHeader title="Change password" subtitle={user.must_change_password ? 'Please choose a new password before continuing.' : 'Changing your password signs you out on other devices.'} />
      <Card>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <Field label="Current password" error={errors.current?.message}>
            <input className="input" type="password" autoComplete="current-password" {...register('current', { required: 'Required' })} />
          </Field>
          <Field label="New password" error={errors.password?.message} hint="8+ characters with upper & lower case letters and a number">
            <input className="input" type="password" autoComplete="new-password" {...register('password', passwordRules)} />
          </Field>
          <Field label="Confirm new password" error={errors.confirm?.message}>
            <input className="input" type="password" autoComplete="new-password"
              {...register('confirm', { validate: (v) => v === watch('password') || 'Passwords do not match' })} />
          </Field>
          <button className="btn-primary" disabled={isSubmitting}>
            {isSubmitting && <Spinner className="h-4 w-4 text-white" />} Update password
          </button>
        </form>
      </Card>
    </div>
  )
}
