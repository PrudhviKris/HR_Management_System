// Captures UI screenshots of the running app into ../docs/screenshots.
// Usage: start backend + frontend, then `npm run screenshots` (uses the installed Edge/Chrome).
import { chromium } from 'playwright-core'
import { mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const BASE = process.env.APP_URL || 'http://localhost:5173'
const OUT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../docs/screenshots')
mkdirSync(OUT, { recursive: true })

const ACCOUNTS = {
  admin: ['admin@example.com', 'Admin@123'],
  hr: ['hr@example.com', 'Hr@12345'],
  employee: ['rahul.verma@example.com', 'Employee@123'],
}

const SHOTS = {
  admin: [
    ['admin_01_dashboard', '/'],
    ['admin_02_employees', '/employees'],
    ['admin_03_employee_profile', '/employees/3'],
    ['admin_04_attendance_board', '/attendance'],
    ['admin_05_leave_approvals', '/leaves/approvals'],
    ['admin_06_payroll_runs', '/payroll'],
    ['admin_07_payroll_draft', '/payroll/3'],
    ['admin_08_reports', '/reports', async (p) => {
      const d = new Date(); const first = new Date(d.getFullYear(), d.getMonth() - 1, 1); const last = new Date(d.getFullYear(), d.getMonth(), 0)
      const iso = (x) => `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`
      await p.locator('input[type=date]').nth(0).fill(iso(first))
      await p.locator('input[type=date]').nth(1).fill(iso(last))
      await p.getByRole('button', { name: 'Run report' }).click(); await p.waitForTimeout(1500)
    }],
    ['admin_09_roles_permissions', '/admin/roles', async (p) => { await p.getByRole('button', { name: /Edit/ }).first().click(); await p.waitForTimeout(500) }],
    ['admin_10_audit_logs', '/audit'],
    ['admin_11_email_log', '/admin/emails'],
    ['admin_12_new_employee_form', '/employees/new'],
  ],
  employee: [
    ['employee_01_dashboard', '/'],
    ['employee_02_attendance', '/my/attendance'],
    ['employee_03_leaves', '/my/leaves'],
    ['employee_04_apply_leave', '/my/leaves', async (p) => { await p.getByRole('button', { name: 'Apply for leave' }).first().click(); await p.waitForTimeout(400) }],
    ['employee_05_payslips', '/my/payslips'],
    ['employee_06_payslip_detail', '/my/payslips', async (p) => { await p.locator('tbody tr').first().click(); await p.waitForTimeout(500) }],
    ['employee_07_profile', '/profile'],
  ],
}

const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true })
try {
  const ctx0 = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const p0 = await ctx0.newPage()
  await p0.goto(`${BASE}/login`)
  await p0.waitForSelector('input[type=email]')
  await p0.screenshot({ path: path.join(OUT, '00_login.png') })
  await ctx0.close()

  for (const [who, shots] of Object.entries(SHOTS)) {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })
    const page = await ctx.newPage()
    await page.goto(`${BASE}/login`)
    await page.fill('input[type=email]', ACCOUNTS[who][0])
    await page.fill('input[type=password]', ACCOUNTS[who][1])
    await page.click('form button.btn-primary')
    await page.waitForURL(`${BASE}/`)
    for (const [name, url, action] of shots) {
      await page.goto(`${BASE}${url}`)
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(700)
      if (action) await action(page)
      await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: !action })
      console.log('saved', name)
    }
    await ctx.close()
  }
} finally {
  await browser.close()
}
