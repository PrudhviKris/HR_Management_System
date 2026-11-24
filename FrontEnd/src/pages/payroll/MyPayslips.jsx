import { useState } from 'react'
import toast from 'react-hot-toast'
import { Download, FileText } from 'lucide-react'
import { downloadFile, errorMessage } from '../../api/client'
import { useApi } from '../../lib/hooks'
import { money } from '../../lib/format'
import { Card, PageHeader, Pagination, Spinner, StatusBadge, Table } from '../../components/ui'
import PayslipView from '../../components/PayslipView'

export default function MyPayslips() {
  const [page, setPage] = useState(1)
  const [view, setView] = useState(null)
  const { data, isLoading } = useApi(['my-payslips', page], '/payroll/payslips/me', { page, page_size: 12 })
  const dl = (s, e) => {
    e.stopPropagation()
    downloadFile(`/payroll/payslips/${s.id}/pdf`, null, `payslip_${s.period}.pdf`).catch((err) => toast.error(errorMessage(err, 'Download failed')))
  }
  return (
    <>
      <PageHeader title="My payslips" subtitle="Monthly salary slips. Released once payroll is locked." />
      <Card bodyClass="p-0">
        {isLoading ? <div className="flex justify-center py-10"><Spinner /></div> : (
          <>
            <Table rows={data.items} onRowClick={setView} empty={{ icon: FileText, title: 'No payslips yet', message: 'Your salary slips appear here after payroll is processed.' }} columns={[
              { key: 'period', label: 'Period', render: (s) => <span className="font-medium text-slate-900">{s.period}</span> },
              { key: 'paid_days', label: 'Paid days', render: (s) => `${s.paid_days} / ${s.working_days}` },
              { key: 'lop_days', label: 'LOP', render: (s) => <span className={s.lop_days > 0 ? 'text-rose-600' : ''}>{s.lop_days}</span> },
              { key: 'gross_earnings', label: 'Gross', render: (s) => money(s.gross_earnings) },
              { key: 'total_deductions', label: 'Deductions', render: (s) => money(s.total_deductions) },
              { key: 'net_salary', label: 'Net pay', render: (s) => <b>{money(s.net_salary)}</b> },
              { key: 'payment_status', label: 'Payment', render: (s) => <StatusBadge status={s.payment_status} /> },
              { key: 'dl', label: '', tdClass: 'text-right', render: (s) => <button className="btn-secondary btn-sm" onClick={(e) => dl(s, e)}><Download className="h-3.5 w-3.5" /> PDF</button> },
            ]} />
            <Pagination page={data.page} pages={data.pages} total={data.total} onChange={setPage} />
          </>
        )}
      </Card>
      <PayslipView slip={view} onClose={() => setView(null)} />
    </>
  )
}
