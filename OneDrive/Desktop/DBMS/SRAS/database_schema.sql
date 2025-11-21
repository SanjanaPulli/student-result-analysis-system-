-- Create Database
CREATE DATABASE IF NOT EXISTS student_result_db;
USE student_result_db;

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role ENUM('admin', 'user') DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Students Table (with branch column)
CREATE TABLE IF NOT EXISTS students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    roll_number VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    semester VARCHAR(20) NOT NULL,
    subject VARCHAR(100) NOT NULL,
    marks DECIMAL(5,2) NOT NULL,
    branch VARCHAR(50) NOT NULL DEFAULT 'General',
    grade VARCHAR(10) NOT NULL,
    grade_point DECIMAL(3,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_roll (roll_number),
    INDEX idx_semester (semester),
    INDEX idx_subject (subject),
    INDEX idx_grade (grade),
    INDEX idx_branch (branch)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Insert default admin user (password: admin123)
INSERT INTO users (username, password, role) VALUES 
('admin', 'scrypt:32768:8:1$KvZ8YGxLzMqJYqBP$c3d4c8c7e8b5d6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4', 'admin')
ON DUPLICATE KEY UPDATE username=username;

-- Sample Data with BRANCH column (FIXED!)
INSERT INTO students (roll_number, name, semester, subject, marks, branch, grade, grade_point) VALUES
('CS101', 'John Doe', 'Semester 1', 'Mathematics', 85, 'CSE', 'A', 9),
('CS101', 'John Doe', 'Semester 1', 'Physics', 78, 'CSE', 'B', 8),
('CS101', 'John Doe', 'Semester 1', 'Chemistry', 92, 'CSE', 'S', 10),
('CS102', 'Jane Smith', 'Semester 1', 'Mathematics', 95, 'CSE', 'S', 10),
('CS102', 'Jane Smith', 'Semester 1', 'Physics', 88, 'CSE', 'A', 9),
('CS102', 'Jane Smith', 'Semester 1', 'Chemistry', 76, 'CSE', 'B', 8),
('CS103', 'Mike Johnson', 'Semester 1', 'Mathematics', 65, 'CSE', 'C', 7),
('CS103', 'Mike Johnson', 'Semester 1', 'Physics', 72, 'CSE', 'B', 8),
('CS103', 'Mike Johnson', 'Semester 1', 'Chemistry', 58, 'CSE', 'D', 6),
-- Additional sample data for testing branch-wise grading
('EC101', 'Alice Brown', 'Semester 1', 'Mathematics', 90, 'ECE', 'S', 10),
('EC101', 'Alice Brown', 'Semester 1', 'Physics', 82, 'ECE', 'A', 9),
('EC101', 'Alice Brown', 'Semester 1', 'Chemistry', 78, 'ECE', 'B', 8),
('EC102', 'Bob Wilson', 'Semester 1', 'Mathematics', 75, 'ECE', 'B', 8),
('EC102', 'Bob Wilson', 'Semester 1', 'Physics', 70, 'ECE', 'B', 8),
('EC102', 'Bob Wilson', 'Semester 1', 'Chemistry', 68, 'ECE', 'C', 7);

-- Verify setup
SELECT 'Database setup complete!' AS Status;
SELECT COUNT(*) AS total_students FROM students;
SELECT COUNT(*) AS total_users FROM users;