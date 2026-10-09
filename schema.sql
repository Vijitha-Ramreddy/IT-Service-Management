CREATE DATABASE IF NOT EXISTS it_service_management
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE it_service_management;

-- =====================================================
-- 1. USERS
-- Employees, IT agents, managers and administrators
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    employee_code VARCHAR(30) NOT NULL,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('EMPLOYEE', 'IT_AGENT', 'MANAGER', 'ADMIN') NOT NULL DEFAULT 'EMPLOYEE',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_employee_code (employee_code),
    UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- 2. CATEGORIES
-- Request categories
-- =====================================================
CREATE TABLE IF NOT EXISTS categories (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(255) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_categories_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- 3. PRIORITIES
-- Request priority levels and SLA expectations
-- =====================================================
CREATE TABLE IF NOT EXISTS priorities (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(50) NOT NULL,
    sla_hours INT NOT NULL,
    description VARCHAR(255) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_priorities_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- 4. STATUSES
-- Lifecycle states for service requests
-- =====================================================
CREATE TABLE IF NOT EXISTS statuses (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(50) NOT NULL,
    description VARCHAR(255) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_statuses_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- 5. SLA POLICIES
-- SLA rules applied to requests
-- =====================================================
CREATE TABLE IF NOT EXISTS sla_policies (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    response_time_hours INT NOT NULL,
    resolution_time_hours INT NOT NULL,
    description VARCHAR(255) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_sla_policies_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- 6. REQUESTS
-- Service request tickets
-- =====================================================
CREATE TABLE IF NOT EXISTS requests (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    requester_id BIGINT UNSIGNED NOT NULL,
    assigned_agent_id BIGINT UNSIGNED NULL,
    category_id BIGINT UNSIGNED NOT NULL,
    priority_id BIGINT UNSIGNED NOT NULL,
    status_id BIGINT UNSIGNED NOT NULL,
    sla_policy_id BIGINT UNSIGNED NOT NULL,
    subject VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    attachments JSON NULL,
    due_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6),
    resolved_at DATETIME(6) NULL,
    closed_at DATETIME(6) NULL,
    PRIMARY KEY (id),
    KEY idx_requests_requester_id (requester_id),
    KEY idx_requests_assigned_agent_id (assigned_agent_id),
    KEY idx_requests_category_id (category_id),
    KEY idx_requests_priority_id (priority_id),
    KEY idx_requests_status_id (status_id),
    KEY idx_requests_sla_policy_id (sla_policy_id),
    CONSTRAINT fk_requests_requester
        FOREIGN KEY (requester_id) REFERENCES users(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_requests_assigned_agent
        FOREIGN KEY (assigned_agent_id) REFERENCES users(id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_requests_category
        FOREIGN KEY (category_id) REFERENCES categories(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_requests_priority
        FOREIGN KEY (priority_id) REFERENCES priorities(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_requests_status
        FOREIGN KEY (status_id) REFERENCES statuses(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_requests_sla_policy
        FOREIGN KEY (sla_policy_id) REFERENCES sla_policies(id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- 7. COMMENTS
-- Conversation on each request
-- =====================================================
CREATE TABLE IF NOT EXISTS comments (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    request_id BIGINT UNSIGNED NOT NULL,
    author_id BIGINT UNSIGNED NOT NULL,
    message TEXT NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    KEY idx_comments_request_id (request_id),
    KEY idx_comments_author_id (author_id),
    CONSTRAINT fk_comments_request
        FOREIGN KEY (request_id) REFERENCES requests(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_comments_author
        FOREIGN KEY (author_id) REFERENCES users(id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- 8. REQUEST HISTORY
-- General audit trail for request changes
-- =====================================================
CREATE TABLE IF NOT EXISTS request_history (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    request_id BIGINT UNSIGNED NOT NULL,
    changed_by_id BIGINT UNSIGNED NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    old_value TEXT NULL,
    new_value TEXT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    KEY idx_request_history_request_id (request_id),
    KEY idx_request_history_changed_by_id (changed_by_id),
    CONSTRAINT fk_request_history_request
        FOREIGN KEY (request_id) REFERENCES requests(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_request_history_user
        FOREIGN KEY (changed_by_id) REFERENCES users(id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- 9. STATUS HISTORY
-- Track every status transition over time
-- =====================================================
CREATE TABLE IF NOT EXISTS status_history (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    request_id BIGINT UNSIGNED NOT NULL,
    from_status_id BIGINT UNSIGNED NULL,
    to_status_id BIGINT UNSIGNED NOT NULL,
    changed_by_id BIGINT UNSIGNED NOT NULL,
    notes VARCHAR(255) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    KEY idx_status_history_request_id (request_id),
    KEY idx_status_history_from_status_id (from_status_id),
    KEY idx_status_history_to_status_id (to_status_id),
    KEY idx_status_history_changed_by_id (changed_by_id),
    CONSTRAINT fk_status_history_request
        FOREIGN KEY (request_id) REFERENCES requests(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_status_history_from_status
        FOREIGN KEY (from_status_id) REFERENCES statuses(id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_status_history_to_status
        FOREIGN KEY (to_status_id) REFERENCES statuses(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_status_history_changed_by
        FOREIGN KEY (changed_by_id) REFERENCES users(id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- 10. ASSIGNMENT HISTORY
-- Track who is assigned and re-assigned over time
-- =====================================================
CREATE TABLE IF NOT EXISTS assignment_history (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    request_id BIGINT UNSIGNED NOT NULL,
    from_agent_id BIGINT UNSIGNED NULL,
    to_agent_id BIGINT UNSIGNED NOT NULL,
    changed_by_id BIGINT UNSIGNED NOT NULL,
    reason VARCHAR(255) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    KEY idx_assignment_history_request_id (request_id),
    KEY idx_assignment_history_from_agent_id (from_agent_id),
    KEY idx_assignment_history_to_agent_id (to_agent_id),
    KEY idx_assignment_history_changed_by_id (changed_by_id),
    CONSTRAINT fk_assignment_history_request
        FOREIGN KEY (request_id) REFERENCES requests(id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_assignment_history_from_agent
        FOREIGN KEY (from_agent_id) REFERENCES users(id)
        ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT fk_assignment_history_to_agent
        FOREIGN KEY (to_agent_id) REFERENCES users(id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_assignment_history_changed_by
        FOREIGN KEY (changed_by_id) REFERENCES users(id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- SEED DATA
-- =====================================================
INSERT INTO users (employee_code, full_name, email, password_hash, role)
VALUES
    ('EMP-1001', 'Alice Johnson', 'alice.johnson@company.com', 'temporary_hash_1', 'EMPLOYEE'),
    ('IT-2001', 'Bob Smith', 'bob.smith@company.com', 'temporary_hash_2', 'IT_AGENT'),
    ('MGR-3001', 'Carol White', 'carol.white@company.com', 'temporary_hash_3', 'MANAGER'),
    ('ADM-4001', 'David Brown', 'david.brown@company.com', 'temporary_hash_4', 'ADMIN')
ON DUPLICATE KEY UPDATE full_name = VALUES(full_name), email = VALUES(email);

INSERT INTO categories (name, description)
VALUES
    ('Hardware', 'Laptop, desktop, printer, and peripheral issues'),
    ('Software', 'Application install, patching, and configuration tickets'),
    ('Network', 'Wi-Fi, VPN, LAN, and connectivity problems'),
    ('Access', 'Passwords, permissions, and account access issues'),
    ('Email', 'Outlook, mail routing, and mailbox assistance'),
    ('Other', 'General IT requests and miscellaneous issues')
ON DUPLICATE KEY UPDATE description = VALUES(description);

INSERT INTO priorities (name, sla_hours, description)
VALUES
    ('LOW', 48, 'Minor issue or general inquiry'),
    ('MEDIUM', 24, 'Moderate operational impact'),
    ('HIGH', 8, 'Significant impact on business operations'),
    ('CRITICAL', 4, 'Severe disruption requiring immediate support')
ON DUPLICATE KEY UPDATE sla_hours = VALUES(sla_hours), description = VALUES(description);

INSERT INTO statuses (name, description)
VALUES
    ('NEW', 'Ticket created and awaiting assessment'),
    ('ASSIGNED', 'Assigned to an IT agent'),
    ('IN_PROGRESS', 'Work is actively underway'),
    ('PENDING', 'Waiting on user, vendor, or dependency'),
    ('RESOLVED', 'Issue has been fixed and awaiting confirmation'),
    ('CLOSED', 'Ticket completed and closed')
ON DUPLICATE KEY UPDATE description = VALUES(description);

INSERT INTO sla_policies (name, response_time_hours, resolution_time_hours, description)
VALUES
    ('Standard', 4, 24, 'Default SLA for routine business requests'),
    ('Priority', 2, 8, 'Faster SLA for high-impact incidents'),
    ('Critical', 1, 4, 'Emergency SLA for severe service disruptions')
ON DUPLICATE KEY UPDATE response_time_hours = VALUES(response_time_hours), resolution_time_hours = VALUES(resolution_time_hours);

INSERT INTO requests (
    requester_id,
    assigned_agent_id,
    category_id,
    priority_id,
    status_id,
    sla_policy_id,
    subject,
    description,
    due_at
)
VALUES
    (
        1,
        2,
        1,
        4,
        1,
        3,
        'Laptop battery drains too quickly',
        'The employee laptop battery is dropping rapidly during regular office use.',
        DATE_ADD(CURRENT_TIMESTAMP(6), INTERVAL 4 HOUR)
    )
ON DUPLICATE KEY UPDATE subject = VALUES(subject), description = VALUES(description);

INSERT INTO comments (request_id, author_id, message)
VALUES
    (1, 1, 'The battery issue began after the latest system update.'),
    (1, 2, 'I will check the battery health and power settings.');

INSERT INTO request_history (request_id, changed_by_id, field_name, old_value, new_value)
VALUES
    (1, 1, 'status', 'NEW', 'ASSIGNED');

INSERT INTO status_history (request_id, from_status_id, to_status_id, changed_by_id, notes)
VALUES
    (1, 1, 2, 2, 'Assigned to IT agent for troubleshooting');

INSERT INTO assignment_history (request_id, from_agent_id, to_agent_id, changed_by_id, reason)
VALUES
    (1, NULL, 2, 3, 'Initial assignment to the IT support queue');


