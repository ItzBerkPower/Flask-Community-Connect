# app.py
import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import re

# DATABASE = 'database.db', kept creating it in outer file if you run the code in outer directory
base_dir = os.path.abspath(os.path.dirname(__file__)) # So defines the directory
db_path = os.path.join(base_dir, "database.db")

# Flask app
app = Flask(__name__)
app.secret_key = "berkay"  # Secret key (Don't really know why)

# Get DB connection
def get_db():
    conn = sqlite3.connect(db_path) # Create connection between database and flask
    conn.row_factory = sqlite3.Row # Allows fetching rows as dictionaries
    return conn 


# Initialise DB with all tables
def init_db():
    with get_db() as conn:
        cursor = conn.cursor() # Initialising cursor object

        # Creating the 'user' table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            phone_number TEXT,
            role TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ''')

        # Creating the 'volunteer' table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS volunteer (
            volunteer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            availability TEXT,
            FOREIGN KEY (user_id) REFERENCES user(user_id) ON DELETE CASCADE
        );
        ''')

        # Creating the 'organisation' table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS organisation (
            organisation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            address TEXT,
            website_url TEXT,
            FOREIGN KEY (user_id) REFERENCES user(user_id) ON DELETE CASCADE
        );
        ''')

        # Creating the 'event' table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            organisation_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            event_date TIMESTAMP NOT NULL,
            location TEXT,
            max_volunteers INTEGER,
            FOREIGN KEY (organisation_id) REFERENCES organisation(organisation_id) ON DELETE CASCADE
        );
        ''')

        # Creating the 'skills' table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS skill (
            skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        );
        ''')

        # Creating the 'volunteer_event' junction table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS volunteer_event (
            volunteer_id INTEGER NOT NULL,
            event_id INTEGER NOT NULL,
            signup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (volunteer_id, event_id),
            FOREIGN KEY (volunteer_id) REFERENCES volunteer(volunteer_id) ON DELETE CASCADE,
            FOREIGN KEY (event_id) REFERENCES event(event_id) ON DELETE CASCADE
        );
        ''')

        # Creating the 'volunteer_skill' junction table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS volunteer_skill (
            volunteer_id INTEGER NOT NULL,
            skill_id INTEGER NOT NULL,
            volunteer_proficiency_level TEXT,
            PRIMARY KEY (volunteer_id, skill_id),
            FOREIGN KEY (volunteer_id) REFERENCES volunteer(volunteer_id) ON DELETE CASCADE,
            FOREIGN KEY (skill_id) REFERENCES skill(skill_id) ON DELETE CASCADE
        );
        ''')

        # Creating the 'event_skill' junction table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS event_skill (
            event_id INTEGER NOT NULL,
            skill_id INTEGER NOT NULL,
            PRIMARY KEY (event_id, skill_id),
            FOREIGN KEY (event_id) REFERENCES event(event_id) ON DELETE CASCADE,
            FOREIGN KEY (skill_id) REFERENCES skill(skill_id) ON DELETE CASCADE
        );
        ''')

        conn.commit()
        #conn.close(), don't need as in 'with' command, which is pythonic way of automatically closing website



# ROUTES ---------------------

# Default route
@app.route("/")
def index():
    return render_template('index.html') # Render the homepage template


# Route to register the user
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        role = request.form['role']

        conn = get_db()
        cursor = conn.cursor()

        # Insert into user table
        cursor.execute("INSERT INTO user (email, password_hash, role) VALUES (?, ?, ?)",
                       (email, password, role))
        user_id = cursor.lastrowid

        if role == "volunteer":
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            cursor.execute("INSERT INTO volunteer (user_id, first_name, last_name) VALUES (?, ?, ?)",
                           (user_id, first_name, last_name))

        elif role == "organisation":
            org_name = request.form['organisation_name']
            org_desc = request.form['organisation_description']
            org_addr = request.form['organisation_address']
            cursor.execute("INSERT INTO organisation (user_id, name, description, address) VALUES (?, ?, ?, ?)",
                           (user_id, org_name, org_desc, org_addr))

        conn.commit()
        conn.close()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

        


# Route for user to log in
@app.route('/login', methods = ['GET', 'POST'])
def login():
    # Gather email and password from form after submission
    if request.method == 'POST': 
        email = request.form['email']
        password = request.form['password']

        # Try to find user from database
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM user WHERE email = ?', (email,))
            user = cursor.fetchone()

        # If the user row is correct, and the password is correct, update the session to log user in
        if user and check_password_hash(user['password_hash'], password):
            session['loggedin'] = True
            session['user_id'] = user['user_id']
            session["role"] = user["role"]

            return redirect(url_for('index')) # Sends user back to home page
        
        # If wrong details
        else:
            flash('Invalid email or password. Please try again.', 'danger') # Can't find user, send warning message
    
    return render_template('login.html') # Render template


# Route for user to logout
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')

    return redirect(url_for('index'))


# Route to show all volunteers (Only in view of organisation)
@app.route("/volunteers")
def all_volunteers():
    if session.get("role") != "organisation":
        flash("Access denied.")
        return redirect(url_for("index"))
    
    with get_db() as conn:
        volunteers = conn.execute("SELECT * FROM user WHERE role='volunteer'").fetchall()
    
    return render_template("volunteers.html", volunteers=volunteers)

# Route to show all organisations (Only in view of volunteers)
@app.route("/organisations")
def all_organisations():
    if session.get("role") != "volunteer":
        flash("Access denied.")
        return redirect(url_for("index"))
    
    with get_db() as conn:
        organisations = conn.execute("SELECT * FROM user WHERE role='organisation'").fetchall()

    return render_template("organisations.html", organisations=organisations)



# My Account (update details)
@app.route("/myaccount", methods=["GET", "POST"])
def my_account():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    with get_db() as conn:
        cursor = conn.cursor()

        if request.method == "POST":
            new_email = request.form.get("email")
            new_phone = request.form.get("phone_number")
            cursor.execute(
                "UPDATE user SET email=?, phone_number=? WHERE user_id=?",
                (new_email, new_phone, session["user_id"])
            )
            conn.commit()
            flash("Account updated successfully!", "success")
            return redirect(url_for("my_account"))

        user = cursor.execute(
            "SELECT * FROM user WHERE user_id=?", (session["user_id"],)
        ).fetchone()

    return render_template("myaccount.html", user=user)


# Checks if script is run directly (Not imported)
if __name__ == "__main__":
    init_db() # Initialise databse
    app.run(debug=True) # Runs the Flask application with debug mode enabled
