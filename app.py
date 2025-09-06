# app.py
import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import re
from sqlite3 import IntegrityError

from models import *

# ------------------- ROUTES ---------------------

# Home page route
@app.route("/")
def index():
    return render_template('index.html') # Render the homepage template

# Route to register the user
@app.route('/register', methods=['GET', 'POST'])
def register():
    # Get the role, email and password from the general user, as is shared fields
    if request.method == 'POST':
        role = request.form.get('role')
        email = request.form.get('email', '').strip().lower() # Lower to keep consistent with naming
        password = request.form.get('password')

        # Input validation, though flask has built-in validation
        if not email or not password:
            flash("Email and password are required.", "danger")
            return redirect(url_for('register')) # Reload to display flash

        # Pythonic way of initialising cursor
        with get_db() as conn:
            cursor = conn.cursor()

            # try-except block to catch error from UNIQUE constraint for email
            try:
                # Insert the general details of user into the table
                cursor.execute("INSERT INTO user (email, password_hash, role) VALUES (?, ?, ?)",
                        (email, generate_password_hash(password), role))
                user_id = cursor.lastrowid # Get user id, as the new user is the last user record entered


                # If volunteer, get fields unique to the volunteer from form
                if role == "volunteer":
                    # First name, Last name, Date of Birth
                    first_name = request.form.get('first_name')
                    last_name = request.form.get('last_name')
                    dob = request.form.get('dob')

                    # Input validation, though Flask has in-built input validation so not needed
                    if not first_name or not last_name or not dob:
                        raise ValueError("All volunteer fields are required.")

                    # Insert the final details for volunteer into same user row (Was empty initially)
                    cursor.execute("INSERT INTO volunteer (user_id, first_name, last_name, dob) VALUES (?, ?, ?, ?)",
                        (user_id, first_name, last_name, dob))


                # If organisation, get fields unique to the organisation from form
                elif role == "organisation":
                    # Organisation name, Organisation description, Organisation Address (Physical Address)
                    org_name = request.form.get('organisation_name')
                    description = request.form.get('organisation_description', '')
                    address = request.form.get('organisation_address', '')

                    # Input validation, though Flask has already got in-built input validation, but just incase
                    if not org_name:
                        raise ValueError("Organisation name is required.")

                    # Insert the final details for volunteer into same organisation row (Was empty initially)
                    cursor.execute("INSERT INTO organisation (user_id, name, description, address) VALUES (?, ?, ?, ?)",
                        (user_id, org_name, description, address))

                conn.commit() # Commit changes
                flash("Account created successfully! Please log in.", "success") # Throw the success flash message
                return redirect(url_for('login')) # Redirect user to login page

            # If user tried registering with an already-used e-mail address
            except IntegrityError:
                conn.rollback() # Undo the uncommitted changes to last committed change
                flash("That e-mail is already associated with an account.", "danger") # Throw error flash message
                return redirect(url_for('register')) # Reload register page

            # If the error thrown for a field not filled out (To reduce duplicated code)
            except ValueError as ve:
                conn.rollback() # Undo the uncommitted changes to last committed changes
                flash(str(ve), "danger") # Throw the error flash message
                return redirect(url_for('register')) # Reload the register page

    return render_template("register.html") # Render the actual HTML page

        


# Route for user to log in
@app.route('/login', methods = ['GET', 'POST'])
def login():
    # Gather email and password from form after submission
    if request.method == 'POST': 
        email = request.form['email']
        password = request.form['password']

        # Try to find user from database
        # Pythonic way of initialising cursor object
        with get_db() as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM user WHERE email = ?', (email,)) # Gather all details of that user with that email address
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


# Route to show all volunteers (Only accessible to organisations)
@app.route("/volunteers")
def all_volunteers():
    if session.get("role") != "organisation":
        flash("Access denied.", "danger")
        return redirect(url_for("index"))

    skill_filter = request.args.get("skill_id")

    conn = get_db()
    cursor = conn.cursor()

    if skill_filter:
        cursor.execute('''
            SELECT v.first_name, v.last_name,
                   CAST((julianday('now') - julianday(v.dob)) / 365 AS INT) AS age,
                   u.email
            FROM volunteer v
            JOIN user u ON v.user_id = u.user_id
            JOIN volunteer_skill vs ON v.volunteer_id = vs.volunteer_id
            WHERE vs.skill_id = ?
        ''', (skill_filter,))
    else:
        cursor.execute('''
            SELECT v.first_name, v.last_name,
                   CAST((julianday('now') - julianday(v.dob)) / 365 AS INT) AS age,
                   u.email
            FROM volunteer v
            JOIN user u ON v.user_id = u.user_id
        ''')
    volunteers = cursor.fetchall()

    # Fetch skills for dropdown
    cursor.execute("SELECT * FROM skill")
    skills = cursor.fetchall()

    conn.close()

    return render_template("volunteers.html", volunteers=volunteers, skills=skills)



