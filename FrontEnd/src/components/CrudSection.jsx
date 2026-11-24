import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { api } from '../api/client'
import { useAction, useApi } from '../lib/hooks'
import { Card, ConfirmDialog, Field, Modal, Spinner, Table } from './ui'

/**
 * Generic list + create/edit/delete for simple reference entities.
 * fields: [{ name, label, type: 'text'|'number'|'date'|'checkbox'|'select'|'color', options, rules, default }]
 */
export default function CrudSection({ title, url, queryKey, columns, fields, params, canDelete = true, toBody = (v) => v, invalidate = [] }) {
  const key = [queryKey, params]
  const { data, isLoading } = useApi(key, url, params)
  const [editing, setEditing] = useState(null) // {} for new, row for edit
  const [toDelete, setToDelete] = useState(null)
  const { register, handleSubmit, reset, formState: { errors } } = useForm()
  const inv = [queryKey, ...invalidate]
  const close = () => setEditing(null)
  const save = useAction(
    (v) => (editing?.id ? api.put(`${url}/${editing.id}`, toBody(v)) : api.post(url, toBody(v))),
    { success: 'Saved', invalidate: inv, onSuccess: close },
  )
  const del = useAction((id) => api.delete(`${url}/${id}`), { success: 'Deleted', invalidate: inv, onSuccess: () => setToDelete(null) })

  const open = (row) => {
    const defaults = Object.fromEntries(fields.map((f) => [f.name, row?.[f.name] ?? f.default ?? (f.type === 'checkbox' ? false : '')]))
    reset(defaults)
    setEditing(row || {})
  }

  return (
    <Card title={title} bodyClass="p-0" actions={<button className="btn-primary btn-sm" onClick={() => open(null)}><Plus className="h-3.5 w-3.5" /> Add</button>}>
      {isLoading ? <div className="flex justify-center py-8"><Spinner /></div> : (
        <Table rows={data} columns={[...columns, {
          key: '_act', label: '', tdClass: 'text-right', render: (r) => (
            <div className="flex justify-end gap-1">
              <button className="btn-ghost btn-sm" onClick={() => open(r)} aria-label="Edit"><Pencil className="h-3.5 w-3.5" /></button>
              {canDelete && <button className="btn-ghost btn-sm text-rose-600" onClick={() => setToDelete(r)} aria-label="Delete"><Trash2 className="h-3.5 w-3.5" /></button>}
            </div>
          ),
        }]} />
      )}
      <Modal open={!!editing} onClose={close} title={`${editing?.id ? 'Edit' : 'Add'} ${title.replace(/s$/, '').toLowerCase()}`}
        footer={<button className="btn-primary" disabled={save.isPending} onClick={handleSubmit((v) => save.mutate(v))}>Save</button>}>
        <div className="grid grid-cols-2 gap-4">
          {fields.map((f) => f.type === 'checkbox' ? (
            <label key={f.name} className="col-span-2 flex items-center gap-2 text-sm"><input type="checkbox" {...register(f.name)} /> {f.label}</label>
          ) : (
            <Field key={f.name} label={f.label} error={errors[f.name]?.message} className={f.half ? '' : 'col-span-2'} hint={f.hint}>
              {f.type === 'select' ? (
                <select className="input" {...register(f.name, f.rules)}>
                  <option value="">—</option>
                  {f.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              ) : (
                <input className={f.type === 'color' ? 'input h-10 p-1' : 'input'} type={f.type || 'text'} step={f.step} {...register(f.name, f.rules)} />
              )}
            </Field>
          ))}
        </div>
      </Modal>
      <ConfirmDialog open={!!toDelete} title="Delete?" tone="danger" confirmLabel="Delete" busy={del.isPending}
        message="This cannot be undone. Items in use cannot be deleted; mark them inactive instead." onClose={() => setToDelete(null)} onConfirm={() => del.mutate(toDelete.id)} />
    </Card>
  )
}
