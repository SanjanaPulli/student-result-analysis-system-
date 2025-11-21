from flask import Flask, render_template, request, redirect, session, flash, jsonify
from flask_mysqldb import MySQL
from collections import defaultdict
import MySQLdb.cursors
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import numpy as np
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'student_result_db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

mysql = MySQL(app)

# ==========================================
# GRADING SYSTEMS
# ==========================================

def calculate_absolute_grade(marks):
    """Absolute grading based on fixed thresholds"""
    try:
        marks = float(marks)
        if marks == -1:
            return 'AB', 0
        elif marks < 0 or marks > 100:
            return 'Invalid', 0
        elif marks >= 90:
            return 'S', 10
        elif marks >= 80:
            return 'A', 9
        elif marks >= 70:
            return 'B', 8
        elif marks >= 60:
            return 'C', 7
        elif marks >= 50:
            return 'D', 6
        elif marks >= 40:
            return 'E', 5
        else:
            return 'F', 0
    except:
        return 'Invalid', 0

def calculate_relative_grade(marks_list, marks):
    """
    Relative grading using percentile method
    Top 10% -> S, Next 15% -> A, Next 25% -> B, Next 25% -> C, Next 15% -> D, Next 10% -> E, Rest -> F
    """
    try:
        marks = float(marks)
        if marks == -1:
            return 'AB', 0
        
        # Filter valid marks (exclude absent)
        valid_marks = [m for m in marks_list if m >= 0]
        if not valid_marks:
            return calculate_absolute_grade(marks)
        
        # Calculate percentile
        percentile = (sum(m < marks for m in valid_marks) / len(valid_marks)) * 100
        
        # Assign grade based on percentile
        if percentile >= 90:
            return 'S', 10
        elif percentile >= 75:
            return 'A', 9
        elif percentile >= 50:
            return 'B', 8
        elif percentile >= 25:
            return 'C', 7
        elif percentile >= 10:
            return 'D', 6
        elif percentile >= 5:
            return 'E', 5
        else:
            return 'F', 0
    except:
        return 'Invalid', 0

def apply_relative_grading(semester, subject):
    """Apply relative grading to all students in a semester-subject combination"""
    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Get all marks for this semester-subject
        cur.execute("""
            SELECT id, marks FROM students 
            WHERE semester = %s AND subject = %s AND marks >= 0
        """, (semester, subject))
        
        records = cur.fetchall()
        if not records:
            return 0
        
        marks_list = [r['marks'] for r in records]
        
        # Update grades for each student
        updated = 0
        for record in records:
            grade, grade_point = calculate_relative_grade(marks_list, record['marks'])
            cur.execute("""
                UPDATE students 
                SET grade = %s, grade_point = %s 
                WHERE id = %s
            """, (grade, grade_point, record['id']))
            updated += 1
        
        mysql.connection.commit()
        cur.close()
        return updated
    except Exception as e:
        print(f"Error in relative grading: {e}")
        return 0

