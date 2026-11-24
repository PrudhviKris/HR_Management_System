import { useMemo, useState } from 'react'
import { Lock, Pencil, Plus, Search, Trash2 } from 'lucide-react'
import { api } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import { useAction, useApi } from '../../lib/hooks'
import { fmtDateTime, titleCase } from '../../lib/format'
import { Badge, Card, ConfirmDialog, Field, Modal, PageHeader, Pagination, Spinner, StatusBadge, Table, Tabs } from '../../components/ui'

function RoleEditor({ role, perms, onClose }) {
  const [name, setName] = useState(role.name || '')
  const [description, setDescription] = useState(role.description || '')
  const [selected, setSelected] = useState(new Set(role.permissions || []))
  const locked = role.name === 'Admin'
  const save = useAction(
    (b) => (role.id ? api.put(`/roles/${role.id}`, b) : api.post('/roles', b)),
    { success: 'Role saved', invalidate: ['roles'], onSuccess: onClose },
  )
  const modules = useMemo(() => perms.reduce((acc, p) => ({ ...acc, [p.module]: [...(acc[p.module] || []), p] }), {}), [perms])
  const toggle = (code) => setSelected((s) => { const n = new Set(s); n.has(code) ? n.delete(code) : n.add(code); return n })
  const toggleModule = (list, on) => setSelected((s) => { const n = new Set(s); list.forEach((p) => (on ? n.add(p.code) : n.delete(p.code))); return n })
  return (
    <Modal open onClose={onClose} size="xl" title={role.id ? `Edit role · ${role.name}` : 'New role'}
      footer={!locked && <button className="btn-primary" disabled={save.isPending || name.trim().length < 2} onClick={() => save.mutate({ name, description, permissions: [...selected] })}>Save role</button>}>
      {locked && <p className="mb-4 flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600"><Lock className="h-4 w-4" /> The Admin role always has every permission.</p>}
      <div className="mb-5 grid gap-4 sm:grid-cols-2">
        <Field label="Role name"><input className="input" value={name} disabled={role.is_system} onChange={(e) => setName(e.target.value)} /></Field>
        <Field label="Description"><input className="input" value={description} disabled={locked} onChange={(e) => setDescription(e.target.value)} /></Field>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {Object.entries(modules).map(([mod, list]) => {
          const all = list.every((p) => selected.has(p.code))
          return (
            <div key={mod} className="rounded-lg border border-slate-200 p-3">
              <label className="mb-2 flex items-center justify-between text-sm font-semibold capitalize">
                {mod}
                <input type="checkbox" disabled={locked} checked={all} onChange={(e) => toggleModule(list, e.target.checked)} />
              </label>
              <div className="space-y-1.5">
                {list.map((p) => (
                  <label key={p.code} className="flex items-start gap-2 text-sm">
                    <input type="checkbox" className="mt-0.5" disabled={locked} checked={selected.has(p.code)} onChange={() => toggle(p.code)} />
                    <span><span className="text-slate-700">{p.description}</span> <code className="text-[11px] text-slate-400">{p.code}</code></span>
                  </label>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </Modal>
  )
}

function Roles() {
  const { data: roles, isLoading } = useApi('roles', '/roles')
  const { data: perms } = useApi('permissions', '/permissions')
  const [edit, setEdit] = useState(null)
  const [del, setDel] = useState(null)
  const remove = useAction((id) => api.delete(`/roles/${id}`), { success: 'Role deleted', invalidate: ['roles'], onSuccess: () => setDel(null) })
  if (isLoading || !perms) return <div className="flex justify-center py-10"><Spinner /></div>
  return (
    <Card title="Roles" bodyClass="p-0" actions={<button className="btn-primary btn-sm" onClick={() => setEdit({})}><Plus className="h-3.5 w-3.5" /> New role</button>}>
      <Table rows={roles} columns={[
        { key: 'name', label: 'Role', render: (r) => <span className="flex items-center gap-2 font-medium text-slate-800">{r.name}{r.is_system && <Badge tone="indigo">system</Badge>}</span> },
        { key: 'description', label: 'Description', tdClass: 'max-w-md truncate whitespace-normal' },
        { key: 'permissions', label: 'Permissions', render: (r) => `${r.permissions.length} / ${perms.length}` },
        { key: 'user_count', label: 'Users' },
        { key: 'act', label: '', tdClass: 'text-right', render: (r) => (
          <div className="flex justify-end gap-1">
            <button className="btn-ghost btn-sm" onClick={() => setEdit(r)}><Pencil className="h-3.5 w-3.5" /> {r.name === 'Admin' ? 'View' : 'Edit'}</button>
            {!r.is_system && <button className="btn-ghost btn-sm text-rose-600" onClick={() => setDel(r)} aria-label="Delete"><Trash2 className="h-3.5 w-3.5" /></button>}
          </div>
        ) },
      ]} />
      {edit && <RoleEditor role={edit} perms={perms} onClose={() => setEdit(null)} />}
      <ConfirmDialog open={!!del} title={`Delete role ${del?.name}?`} tone="danger" confirmLabel="Delete" busy={remove.isPending}
        message="Roles assigned to users cannot be deleted." onClose={() => setDel(null)} onConfirm={() => remove.mutate(del.id)} />
    </Card>
  )
}

function Users() {
  const { user: me } = useAuth()
  const [q, setQ] = useState({ search: '', role_id: '', page: 1 })
  const params = Object.fromEntries(Object.entries({ ...q, page_size: 15 }).filter(([, v]) => v !== ''))
  const { data, isLoading } = useApi(['users', params], '/users', params, { placeholderData: (p) => p })
  const { data: roles } = useApi('roles', '/roles')
  const [change, setChange] = useState(null)
  const update = useAction(({ id, role_id }) => api.put(`/users/${id}/role`, { role_id }).then((r) => r.data), { success: (d) => d.message, invalidate: ['users', 'roles'], onSuccess: () => setChange(null) })
  return (
    <Card bodyClass="p-0">
      <div className="flex flex-wrap gap-3 border-b border-slate-100 p-4">
        <div className="relative min-w-56 flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input className="input pl-9" placeholder="Search users" value={q.search} onChange={(e) => setQ({ ...q, search: e.target.value, page: 1 })} />
        </div>
        <select className="input w-44" value={q.role_id} onChange={(e) => setQ({ ...q, role_id: e.target.value, page: 1 })}>
          <option value="">All roles</option>{roles?.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </select>
      </div>
      {isLoading ? <div className="flex justify-center py-10"><Spinner /></div> : (
        <>
          <Table rows={data.items} columns={[
            { key: 'full_name', label: 'User', render: (u) => <div><p className="font-medium text-slate-800">{u.full_name}</p><p className="text-xs text-slate-500">{u.email}</p></div> },
            { key: 'employee_code', label: 'Employee ID' },
            { key: 'role', label: 'Role', render: (u) => <Badge tone="indigo">{u.role}</Badge> },
            { key: 'is_active', label: 'Account', render: (u) => <StatusBadge status={u.is_active ? 'active' : 'inactive'} /> },
            { key: 'last_login_at', label: 'Last login', render: (u) => fmtDateTime(u.last_login_at) },
            { key: 'act', label: '', tdClass: 'text-right', render: (u) => u.id !== me.id && <button className="btn-ghost btn-sm" onClick={() => setChange({ ...u })}>Change role</button> },
          ]} />
          <Pagination page={data.page} pages={data.pages} total={data.total} onChange={(page) => setQ({ ...q, page })} />
        </>
      )}
      <Modal open={!!change} onClose={() => setChange(null)} title={`Change role · ${change?.full_name}`}
        footer={<button className="btn-primary" disabled={update.isPending} onClick={() => update.mutate({ id: change.id, role_id: Number(change.role_id) })}>Save</button>}>
        <Field label="Role" hint="Takes effect on the user's next request.">
          <select className="input" value={change?.role_id || ''} onChange={(e) => setChange({ ...change, role_id: e.target.value })}>
            {roles?.map((r) => <option key={r.id} value={r.id}>{r.name}: {titleCase(r.description).slice(0, 60)}</option>)}
          </select>
        </Field>
      </Modal>
    </Card>
  )
}

export default function RolesUsers() {
  const [tab, setTab] = useState('roles')
  return (
    <>
      <PageHeader title="Roles & users" subtitle="Role-based access control: define what each role can do and assign roles to users" />
      <Tabs value={tab} onChange={setTab} tabs={[{ value: 'roles', label: 'Roles & permissions' }, { value: 'users', label: 'User accounts' }]} />
      {tab === 'roles' ? <Roles /> : <Users />}
    </>
  )
}
