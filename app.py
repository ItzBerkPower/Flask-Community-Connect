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

            cursor.execute('SELECT user_id, role, password_hash FROM user WHERE email = ?', (email,)) # Get the user_id, user's role and their password
            user = cursor.fetchone() # Fetch the next available row

        # If the user row is correct, and the password is correct, update the session to log user in
        if user and check_password_hash(user['password_hash'], password):
            # Update session
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
    # If user is not an organisation account, then can't see volunteers page
    if session.get("role") != "organisation":
        flash("Access denied.", "danger") # Throw error message
        return redirect(url_for("index")) # Redirect user back to home page

    # For filtering skills, reads filters passed in URL, e.g. '/volunteers?skill_id=3'
    # If no skill filter, skill_filter = None
    skill_filter = request.args.get("skill_id")

    # Pythonic way of initialising cursor object (For running queries)
    with get_db() as conn:
        cursor = conn.cursor()

        # If a skill filter is applied, only want to show volunteers with that skill
        if skill_filter:
            # Only show volunteers that have that skill
            # Also calculates age directly in SQL
            cursor.execute('''
                SELECT v.first_name, v.last_name, CAST((julianday('now') - julianday(v.dob)) / 365 AS INT) AS age, u.email
                FROM volunteer v
                INNER JOIN user u ON v.user_id = u.user_id
                INNER JOIN volunteer_skill vs ON v.volunteer_id = vs.volunteer_id
                WHERE vs.skill_id = ?''', (skill_filter,))


        # If no skill filter applied, show all volunteers with that skill (Default view)
        # Also calculates age directly in SQL
        else:
            cursor.execute('''
                SELECT v.first_name, v.last_name, CAST((julianday('now') - julianday(v.dob)) / 365 AS INT) AS age, u.email
                FROM volunteer v
                INNER JOIN user u ON v.user_id = u.user_id
            ''')

        volunteers = cursor.fetchall() # Fetch all rows from query, return them as a list of dictionaries

    # Fetch the actual skills for the drop down menu
    cursor.execute("SELECT * FROM skill")
    skills = cursor.fetchall() # Fetch all rows from query, return them as a list of dictionaries


    return render_template("volunteers.html", volunteers=volunteers, skills=skills) # Render the actual volunteers page


# Route to view organisations
@app.route('/organisations')
def all_organisations():

    # If user is not an volunteer account, then can't see organisations page
    if session.get("role") != "volunteer":
        flash("Access denied.", "danger") # Throw error message
        return redirect(url_for("index")) # Redirect user back to home page

    # For filtering skills, reads filters passed in URL
    # If no skill filter, skill_filter = None
    filter_type = request.args.get('filter')

    # Pythonic way of initialising cursor object
    with get_db() as conn:
        cursor = conn.cursor()

        # If filter set to 'Matching MySkills', need to first get the users skills, then show only orgs who look for those skills
        if filter_type == 'skills':
            cursor.execute("SELECT volunteer_id FROM volunteer WHERE user_id = ?", (session['user_id'],)) # Get the id of the volunteer
            v = cursor.fetchone() # Fetch next available row

            # If user does exist,
            if v:
                volunteer_id = v['volunteer_id'] # Save volunteer to variable

                # Get volunteer skills
                cursor.execute("SELECT skill_id FROM volunteer_skill WHERE volunteer_id = ?", (volunteer_id,)) # Get all the id's of the skills the volunteer possesses
                skill_ids = [row['skill_id'] for row in cursor.fetchall()] # Save all of the skill_ids to a list using list comprehension

                # If there are any skills the user has
                if skill_ids:
                    placeholders = ",".join("?" * len(skill_ids)) # Placeholders for skills, as don't know how many skills user has (Is also a secret safety against SQL injection)

                    # Find alll organisations that have events that require the skills the volunteer has (At least one overlap)
                    cursor.execute(f"""
                        SELECT DISTINCT o.organisation_id, o.name, o.description, o.address
                        FROM organisation o
                        INNER JOIN event e ON o.organisation_id = e.organisation_id
                        INNER JOIN event_skill es ON e.event_id = es.event_id
                        WHERE es.skill_id IN ({placeholders})""", skill_ids)

                    organisations = cursor.fetchall() # Retrieve all matching organisations into list of dictionaries
                
                # If volunteer has no skills, no organisations to match, so return empty list for HTML template message
                else:
                    organisations = []
            
            # If no volunteer record for user, also return empty list for HTML template message, as no user to have skills?
            else:
                organisations = []

        # Default case if no filter, where just show all organisations
        else:
            cursor.execute("SELECT * FROM organisation") # Simple SQL command
            organisations = cursor.fetchall() # Fetch all organisations into list of dictionaries

    # Render template for organisations HTML page
    return render_template("organisations.html", organisations=organisations, role=session.get('role'), filter = filter_type)
    # 'filter = filter_type' to make sure dropdown menu text shows current mode of filter TOOK SO LONG TO FIX


