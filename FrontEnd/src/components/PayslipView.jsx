import toast from 'react-hot-toast'
import { Download } from 'lucide-react'
import { downloadFile, errorMessage } from '../api/client'
import { fmtDate, fmtDateTime, money } from '../lib/format'
import { Modal, StatusBadge } from './ui'

function Rows({ rows }) {
  return rows.filter(([, v, always]) => always || Number(v) !== 0).map(([k, v]) => (
    <div key={k} className="flex justify-between py-1.5 text-sm"><span className="text-slate-600">{k}</span><span className="font-medium tabular-nums">{money(v)}</span></div>
  ))
}

export default function PayslipView({ slip, onClose, footerExtra, children }) {
  if (!slip) return null
  const adjE = slip.adjustments.filter((a) => a.kind === 'earning').map((a) => [`${a.label} (adj.)`, a.amount])
  const adjD = slip.adjustments.filter((a) => a.kind === 'deduction').map((a) => [`${a.label} (adj.)`, a.amount])
  const download = () => downloadFile(`/payroll/payslips/${slip.id}/pdf`, null, `payslip_${slip.period}.pdf`).catch((e) => toast.error(errorMessage(e, 'Download failed')))
  return (
    <Modal open onClose={onClose} title={`Salary slip · ${slip.period}`} size="lg"
      footer={<>{footerExtra}<button className="btn-primary" onClick={download}><Download className="h-4 w-4" /> Download PDF</button></>}>
      <div className="grid gap-x-6 gap-y-2 rounded-lg bg-slate-50 p-4 text-sm sm:grid-cols-2">
        {[['Employee', `${slip.employee_name} (${slip.employee_code})`], ['Department', slip.department_name], ['Designation', slip.designation_title],
          ['Joined', fmtDate(slip.date_of_joining)], ['Bank', [slip.bank_name, slip.bank_account_masked].filter(Boolean).join(' · ')], ['PAN', slip.pan_number]].map(([k, v]) => (
          <div key={k} className="flex justify-between gap-2"><span className="text-slate-500">{k}</span><span className="text-right font-medium text-slate-800">{v || '—'}</span></div>
        ))}
      </div>
      <div className="mt-4 grid grid-cols-3 gap-3 text-center sm:grid-cols-6">
        {[['Working', slip.working_days], ['Eligible', slip.eligible_days], ['Present', slip.present_days], ['Paid leave', slip.paid_leave_days], ['LOP', slip.lop_days], ['Paid days', slip.paid_days]].map(([k, v]) => (
          <div key={k} className="rounded-lg border border-slate-200 py-2"><p className="text-[11px] uppercase text-slate-500">{k}</p><p className="font-semibold">{v}</p></div>
        ))}
      </div>
      <div className="mt-4 grid gap-6 sm:grid-cols-2">
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Earnings</p>
          <div className="divide-y divide-slate-100">
            <Rows rows={[['Basic', slip.basic, true], ['HRA', slip.hra], ['Conveyance', slip.conveyance_allowance], ['Medical', slip.medical_allowance], ['Special allowance', slip.special_allowance], ...adjE]} />
            <div className="flex justify-between py-2 text-sm font-semibold"><span>Gross earnings</span><span>{money(slip.gross_earnings)}</span></div>
          </div>
        </div>
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Deductions</p>
          <div className="divide-y divide-slate-100">
            <Rows rows={[[`Loss of pay (${slip.lop_days} d)`, slip.lop_deduction], ['Provident fund', slip.provident_fund], ['Professional tax', slip.professional_tax], ['Income tax (TDS)', slip.income_tax], ...adjD]} />
            <div className="flex justify-between py-2 text-sm font-semibold"><span>Total deductions</span><span>{money(slip.total_deductions)}</span></div>
          </div>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg bg-brand-50 px-4 py-3">
        <div>
          <p className="text-xs font-medium uppercase text-brand-700">Net salary</p>
          <p className="text-2xl font-bold text-brand-700">{money(slip.net_salary)}</p>
        </div>
        <div className="text-right text-xs text-slate-600">
          <StatusBadge status={slip.payment_status} />
          {slip.transaction_ref && <p className="mt-1">Ref <code>{slip.transaction_ref}</code> · {fmtDateTime(slip.credited_at)}</p>}
        </div>
      </div>
      {children}
    </Modal>
  )
}
