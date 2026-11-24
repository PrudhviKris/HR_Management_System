export const passwordRules = {
  required: 'Password is required',
  minLength: { value: 8, message: 'At least 8 characters' },
  maxLength: { value: 128, message: 'At most 128 characters' },
  validate: (v) =>
    (/[a-z]/.test(v) && /[A-Z]/.test(v) && /\d/.test(v)) || 'Include an uppercase letter, a lowercase letter and a digit',
}