# Route for the account details editing of the user
@app.route('/my_account', methods=['GET', 'POST'])
def my_account():

    # If user tries to access page before logging in, restrict it
    if 'user_id' not in session:
        flash("Please log in first.", "warning") # Throw error message
        return redirect(url_for('login')) # Redirect user back to the login page

    # Pythonic way of initialising cursor object
    with get_db() as conn:
        cursor = conn.cursor()

        # Gather all of the user details (That corresponds to that user id)
        cursor.execute("SELECT * FROM user WHERE user_id = ?", (session['user_id'],))
        user = cursor.fetchone() # Fetch next available row

        # Initialise variables
        volunteer = organisation = None
        volunteer_skills = []
        all_skills = []

        # Gather all generic details for general user
        if request.method == "POST":
            # Email, Phone number, Password
            email = request.form.get('email')
            phone_number = request.form.get('phone_number')
            password = request.form.get('password')

            # Update password only if provided
            if password:
                password_hash = generate_password_hash(password) # Generate new password hash for password (Encryption)
                # Update all details of user
                # If email or phone number not changed or changed, update either way (Easiest way to do it)
                cursor.execute("""
                    UPDATE user 
                    SET email = ?, phone_number = ?, password_hash = ? 
                    WHERE user_id = ?""", (email, phone_number, password_hash, user['user_id']))
            
            # If updated password not provided, only update the other fields
            else:
                # Update email and phone number even if not changed (Easiest way to do it)
                cursor.execute("""
                    UPDATE user 
                    SET email = ?, phone_number = ? 
                    WHERE user_id = ?""", (email, phone_number, user['user_id']))


            # Role-specific updates
            # If user is a volunteer, update the fields specific to the user
            if user['role'] == 'volunteer':
                # First name, Last name, and their availability (Not really used)
                first_name = request.form.get('first_name')
                last_name = request.form.get('last_name')
                availability = request.form.get('availability')

                # Update the fields even if not changed (Easiest way to do it)
                cursor.execute("""
                    UPDATE volunteer 
                    SET first_name = ?, last_name = ?, availability = ?
                    WHERE user_id = ?""", (first_name, last_name, availability, user['user_id']))

            # If user is an organisation, update the fields specific to the organisation
            elif user['role'] == 'organisation':
                # Organisation name, Physical address, Website URL, Description of organisation
                name = request.form.get('organisation_name')
                address = request.form.get('organisation_address')
                website = request.form.get('organisation_website')
                description = request.form.get('organisation_description')

                # Update the fields even if not changed (Easiest way to do it)
                cursor.execute("""
                    UPDATE organisation 
                    SET name = ?, address = ?, website_url = ?, description = ?
                    WHERE user_id = ?
                """, (name, address, website, description, user['user_id']))

            conn.commit() # Commit changes
            flash("Account updated successfully!", "success") # Throw the success message
            return redirect(url_for('my_account')) # Reload the page to save changes

        # Updating skills of volunteer
        if user['role'] == 'volunteer':
            cursor.execute("SELECT * FROM volunteer WHERE user_id = ?", (user['user_id'],)) # Gather all information of volunteer
            volunteer = cursor.fetchone() # Fetch next available row

            # Gather all skills into list of dictionaries
            cursor.execute("SELECT * FROM skill")
            all_skills = cursor.fetchall()

            # Find volunteer’s currently selected skills
            cursor.execute("""
                SELECT s.skill_id 
                FROM volunteer_skill vs 
                JOIN skill s ON vs.skill_id = s.skill_id 
                WHERE vs.volunteer_id = ?""", (volunteer['volunteer_id'],))
            
            volunteer_skills = [row['skill_id'] for row in cursor.fetchall()] # Put all skill_id's of skills volunteer has through list comprehension THIS PART TOOK 40 MINUTES

        # If user is an organisation, just get all their information
        elif user['role'] == 'organisation':
            cursor.execute("SELECT * FROM organisation WHERE user_id = ?", (user['user_id'],)) # Collecting all available information of organisation
            organisation = cursor.fetchone() # Fetching next available row
    
    # Render actual HTML page of account update
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
        flash("Only organisations can create events.", "danger") # Throw error message
        return redirect(url_for('events')) # Redirect back to events page

    # Pythonic way of initialising cursor object
    with get_db() as conn:
        cursor = conn.cursor()

        # Fetch all available skills for form
        cursor.execute("SELECT * FROM skill")
        skills = cursor.fetchall()

        # Request all fields to make event
        if request.method == "POST":
            # All the fields needed to make event
            title = request.form['title']
            description = request.form['description']
            event_date = request.form['event_date']
            location = request.form['location']
            max_volunteers = request.form['max_volunteers']
            selected_skills = request.form.getlist('skills') # Get the list of all the skills from the skills table

            # Get organisation_id for current user
            cursor.execute("SELECT organisation_id FROM organisation WHERE user_id = ?", (session['user_id'],))
            org = cursor.fetchone() # Fetch next availble row)

            # Extra check to ensure that organisation exists
            if not org:
                flash("Organisation not found", "danger") # Throw error message
                return redirect(url_for('events')) # Redirect user back to events page 

            # Insert event
            cursor.execute('''INSERT INTO event (organisation_id, title, description, event_date, location, max_volunteers) VALUES (?, ?, ?, ?, ?, ?)''',
                            (org['organisation_id'], title, description, event_date, location, max_volunteers))
            event_id = cursor.lastrowid # Need event_id to insert into junction table


            # Insert selected skills into junction
            for skill_id in selected_skills[:3]:  # limit to 3 skills for user
                cursor.execute("INSERT INTO event_skill (event_id, skill_id) VALUES (?, ?)", (event_id, skill_id)) # Insert skills

            # Commit database changes
            conn.commit()
            flash("Event created successfully!", "success") # Throw success message
            return redirect(url_for('events')) # Redirect user back to the events page


    return render_template("create_event.html", skills=skills) # Render the actual create events form


