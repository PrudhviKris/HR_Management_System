-- HRMS database - generated 2026-11-24 14:36
-- Target: MySQL 8+/9 (utf8mb4)
-- Apply with:  mysql -u root -p hrms_db < schema.sql   (or run `alembic upgrade head`)

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE TABLE departments (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    name VARCHAR(100) NOT NULL, 
    code VARCHAR(20) NOT NULL, 
    description VARCHAR(255), 
    is_active BOOL NOT NULL, 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    CONSTRAINT pk_departments PRIMARY KEY (id), 
    CONSTRAINT uq_departments_code UNIQUE (code), 
    CONSTRAINT uq_departments_name UNIQUE (name)
);

CREATE TABLE email_logs (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    template_code VARCHAR(50) NOT NULL, 
    recipient VARCHAR(255) NOT NULL, 
    subject VARCHAR(255) NOT NULL, 
    body_html TEXT NOT NULL, 
    status ENUM('queued','sent','logged','failed') NOT NULL, 
    error_message VARCHAR(500), 
    entity_type VARCHAR(50), 
    entity_id VARCHAR(50), 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    sent_at DATETIME, 
    CONSTRAINT pk_email_logs PRIMARY KEY (id)
);

CREATE INDEX ix_email_logs_created ON email_logs (created_at);

CREATE INDEX ix_email_logs_recipient ON email_logs (recipient);

CREATE INDEX ix_email_logs_template_code ON email_logs (template_code);

CREATE TABLE holidays (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    holiday_date DATE NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    is_optional BOOL NOT NULL, 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    CONSTRAINT pk_holidays PRIMARY KEY (id), 
    CONSTRAINT uq_holidays_holiday_date UNIQUE (holiday_date)
);

CREATE TABLE leave_types (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    name VARCHAR(50) NOT NULL, 
    code VARCHAR(10) NOT NULL, 
    annual_quota NUMERIC(5, 1) NOT NULL, 
    is_paid BOOL NOT NULL, 
    carry_forward BOOL NOT NULL, 
    max_carry_forward NUMERIC(5, 1) NOT NULL, 
    color VARCHAR(10) NOT NULL, 
    description VARCHAR(255), 
    is_active BOOL NOT NULL, 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    CONSTRAINT pk_leave_types PRIMARY KEY (id), 
    CONSTRAINT uq_leave_types_code UNIQUE (code), 
    CONSTRAINT uq_leave_types_name UNIQUE (name)
);

CREATE TABLE permissions (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    code VARCHAR(64) NOT NULL, 
    module VARCHAR(40) NOT NULL, 
    description VARCHAR(255) NOT NULL, 
    CONSTRAINT pk_permissions PRIMARY KEY (id), 
    CONSTRAINT uq_permissions_code UNIQUE (code)
);

CREATE TABLE roles (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    name VARCHAR(50) NOT NULL, 
    description VARCHAR(255) NOT NULL, 
    is_system BOOL NOT NULL, 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    CONSTRAINT pk_roles PRIMARY KEY (id), 
    CONSTRAINT uq_roles_name UNIQUE (name)
);

CREATE TABLE system_settings (
    `key` VARCHAR(64) NOT NULL, 
    value TEXT NOT NULL, 
    description VARCHAR(255) NOT NULL, 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    CONSTRAINT pk_system_settings PRIMARY KEY (`key`)
);

CREATE TABLE designations (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    title VARCHAR(100) NOT NULL, 
    department_id INTEGER, 
    description VARCHAR(255), 
    is_active BOOL NOT NULL, 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    CONSTRAINT pk_designations PRIMARY KEY (id), 
    CONSTRAINT fk_designations_department_id_departments FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL, 
    CONSTRAINT uq_designations_title UNIQUE (title)
);

CREATE INDEX ix_designations_department_id ON designations (department_id);

