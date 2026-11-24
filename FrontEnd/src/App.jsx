import { Suspense, lazy } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth/AuthContext'
import Layout from './components/Layout'
import { EmptyState, PageLoader } from './components/ui'
import Login from './pages/auth/Login'
const ForgotPassword = lazy(() => import('./pages/auth/ForgotPassword'))
const ResetPassword = lazy(() => import('./pages/auth/ResetPassword'))
const ChangePassword = lazy(() => import('./pages/auth/ChangePassword'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Profile = lazy(() => import('./pages/Profile'))
const EmployeeList = lazy(() => import('./pages/employees/EmployeeList'))
const EmployeeForm = lazy(() => import('./pages/employees/EmployeeForm'))
const EmployeeDetail = lazy(() => import('./pages/employees/EmployeeDetail'))
const MyAttendance = lazy(() => import('./pages/attendance/MyAttendance'))
const AttendanceAdmin = lazy(() => import('./pages/attendance/AttendanceAdmin'))
const MyLeaves = lazy(() => import('./pages/leaves/MyLeaves'))
const LeaveRequests = lazy(() => import('./pages/leaves/LeaveRequests'))
const PayrollRuns = lazy(() => import('./pages/payroll/PayrollRuns'))
const PayrollRunDetail = lazy(() => import('./pages/payroll/PayrollRunDetail'))
const MyPayslips = lazy(() => import('./pages/payroll/MyPayslips'))
const Reports = lazy(() => import('./pages/Reports'))
const AuditLogs = lazy(() => import('./pages/admin/AuditLogs'))
const Organization = lazy(() => import('./pages/admin/Organization'))
const LeaveTypes = lazy(() => import('./pages/admin/LeaveTypes'))
const RolesUsers = lazy(() => import('./pages/admin/RolesUsers'))
const EmailCenter = lazy(() => import('./pages/admin/EmailCenter'))
const SettingsPage = lazy(() => import('./pages/admin/Settings'))
import { ShieldOff } from 'lucide-react'

function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <PageLoader />
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />
  if (user.must_change_password && location.pathname !== '/change-password') return <Navigate to="/change-password" replace />
  return children
}

function Guard({ perm, any, employee, children }) {
  const { can, canAny, hasEmployee } = useAuth()
  const ok = (!perm || can(...[].concat(perm))) && (!any || canAny(...any)) && (!employee || hasEmployee)
  return ok ? children : <EmptyState icon={ShieldOff} title="Access denied" message="You don't have permission to view this page." />
}

export default function App() {
  const { user } = useAuth()
  return (
    <Suspense fallback={<PageLoader />}>
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route index element={<Dashboard />} />
        <Route path="change-password" element={<ChangePassword />} />
        <Route path="profile" element={<Guard employee><Profile /></Guard>} />
        <Route path="my/attendance" element={<Guard perm="attendance:self" employee><MyAttendance /></Guard>} />
        <Route path="my/leaves" element={<Guard perm="leave:apply" employee><MyLeaves /></Guard>} />
        <Route path="my/payslips" element={<Guard perm="payslip:self" employee><MyPayslips /></Guard>} />
        <Route path="employees" element={<Guard perm="employee:view"><EmployeeList /></Guard>} />
        <Route path="employees/new" element={<Guard perm={['employee:create', 'salary:manage']}><EmployeeForm /></Guard>} />
        <Route path="employees/:id" element={<Guard perm="employee:view"><EmployeeDetail /></Guard>} />
        <Route path="employees/:id/edit" element={<Guard perm="employee:update"><EmployeeForm /></Guard>} />
        <Route path="attendance" element={<Guard perm="attendance:view"><AttendanceAdmin /></Guard>} />
        <Route path="leaves" element={<Guard perm="leave:view"><LeaveRequests /></Guard>} />
        <Route path="leaves/approvals" element={<Guard perm="leave:view"><LeaveRequests initialStatus="pending" /></Guard>} />
        <Route path="payroll" element={<Guard perm="payroll:view"><PayrollRuns /></Guard>} />
        <Route path="payroll/:id" element={<Guard perm="payroll:view"><PayrollRunDetail /></Guard>} />
        <Route path="reports" element={<Guard perm="reports:view"><Reports /></Guard>} />
        <Route path="audit" element={<Guard perm="audit:view"><AuditLogs /></Guard>} />
        <Route path="admin/organization" element={<Guard perm="org:manage"><Organization /></Guard>} />
        <Route path="admin/leave-types" element={<Guard perm="leave:configure"><LeaveTypes /></Guard>} />
        <Route path="admin/roles" element={<Guard perm="role:manage"><RolesUsers /></Guard>} />
        <Route path="admin/emails" element={<Guard perm="notification:manage"><EmailCenter /></Guard>} />
        <Route path="admin/settings" element={<Guard perm="settings:manage"><SettingsPage /></Guard>} />
        {/* links used in notifications/emails */}
        <Route path="payslips" element={<Navigate to="/my/payslips" replace />} />
        <Route path="*" element={<EmptyState title="Page not found" message="The page you're looking for doesn't exist." />} />
      </Route>
    </Routes>
    </Suspense>
  )
}