@app.route('/organisations')
def all_organisations():
    filter_type = request.args.get('filter')

    with get_db() as conn:
        cursor = conn.cursor()

        if filter_type == 'skills' and session.get('role') == 'volunteer':
            # Get volunteer_id
            cursor.execute("SELECT volunteer_id FROM volunteer WHERE user_id = ?", (session['user_id'],))
            v = cursor.fetchone()
            if v:
                volunteer_id = v['volunteer_id']

                # Get volunteer skills
                cursor.execute("""
                    SELECT skill_id FROM volunteer_skill WHERE volunteer_id = ?
                """, (volunteer_id,))
                skill_ids = [row['skill_id'] for row in cursor.fetchall()]

                if skill_ids:
                    # Organisations that have events requiring these skills
                    placeholders = ",".join("?" * len(skill_ids))
                    cursor.execute(f"""
                        SELECT DISTINCT o.organisation_id, o.name, o.description, o.address
                        FROM organisation o
                        JOIN event e ON o.organisation_id = e.organisation_id
                        JOIN event_skill es ON e.event_id = es.event_id
                        WHERE es.skill_id IN ({placeholders})
                    """, skill_ids)
                    organisations = cursor.fetchall()
                else:
                    organisations = []
            else:
                organisations = []
        else:
            # Default: get all organisations
            cursor.execute("SELECT * FROM organisation")
            organisations = cursor.fetchall()

    return render_template("organisations.html", organisations=organisations, role=session.get('role'))




@app.route('/my_account', methods=['GET', 'POST'])
def my_account():
    if 'user_id' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))

    with get_db() as conn:
        cursor = conn.cursor()

        # Get user details
        cursor.execute("SELECT * FROM user WHERE user_id = ?", (session['user_id'],))
        user = cursor.fetchone()

        volunteer = organisation = None
        volunteer_skills = []
        all_skills = []

        if request.method == "POST":
            # Shared fields
            email = request.form.get('email')
            phone_number = request.form.get('phone_number')
            password = request.form.get('password')

            # Update password only if provided
            if password:
                from werkzeug.security import generate_password_hash
                password_hash = generate_password_hash(password)
                cursor.execute("""
                    UPDATE user 
                    SET email = ?, phone_number = ?, password_hash = ? 
                    WHERE user_id = ?
                """, (email, phone_number, password_hash, user['user_id']))
            else:
                cursor.execute("""
                    UPDATE user 
                    SET email = ?, phone_number = ? 
                    WHERE user_id = ?
                """, (email, phone_number, user['user_id']))

            # Role-specific updates
            if user['role'] == 'volunteer':
                first_name = request.form.get('first_name')
                last_name = request.form.get('last_name')
                availability = request.form.get('availability')
                cursor.execute("""
                    UPDATE volunteer 
                    SET first_name = ?, last_name = ?, availability = ?
                    WHERE user_id = ?
                """, (first_name, last_name, availability, user['user_id']))

            elif user['role'] == 'organisation':
                name = request.form.get('organisation_name')
                address = request.form.get('organisation_address')
                website = request.form.get('organisation_website')
                description = request.form.get('organisation_description')
                cursor.execute("""
                    UPDATE organisation 
                    SET name = ?, address = ?, website_url = ?, description = ?
                    WHERE user_id = ?
                """, (name, address, website, description, user['user_id']))

            conn.commit()
            flash("Account updated successfully!", "success")
            return redirect(url_for('my_account'))

        # GET request or after update: fetch role-specific info
        if user['role'] == 'volunteer':
            cursor.execute("SELECT * FROM volunteer WHERE user_id = ?", (user['user_id'],))
            volunteer = cursor.fetchone()

            # All skills
            cursor.execute("SELECT * FROM skill")
            all_skills = cursor.fetchall()

            # Volunteer’s selected skills
            cursor.execute("""
                SELECT s.skill_id 
                FROM volunteer_skill vs 
                JOIN skill s ON vs.skill_id = s.skill_id 
                WHERE vs.volunteer_id = ?
            """, (volunteer['volunteer_id'],))
            volunteer_skills = [row['skill_id'] for row in cursor.fetchall()]

        elif user['role'] == 'organisation':
            cursor.execute("SELECT * FROM organisation WHERE user_id = ?", (user['user_id'],))
            organisation = cursor.fetchone()

    return render_template(
        'my_account.html',
        user=user,
        volunteer=volunteer,
        organisation=organisation,
        all_skills=all_skills,
        volunteer_skills=volunteer_skills
    )


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