# Route to view events
@app.route('/events')
def events():

    # If user not logged in, do not let them view the events
    if 'user_id' not in session:
        flash("You need to be logged in to explore the events!", "danger") # Throw error message
        return redirect(url_for('login')) # Redirect user to login page

    # Pythonic way of initialising cursor object
    with get_db() as conn:
        cursor = conn.cursor()

        # Get role of user, to see what view to present
        cursor.execute("SELECT role FROM user WHERE user_id = ?", (session['user_id'],))
        role = cursor.fetchone()['role'] # Fetch the role of user only (That's all that's needed)

        # Fetch events with the volunteer count (Used GROUP BY here)
        cursor.execute("""
            SELECT e.event_id, e.title, e.description, e.event_date, e.location, o.name AS name, u.user_id, COUNT(ve.volunteer_id) AS volunteer_count
            FROM event e
            INNER JOIN organisation o ON e.organisation_id = o.organisation_id
            INNER JOIN user u ON o.user_id = u.user_id
            LEFT JOIN volunteer_event ve ON e.event_id = ve.event_id
            GROUP BY e.event_id
        """) # (Needed to use a LEFT JOIN here)

        events = cursor.fetchall() # Fetch all events into a list of dictionaries

        event_data = [] # Initialise variable

        # Loop through all events and get the required skills for each event
        for e in events:
            # Get required skills for this event
            cursor.execute("""
                SELECT s.skill_id, s.name
                FROM event_skill es
                JOIN skill s ON es.skill_id = s.skill_id
                WHERE es.event_id = ?""", (e['event_id'],))
            skills = cursor.fetchall() # Fetch all required skills into list of dictionaries

            # This event_data list will be the one showed on the actual HTML template, so put the skill name and their skill id in list
            event_data.append({
                **dict(e),
                "skills": [s['name'] for s in skills],
                "skill_ids": [int(s['skill_id']) for s in skills]
            })


        # Volunteer’s skills
        volunteer_skills = [] # Initialise variable

        # If the user is a volunteer,
        if role == "volunteer":
            
            # Find the volunteer id from the supplied user id
            cursor.execute("SELECT volunteer_id FROM volunteer WHERE user_id = ?", (session['user_id'],))
            volunteer = cursor.fetchone() # Fetch next available row

            # If the volunteer exists (Extra check)
            if volunteer:
                # Retrieve all skills associated with the volunteer
                cursor.execute("SELECT skill_id FROM volunteer_skill WHERE volunteer_id = ?", (volunteer['volunteer_id'],))
                volunteer_skills = [int(row['skill_id']) for row in cursor.fetchall()] # List comprehension iterates through each row, extracting skill id, and converting to integer and storing in list SO LONG TO DO

    # Render the actual events HTML page
    return render_template("events.html",
                           events=event_data,
                           role=role,
                           volunteer_skills=volunteer_skills)



