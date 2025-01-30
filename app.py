from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
import os

app = Flask(__name__)

# MySQL configuration
app.config['MYSQL_HOST'] = 'host.docker.internal'
app.config['MYSQL_USER'] = 'Fatna'  # your MySQL username
app.config['MYSQL_PASSWORD'] = 'Parkminju123'  # your MySQL password
app.config['MYSQL_DB'] = 'to_do_list'  # your MySQL database name

SQLALCHEMY_DATABASE_URI = "mysql+pymysql://Fatna:Parkminju123@host.docker.internal/to_do_list"
SQLALCHEMY_TRACK_MODIFICATIONS = False


# Initialize MySQL connection
db = mysql.connector.connect(
    host=app.config['MYSQL_HOST'],
    user=app.config['MYSQL_USER'],
    password=app.config['MYSQL_PASSWORD'],
    database=app.config['MYSQL_DB']
)
cursor = db.cursor()

# Ensure templates directory exists
app.template_folder = os.path.join(os.path.dirname(__file__), 'templates')
os.makedirs(app.template_folder, exist_ok=True)

# Configure session
app.secret_key = 'your_secret_key'  # Change this to a secure key

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
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user_exists = cursor.fetchone()
            if user_exists:
                flash('Email already in use. Please choose another one.', 'danger')
            else:
                cursor.execute(
                    "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                    (username, email, password)
                )
                db.commit()
                flash('Registration successful. Please login.', 'success')
                return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
        user = cursor.fetchone()
        
        if user:
            session['user_id'] = user[0]  # Store the user's ID in the session
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

        # Fetch active tasks
        cursor.execute(
            "SELECT id, title, due_date, priority, category, completed FROM tasks WHERE user_id = %s AND is_deleted = FALSE",
            (user_id,)
        )
        tasks_data = cursor.fetchall()
        tasks = [
            {'id': task[0], 'title': task[1], 'due_date': task[2], 'priority': task[3], 'category': task[4], 'completed': task[5]}
            for task in tasks_data
        ]

        # Fetch deleted tasks
        cursor.execute(
            "SELECT id, title FROM tasks WHERE user_id = %s AND is_deleted = TRUE",
            (user_id,)
        )
        deleted_tasks_data = cursor.fetchall()
        deleted_tasks = [{'id': task[0], 'title': task[1]} for task in deleted_tasks_data]

        return render_template('tasks.html', tasks=tasks, deleted_tasks=deleted_tasks)

    return redirect(url_for('login'))


@app.route('/add', methods=['POST'])
def add_task():
    if 'user_id' in session:
        user_id = session['user_id']
        title = request.form.get('title')
        due_date = request.form.get('due_date')
        priority = request.form.get('priority')
        category = request.form.get('category')

        if title and due_date:
            cursor.execute(
                "INSERT INTO tasks (title, due_date, priority, category, completed, user_id) VALUES (%s, %s, %s, %s, %s, %s)",
                (title, due_date, priority, category, False, user_id)
            )
            db.commit()
            # Fetch the newly added task
            cursor.execute("SELECT * FROM tasks WHERE id = LAST_INSERT_ID()")
            new_task = cursor.fetchone()
            task = {
                'id': new_task[0],
                'title': new_task[1],
                'due_date': new_task[2],
                'priority': new_task[3],
                'category': new_task[4],
                'completed': new_task[5]
            }
            return jsonify({'status': 'success', 'task': task})
        else:
            return jsonify({'status': 'error', 'message': 'Please fill in all the fields'})
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
        # Get the task's title before deleting
        cursor.execute("SELECT title FROM tasks WHERE id = %s", (task_id,))
        task = cursor.fetchone()
        
        if task:
            cursor.execute("UPDATE tasks SET is_deleted = TRUE WHERE id = %s", (task_id,))
            db.commit()
            
            return jsonify({'status': 'success', 'task_id': task_id, 'task': {'title': task[0]}})
    
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