# Admin required decorator
def admin_required(f):
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            flash('Unauthorized access! Admin privileges required.', 'error')
            return redirect('/login')
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# ==========================================
# ROUTES
# ==========================================

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Please provide both username and password', 'error')
            return render_template('login.html')

        try:
            cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cur.execute("SELECT * FROM users WHERE username=%s", (username,))
            user = cur.fetchone()
            cur.close()

            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                flash(f'Welcome back, {username}!', 'success')
                return redirect('/dashboard' if user['role'] == 'admin' else '/results')
            else:
                flash('Invalid username or password', 'error')
        except Exception as e:
            flash(f'Login error: {str(e)}', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    username = session.get('username', 'User')
    session.clear()
    flash(f'Goodbye, {username}!', 'info')
    return redirect('/login')

@app.route('/add_student', methods=['GET', 'POST'])
@admin_required
def add_student():
    if request.method == 'POST':
        try:
            roll_number = request.form.get('roll_number', '').strip()
            name = request.form.get('name', '').strip()
            semester = request.form.get('semester', '').strip()
            subject = request.form.get('subject', '').strip()
            marks = request.form.get('marks', '').strip()
            branch = request.form.get('branch', '').strip()  # NEW: Branch field
            grading_type = request.form.get('grading_type', 'absolute')  # NEW

            if not all([roll_number, name, semester, subject, marks, branch]):
                flash('All fields are required!', 'error')
                return render_template('add_student.html')

            marks = float(marks)
            if marks < -1 or marks > 100:
                flash('Marks must be between 0 and 100 (or -1 for absent)', 'error')
                return render_template('add_student.html')

            # Calculate grade based on selected method
            if grading_type == 'relative':
                # Get existing marks for relative grading
                cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                cur.execute("""
                    SELECT marks FROM students 
                    WHERE semester = %s AND subject = %s AND marks >= 0
                """, (semester, subject))
                existing_marks = [r['marks'] for r in cur.fetchall()]
                existing_marks.append(marks)
                grade, grade_point = calculate_relative_grade(existing_marks, marks)
                cur.close()
            else:
                grade, grade_point = calculate_absolute_grade(marks)

            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO students (roll_number, name, semester, subject, marks, grade, grade_point, branch)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (roll_number, name, semester, subject, marks, grade, grade_point, branch))
            mysql.connection.commit()
            cur.close()

            flash(f'Student record for {name} added successfully!', 'success')
            return redirect('/dashboard')
        except Exception as e:
            flash(f'Error adding student: {str(e)}', 'error')

    return render_template('add_student.html')