# Route to delete events
@app.route('/delete_event/<int:event_id>', methods=['POST'])
def delete_event(event_id):

    # Check if user is organisation account, as if not, cannot delete events at all
    if 'user_id' not in session or session.get('role') != 'organisation':
        flash('You are not allowed to do that.', 'danger') # Throw error message
        return redirect(url_for('events')) # Redirect user back to events page

    # Pythonic way of initialising cursor object
    with get_db() as conn:
        cursor = conn.cursor()

        # Make sure that event exists
        cursor.execute('SELECT organisation_id FROM event WHERE event_id = ?', (event_id,))
        event = cursor.fetchone() # Fetch next available row

        # If event exists
        if event:
            # Get organisation_id of logged in user
            cursor.execute('SELECT organisation_id FROM organisation WHERE user_id = ?', (session['user_id'],))
            org = cursor.fetchone() # Fetch next available row

            # Check if organisation_id is same as the one recorded in the event
            # If its the same, then that organisation created the event 
            if org and org['organisation_id'] == event['organisation_id']:
                cursor.execute('DELETE FROM event WHERE event_id = ?', (event_id,)) # Delete event
                conn.commit() # Update changes
                flash('Event deleted successfully.', 'success') # Throw success message

            # If organisation doesn't own event, throw an error message
            else:
                flash('You can only delete your own events.', 'danger')

        # If event doesn't exist, throw an error message
        else:
            flash('Event not found.', 'danger')

    return redirect(url_for('events')) # Redirect user to the events page


# Route for volunteers to join event
@app.route('/join_event/<int:event_id>', methods=['POST'])
def join_event(event_id):
    # If user not logged in OR user is not a volunteer, restrict them from joining an event
    if 'user_id' not in session or session.get('role') != 'volunteer':
        flash("Only volunteers can join events.", "danger") # Throw error message
        return redirect(url_for('events')) # Reload the page

    # Pythonic way of initialising cursor object
    with get_db() as conn:
        cursor = conn.cursor()

        # Get the volunteer id from the user id
        cursor.execute("SELECT volunteer_id FROM volunteer WHERE user_id = ?", (session['user_id'],))
        volunteer = cursor.fetchone() # Fetch next available row

        # If volunteer actually exists (Extra safety check)
        if volunteer:
            # Check event capacity of the event
            cursor.execute("SELECT max_volunteers FROM event WHERE event_id = ?", (event_id,))
            event = cursor.fetchone() # Fetch next available row
            
            # If event doesn't exist (Extra safety check)
            if not event:
                flash("Event not found.", "danger") # Throw error message
                return redirect(url_for('events')) # Redirect user back to the events page

            # Count the currently accepted volunteers (To check if space)
            cursor.execute("""
                SELECT COUNT(*) AS count
                FROM volunteer_event
                WHERE event_id = ?""", (event_id,))
            current_count = cursor.fetchone()["count"]

            # If the event is full, where the current number of volunteers is same or more than the initial max number of volunteers
            if event["max_volunteers"] is not None and current_count >= event["max_volunteers"]:
                flash("Event is already full. Explore other events!", "warning") # Throw error message
                return redirect(url_for('events')) # Reload the page

            # 'try' to join the event (To catch errors)
            try:
                # Insert into the requesting to join events table, for organisation to accept
                cursor.execute("""
                    INSERT INTO event_request (volunteer_id, event_id, status)
                    VALUES (?, ?, 'pending')""", (volunteer['volunteer_id'], event_id))
                
                conn.commit() # Save all committed changes
                flash("Your request to join has been sent!", "success") # Send success message

            # If user tries to join event more than once, raise an error
            except sqlite3.IntegrityError:
                flash("You already requested to join this event.", "warning") # Throw error message

    return redirect(url_for('events')) # Render the events HTML page