@app.route('/events')
def events():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    with get_db() as conn:
        cursor = conn.cursor()

        # Get user role
        cursor.execute("SELECT role FROM user WHERE user_id = ?", (session['user_id'],))
        role = cursor.fetchone()['role']

        # Fetch events with volunteer count (aggregate + GROUP BY)
        cursor.execute("""
            SELECT e.event_id, e.title, e.description, e.event_date, e.location,
                   o.name AS name, u.user_id,
                   COUNT(ve.volunteer_id) AS volunteer_count
            FROM event e
            JOIN organisation o ON e.organisation_id = o.organisation_id
            JOIN user u ON o.user_id = u.user_id
            LEFT JOIN volunteer_event ve ON e.event_id = ve.event_id
            GROUP BY e.event_id
        """)
        events = cursor.fetchall()

        event_data = []
        for e in events:
            # Get required skills for this event
            cursor.execute("""
                SELECT s.skill_id, s.name
                FROM event_skill es
                JOIN skill s ON es.skill_id = s.skill_id
                WHERE es.event_id = ?
            """, (e['event_id'],))
            skills = cursor.fetchall()

            event_data.append({
                **dict(e),
                "skills": [s['name'] for s in skills],
                "skill_ids": [int(s['skill_id']) for s in skills]
            })

        # Volunteer’s skills
        volunteer_skills = []
        if role == "volunteer":
            cursor.execute("SELECT volunteer_id FROM volunteer WHERE user_id = ?", (session['user_id'],))
            volunteer = cursor.fetchone()
            if volunteer:
                cursor.execute("SELECT skill_id FROM volunteer_skill WHERE volunteer_id = ?", (volunteer['volunteer_id'],))
                volunteer_skills = [int(row['skill_id']) for row in cursor.fetchall()]

    return render_template("events.html",
                           events=event_data,
                           role=role,
                           volunteer_skills=volunteer_skills)



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


@app.route('/join_event/<int:event_id>', methods=['POST'])
def join_event(event_id):
    if 'user_id' not in session or session.get('role') != 'volunteer':
        flash("Only volunteers can join events.", "danger")
        return redirect(url_for('events'))

    with get_db() as conn:
        cursor = conn.cursor()

        # Get volunteer_id
        cursor.execute("SELECT volunteer_id FROM volunteer WHERE user_id = ?", (session['user_id'],))
        volunteer = cursor.fetchone()

        if volunteer:
            # Check event capacity
            cursor.execute("SELECT max_volunteers FROM event WHERE event_id = ?", (event_id,))
            event = cursor.fetchone()

            if not event:
                flash("Event not found.", "danger")
                return redirect(url_for('events'))

            # Count currently accepted volunteers
            cursor.execute("""
                SELECT COUNT(*) AS count
                FROM volunteer_event
                WHERE event_id = ?
            """, (event_id,))
            current_count = cursor.fetchone()["count"]

            if event["max_volunteers"] is not None and current_count >= event["max_volunteers"]:
                flash("Event is already full. Explore other events!", "warning")
                return redirect(url_for('events'))

            try:
                # Insert join request if not already there
                cursor.execute("""
                    INSERT INTO event_request (volunteer_id, event_id, status)
                    VALUES (?, ?, 'pending')
                """, (volunteer['volunteer_id'], event_id))
                conn.commit()
                flash("Your request to join has been sent!", "success")
            except sqlite3.IntegrityError:
                flash("You already requested to join this event.", "warning")

    return redirect(url_for('events'))