CREATE TABLE role_permissions (
    role_id INTEGER NOT NULL, 
    permission_id INTEGER NOT NULL, 
    CONSTRAINT pk_role_permissions PRIMARY KEY (role_id, permission_id), 
    CONSTRAINT fk_role_permissions_permission_id_permissions FOREIGN KEY(permission_id) REFERENCES permissions (id) ON DELETE CASCADE, 
    CONSTRAINT fk_role_permissions_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE
);

CREATE TABLE users (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    email VARCHAR(255) NOT NULL, 
    full_name VARCHAR(150) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    role_id INTEGER NOT NULL, 
    is_active BOOL NOT NULL, 
    must_change_password BOOL NOT NULL, 
    token_version INTEGER NOT NULL, 
    failed_login_attempts INTEGER NOT NULL, 
    locked_until DATETIME, 
    last_login_at DATETIME, 
    password_changed_at DATETIME, 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    CONSTRAINT pk_users PRIMARY KEY (id), 
    CONSTRAINT fk_users_role_id_roles FOREIGN KEY(role_id) REFERENCES roles (id), 
    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE INDEX ix_users_role_id ON users (role_id);

CREATE TABLE audit_logs (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    actor_id INTEGER, 
    actor_email VARCHAR(255), 
    action VARCHAR(64) NOT NULL, 
    entity_type VARCHAR(50), 
    entity_id VARCHAR(50), 
    description VARCHAR(500) NOT NULL, 
    changes JSON, 
    ip_address VARCHAR(64), 
    user_agent VARCHAR(255), 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    CONSTRAINT pk_audit_logs PRIMARY KEY (id), 
    CONSTRAINT fk_audit_logs_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_audit_created ON audit_logs (created_at);

CREATE INDEX ix_audit_entity ON audit_logs (entity_type, entity_id);

CREATE INDEX ix_audit_logs_action ON audit_logs (action);

CREATE INDEX ix_audit_logs_actor_id ON audit_logs (actor_id);

CREATE TABLE email_templates (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    code VARCHAR(50) NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    subject VARCHAR(255) NOT NULL, 
    body_html TEXT NOT NULL, 
    description VARCHAR(255), 
    variables VARCHAR(500), 
    is_active BOOL NOT NULL, 
    updated_by_id INTEGER, 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    CONSTRAINT pk_email_templates PRIMARY KEY (id), 
    CONSTRAINT fk_email_templates_updated_by_id_users FOREIGN KEY(updated_by_id) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT uq_email_templates_code UNIQUE (code)
);

CREATE TABLE employees (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    user_id INTEGER NOT NULL, 
    employee_code VARCHAR(20) NOT NULL, 
    first_name VARCHAR(75) NOT NULL, 
    last_name VARCHAR(75) NOT NULL, 
    phone VARCHAR(20), 
    date_of_birth DATE, 
    gender ENUM('male','female','other'), 
    address TEXT, 
    emergency_contact_name VARCHAR(150), 
    emergency_contact_phone VARCHAR(20), 
    department_id INTEGER, 
    designation_id INTEGER, 
    manager_id INTEGER, 
    date_of_joining DATE NOT NULL, 
    employment_type ENUM('full_time','part_time','contract','intern') NOT NULL, 
    work_location VARCHAR(100), 
    status ENUM('active','inactive') NOT NULL, 
    exit_date DATE, 
    exit_reason VARCHAR(255), 
    bank_name VARCHAR(100), 
    bank_account_number VARCHAR(30), 
    ifsc_code VARCHAR(15), 
    pan_number VARCHAR(10), 
    created_by_id INTEGER, 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    CONSTRAINT pk_employees PRIMARY KEY (id), 
    CONSTRAINT fk_employees_created_by_id_users FOREIGN KEY(created_by_id) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT fk_employees_department_id_departments FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL, 
    CONSTRAINT fk_employees_designation_id_designations FOREIGN KEY(designation_id) REFERENCES designations (id) ON DELETE SET NULL, 
    CONSTRAINT fk_employees_manager_id_employees FOREIGN KEY(manager_id) REFERENCES employees (id) ON DELETE SET NULL, 
    CONSTRAINT fk_employees_user_id_users FOREIGN KEY(user_id) REFERENCES users (id), 
    CONSTRAINT uq_employees_employee_code UNIQUE (employee_code), 
    CONSTRAINT uq_employees_user_id UNIQUE (user_id)
);

CREATE INDEX ix_employees_department_id ON employees (department_id);

CREATE INDEX ix_employees_designation_id ON employees (designation_id);

CREATE INDEX ix_employees_manager_id ON employees (manager_id);

CREATE INDEX ix_employees_status_department ON employees (status, department_id);

CREATE TABLE notifications (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    user_id INTEGER NOT NULL, 
    title VARCHAR(150) NOT NULL, 
    message VARCHAR(500) NOT NULL, 
    link VARCHAR(255), 
    is_read BOOL NOT NULL, 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    CONSTRAINT pk_notifications PRIMARY KEY (id), 
    CONSTRAINT fk_notifications_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_notifications_user_read ON notifications (user_id, is_read);

CREATE TABLE password_reset_tokens (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    user_id INTEGER NOT NULL, 
    token_hash VARCHAR(64) NOT NULL, 
    purpose ENUM('onboarding','reset') NOT NULL, 
    expires_at DATETIME NOT NULL, 
    used_at DATETIME, 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    note TEXT, 
    CONSTRAINT pk_password_reset_tokens PRIMARY KEY (id), 
    CONSTRAINT fk_password_reset_tokens_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_password_reset_tokens_token_hash UNIQUE (token_hash)
);

CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens (user_id);

CREATE TABLE payroll_runs (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    year INTEGER NOT NULL, 
    month INTEGER NOT NULL, 
    status ENUM('draft','locked','paid') NOT NULL, 
    working_days INTEGER NOT NULL, 
    employee_count INTEGER NOT NULL, 
    total_gross NUMERIC(12, 2) NOT NULL, 
    total_deductions NUMERIC(12, 2) NOT NULL, 
    total_net NUMERIC(12, 2) NOT NULL, 
    notes TEXT, 
    generated_by_id INTEGER, 
    generated_at DATETIME, 
    locked_by_id INTEGER, 
    locked_at DATETIME, 
    paid_by_id INTEGER, 
    paid_at DATETIME, 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    CONSTRAINT pk_payroll_runs PRIMARY KEY (id), 
    CONSTRAINT fk_payroll_runs_generated_by_id_users FOREIGN KEY(generated_by_id) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT fk_payroll_runs_locked_by_id_users FOREIGN KEY(locked_by_id) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT fk_payroll_runs_paid_by_id_users FOREIGN KEY(paid_by_id) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT uq_payroll_period UNIQUE (year, month)
);

CREATE TABLE refresh_tokens (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    user_id INTEGER NOT NULL, 
    jti VARCHAR(64) NOT NULL, 
    expires_at DATETIME NOT NULL, 
    revoked_at DATETIME, 
    replaced_by_jti VARCHAR(64), 
    ip_address VARCHAR(64), 
    user_agent VARCHAR(255), 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    CONSTRAINT pk_refresh_tokens PRIMARY KEY (id), 
    CONSTRAINT fk_refresh_tokens_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_refresh_tokens_jti UNIQUE (jti)
);

CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens (user_id);

CREATE TABLE attendance (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    employee_id INTEGER NOT NULL, 
    work_date DATE NOT NULL, 
    check_in DATETIME, 
    check_out DATETIME, 
    work_minutes INTEGER NOT NULL, 
    status ENUM('present','half_day','absent') NOT NULL, 
    is_late BOOL NOT NULL, 
    check_in_ip VARCHAR(64), 
    remarks VARCHAR(255), 
    is_overridden BOOL NOT NULL, 
    override_reason VARCHAR(255), 
    overridden_by_id INTEGER, 
    overridden_at DATETIME, 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    CONSTRAINT pk_attendance PRIMARY KEY (id), 
    CONSTRAINT fk_attendance_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
    CONSTRAINT fk_attendance_overridden_by_id_users FOREIGN KEY(overridden_by_id) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT uq_attendance_employee_date UNIQUE (employee_id, work_date)
);

CREATE INDEX ix_attendance_work_date ON attendance (work_date);

CREATE TABLE employee_documents (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    employee_id INTEGER NOT NULL, 
    document_type VARCHAR(50) NOT NULL, 
    original_filename VARCHAR(255) NOT NULL, 
    stored_filename VARCHAR(100) NOT NULL, 
    content_type VARCHAR(100) NOT NULL, 
    size_bytes INTEGER NOT NULL, 
    sha256 VARCHAR(64) NOT NULL, 
    uploaded_by_id INTEGER, 
    uploaded_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    CONSTRAINT pk_employee_documents PRIMARY KEY (id), 
    CONSTRAINT fk_employee_documents_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
    CONSTRAINT fk_employee_documents_uploaded_by_id_users FOREIGN KEY(uploaded_by_id) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT uq_employee_documents_stored_filename UNIQUE (stored_filename)
);

CREATE INDEX ix_employee_documents_employee_id ON employee_documents (employee_id);

CREATE TABLE leave_balances (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    employee_id INTEGER NOT NULL, 
    leave_type_id INTEGER NOT NULL, 
    year INTEGER NOT NULL, 
    allocated NUMERIC(5, 1) NOT NULL, 
    carried_forward NUMERIC(5, 1) NOT NULL, 
    used NUMERIC(5, 1) NOT NULL, 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    CONSTRAINT pk_leave_balances PRIMARY KEY (id), 
    CONSTRAINT fk_leave_balances_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
    CONSTRAINT fk_leave_balances_leave_type_id_leave_types FOREIGN KEY(leave_type_id) REFERENCES leave_types (id) ON DELETE CASCADE, 
    CONSTRAINT uq_leave_balance UNIQUE (employee_id, leave_type_id, year)
);

CREATE TABLE leave_requests (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    employee_id INTEGER NOT NULL, 
    leave_type_id INTEGER NOT NULL, 
    start_date DATE NOT NULL, 
    end_date DATE NOT NULL, 
    is_half_day BOOL NOT NULL, 
    total_days NUMERIC(5, 1) NOT NULL, 
    paid_days NUMERIC(5, 1) NOT NULL, 
    lop_days NUMERIC(5, 1) NOT NULL, 
    reason TEXT NOT NULL, 
    status ENUM('pending','approved','rejected','cancelled') NOT NULL, 
    reviewed_by_id INTEGER, 
    reviewed_at DATETIME, 
    review_comment VARCHAR(255), 
    cancelled_at DATETIME, 
    applied_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    CONSTRAINT pk_leave_requests PRIMARY KEY (id), 
    CONSTRAINT ck_leave_requests_date_order CHECK (end_date >= start_date), 
    CONSTRAINT fk_leave_requests_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE, 
    CONSTRAINT fk_leave_requests_leave_type_id_leave_types FOREIGN KEY(leave_type_id) REFERENCES leave_types (id), 
    CONSTRAINT fk_leave_requests_reviewed_by_id_users FOREIGN KEY(reviewed_by_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_leave_employee_dates ON leave_requests (employee_id, start_date, end_date);

CREATE INDEX ix_leave_status ON leave_requests (status);

CREATE TABLE payslips (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    payroll_run_id INTEGER NOT NULL, 
    employee_id INTEGER NOT NULL, 
    employee_code VARCHAR(20) NOT NULL, 
    employee_name VARCHAR(150) NOT NULL, 
    department_name VARCHAR(100), 
    designation_title VARCHAR(100), 
    date_of_joining DATE, 
    bank_name VARCHAR(100), 
    bank_account_masked VARCHAR(30), 
    pan_number VARCHAR(10), 
    working_days INTEGER NOT NULL, 
    eligible_days INTEGER NOT NULL, 
    present_days NUMERIC(5, 1) NOT NULL, 
    paid_leave_days NUMERIC(5, 1) NOT NULL, 
    lop_days NUMERIC(5, 1) NOT NULL, 
    paid_days NUMERIC(5, 1) NOT NULL, 
    monthly_gross NUMERIC(12, 2) NOT NULL, 
    basic NUMERIC(12, 2) NOT NULL, 
    hra NUMERIC(12, 2) NOT NULL, 
    conveyance_allowance NUMERIC(12, 2) NOT NULL, 
    medical_allowance NUMERIC(12, 2) NOT NULL, 
    special_allowance NUMERIC(12, 2) NOT NULL, 
    adjustment_earnings NUMERIC(12, 2) NOT NULL, 
    gross_earnings NUMERIC(12, 2) NOT NULL, 
    lop_deduction NUMERIC(12, 2) NOT NULL, 
    provident_fund NUMERIC(12, 2) NOT NULL, 
    professional_tax NUMERIC(12, 2) NOT NULL, 
    income_tax NUMERIC(12, 2) NOT NULL, 
    adjustment_deductions NUMERIC(12, 2) NOT NULL, 
    total_deductions NUMERIC(12, 2) NOT NULL, 
    net_salary NUMERIC(12, 2) NOT NULL, 
    payment_status ENUM('pending','credited','failed') NOT NULL, 
    transaction_ref VARCHAR(40), 
    credited_at DATETIME, 
    pdf_filename VARCHAR(100), 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    CONSTRAINT pk_payslips PRIMARY KEY (id), 
    CONSTRAINT fk_payslips_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id), 
    CONSTRAINT fk_payslips_payroll_run_id_payroll_runs FOREIGN KEY(payroll_run_id) REFERENCES payroll_runs (id) ON DELETE CASCADE, 
    CONSTRAINT uq_payslip_run_employee UNIQUE (payroll_run_id, employee_id)
);

CREATE INDEX ix_payslips_employee_id ON payslips (employee_id);

CREATE TABLE salary_structures (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    employee_id INTEGER NOT NULL, 
    effective_from DATE NOT NULL, 
    basic NUMERIC(12, 2) NOT NULL, 
    hra NUMERIC(12, 2) NOT NULL, 
    conveyance_allowance NUMERIC(12, 2) NOT NULL, 
    medical_allowance NUMERIC(12, 2) NOT NULL, 
    special_allowance NUMERIC(12, 2) NOT NULL, 
    pf_applicable BOOL NOT NULL, 
    professional_tax_applicable BOOL NOT NULL, 
    tds_monthly NUMERIC(12, 2) NOT NULL, 
    remarks VARCHAR(255), 
    created_by_id INTEGER, 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    CONSTRAINT pk_salary_structures PRIMARY KEY (id), 
    CONSTRAINT fk_salary_structures_created_by_id_users FOREIGN KEY(created_by_id) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT fk_salary_structures_employee_id_employees FOREIGN KEY(employee_id) REFERENCES employees (id) ON DELETE CASCADE
);

CREATE INDEX ix_salary_employee_effective ON salary_structures (employee_id, effective_from);

CREATE TABLE payroll_adjustments (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    payslip_id INTEGER NOT NULL, 
    kind ENUM('earning','deduction') NOT NULL, 
    label VARCHAR(100) NOT NULL, 
    amount NUMERIC(12, 2) NOT NULL, 
    reason VARCHAR(255) NOT NULL, 
    created_by_id INTEGER, 
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP), 
    CONSTRAINT pk_payroll_adjustments PRIMARY KEY (id), 
    CONSTRAINT fk_payroll_adjustments_created_by_id_users FOREIGN KEY(created_by_id) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT fk_payroll_adjustments_payslip_id_payslips FOREIGN KEY(payslip_id) REFERENCES payslips (id) ON DELETE CASCADE
);

CREATE INDEX ix_payroll_adjustments_payslip_id ON payroll_adjustments (payslip_id);

CREATE TRIGGER trg_audit_logs_no_update BEFORE UPDATE ON audit_logs
                FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'audit_logs is append-only';

CREATE TRIGGER trg_audit_logs_no_delete BEFORE DELETE ON audit_logs
                FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'audit_logs is append-only';

INSERT INTO alembic_version (version_num) VALUES ('0001');