@app.route('/upload_results', methods=['GET', 'POST'])
@admin_required
def upload_results():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file uploaded!', 'error')
            return redirect('/upload_results')

        file = request.files['file']
        grading_type = request.form.get('grading_type', 'absolute')
        
        if file.filename == '':
            flash('No file selected!', 'error')
            return redirect('/upload_results')

        if not (file.filename.endswith('.csv') or file.filename.endswith(('.xlsx', '.xls'))):
            flash('Only CSV and Excel files are allowed!', 'error')
            return redirect('/upload_results')

        try:
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)

            if file.filename.endswith('.csv'):
                df = pd.read_csv(filepath)
            else:
                df = pd.read_excel(filepath)

            required_columns = ['Roll Number', 'Name', 'Semester', 'Subject', 'Marks', 'Branch']
            if not all(col in df.columns for col in required_columns):
                flash(f'Invalid file format! Required columns: {", ".join(required_columns)}', 'error')
                os.remove(filepath)
                return redirect('/upload_results')

            cur = mysql.connection.cursor()
            success_count = 0
            error_count = 0

            # Group by semester and subject for relative grading
            if grading_type == 'relative':
                grouped = df.groupby(['Semester', 'Subject'])
                for (sem, subj), group in grouped:
                    marks_list = group['Marks'].tolist()
                    for idx, row in group.iterrows():
                        try:
                            roll = str(row['Roll Number']).strip()
                            name = str(row['Name']).strip()
                            marks = float(row['Marks'])
                            branch = str(row['Branch']).strip()

                            if marks < -1 or marks > 100:
                                error_count += 1
                                continue

                            grade, grade_point = calculate_relative_grade(marks_list, marks)
                            
                            cur.execute("""
                                INSERT INTO students (roll_number, name, semester, subject, marks, grade, grade_point, branch)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """, (roll, name, sem, subj, marks, grade, grade_point, branch))
                            success_count += 1
                        except Exception as e:
                            error_count += 1
                            print(f"Error on row {idx}: {str(e)}")
            else:
                # Absolute grading
                for idx, row in df.iterrows():
                    try:
                        roll = str(row['Roll Number']).strip()
                        name = str(row['Name']).strip()
                        sem = str(row['Semester']).strip()
                        subj = str(row['Subject']).strip()
                        marks = float(row['Marks'])
                        branch = str(row['Branch']).strip()

                        if marks < -1 or marks > 100:
                            error_count += 1
                            continue

                        grade, grade_point = calculate_absolute_grade(marks)
                        
                        cur.execute("""
                            INSERT INTO students (roll_number, name, semester, subject, marks, grade, grade_point, branch)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (roll, name, sem, subj, marks, grade, grade_point, branch))
                        success_count += 1
                    except Exception as e:
                        error_count += 1
                        print(f"Error on row {idx}: {str(e)}")

            mysql.connection.commit()
            cur.close()
            os.remove(filepath)

            flash(f'Upload complete! {success_count} records added, {error_count} errors.', 'success')
            return redirect('/dashboard')

        except Exception as e:
            flash(f'Error processing file: {str(e)}', 'error')

    return render_template('upload_results.html')

@app.route('/results')
def show_results():
    if 'user_id' not in session:
        flash('Please login to view results', 'error')
        return redirect('/login')

    try:
        # Get filter parameters
        semester_filter = request.args.get('semester', '')
        subject_filter = request.args.get('subject', '')
        branch_filter = request.args.get('branch', '')
        
        # Base query
        query = """
            SELECT roll_number, name, semester, subject, marks, grade, grade_point, branch 
            FROM students 
            WHERE 1=1
        """
        params = []
        
        # Add filters
        if semester_filter:
            query += " AND semester = %s"
            params.append(semester_filter)
        if subject_filter:
            query += " AND subject = %s"
            params.append(subject_filter)
        if branch_filter:
            query += " AND branch = %s"
            params.append(branch_filter)
        
        query += " ORDER BY semester, branch, roll_number, subject"
        
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute(query, params)
        data = cur.fetchall()
        
        # Get unique values for filters
        cur.execute("SELECT DISTINCT semester FROM students ORDER BY semester")
        semesters = [r['semester'] for r in cur.fetchall()]
        
        cur.execute("SELECT DISTINCT subject FROM students ORDER BY subject")
        subjects = [r['subject'] for r in cur.fetchall()]
        
        cur.execute("SELECT DISTINCT branch FROM students ORDER BY branch")
        branches = [r['branch'] for r in cur.fetchall()]
        
        cur.close()
        
        return render_template('results.html', 
                             data=data,
                             semesters=semesters,
                             subjects=subjects,
                             branches=branches,
                             current_semester=semester_filter,
                             current_subject=subject_filter,
                             current_branch=branch_filter)
    except Exception as e:
        flash(f'Error loading results: {str(e)}', 'error')
        return redirect('/dashboard')

@app.route('/dashboard')
@admin_required
def dashboard():
    try:
        # Get filter parameters
        semester_filter = request.args.get('semester', '')
        branch_filter = request.args.get('branch', '')
        
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Base query with filters
        filter_query = "WHERE 1=1"
        params = []
        if semester_filter:
            filter_query += " AND semester = %s"
            params.append(semester_filter)
        if branch_filter:
            filter_query += " AND branch = %s"
            params.append(branch_filter)
        
        # Get all student records
        cur.execute(f"""
            SELECT roll_number, name, semester, subject, marks, grade, grade_point, branch 
            FROM students 
            {filter_query}
            ORDER BY semester, branch, name
        """, params)
        rows = cur.fetchall()
        
        # Get statistics
        cur.execute(f"SELECT COUNT(DISTINCT roll_number) as total_students FROM students {filter_query}", params)
        stats = cur.fetchone()
        total_students = stats['total_students'] if stats else 0
        
        cur.execute(f"SELECT COUNT(DISTINCT subject) as total_subjects FROM students {filter_query}", params)
        stats = cur.fetchone()
        total_subjects = stats['total_subjects'] if stats else 0
        
        cur.execute(f"SELECT COUNT(DISTINCT semester) as total_semesters FROM students {filter_query}", params)
        stats = cur.fetchone()
        total_semesters = stats['total_semesters'] if stats else 0
        
        # Get filter options
        cur.execute("SELECT DISTINCT semester FROM students ORDER BY semester")
        semesters = [r['semester'] for r in cur.fetchall()]
        
        cur.execute("SELECT DISTINCT branch FROM students ORDER BY branch")
        branches = [r['branch'] for r in cur.fetchall()]
        
        cur.close()

        # Organize data by semester
        semester_data = defaultdict(list)
        for row in rows:
            semester_data[row['semester']].append(row)

        return render_template('dashboard.html', 
                             semester_data=dict(semester_data),
                             total_students=total_students,
                             total_subjects=total_subjects,
                             total_semesters=total_semesters,
                             semesters=semesters,
                             branches=branches,
                             current_semester=semester_filter,
                             current_branch=branch_filter)
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'error')
        return redirect('/login')

@app.route('/api/analytics')
@admin_required
def analytics():
    try:
        # Get filter parameters
        semester_filter = request.args.get('semester', '')
        branch_filter = request.args.get('branch', '')
        
        filter_query = "WHERE grade != 'AB'"
        params = []
        if semester_filter:
            filter_query += " AND semester = %s"
            params.append(semester_filter)
        if branch_filter:
            filter_query += " AND branch = %s"
            params.append(branch_filter)
        
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # Grade distribution
        cur.execute(f"""
            SELECT grade, COUNT(*) as count 
            FROM students 
            {filter_query}
            GROUP BY grade
        """, params)
        grade_dist = cur.fetchall()
        
        # Subject-wise average
        cur.execute(f"""
            SELECT subject, AVG(marks) as avg_marks 
            FROM students 
            WHERE marks >= 0 {' AND semester = %s' if semester_filter else ''} {' AND branch = %s' if branch_filter else ''}
            GROUP BY subject
        """, params)
        subject_avg = cur.fetchall()
        
        # Semester-wise performance
        cur.execute(f"""
            SELECT semester, AVG(marks) as avg_marks, COUNT(*) as total_students
            FROM students 
            WHERE marks >= 0 {' AND branch = %s' if branch_filter else ''}
            GROUP BY semester
        """, [branch_filter] if branch_filter else [])
        semester_perf = cur.fetchall()
        
        cur.close()
        
        return jsonify({
            'grade_distribution': grade_dist,
            'subject_averages': subject_avg,
            'semester_performance': semester_perf
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/apply_relative_grading', methods=['POST'])
@admin_required
def apply_relative_grading_route():
    try:
        semester = request.form.get('semester')
        subject = request.form.get('subject')
        
        if not semester or not subject:
            flash('Semester and subject are required!', 'error')
            return redirect('/dashboard')
        
        updated = apply_relative_grading(semester, subject)
        flash(f'Relative grading applied! {updated} records updated.', 'success')
        return redirect('/dashboard')
    except Exception as e:
        flash(f'Error applying relative grading: {str(e)}', 'error')
        return redirect('/dashboard')

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        try:
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            role = request.form.get('role', 'user')

            if not username or not password:
                flash('Username and password are required!', 'error')
                return render_template('add_user.html')

            if len(password) < 6:
                flash('Password must be at least 6 characters long!', 'error')
                return render_template('add_user.html')

            hashed_password = generate_password_hash(password)

            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO users (username, password, role) 
                VALUES (%s, %s, %s)
            """, (username, hashed_password, role))
            mysql.connection.commit()
            cur.close()

            flash('User registered successfully! Please login.', 'success')
            return redirect('/login')
        except MySQLdb.IntegrityError:
            flash('Username already exists!', 'error')
        except Exception as e:
            flash(f'Error creating user: {str(e)}', 'error')

    return render_template('add_user.html')

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)