# Route for organisations to manage their events
@app.route('/manage_event/<int:event_id>')
def manage_event(event_id):

    # If user not logged in OR user account is not an organisation account (Extra safety check)
    if 'user_id' not in session or session.get('role') != 'organisation':
        flash("Only organisations can manage events.", "danger") # Throw error message
        return redirect(url_for('events')) # Reload page

    # Pythonic way of initalising cursor object
    with get_db() as conn:
        cursor = conn.cursor()

        # Ensure event belongs to this organisation
        # Find organisation id from the user id
        cursor.execute("SELECT organisation_id FROM organisation WHERE user_id = ?", (session['user_id'],))
        org = cursor.fetchone() # Fetch next evailable row

        # Find the record of that event owned by that organisation
        cursor.execute("SELECT * FROM event WHERE event_id = ? AND organisation_id = ?", (event_id, org['organisation_id']))
        event = cursor.fetchone() # Fetch next available row

        # If organisation doesn't own that event, will be empty variable, hence organisation doesn't own event (Extra safety check)
        if not event:
            flash("You cannot manage this event.", "danger") # Throw error message
            return redirect(url_for('events')) # Reload the page

        # Find the requests of the volunteers (With the concatenated names and calculated ages, as per requirements) TOOK SO LONG
        cursor.execute("""
            SELECT er.request_id, er.status, v.first_name || ' ' || v.last_name AS full_name, CAST((julianday('now') - julianday(v.dob)) / 365 AS INT) AS age, u.email
            FROM event_request er
            INNER JOIN volunteer v ON er.volunteer_id = v.volunteer_id
            INNER JOIN user u ON v.user_id = u.user_id
            WHERE er.event_id = ?""", (event_id,))
        
        requests = cursor.fetchall() # Put all requests as dictionaries in a list

        # Display all volunteers who are currently involved with the event
        cursor.execute("""
            SELECT v.first_name || ' ' || v.last_name AS full_name, CAST((julianday('now') - julianday(v.dob)) / 365 AS INT) AS age, u.email
            FROM volunteer_event ve
            JOIN volunteer v ON ve.volunteer_id = v.volunteer_id
            JOIN user u ON v.user_id = u.user_id
            WHERE ve.event_id = ?""", (event_id,))
        
        attendees = cursor.fetchall() # Put all attendees as dictionaries in a list

        # Find the average age of attendees on the bottom, as per requirements
        cursor.execute("""
            SELECT ROUND(AVG((julianday('now') - julianday(v.dob)) / 365), 1) AS avg_age
            FROM volunteer_event ve
            JOIN volunteer v ON ve.volunteer_id = v.volunteer_id
            WHERE ve.event_id = ?""", (event_id,))
        
        avg_age_row = cursor.fetchone() # Fetch next available row

        # If the average age exists, then save it into variable, if not, initialise the variable as None (For the HTML template)
        avg_age = avg_age_row['avg_age'] if avg_age_row and avg_age_row['avg_age'] else None

    # Render the actual HTML page to manage the events
    return render_template("manage_event.html",
                           event=event,
                           requests=requests,
                           attendees=attendees,
                           avg_age=avg_age)


