import os
import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
import sqlite3

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_session' # จำเป็นสำหรับ Flash messages
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # จำกัดไฟล์ไม่เกิน 16MB

# สร้างโฟลเดอร์เก็บไฟล์ถ้ายังไม่มี
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ฟังก์ชันเชื่อมต่อ Database
def get_db_connection():
    conn = sqlite3.connect('project_data.db')
    conn.row_factory = sqlite3.Row
    return conn

# ฟังก์ชันสร้างตาราง Database เมื่อเริ่มระบบครั้งแรก
def init_db():
    conn = get_db_connection()
    # ตารางเก็บข้อมูลโปรเจค
    conn.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            owner1 TEXT NOT NULL,
            owner2 TEXT,
            level TEXT NOT NULL,
            details TEXT,
            year TEXT NOT NULL,
            file_report TEXT,
            file_manual TEXT,
            file_code TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # ตารางเก็บประวัติ (Log)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL, -- ADD, EDIT, DELETE
            project_name TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# เรียกใช้ฟังก์ชันสร้าง Database
init_db()

# --- Routes ---

@app.route('/')
def index():
    conn = get_db_connection()
    # ดึงประวัติ 5 รายการล่าสุด
    recent_history = conn.execute('SELECT * FROM history ORDER BY id DESC LIMIT 5').fetchall()
    conn.close()
    return render_template('index.html', recent_history=recent_history, page='home')

@app.route('/projects')
def projects():
    conn = get_db_connection()
    projects = conn.execute('SELECT * FROM projects ORDER BY year DESC, id DESC').fetchall()
    conn.close()
    
    # จัดกลุ่มโปรเจคตามปีการศึกษา
    projects_by_year = {}
    for p in projects:
        year = p['year']
        if year not in projects_by_year:
            projects_by_year[year] = []
        projects_by_year[year].append(p)
        
    return render_template('projects.html', projects_by_year=projects_by_year, page='projects')

@app.route('/history')
def history():
    conn = get_db_connection()
    all_history = conn.execute('SELECT * FROM history ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('history.html', history=all_history, page='history')

# --- API / Action Routes ---

@app.route('/add_project', methods=['POST'])
def add_project():
    if request.method == 'POST':
        name = request.form['name']
        owner1 = request.form['owner1']
        owner2 = request.form['owner2'] or '-'
        level = request.form['level']
        details = request.form['details']
        
        # จัดการปีการศึกษา
        year_select = request.form['year_select']
        if year_select == 'other':
            year = request.form['year_custom']
        else:
            year = year_select

        # จัดการไฟล์
        def save_file(file_obj):
            if file_obj and file_obj.filename != '':
                filename = secure_filename(file_obj.filename)
                # เติม Timestamp หน้าชื่อไฟล์กันชื่อซ้ำ
                filename = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                file_obj.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                return filename
            return None

        file_report = save_file(request.files.get('file_report'))
        file_manual = save_file(request.files.get('file_manual'))
        
        # สำหรับไฟล์ Code อาจจะเป็น Link GitHub หรือ File ก็ได้ (ในฟอร์มเป็น File แต่ถ้าอยากประยุกต์รับ Link ก็แก้ได้)
        file_code = save_file(request.files.get('file_code'))

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO projects (name, owner1, owner2, level, details, year, file_report, file_manual, file_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, owner1, owner2, level, details, year, file_report, file_manual, file_code))
        
        # บันทึกประวัติ
        conn.execute('INSERT INTO history (action, project_name) VALUES (?, ?)', ('เพิ่มข้อมูล', name))
        conn.commit()
        conn.close()

        # ส่งสัญญาณกลับไปบอก Frontend (ถ้าใช้ AJAX) หรือ Redirect
        # ในที่นี้ใช้ Redirect ปกติแต่จะมี Script ในหน้าเว็บแสดง Popup
        flash('บันทึกสำเร็จ', 'success')
        return redirect(url_for('index'))

@app.route('/edit_project/<int:id>', methods=['POST'])
def edit_project(id):
    conn = get_db_connection()
    # รับค่าเดิมมาก่อน
    # (ในตัวอย่างนี้เพื่อความกระชับ จะทำการ Update ข้อมูลหลักๆ)
    name = request.form['name']
    owner1 = request.form['owner1']
    # ... รับค่าอื่นๆ เหมือนตอน Add ...
    # หมายเหตุ: การเขียน Edit แบบสมบูรณ์ต้องเช็คไฟล์ใหม่ด้วย ถ้าไม่มีใช้ไฟล์เดิม
    # เพื่อความง่ายของโค้ดตัวอย่าง จะขอข้ามส่วน Update File ไปเน้นที่ Text Data
    
    conn.execute('UPDATE projects SET name = ?, owner1 = ? WHERE id = ?', (name, owner1, id))
    conn.execute('INSERT INTO history (action, project_name) VALUES (?, ?)', ('แก้ไขข้อมูล', name))
    conn.commit()
    conn.close()
    
    flash('แก้ไขข้อมูลสำเร็จ', 'success')
    return redirect(url_for('projects'))

@app.route('/delete_project/<int:id>', methods=['POST'])
def delete_project(id):
    conn = get_db_connection()
    project = conn.execute('SELECT * FROM projects WHERE id = ?', (id,)).fetchone()
    if project:
        conn.execute('DELETE FROM projects WHERE id = ?', (id,))
        conn.execute('INSERT INTO history (action, project_name) VALUES (?, ?)', ('ลบข้อมูล', project['name']))
        conn.commit()
    conn.close()
    flash('ลบข้อมูลสำเร็จ', 'success')
    return redirect(url_for('projects'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)