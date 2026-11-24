import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { api, errorMessage } from '../api/client'

/** GET helper: useApi(['employees', params], '/employees', params) */
export function useApi(key, url, params, options = {}) {
  return useQuery({
    queryKey: Array.isArray(key) ? key : [key],
    queryFn: () => api.get(url, { params }).then((r) => r.data),
    ...options,
  })
}

/** Mutation helper with toast feedback + cache invalidation. */
export function useAction(fn, { success, invalidate = [], onSuccess, onError } = {}) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: (data, vars) => {
      if (success) toast.success(typeof success === 'function' ? success(data, vars) : success)
      invalidate.forEach((k) => qc.invalidateQueries({ queryKey: Array.isArray(k) ? k : [k] }))
      onSuccess?.(data, vars)
    },
    onError: (err) => {
      toast.error(errorMessage(err))
      onError?.(err)
    },
  })
}

export const reference = {
  departments: () => api.get('/departments').then((r) => r.data),
  designations: () => api.get('/designations').then((r) => r.data),
  leaveTypes: () => api.get('/leaves/types').then((r) => r.data),
}

export function useDepartments() {
  return useQuery({ queryKey: ['departments'], queryFn: reference.departments, staleTime: 60_000 })
}
export function useDesignations() {
  return useQuery({ queryKey: ['designations'], queryFn: reference.designations, staleTime: 60_000 })
}
export function useLeaveTypes() {
  return useQuery({ queryKey: ['leave-types'], queryFn: reference.leaveTypes, staleTime: 60_000 })
}