@app.route('/manage_event/<int:event_id>')
def manage_event(event_id):
    if 'user_id' not in session or session.get('role') != 'organisation':
        flash("Only organisations can manage events.", "danger")
        return redirect(url_for('events'))

    with get_db() as conn:
        cursor = conn.cursor()

        # Ensure event belongs to this org
        cursor.execute("SELECT organisation_id FROM organisation WHERE user_id = ?", (session['user_id'],))
        org = cursor.fetchone()
        cursor.execute("SELECT * FROM event WHERE event_id = ? AND organisation_id = ?", (event_id, org['organisation_id']))
        event = cursor.fetchone()
        if not event:
            flash("You cannot manage this event.", "danger")
            return redirect(url_for('events'))

        # Volunteer requests (pending/accepted/declined)
        cursor.execute("""
            SELECT er.request_id, er.status,
                   v.first_name || ' ' || v.last_name AS full_name,
                   CAST((julianday('now') - julianday(v.dob)) / 365 AS INT) AS age,
                   u.email
            FROM event_request er
            JOIN volunteer v ON er.volunteer_id = v.volunteer_id
            JOIN user u ON v.user_id = u.user_id
            WHERE er.event_id = ?
        """, (event_id,))
        requests = cursor.fetchall()

        # Volunteers who are officially in the event
        cursor.execute("""
            SELECT v.first_name || ' ' || v.last_name AS full_name,
                   CAST((julianday('now') - julianday(v.dob)) / 365 AS INT) AS age,
                   u.email
            FROM volunteer_event ve
            JOIN volunteer v ON ve.volunteer_id = v.volunteer_id
            JOIN user u ON v.user_id = u.user_id
            WHERE ve.event_id = ?
        """, (event_id,))
        attendees = cursor.fetchall()

        # Aggregate function: average age of attendees
        cursor.execute("""
            SELECT ROUND(AVG((julianday('now') - julianday(v.dob)) / 365), 1) AS avg_age
            FROM volunteer_event ve
            JOIN volunteer v ON ve.volunteer_id = v.volunteer_id
            WHERE ve.event_id = ?
        """, (event_id,))
        avg_age_row = cursor.fetchone()
        avg_age = avg_age_row['avg_age'] if avg_age_row and avg_age_row['avg_age'] else None

    return render_template("manage_event.html",
                           event=event,
                           requests=requests,
                           attendees=attendees,
                           avg_age=avg_age)




@app.route('/handle_request/<int:request_id>/<string:action>', methods=['POST'])
def handle_request(request_id, action):
    if 'user_id' not in session or session.get('role') != 'organisation':
        flash("Only organisations can handle requests.", "danger")
        return redirect(url_for('events'))

    with get_db() as conn:
        cursor = conn.cursor()

        # Get request
        cursor.execute("SELECT * FROM event_request WHERE request_id = ?", (request_id,))
        request = cursor.fetchone()

        if not request:
            flash("Request not found.", "danger")
            return redirect(url_for('events'))

        if action == "accept":
            # Update request status
            cursor.execute("UPDATE event_request SET status = 'accepted' WHERE request_id = ?", (request_id,))

            # Add to volunteer_event table
            cursor.execute("""
                INSERT OR IGNORE INTO volunteer_event (volunteer_id, event_id)
                VALUES (?, ?)
            """, (request['volunteer_id'], request['event_id']))

            flash("Volunteer accepted and added to event.", "success")

        elif action == "decline":
            cursor.execute("UPDATE event_request SET status = 'declined' WHERE request_id = ?", (request_id,))
            flash("Volunteer request declined.", "info")

        conn.commit()

    return redirect(url_for('manage_event', event_id=request['event_id']))


@app.route('/update_skills', methods=['POST'])
def update_skills():
    if 'user_id' not in session or session.get('role') != 'volunteer':
        flash("Only volunteers can update skills.", "danger")
        return redirect(url_for('my_account'))

    user_id = session['user_id']

    with get_db() as conn:
        cursor = conn.cursor()

        # Double-check this user is really a volunteer
        cursor.execute("SELECT volunteer_id FROM volunteer WHERE user_id = ?", (user_id,))
        volunteer = cursor.fetchone()
        if not volunteer:
            flash("Volunteer record not found.", "danger")
            return redirect(url_for('my_account'))

        volunteer_id = volunteer['volunteer_id']

        # Debug log
        print(f"Updating skills for volunteer_id={volunteer_id}, user_id={user_id}")

        # Get submitted skills
        selected_skills = request.form.getlist("skills")
        print("Selected skills:", selected_skills)

        # Enforce max 3
        if len(selected_skills) > 3:
            flash("You can only select up to 3 skills.", "warning")
            return redirect(url_for('my_account'))

        # Clear old
        cursor.execute("DELETE FROM volunteer_skill WHERE volunteer_id = ?", (volunteer_id,))

        # Insert new
        for skill_id in selected_skills:
            cursor.execute(
                "INSERT INTO volunteer_skill (volunteer_id, skill_id) VALUES (?, ?)",
                (volunteer_id, skill_id)
            )

        conn.commit()
        flash("Skills updated successfully.", "success")

    return redirect(url_for('my_account'))



# Checks if script is run directly (Not imported)
if __name__ == "__main__":
    init_db() # Initialise database
    app.run(debug=True) # Runs the Flask application with debug mode enabled