# Route for handling requests
@app.route('/handle_request/<int:request_id>/<string:action>', methods=['POST'])
def handle_request(request_id, action):

    # If user not logged in OR user account not organisation account, restrict from accessing 
    if 'user_id' not in session or session.get('role') != 'organisation':
        flash("Only organisations can handle requests.", "danger") # Throw error message
        return redirect(url_for('events')) # Redirect user back to the events page

    # Pythonic way of initialising cursor object
    with get_db() as conn:
        cursor = conn.cursor()

        # Retrieve the actual request from the volunteer for that event
        cursor.execute("SELECT * FROM event_request WHERE request_id = ?", (request_id,))
        request = cursor.fetchone() # Fetch next available row

        # If no request, then raise an error instead of crashing app (Extra safety check)
        if not request:
            flash("Request not found.", "danger") # Throw error message
            return redirect(url_for('events')) # Redirect user back to the events page

        # If organisation accepts the volunteer
        if action == "accept":
            # Update the request status in the table
            cursor.execute("UPDATE event_request SET status = 'accepted' WHERE request_id = ?", (request_id,))

            # Add the volunteer to the event (OR IGNORE for extra safety check if volunteer already added)
            cursor.execute("""
                INSERT OR IGNORE INTO volunteer_event (volunteer_id, event_id)VALUES (?, ?)""", 
                (request['volunteer_id'], request['event_id']))

            flash("Volunteer accepted and added to event.", "success") # Throw success message

        # If organisation declines volunteer
        elif action == "decline":
            # Update the request status in the table
            cursor.execute("UPDATE event_request SET status = 'declined' WHERE request_id = ?", (request_id,))

            flash("Volunteer request declined.", "info") # Throw message

        conn.commit() # Update all changes

    return redirect(url_for('manage_event', event_id=request['event_id'])) # Render the actual HTML page


# Route for the user to update their skills (Connected with the 'my_account' route)
@app.route('/update_skills', methods=['POST'])
def update_skills():

    # If user not logged in OR the user account is not a volunteer account, restrict them from trying to update skills
    if 'user_id' not in session or session.get('role') != 'volunteer':
        flash("Only volunteers can update skills.", "danger") # Throw error message
        return redirect(url_for('my_account')) # Redirect user back to the information-updating page

    user_id = session['user_id'] # If logged in, update session

    # Pythonic way of initialising cursor object
    with get_db() as conn:
        cursor = conn.cursor()

        # Double-check this user is really a volunteer, by trying to get the volunteer id from the user id
        cursor.execute("SELECT volunteer_id FROM volunteer WHERE user_id = ?", (user_id,))
        volunteer = cursor.fetchone() # Fetch next available row

        # If not a volunteer, then throw an error before it crashes the app
        if not volunteer:
            flash("Volunteer record not found.", "danger") # Throw error message 
            return redirect(url_for('my_account')) # Redirect user back to the my_account page

        volunteer_id = volunteer['volunteer_id'] # Put the volunteer_id into a separate variable, easier to use

        # Debugging purposes (DON'T LEAVE IN)
        print(f"Updating skills for volunteer_id={volunteer_id}, user_id={user_id}")

        # Get submitted skills from the form as a list
        selected_skills = request.form.getlist("skills")
        print("Selected skills:", selected_skills) # Debugging purposes (DON'T LEAVE IN)

        # Enforce max 3 skils only, if more than 3, raise an error
        if len(selected_skills) > 3:
            flash("You can only select up to 3 skills.", "warning") # Throw a warning message
            return redirect(url_for('my_account')) # Reload the page

        # If successful in selecting, delete old records of the users skills
        cursor.execute("DELETE FROM volunteer_skill WHERE volunteer_id = ?", (volunteer_id,))

        # Insert new records of the users skills (Technically updates them)
        for skill_id in selected_skills: # Loop through every skill and inserts it (Ensures atomicity IM COOKING)
            cursor.execute("INSERT INTO volunteer_skill (volunteer_id, skill_id) VALUES (?, ?)",(volunteer_id, skill_id))

        conn.commit() # Commit changes
        flash("Skills updated successfully.", "success") # Throw success message

    return redirect(url_for('my_account')) # Render actual HTML page



# Checks if script is run directly (Not imported)
if __name__ == "__main__":
    init_db() # Initialise database
    app.run(debug=True) # Runs the Flask application with debug mode enabled
