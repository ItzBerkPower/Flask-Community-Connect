# ALL IMPORTS
import sqlite3
import os
from flask import Flask

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

    # Add skills into skill table, 'INSERT OR IGNORE' is like 'CREATE IF NOT EXISTS'
    cursor.executemany('''
    INSERT OR IGNORE INTO skill (name, description) VALUES (?, ?)
    ''', [
        ("Endurance", "Ability to sustain effort for long periods"),
        ("Listening", "Good at understanding and following others"),
        ("Talkative", "Engages easily in conversation"),
        ("Public Speaking", "Confident in speaking to groups")
    ])

    conn.commit()
    #conn.close(), don't need as in 'with' command, which is pythonic way of automatically closing website
