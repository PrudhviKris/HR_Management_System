"""Default email templates (seeded into the email_templates table, editable from the admin panel).

Subjects and bodies are Jinja2 templates rendered in a sandbox with HTML auto-escaping.
`company_name` and `app_url` are always available.
"""

LAYOUT = """<!doctype html>
<html><body style="margin:0;padding:24px;background:#f4f5f7;font-family:Segoe UI,Arial,sans-serif;color:#1f2937">
<table role="presentation" width="100%" style="max-width:600px;margin:0 auto;background:#ffffff;border-radius:8px;overflow:hidden">
<tr><td style="background:#4f46e5;color:#ffffff;padding:18px 24px;font-size:18px;font-weight:600">{{ company_name }}</td></tr>
<tr><td style="padding:24px;font-size:14px;line-height:1.6">{{ content }}</td></tr>
<tr><td style="padding:14px 24px;background:#f9fafb;color:#6b7280;font-size:12px">
This is an automated message from the {{ company_name }} HR system. Please do not reply.</td></tr>
</table></body></html>"""

DEFAULT_TEMPLATES: list[dict] = [
    {
        "code": "employee_onboarding",
        "name": "Employee onboarding",
        "description": "Sent to a new employee when their profile is created",
        "variables": "employee_name, employee_code, email, designation, department, joining_date, login_url, set_password_url",
        "subject": "Welcome to {{ company_name }}, {{ employee_name }}!",
        "body_html": """<p>Hi {{ employee_name }},</p>
<p>Welcome aboard! Your employee profile has been created.</p>
<table style="border-collapse:collapse">
<tr><td style="padding:2px 12px 2px 0;color:#6b7280">Employee ID</td><td><b>{{ employee_code }}</b></td></tr>
<tr><td style="padding:2px 12px 2px 0;color:#6b7280">Designation</td><td>{{ designation or '-' }}</td></tr>
<tr><td style="padding:2px 12px 2px 0;color:#6b7280">Department</td><td>{{ department or '-' }}</td></tr>
<tr><td style="padding:2px 12px 2px 0;color:#6b7280">Joining date</td><td>{{ joining_date }}</td></tr>
<tr><td style="padding:2px 12px 2px 0;color:#6b7280">Login email</td><td>{{ email }}</td></tr>
</table>
{% if set_password_url %}
<p>Please set your password to activate your account (link valid for 72 hours):</p>
<p><a href="{{ set_password_url }}" style="background:#4f46e5;color:#fff;padding:10px 16px;border-radius:6px;text-decoration:none">Set my password</a></p>
{% else %}
<p>Your HR team will share your temporary password separately. You will be asked to change it at first login: <a href="{{ login_url }}">{{ login_url }}</a></p>
{% endif %}
<p>Regards,<br>HR Team</p>""",
    },
    {
        "code": "leave_applied",
        "name": "Leave application (to approvers)",
        "description": "Sent to HR/Admin approvers when an employee applies for leave",
        "variables": "approver_name, employee_name, employee_code, leave_type, start_date, end_date, days, lop_days, reason, review_url",
        "subject": "Leave request: {{ employee_name }} ({{ days }} day{{ '' if days == 1 else 's' }})",
        "body_html": """<p>Hi {{ approver_name }},</p>
<p><b>{{ employee_name }}</b> ({{ employee_code }}) has applied for <b>{{ leave_type }}</b>.</p>
<ul>
<li>Period: {{ start_date }} to {{ end_date }} ({{ days }} working day(s))</li>
{% if lop_days and lop_days > 0 %}<li style="color:#b45309">Estimated Loss of Pay: {{ lop_days }} day(s) (insufficient balance)</li>{% endif %}
<li>Reason: {{ reason }}</li>
</ul>
<p><a href="{{ review_url }}">Review the request</a></p>""",
    },
    {
        "code": "leave_applied_confirmation",
        "name": "Leave application (to employee)",
        "description": "Acknowledgement sent to the employee after applying for leave",
        "variables": "employee_name, leave_type, start_date, end_date, days, lop_days",
        "subject": "Your {{ leave_type }} request has been submitted",
        "body_html": """<p>Hi {{ employee_name }},</p>
<p>Your <b>{{ leave_type }}</b> request for {{ start_date }} to {{ end_date }} ({{ days }} day(s)) has been submitted and is pending approval.</p>
{% if lop_days and lop_days > 0 %}<p style="color:#b45309">Note: based on your current balance, {{ lop_days }} day(s) may be treated as Loss of Pay.</p>{% endif %}
<p>Regards,<br>HR Team</p>""",
    },
    {
        "code": "leave_status",
        "name": "Leave approved / rejected",
        "description": "Sent to the employee when a leave request is approved or rejected",
        "variables": "employee_name, leave_type, start_date, end_date, days, status, paid_days, lop_days, comment, reviewer_name",
        "subject": "Your {{ leave_type }} request has been {{ status }}",
        "body_html": """<p>Hi {{ employee_name }},</p>
<p>Your <b>{{ leave_type }}</b> request for {{ start_date }} to {{ end_date }} ({{ days }} day(s)) has been
<b style="color:{{ '#15803d' if status == 'approved' else '#b91c1c' }}">{{ status }}</b> by {{ reviewer_name }}.</p>
{% if status == 'approved' %}<p>Paid days: {{ paid_days }}{% if lop_days and lop_days > 0 %} &middot; <span style="color:#b45309">Loss of Pay days: {{ lop_days }}</span>{% endif %}</p>{% endif %}
{% if comment %}<p>Comment: <i>{{ comment }}</i></p>{% endif %}
<p>Regards,<br>HR Team</p>""",
    },
    {
        "code": "payslip_generated",
        "name": "Salary slip generated",
        "description": "Sent to each employee when payroll is locked and the payslip PDF is available",
        "variables": "employee_name, period, net_salary, paid_days, lop_days, payslip_url",
        "subject": "Your salary slip for {{ period }} is available",
        "body_html": """<p>Hi {{ employee_name }},</p>
<p>Your salary slip for <b>{{ period }}</b> has been generated.</p>
<p>Net salary: <b>&#8377; {{ net_salary }}</b><br>Paid days: {{ paid_days }}{% if lop_days and lop_days > 0 %} &middot; LOP days: {{ lop_days }}{% endif %}</p>
<p><a href="{{ payslip_url }}">View and download your payslip</a></p>""",
    },
    {
        "code": "payroll_processed",
        "name": "Payroll processed (to admins)",
        "description": "Sent to payroll administrators when a payroll run is locked or credited",
        "variables": "recipient_name, period, action, employee_count, total_gross, total_net, actor_name",
        "subject": "Payroll {{ action }}: {{ period }}",
        "body_html": """<p>Hi {{ recipient_name }},</p>
<p>The payroll for <b>{{ period }}</b> was <b>{{ action }}</b> by {{ actor_name }}.</p>
<ul><li>Employees: {{ employee_count }}</li><li>Total gross: &#8377; {{ total_gross }}</li><li>Total net payout: &#8377; {{ total_net }}</li></ul>""",
    },
    {
        "code": "salary_credited",
        "name": "Salary credited",
        "description": "Sent to the employee when the (simulated) salary credit is completed",
        "variables": "employee_name, period, net_salary, transaction_ref, bank_account",
        "subject": "Salary credited for {{ period }}",
        "body_html": """<p>Hi {{ employee_name }},</p>
<p>Your salary of <b>&#8377; {{ net_salary }}</b> for {{ period }} has been credited to account {{ bank_account or 'on file' }}.</p>
<p>Transaction reference: <code>{{ transaction_ref }}</code></p>""",
    },
    {
        "code": "password_reset",
        "name": "Password reset",
        "description": "Sent when a password reset is requested",
        "variables": "user_name, reset_url, expires_hours",
        "subject": "Reset your {{ company_name }} HRMS password",
        "body_html": """<p>Hi {{ user_name }},</p>
<p>We received a request to reset your password. This link is valid for {{ expires_hours }} hours:</p>
<p><a href="{{ reset_url }}" style="background:#4f46e5;color:#fff;padding:10px 16px;border-radius:6px;text-decoration:none">Reset password</a></p>
<p>If you didn't request this, you can ignore this email.</p>""",
    },
]
