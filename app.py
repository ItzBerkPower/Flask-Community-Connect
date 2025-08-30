# app.py
import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import re

from models import *

# ------------------- ROUTES ---------------------

# Home page route
@app.route("/")
def index():
    return render_template('index.html') # Render the homepage template


# Route to register the user
@app.route('/register', methods=['GET', 'POST'])
def register():

    # Send request to get information required to insert user
    if request.method == 'POST': 
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        role = request.form['role']

        # Initialise cursor
        conn = get_db()
        cursor = conn.cursor()

        # Insert into user table
        cursor.execute("INSERT INTO user (email, password_hash, role) VALUES (?, ?, ?)", (email, password, role))
        user_id = cursor.lastrowid

        # If it is a volunteer acount, also get first & last name of volunteer
        if role == "volunteer":
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            
            # Did separate insert, as can still insert into same role using the user_id (Autoincrement)
            cursor.execute("INSERT INTO volunteer (user_id, first_name, last_name) VALUES (?, ?, ?)", (user_id, first_name, last_name))

        # If it is an organisation account, also get other required fields
        elif role == "organisation":
            org_name = request.form['organisation_name']
            org_desc = request.form['organisation_description']
            org_addr = request.form['organisation_address']
            cursor.execute("INSERT INTO organisation (user_id, name, description, address) VALUES (?, ?, ?, ?)", (user_id, org_name, org_desc, org_addr))

        # Commit changes and update
        conn.commit()
        conn.close()
        flash('Registration successful! Please log in.', 'success')

        return redirect(url_for('login')) # Redirect user back to login page after registering

    return render_template('register.html') # Render the register website page

        


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
            user = cursor.fetchone() # Fetch the next available row

        # If the user row is correct, and the password is correct, update the session to log user in
        if user and check_password_hash(user['password_hash'], password):
            session['loggedin'] = True
            session['user_id'] = user['user_id']
            session["role"] = user["role"]

            return redirect(url_for('index')) # Redirect user back to home page
        
        # If wrong details
        else:
            flash('Invalid email or password. Please try again.', 'danger') # Can't find user, send warning message
    
    return render_template('login.html') # Render template


# Route for user to logout
@app.route('/logout')
def logout():
    session.clear() # Clear the session, so user no longer logged in
    flash('You have been logged out.', 'info') # Send logged out message

    return redirect(url_for('index')) # Redirect user back to home page


# Route to show all volunteers (Only in view of organisation)
@app.route("/volunteers")
def all_volunteers():

    # Check if user is not an organisation account
    if session.get("role") != "organisation":
        flash("Access denied.") 
        return redirect(url_for("index")) # If not, can't access, so redirect back to home page
    
    # Find all users who are volunteers
    with get_db() as conn:
        volunteers = conn.execute("SELECT * FROM user WHERE role='volunteer'").fetchall()
    
    return render_template("volunteers.html", volunteers=volunteers) # Render the volunteers webpage


# Route to show all organisations (Only in view of volunteers)
@app.route("/organisations")
def all_organisations():

    # Check if the user is not a volunteer account
    if session.get("role") != "volunteer":
        flash("Access denied.")
        return redirect(url_for("index")) # If not, can't access, so redirect back to home page
    
    # Find all users who are organisations
    with get_db() as conn:
        organisations = conn.execute("SELECT * FROM user WHERE role='organisation'").fetchall()

    return render_template("organisations.html", organisations=organisations) # Render the organisations webpage



# Route to update user details
@app.route('/my_account', methods=['GET', 'POST'])
def my_account():

    # Redirect if not logged in, as shouldn't be able to access page
    if 'user_id' not in session:
        flash("You need to log in first.", "warning")
        return redirect(url_for('login'))
    
    # Initialise cursor, as separate SQL statements needed, so can't put it in pythonic way
    conn = get_db()
    cursor = conn.cursor()

    # Get current user info
    cursor.execute("SELECT * FROM user WHERE user_id = ?", (session['user_id'],))
    user = cursor.fetchone()

    volunteer = organisation = None # Intiialise variable(s)

    # If user is volunteer, find the user details
    if user['role'] == "volunteer":
        cursor.execute("SELECT * FROM volunteer WHERE user_id = ?", (user['user_id'],))
        volunteer = cursor.fetchone()

    # If user is organisation, find the user details
    elif user['role'] == "organisation":
        cursor.execute("SELECT * FROM organisation WHERE user_id = ?", (user['user_id'],))
        organisation = cursor.fetchone()

    # Now to update the details
    if request.method == "POST":
        # Fields that are common between both organisation and volunteer
        email = request.form['email']
        phone_number = request.form['phone_number']
        new_password = request.form['password']

        # Update shared user info
        if new_password: # If new password entered, update that one as well
            password_hash = generate_password_hash(new_password)
            cursor.execute("UPDATE user SET email = ?, phone_number = ?, password_hash = ? WHERE user_id = ?",
                           (email, phone_number, password_hash, user['user_id']))
            
        else: # If no new password is entered, just update other three fields
            cursor.execute("UPDATE user SET email = ?, phone_number = ? WHERE user_id = ?",
                            (email, phone_number, user['user_id']))


        # Update volunteer-specific information
        if user['role'] == "volunteer":
            # Only these fields are volunteer specific, will appear at very end of form
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            availability = request.form['availability']

            # Update the details of user
            cursor.execute("""UPDATE volunteer SET first_name = ?, last_name = ?, availability = ? WHERE user_id = ?""",
                           (first_name, last_name, availability, user['user_id']))


        # Update organisation-specific information
        elif user['role'] == "organisation":
            # These fields are organisation specific, will appear at very end of form
            name = request.form['organisation_name']
            address = request.form['organisation_address']
            website = request.form['organisation_website']
            description = request.form['organisation_description']

            # Update the details of organisation
            cursor.execute("""UPDATE organisation SET name = ?, address = ?, website_url = ?, description = ? WHERE user_id = ?""",
                           (name, address, website, description, user['user_id']))

        conn.commit() # Commit changes
        flash("Account updated successfully!", "success")
        return redirect(url_for('my_account')) # Redirect user back to their account page (Just reloads page)

    conn.close()
    return render_template("my_account.html", user=user, volunteer=volunteer, organisation=organisation) # Render the actual webpage with the form


