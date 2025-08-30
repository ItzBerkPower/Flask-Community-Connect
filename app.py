# app.py
import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import re

from models import *


# ROUTES ---------------------

# Default route
@app.route("/")
def index():
    return render_template('index.html') # Render the homepage template


# Route to register the user
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
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
@app.route('/my_account', methods=['GET', 'POST'])
def my_account():

    # Redirect if not logged in
    if 'user_id' not in session:
        flash("You need to log in first.", "warning")
        return redirect(url_for('login'))
    
    conn = get_db()
    cursor = conn.cursor()

    # Get current user info
    cursor.execute("SELECT * FROM user WHERE user_id = ?", (session['user_id'],))
    user = cursor.fetchone()

    volunteer = organisation = None
    if user['role'] == "volunteer":
        cursor.execute("SELECT * FROM volunteer WHERE user_id = ?", (user['user_id'],))
        volunteer = cursor.fetchone()
    elif user['role'] == "organisation":
        cursor.execute("SELECT * FROM organisation WHERE user_id = ?", (user['user_id'],))
        organisation = cursor.fetchone()

    if request.method == "POST":
        email = request.form['email']
        phone_number = request.form['phone_number']
        new_password = request.form['password']

        # Update shared user info
        if new_password:
            password_hash = generate_password_hash(new_password)
            cursor.execute("UPDATE user SET email = ?, phone_number = ?, password_hash = ? WHERE user_id = ?",
                           (email, phone_number, password_hash, user['user_id']))
        else:
            cursor.execute("UPDATE user SET email = ?, phone_number = ? WHERE user_id = ?",
                           (email, phone_number, user['user_id']))

        # Update volunteer-specific info
        if user['role'] == "volunteer":
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            availability = request.form['availability']
            cursor.execute("""UPDATE volunteer 
                              SET first_name = ?, 
                                  last_name = ?, 
                                  availability = ?
                              WHERE user_id = ?""",
                           (first_name, last_name, availability, user['user_id']))

        # Update organisation-specific info
        elif user['role'] == "organisation":
            name = request.form['organisation_name']
            address = request.form['organisation_address']
            website = request.form['organisation_website']
            description = request.form['organisation_description']
            cursor.execute("""UPDATE organisation 
                              SET name = ?, 
                                  address = ?, 
                                  website_url = ?, 
                                  description = ?
                              WHERE user_id = ?""",
                           (name, address, website, description, user['user_id']))

        conn.commit()
        flash("Account updated successfully!", "success")
        return redirect(url_for('my_account'))

    conn.close()
    return render_template("my_account.html", user=user, volunteer=volunteer, organisation=organisation)

# Route to create events
@app.route("/create_event", methods=["GET", "POST"])
def create_event():
    if 'user_id' not in session or session.get('role') != 'organisation':
        flash("Only organisations can create events.", "danger")
        return redirect(url_for('events'))

    conn = get_db()
    cursor = conn.cursor()

    # Always fetch available skills for form
    cursor.execute("SELECT * FROM skill")
    skills = cursor.fetchall()

    if request.method == "POST":
        title = request.form['title']
        description = request.form['description']
        event_date = request.form['event_date']
        location = request.form['location']
        max_volunteers = request.form['max_volunteers']
        selected_skills = request.form.getlist('skills')

        # Get organisation_id for current user
        cursor.execute("SELECT organisation_id FROM organisation WHERE user_id = ?", (session['user_id'],))
        org = cursor.fetchone()

        # Insert event
        cursor.execute('''INSERT INTO event (organisation_id, title, description, event_date, location, max_volunteers)
                          VALUES (?, ?, ?, ?, ?, ?)''',
                          (org['organisation_id'], title, description, event_date, location, max_volunteers))
        event_id = cursor.lastrowid

        # Insert selected skills into junction
        for skill_id in selected_skills[:3]:  # limit to 3 skills
            cursor.execute("INSERT INTO event_skill (event_id, skill_id) VALUES (?, ?)", (event_id, skill_id))

        conn.commit()
        conn.close()

        flash("Event created successfully!", "success")
        return redirect(url_for('events'))

    conn.close()
    return render_template("create_event.html", skills=skills)



# Route for events
@app.route("/events")
def events():
    if 'user_id' not in session:
        flash("You must be logged in to view events.", "warning")
        return redirect(url_for('login'))

    conn = get_db()
    cursor = conn.cursor()

    # Fetch events with their org names
    cursor.execute('''SELECT e.*, o.name, o.user_id
                      FROM event e
                      JOIN organisation o ON e.organisation_id = o.organisation_id''')
    events = cursor.fetchall()

    # For each event, get its skills
    event_data = []
    for e in events:
        cursor.execute('''SELECT s.name 
                          FROM event_skill es 
                          JOIN skill s ON es.skill_id = s.skill_id 
                          WHERE es.event_id = ?''', (e['event_id'],))
        skills = [row['name'] for row in cursor.fetchall()]
        event_data.append({**dict(e), "skills": skills})

    conn.close()
    return render_template("events.html", events=event_data, role=session.get('role'))


# Route to delete events
@app.route('/delete_event/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    if 'user_id' not in session or session.get('role') != 'organisation':
        flash('You are not allowed to do that.', 'danger')
        return redirect(url_for('events'))

    with get_db() as conn:
        cursor = conn.cursor()
        # Make sure the logged-in organisation owns this event
        cursor.execute('SELECT organisation_id FROM event WHERE event_id = ?', (event_id,))
        event = cursor.fetchone()

        if event:
            # Get organisation_id of logged in user
            cursor.execute('SELECT organisation_id FROM organisation WHERE user_id = ?', (session['user_id'],))
            org = cursor.fetchone()

            if org and org['organisation_id'] == event['organisation_id']:
                cursor.execute('DELETE FROM event WHERE event_id = ?', (event_id,))
                conn.commit()
                flash('Event deleted successfully.', 'success')
            else:
                flash('You can only delete your own events.', 'danger')
        else:
            flash('Event not found.', 'danger')

    return redirect(url_for('events'))


# Checks if script is run directly (Not imported)
if __name__ == "__main__":
    init_db() # Initialise databse
    app.run(debug=True) # Runs the Flask application with debug mode enabled
