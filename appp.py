from flask import Flask, redirect, url_for, request, render_template, g, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE = 'user.db'
SECRET_KEY = 'your_secret_key'

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if cursor.fetchone() is None:
            with app.open_resource('schema.sql', mode='r') as f:
                db.cursor().executescript(f.read())
            db.commit()
        
        # Check if the tasks table exists, if not, create it
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
        if cursor.fetchone() is None:
            cursor.execute('''
                CREATE TABLE tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT,
                    due_date DATE,
                    status TEXT,
                    user_id INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')
            db.commit()

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def email_exists(email):
    db = get_db()
    cur = db.execute('SELECT * FROM users WHERE email = ?', (email,))
    return cur.fetchone() is not None

def username_exists(username):
    db = get_db()
    cur = db.execute('SELECT * FROM users WHERE username = ?', (username,))
    return cur.fetchone() is not None

@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if not email or not password:
            flash('Email and password are required.')
            return redirect(url_for('login'))
        
        db = get_db()
        cur = db.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = cur.fetchone()
        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.')
        return redirect(url_for('login'))
    else:
        return render_template('login.html')

@app.route('/signup', methods=['POST', 'GET'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if not username or not email or not password:
            flash('All fields are required.')
            return redirect(url_for('signup'))
        if email_exists(email):
            flash('Email already exists. Please use a different email.')
            return redirect(url_for('signup'))
        if username_exists(username):
            flash('Username already exists. Please choose a different username.')
            return redirect(url_for('signup'))

        db = get_db()
        hashed_password = generate_password_hash(password)
        db.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, hashed_password))
        db.commit()
        session['user_id'] = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()[0]
        return redirect(url_for('dashboard'))
    else:
        return render_template('signup.html')
    
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/dashboard', methods=['GET'])
def dashboard():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    
    db = get_db()
    cur = db.execute('SELECT username FROM users WHERE id = ?', (user_id,))
    user = cur.fetchone()
    
    if user:
        # Check if the user has a task assigned
        cur = db.execute('SELECT * FROM tasks WHERE user_id = ?', (user_id,))
        tasks = cur.fetchall()
        if not tasks:  # If no tasks are assigned to the user, create a default task
            db.execute('INSERT INTO tasks (name, description, due_date, status, user_id) VALUES (?, ?, ?, ?, ?)',
                       ('Default Task', 'This is a default task', '2024-05-23', 'Pending', user_id))
            db.commit()
            # Fetch the tasks again
            cur = db.execute('SELECT * FROM tasks WHERE user_id = ?', (user_id,))
            tasks = cur.fetchall()
        return render_template('dashboard.html', user=user[0], tasks=tasks)
    return redirect(url_for('login'))

@app.route('/add_task', methods=['POST'])
def add_task():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    name = request.form['name']
    description = request.form['description']
    due_date_day = request.form['due-date-day']
    due_date_month = request.form['due-date-month']
    due_date_year = request.form['due-date-year']

    due_date = f"{due_date_year}-{due_date_month.zfill(2)}-{due_date_day.zfill(2)}"

    db = get_db()
    try:
        db.execute('INSERT INTO tasks (name, description, due_date, user_id) VALUES (?, ?, ?, ?)',
                   (name, description, due_date, session['user_id']))
        db.commit()
        flash('Task Added Successfully')
    except Exception as e:
        flash('An error occurred while adding the task.')

    return redirect(url_for('dashboard'))

@app.route('/delete_task/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))

    db = get_db()
    db.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    db.commit()
    
    return redirect(url_for('dashboard'))

@app.route("/")
def hello():
    message = "Hello, World"
    return render_template('index.html', message=message)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
