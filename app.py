from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import pymysql
import mysql.connector
import os
from google.cloud import secretmanager
from flask_sqlalchemy import SQLAlchemy
from models import db, User, Task
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)

# Function to fetch secrets from Google Secret Manager
def get_secret(secret_name):
    client = secretmanager.SecretManagerServiceClient()
    project_id = "to-do-list-flask-449601"
    name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(name=name)
    return response.payload.data.decode("UTF-8")

# Load secrets securely
app.config['MYSQL_USER'] = get_secret('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = get_secret('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = get_secret('MYSQL_DB')
app.config['INSTANCE_CONNECTION_NAME'] = os.getenv('INSTANCE_CONNECTION_NAME')

# Construct Database URI for SQLAlchemy
if app.config['INSTANCE_CONNECTION_NAME']:
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f"mysql+pymysql://{app.config['MYSQL_USER']}:{app.config['MYSQL_PASSWORD']}@"
        f"/{app.config['MYSQL_DB']}?unix_socket=/cloudsql/{app.config['INSTANCE_CONNECTION_NAME']}"
    )
else:
    app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f"mysql+pymysql://{app.config['MYSQL_USER']}:{app.config['MYSQL_PASSWORD']}@"
        f"{app.config['MYSQL_HOST']}/{app.config['MYSQL_DB']}?charset=utf8mb4"
    )

# Initialize SQLAlchemy
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your_default_secret_key')  # Secure Flask sessions

db = SQLAlchemy(app)

# Ensure templates directory exists
app.template_folder = os.path.join(os.path.dirname(__file__), 'templates')

cursor = db.cursor()

@app.route('/')
def home():
    if 'user_id' in session:
        user_id = session['user_id']
        cursor.execute("SELECT * FROM tasks WHERE user_id = %s", (user_id,))
        tasks_data = cursor.fetchall()
        tasks = [{'id': task[0], 'title': task[1], 'due_date': task[2], 'priority': task[3], 'category': task[4], 'completed': task[5]} for task in tasks_data]
        
        # Fetch the username for the greeting message
        cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        username = user[0] if user else 'User'
        
        return render_template('index.html', tasks=tasks, username=username)
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if username and email and password:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('Email already in use. Please choose another one.', 'danger')
            else:
                new_user = User(username=username, email=email)
                new_user.set_password(password)  # Hash password
                db.session.add(new_user)
                db.session.commit()
                flash('Registration successful. Please login.', 'success')
                return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):  # Secure password check
            session['user_id'] = user.id
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials, please try again.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route('/tasks', methods=['GET'])
def get_tasks():
    if 'user_id' in session:
        user_id = session['user_id']
        tasks = Task.query.filter_by(user_id=user_id, is_deleted=False).all()
        deleted_tasks = Task.query.filter_by(user_id=user_id, is_deleted=True).all()

        return render_template('tasks.html', tasks=tasks, deleted_tasks=deleted_tasks)
    return redirect(url_for('login'))


@app.route('/add', methods=['POST'])
def add_task():
    if 'user_id' in session:
        title = request.form.get('title')
        due_date = request.form.get('due_date')
        priority = request.form.get('priority')
        category = request.form.get('category')

        if title and due_date:
            new_task = Task(
                title=title,
                due_date=due_date,
                priority=priority,
                category=category,
                completed=False,
                user_id=session['user_id']
            )
            db.session.add(new_task)
            db.session.commit()

            return jsonify({'status': 'success', 'task': {'id': new_task.id, 'title': new_task.title}})
    return jsonify({'status': 'error', 'message': 'Unauthorized'})

@app.route('/complete/<int:task_id>', methods=['POST'])
def complete_task(task_id):
    if 'user_id' in session:
        cursor.execute("UPDATE tasks SET completed = NOT completed WHERE id = %s", (task_id,))
        db.commit()
        # Fetch the updated task
        cursor.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
        updated_task = cursor.fetchone()
        task = {
            'id': updated_task[0],
            'title': updated_task[1],
            'due_date': updated_task[2],
            'priority': updated_task[3],
            'category': updated_task[4],
            'completed': updated_task[5]
        }
        return jsonify({'status': 'success', 'task': task})
    return jsonify({'status': 'error', 'message': 'Unauthorized'})

@app.route('/delete/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    if 'user_id' in session:
        task = Task.query.filter_by(id=task_id, user_id=session['user_id']).first()
        if task:
            task.is_deleted = True
            db.session.commit()
            return jsonify({'status': 'success', 'task_id': task_id})
    return jsonify({'status': 'error', 'message': 'Unauthorized'})

@app.route('/readd/<int:task_id>', methods=['POST'])
def readd_task(task_id):
    if 'user_id' in session:
        cursor.execute("UPDATE tasks SET is_deleted = FALSE WHERE id = %s", (task_id,))
        db.commit()

        # Fetch the restored task details
        cursor.execute("SELECT id, title, due_date, priority, category, completed FROM tasks WHERE id = %s", (task_id,))
        task = cursor.fetchone()
        if task:
            return jsonify({
                'status': 'success',
                'task': {
                    'id': task[0],
                    'title': task[1],
                    'due_date': task[2],
                    'priority': task[3],
                    'category': task[4],
                    'completed': task[5]
                }
            })
    return jsonify({'status': 'error', 'message': 'Unauthorized'})

@app.route('/activity')
def activity():
    if 'user_id' in session:
        user_id = session['user_id']
        cursor.execute("SELECT * FROM tasks WHERE user_id = %s", (user_id,))
        tasks_data = cursor.fetchall()
        
        tasks = [{'id': task[0], 'title': task[1], 'due_date': task[2], 'priority': task[3], 'category': task[4], 'completed': task[5]} for task in tasks_data]
        
        completed_tasks = len([task for task in tasks if task['completed']])
        total_tasks = len(tasks)
        
        # Pass 'tasks' to the template
        return render_template(
            'activity.html', 
            tasks=tasks,  # Pass tasks here
            completed_tasks=completed_tasks, 
            total_tasks=total_tasks
        )
    return redirect(url_for('login'))

@app.route('/pomodoro')
def pomodoro():
    if 'user_id' in session:
        return render_template('pomodoro.html')
    flash('Please login to access the Pomodoro feature.', 'warning')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