# Route to create events
@app.route("/create_event", methods=["GET", "POST"])
def create_event():
    
    # Check if account logged in is an organisation account, because if not, cannot create events
    if 'user_id' not in session or session.get('role') != 'organisation':
        flash("Only organisations can create events.", "danger")
        return redirect(url_for('events')) # Redirect back to events page

    # Initialise cursor, as multiple different SQL statements, so can't use pythonic way
    conn = get_db()
    cursor = conn.cursor()

    # Fetch all available skills for form
    cursor.execute("SELECT * FROM skill")
    skills = cursor.fetchall()

    # Request all fields to make event
    if request.method == "POST":
        title = request.form['title']
        description = request.form['description']
        event_date = request.form['event_date']
        location = request.form['location']
        max_volunteers = request.form['max_volunteers']
        selected_skills = request.form.getlist('skills') # Get the list of all the skills from the skills table

        # Get organisation_id for current user
        cursor.execute("SELECT organisation_id FROM organisation WHERE user_id = ?", (session['user_id'],))
        org = cursor.fetchone()


        # Insert event
        cursor.execute('''INSERT INTO event (organisation_id, title, description, event_date, location, max_volunteers) VALUES (?, ?, ?, ?, ?, ?)''',
                          (org['organisation_id'], title, description, event_date, location, max_volunteers))
        event_id = cursor.lastrowid # Need event_id to insert into junction table

        # Insert selected skills into junction
        for skill_id in selected_skills[:3]:  # limit to 3 skills
            cursor.execute("INSERT INTO event_skill (event_id, skill_id) VALUES (?, ?)", (event_id, skill_id))

        # Commit database changes and close the database
        conn.commit()
        conn.close()

        flash("Event created successfully!", "success")
        return redirect(url_for('events')) # Redirect user back to the events page

    # Close the database
    conn.close()
    return render_template("create_event.html", skills=skills) # Render the actual create events form



# Route for events
@app.route("/events")
def events():

    # Check if user is logged in, where if they aren't they are unable to view events
    if 'user_id' not in session:
        flash("You must be logged in to view events.", "warning")
        return redirect(url_for('login')) # Redirect the user to the login page

    # Intialise the cursor, as can't use pythonic way due to multiple SQL statements
    conn = get_db()
    cursor = conn.cursor()

    # Fetch events with their org names, e.* selects all of the columns
    cursor.execute('''SELECT e.*, o.name, o.user_id FROM event e JOIN organisation o ON e.organisation_id = o.organisation_id''')
    events = cursor.fetchall() # Get all the rows

    # For each event, get the skills required for it
    event_data = []
    # Loops through every event one-by-one
    for e in events:
        # Select all skills associated with current event
        cursor.execute('''SELECT s.name FROM event_skill es JOIN skill s ON es.skill_id = s.skill_id WHERE es.event_id = ?''', (e['event_id'],))
        skills = [row['name'] for row in cursor.fetchall()] # Extracts skill name from every row
        event_data.append({**dict(e), "skills": skills}) # Append to the event_data list, as dictionaries as sub-arrays

    # Close the database, no need to commit as nothing in dataase updated
    conn.close()
    return render_template("events.html", events=event_data, role=session.get('role')) # Render the actual events website


# Route to delete events
@app.route('/delete_event/<int:event_id>', methods=['POST'])
def delete_event(event_id):

    # Check if user is organisation account, as if not, cannot delete events at all
    if 'user_id' not in session or session.get('role') != 'organisation':
        flash('You are not allowed to do that.', 'danger')
        return redirect(url_for('events')) # Redirect user back to events page

    # Initialise cursor object
    with get_db() as conn:
        cursor = conn.cursor()

        # Make sure that event exists
        cursor.execute('SELECT organisation_id FROM event WHERE event_id = ?', (event_id,))
        event = cursor.fetchone() # Fetch next available row

        # If event exists
        if event:
            # Get organisation_id of logged in user
            cursor.execute('SELECT organisation_id FROM organisation WHERE user_id = ?', (session['user_id'],))
            org = cursor.fetchone()

            # Check if organisation_id is same as the one recorded in the event
            # If its the same, then that organisation created the event 
            if org and org['organisation_id'] == event['organisation_id']:
                cursor.execute('DELETE FROM event WHERE event_id = ?', (event_id,)) # Delete event
                conn.commit() # Update changes
                flash('Event deleted successfully.', 'success')

            # If doesn't own event, throw an error message
            else:
                flash('You can only delete your own events.', 'danger')

        # If event doesn't exist, throw an error message
        else:
            flash('Event not found.', 'danger')

    return redirect(url_for('events')) # Redirect user to the events page


# Checks if script is run directly (Not imported)
if __name__ == "__main__":
    init_db() # Initialise databse
    app.run(debug=True) # Runs the Flask application with debug mode enabled
