from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
import hashlib
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = os.urandom(24)


def get_db_connection():
    connection = mysql.connector.connect(
        host='localhost',
        user='root',
        password='your_password',
        database='volunteer_platform'
    )
    return connection


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') != 'admin':
            flash('You do not have permission to access this page', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def volunteer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') != 'volunteer':
            flash('You do not have permission to access this page', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def charity_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') != 'charity':
            flash('You do not have permission to access this page', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def home():

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    cursor.execute("""
    SELECT e.*, cp.name as charity_name 
    FROM events e
    JOIN charity_profiles cp ON e.charity_id = cp.id
    WHERE e.status = 'approved' AND e.end_datetime > NOW()
    ORDER BY e.start_datetime
    LIMIT 6
    """)
    
    events = cursor.fetchall()
    cursor.close()
    connection.close()
    
    return render_template('home.html', events=events)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, hashed_password))
        user = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if user:
            if user['status'] == 'suspended':
                flash('Your account has been suspended. Please contact the administrator.', 'error')
                return redirect(url_for('login'))
            
            if user['status'] == 'pending':
                flash('Your account is pending approval. Please wait for administrator approval.', 'error')
                return redirect(url_for('login'))
            
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['user_type'] = user['user_type']
            
            if user['user_type'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['user_type'] == 'volunteer':
                return redirect(url_for('volunteer_dashboard'))
            elif user['user_type'] == 'charity':
                return redirect(url_for('charity_dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s AND user_type = 'admin'", 
                      (username, hashed_password))
        user = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['user_type'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials', 'error')
    
    return render_template('admin_login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user_type = request.form['user_type']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('signup'))
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        try:

            cursor.execute("""
            INSERT INTO users (username, email, password, user_type)
            VALUES (%s, %s, %s, %s)
            """, (username, email, hashed_password, user_type))
            
            user_id = cursor.lastrowid
            

            if user_type == 'volunteer':
                first_name = request.form['first_name']
                last_name = request.form['last_name']
                
                cursor.execute("""
                INSERT INTO volunteer_profiles (user_id, first_name, last_name)
                VALUES (%s, %s, %s)
                """, (user_id, first_name, last_name))
                
            elif user_type == 'charity':
                charity_name = request.form['charity_name']
                description = request.form['description']
                
                cursor.execute("""
                INSERT INTO charity_profiles (user_id, name, description)
                VALUES (%s, %s, %s)
                """, (user_id, charity_name, description))
            
            connection.commit()
            flash('Registration successful! Please wait for admin approval.', 'success')
            return redirect(url_for('login'))
            
        except mysql.connector.Error as err:
            connection.rollback()
            if err.errno == 1062:
                flash('Username or email already exists', 'error')
            else:
                flash(f'An error occurred: {err}', 'error')
        finally:
            cursor.close()
            connection.close()
    
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('home'))


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    

    cursor.execute("SELECT COUNT(*) as volunteer_count FROM users WHERE user_type = 'volunteer'")
    volunteer_count = cursor.fetchone()['volunteer_count']
    
    cursor.execute("SELECT COUNT(*) as charity_count FROM users WHERE user_type = 'charity'")
    charity_count = cursor.fetchone()['charity_count']
    
    cursor.execute("SELECT COUNT(*) as event_count FROM events")
    event_count = cursor.fetchone()['event_count']
    
    cursor.execute("SELECT COUNT(*) as registration_count FROM event_registrations")
    registration_count = cursor.fetchone()['registration_count']
    
    cursor.execute("SELECT COUNT(*) as pending_user_count FROM users WHERE status = 'pending'")
    pending_user_count = cursor.fetchone()['pending_user_count']
    
    cursor.execute("SELECT COUNT(*) as pending_event_count FROM events WHERE status = 'pending'")
    pending_event_count = cursor.fetchone()['pending_event_count']
    
    cursor.close()
    connection.close()
    
    stats = {
        'volunteer_count': volunteer_count,
        'charity_count': charity_count,
        'event_count': event_count,
        'registration_count': registration_count,
        'pending_user_count': pending_user_count,
        'pending_event_count': pending_event_count
    }
    
    return render_template('admin/dashboard.html', stats=stats)

@app.route('/admin/users')
@admin_required
def admin_users():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    cursor.execute("""
    SELECT u.*, 
        CASE 
            WHEN u.user_type = 'volunteer' THEN CONCAT(vp.first_name, ' ', vp.last_name)
            WHEN u.user_type = 'charity' THEN cp.name
            ELSE u.username
        END as display_name
    FROM users u
    LEFT JOIN volunteer_profiles vp ON u.id = vp.user_id AND u.user_type = 'volunteer'
    LEFT JOIN charity_profiles cp ON u.id = cp.user_id AND u.user_type = 'charity'
    ORDER BY u.created_at DESC
    """)
    
    users = cursor.fetchall()
    cursor.close()
    connection.close()
    
    return render_template('admin/users.html', users=users)

@app.route('/admin/user/<int:user_id>/update_status', methods=['POST'])
@admin_required
def update_user_status(user_id):
    new_status = request.form['status']
    
    connection = get_db_connection()
    cursor = connection.cursor()
    
    cursor.execute("UPDATE users SET status = %s WHERE id = %s", (new_status, user_id))
    connection.commit()
    
    cursor.close()
    connection.close()
    
    flash(f'User status updated to {new_status}', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/events')
@admin_required
def admin_events():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    
    cursor.execute("""
    SELECT e.*, cp.name as charity_name 
    FROM events e
    JOIN charity_profiles cp ON e.charity_id = cp.id
    ORDER BY e.created_at DESC
    """)
    
    events = cursor.fetchall()
    cursor.close()
    connection.close()
    

    now = datetime.now()
    
    return render_template('admin/events.html', events=events, now=now)

@app.route('/admin/event/<int:event_id>/update_status', methods=['POST'])
@admin_required
def update_event_status(event_id):
    new_status = request.form['status']
    
    connection = get_db_connection()
    cursor = connection.cursor()
    
    cursor.execute("UPDATE events SET status = %s WHERE id = %s", (new_status, event_id))
    connection.commit()
    
    cursor.close()
    connection.close()
    
    flash(f'Event status updated to {new_status}', 'success')
    return redirect(url_for('admin_events'))

@app.route('/admin/registrations')
@admin_required
def admin_registrations():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    

    cursor.execute("""
    SELECT er.*, e.name as event_name, cp.name as charity_name, 
           CONCAT(vp.first_name, ' ', vp.last_name) as volunteer_name
    FROM event_registrations er
    JOIN events e ON er.event_id = e.id
    JOIN charity_profiles cp ON e.charity_id = cp.id
    JOIN volunteer_profiles vp ON er.volunteer_id = vp.id
    ORDER BY er.registered_at DESC
    """)
    
    registrations = cursor.fetchall()
    cursor.close()
    connection.close()
    

    now = datetime.now()
    
    return render_template('admin/registrations.html', registrations=registrations, now=now)

@app.route('/admin/registration/<int:registration_id>/update_status', methods=['POST'])
@admin_required
def update_registration_status(registration_id):
    new_status = request.form['status']
    
    connection = get_db_connection()
    cursor = connection.cursor()
    
    cursor.execute("UPDATE event_registrations SET status = %s WHERE id = %s", (new_status, registration_id))
    connection.commit()
    

    if new_status == 'completed':
        cursor.execute("""
        SELECT er.volunteer_id, e.id as event_id, 
               TIMESTAMPDIFF(HOUR, e.start_datetime, e.end_datetime) as duration
        FROM event_registrations er
        JOIN events e ON er.event_id = e.id
        WHERE er.id = %s
        """, (registration_id,))
        
        result = cursor.fetchone()
        if result:
            volunteer_id = result[0]
            duration = result[2]
            

            cursor.execute("""
            UPDATE volunteer_profiles
            SET hours_contributed = hours_contributed + %s
            WHERE id = %s
            """, (duration, volunteer_id))
            
            connection.commit()
    
    cursor.close()
    connection.close()
    
    flash(f'Registration status updated to {new_status}', 'success')
    return redirect(url_for('admin_registrations'))


@app.route('/volunteer/dashboard')
@volunteer_required
def volunteer_dashboard():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    

    cursor.execute("""
    SELECT * FROM volunteer_profiles WHERE user_id = %s
    """, (session['user_id'],))
    
    profile = cursor.fetchone()
    

    cursor.execute("""
    SELECT e.*, cp.name as charity_name, er.status as registration_status
    FROM event_registrations er
    JOIN events e ON er.event_id = e.id
    JOIN charity_profiles cp ON e.charity_id = cp.id
    WHERE er.volunteer_id = %s AND e.end_datetime > NOW()
    ORDER BY e.start_datetime
    """, (profile['id'],))
    
    upcoming_events = cursor.fetchall()
    

    cursor.execute("""
    SELECT e.name as event_name, er.status, er.registered_at
    FROM event_registrations er
    JOIN events e ON er.event_id = e.id
    WHERE er.volunteer_id = %s
    ORDER BY er.registered_at DESC
    LIMIT 5
    """, (profile['id'],))
    
    notifications = cursor.fetchall()
    
    cursor.close()
    connection.close()
    
    return render_template('volunteer/dashboard.html', 
                          profile=profile, 
                          upcoming_events=upcoming_events, 
                          notifications=notifications)

@app.route('/volunteer/events')
@volunteer_required
def volunteer_events():

    cause = request.args.get('cause', '')
    location = request.args.get('location', '')
    date = request.args.get('date', '')
    
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    

    cursor.execute("SELECT id FROM volunteer_profiles WHERE user_id = %s", (session['user_id'],))
    volunteer = cursor.fetchone()
    volunteer_id = volunteer['id']
    

    query = """
    SELECT e.*, cp.name as charity_name,
           CASE WHEN er.id IS NOT NULL THEN TRUE ELSE FALSE END as is_registered
    FROM events e
    JOIN charity_profiles cp ON e.charity_id = cp.id
    LEFT JOIN event_registrations er ON e.id = er.event_id AND er.volunteer_id = %s
    WHERE e.status = 'approved' AND e.end_datetime > NOW()
    """
    
    params = [volunteer_id]
    

    if cause:
        query += " AND e.description LIKE %s"
        params.append(f'%{cause}%')
    
    if location:
        query += " AND e.location LIKE %s"
        params.append(f'%{location}%')
    
    if date:
        query += " AND DATE(e.start_datetime) = %s"
        params.append(date)
    
    query += " ORDER BY e.start_datetime"
    
    cursor.execute(query, tuple(params))
    events = cursor.fetchall()
    

    cursor.execute("SELECT DISTINCT location FROM events WHERE status = 'approved'")
    locations = [row['location'] for row in cursor.fetchall()]
    
    cursor.close()
    connection.close()
    
    return render_template('volunteer/events.html', 
                          events=events, 
                          locations=locations,
                          selected_cause=cause,
                          selected_location=location,
                          selected_date=date)

@app.route('/volunteer/event/<int:event_id>')
@volunteer_required
def volunteer_event_details(event_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    

    cursor.execute("SELECT id FROM volunteer_profiles WHERE user_id = %s", (session['user_id'],))
    volunteer = cursor.fetchone()
    volunteer_id = volunteer['id']
    

    cursor.execute("""
    SELECT e.*, cp.name as charity_name, cp.description as charity_description,
           CASE WHEN er.id IS NOT NULL THEN er.status ELSE NULL END as registration_status
    FROM events e
    JOIN charity_profiles cp ON e.charity_id = cp.id
    LEFT JOIN event_registrations er ON e.id = er.event_id AND er.volunteer_id = %s
    WHERE e.id = %s
    """, (volunteer_id, event_id))
    
    event = cursor.fetchone()
    
    if not event:
        cursor.close()
        connection.close()
        flash('Event not found', 'error')
        return redirect(url_for('volunteer_events'))
    
    cursor.close()
    connection.close()
    
    return render_template('volunteer/event_details.html', event=event)

@app.route('/volunteer/event/<int:event_id>/register', methods=['POST'])
@volunteer_required
def volunteer_register_event(event_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    

    cursor.execute("SELECT id FROM volunteer_profiles WHERE user_id = %s", (session['user_id'],))
    volunteer = cursor.fetchone()
    volunteer_id = volunteer['id']
    
    try:

        cursor.execute("""
        SELECT * FROM event_registrations 
        WHERE event_id = %s AND volunteer_id = %s
        """, (event_id, volunteer_id))
        
        existing = cursor.fetchone()
        
        if existing:
            flash('You are already registered for this event', 'info')
        else:
            # Register for the event
            cursor.execute("""
            INSERT INTO event_registrations (event_id, volunteer_id)
            VALUES (%s, %s)
            """, (event_id, volunteer_id))
            
            connection.commit()
            flash('Successfully registered for the event', 'success')
    
    except mysql.connector.Error as err:
        connection.rollback()
        flash(f'An error occurred: {err}', 'error')
    
    cursor.close()
    connection.close()
    
    return redirect(url_for('volunteer_event_details', event_id=event_id))

@app.route('/volunteer/my_events')
@volunteer_required
def volunteer_my_events():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT id FROM volunteer_profiles WHERE user_id = %s", (session['user_id'],))
    volunteer = cursor.fetchone()
    volunteer_id = volunteer['id']
    

    cursor.execute("""
    SELECT e.*, cp.name as charity_name, er.status as registration_status
    FROM event_registrations er
    JOIN events e ON er.event_id = e.id
    JOIN charity_profiles cp ON e.charity_id = cp.id
    WHERE er.volunteer_id = %s AND e.end_datetime > NOW()
    ORDER BY e.start_datetime
    """, (volunteer_id,))
    
    upcoming_events = cursor.fetchall()
    

    cursor.execute("""
    SELECT e.*, cp.name as charity_name, er.status as registration_status
    FROM event_registrations er
    JOIN events e ON er.event_id = e.id
    JOIN charity_profiles cp ON e.charity_id = cp.id
    WHERE er.volunteer_id = %s AND e.end_datetime <= NOW()
    ORDER BY e.start_datetime DESC
    """, (volunteer_id,))
    
    past_events = cursor.fetchall()
    
    cursor.close()
    connection.close()
    
    return render_template('volunteer/my_events.html', 
                          upcoming_events=upcoming_events, 
                          past_events=past_events)

@app.route('/volunteer/edit-profile', methods=['GET', 'POST'])
@volunteer_required
def volunteer_edit_profile():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    

    cursor.execute("""
    SELECT * FROM volunteer_profiles WHERE user_id = %s
    """, (session['user_id'],))
    
    profile = cursor.fetchone()
    
    if request.method == 'POST':
        # Get form data
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        bio = request.form['bio']
        skills = request.form['skills']
        
        # Update profile
        cursor.execute("""
        UPDATE volunteer_profiles
        SET first_name = %s, last_name = %s, bio = %s, skills = %s
        WHERE user_id = %s
        """, (first_name, last_name, bio, skills, session['user_id']))
        
        connection.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('volunteer_dashboard'))
    
    cursor.close()
    connection.close()
    
    return render_template('volunteer/edit_profile.html', profile=profile)

@app.route('/charity/edit_profile', methods=['GET', 'POST'])
def charity_edit_profile():
    if 'user_id' not in session or session.get('user_type') != 'charity':
        flash('Please log in as a charity to access this page', 'error')
        return redirect(url_for('login'))
    
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    

    cursor.execute("""
        SELECT c.*, u.email 
        FROM charity_profiles c 
        JOIN users u ON c.user_id = u.id 
        WHERE c.user_id = %s
    """, (session['user_id'],))
    charity = cursor.fetchone()
    
    if request.method == 'POST':
        # Update charity profile
        name = request.form['name']
        description = request.form['description']
        address = request.form['address']
        phone = request.form['phone']
        
        cursor.execute("""
            UPDATE charity_profiles 
            SET name = %s, description = %s, address = %s, phone = %s
            WHERE user_id = %s
        """, (name, description, address, phone, session['user_id']))
        
        # Update email in users table if changed
        if request.form['email'] != charity['email']:
            cursor.execute("UPDATE users SET email = %s WHERE id = %s", 
                          (request.form['email'], session['user_id']))
        
        connection.commit()
        flash('Profile updated successfully', 'success')
        return redirect(url_for('charity_dashboard'))
    
    connection.close()
    return render_template('charity/edit_profile.html', charity=charity)

@app.route('/charity/dashboard')
@charity_required
def charity_dashboard():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    

    cursor.execute("""
    SELECT * FROM charity_profiles WHERE user_id = %s
    """, (session['user_id'],))
    
    profile = cursor.fetchone()
    

    cursor.execute("""
    SELECT e.*, 
           (SELECT COUNT(*) FROM event_registrations WHERE event_id = e.id) as signup_count
    FROM events e
    WHERE e.charity_id = %s AND e.end_datetime > NOW()
    ORDER BY e.start_datetime
    """, (profile['id'],))
    
    upcoming_events = cursor.fetchall()
    

    cursor.execute("""
    SELECT COUNT(DISTINCT volunteer_id) as total_volunteers
    FROM event_registrations er
    JOIN events e ON er.event_id = e.id
    WHERE e.charity_id = %s
    """, (profile['id'],))
    
    total_volunteers = cursor.fetchone()['total_volunteers']
    

    cursor.execute("""
    SELECT COUNT(*) as total_events
    FROM events
    WHERE charity_id = %s
    """, (profile['id'],))
    
    total_events = cursor.fetchone()['total_events']
    
    cursor.close()
    connection.close()
    
    return render_template('charity/dashboard.html', 
                          profile=profile, 
                          upcoming_events=upcoming_events,
                          total_volunteers=total_volunteers,
                          total_events=total_events)

@app.route('/charity/create_event', methods=['GET', 'POST'])
@charity_required
def charity_create_event():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        location = request.form['location']
        start_datetime = request.form['start_datetime']
        end_datetime = request.form['end_datetime']
        required_skills = request.form['required_skills']
        max_volunteers = request.form['max_volunteers']
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        try:

            cursor.execute("SELECT id FROM charity_profiles WHERE user_id = %s", (session['user_id'],))
            charity = cursor.fetchone()
            charity_id = charity[0]
            

            cursor.execute("""
            INSERT INTO events (charity_id, name, description, location, start_datetime, end_datetime, required_skills, max_volunteers)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (charity_id, name, description, location, start_datetime, end_datetime, required_skills, max_volunteers))
            
            connection.commit()
            flash('Event created successfully! It will be reviewed by an administrator.', 'success')
            return redirect(url_for('charity_manage_events'))
            
        except mysql.connector.Error as err:
            connection.rollback()
            flash(f'An error occurred: {err}', 'error')
        finally:
            cursor.close()
            connection.close()
    
    return render_template('charity/create_event.html')

@app.route('/charity/event_volunteers/<int:event_id>')
@charity_required
def charity_event_volunteers(event_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    

    cursor.execute("SELECT id FROM charity_profiles WHERE user_id = %s", (session['user_id'],))
    charity_profile = cursor.fetchone()
    
    if not charity_profile:
        flash('Your charity profile could not be found', 'error')
        return redirect(url_for('charity_dashboard'))
    
    charity_id = charity_profile['id']
    

    cursor.execute("SELECT * FROM events WHERE id = %s AND charity_id = %s", 
                  (event_id, charity_id))
    event = cursor.fetchone()
    
    if not event:
        flash('Event not found or you do not have permission to view it', 'error')
        return redirect(url_for('charity_manage_events'))
    

    cursor.execute("""
        SELECT r.*, u.email, CONCAT(v.first_name, ' ', v.last_name) as volunteer_name, v.phone, v.skills 
        FROM event_registrations r
        JOIN volunteer_profiles v ON r.volunteer_id = v.id
        JOIN users u ON v.user_id = u.id
        WHERE r.event_id = %s
        ORDER BY r.registered_at DESC
    """, (event_id,))
    registrations = cursor.fetchall()
    
    connection.close()
    return render_template('charity/event_volunteers.html', event=event, registrations=registrations)

@app.route('/charity/approve_volunteer/<int:event_id>/<int:registration_id>', methods=['POST'])
@charity_required
def charity_approve_volunteer(event_id, registration_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    

    cursor.execute("SELECT id FROM charity_profiles WHERE user_id = %s", (session['user_id'],))
    charity_profile = cursor.fetchone()
    
    if not charity_profile:
        flash('Your charity profile could not be found', 'error')
        return redirect(url_for('charity_dashboard'))
    
    charity_id = charity_profile['id']
    

    cursor.execute("SELECT * FROM events WHERE id = %s AND charity_id = %s", 
                  (event_id, charity_id))
    event = cursor.fetchone()
    
    if not event:
        flash('Event not found or you do not have permission to modify it', 'error')
        return redirect(url_for('charity_manage_events'))
    

    cursor.execute("UPDATE event_registrations SET status = 'approved' WHERE id = %s AND event_id = %s", 
                  (registration_id, event_id))
    connection.commit()
    
    flash('Volunteer application approved successfully', 'success')
    return redirect(url_for('charity_event_volunteers', event_id=event_id))

@app.route('/charity/reject_volunteer/<int:event_id>/<int:registration_id>', methods=['POST'])
@charity_required
def charity_reject_volunteer(event_id, registration_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    

    cursor.execute("SELECT id FROM charity_profiles WHERE user_id = %s", (session['user_id'],))
    charity_profile = cursor.fetchone()
    
    if not charity_profile:
        flash('Your charity profile could not be found', 'error')
        return redirect(url_for('charity_dashboard'))
    
    charity_id = charity_profile['id']
    

    cursor.execute("SELECT * FROM events WHERE id = %s AND charity_id = %s", 
                  (event_id, charity_id))
    event = cursor.fetchone()
    
    if not event:
        flash('Event not found or you do not have permission to modify it', 'error')
        return redirect(url_for('charity_manage_events'))
    

    cursor.execute("UPDATE event_registrations SET status = 'rejected' WHERE id = %s AND event_id = %s", 
                  (registration_id, event_id))
    connection.commit()
    
    flash('Volunteer application rejected', 'success')
    return redirect(url_for('charity_event_volunteers', event_id=event_id))

@app.route('/charity/manage_events')
@charity_required
def charity_manage_events():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    

    cursor.execute("SELECT id FROM charity_profiles WHERE user_id = %s", (session['user_id'],))
    charity = cursor.fetchone()
    charity_id = charity['id']
    

    cursor.execute("""
    SELECT e.*, 
           (SELECT COUNT(*) FROM event_registrations WHERE event_id = e.id) as signup_count
    FROM events e
    WHERE e.charity_id = %s
    ORDER BY e.start_datetime DESC
    """, (charity_id,))
    
    events = cursor.fetchall()
    
    cursor.close()
    connection.close()
    
    return render_template('charity/manage_events.html', events=events)

@app.route('/charity/edit_event/<int:event_id>', methods=['GET', 'POST'])
@charity_required
def charity_edit_event(event_id):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    

    cursor.execute("SELECT id FROM charity_profiles WHERE user_id = %s", (session['user_id'],))
    charity = cursor.fetchone()
    charity_id = charity['id']
    

    cursor.execute("""
    SELECT * FROM events
    WHERE id = %s AND charity_id = %s
    """, (event_id, charity_id))
    
    event = cursor.fetchone()
    
    if not event:
        cursor.close()
        connection.close()
        flash('Event not found or you do not have permission to edit it', 'error')
        return redirect(url_for('charity_manage_events'))
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        location = request.form['location']
        start_datetime = request.form['start_datetime']
        end_datetime = request.form['end_datetime']
        required_skills = request.form['required_skills']
        max_volunteers = request.form['max_volunteers']
        
        try:

            cursor.execute("""
            UPDATE events 
            SET name = %s, description = %s, location = %s, 
                start_datetime = %s, end_datetime = %s, 
                required_skills = %s, max_volunteers = %s,
                status = 'pending'
            WHERE id = %s AND charity_id = %s
            """, (name, description, location, start_datetime, end_datetime, 
                 required_skills, max_volunteers, event_id, charity_id))
            
            connection.commit()
            flash('Event updated successfully! It will be reviewed by an administrator.', 'success')
            return redirect(url_for('charity_manage_events'))
            
        except mysql.connector.Error as err:
            connection.rollback()
            flash(f'An error occurred: {err}', 'error')
    
    cursor.close()
    connection.close()
    
    return render_template('charity/edit_event.html', event=event)


@app.route('/charity/volunteer_application/<int:registration_id>/update', methods=['POST'])
@charity_required
def charity_update_volunteer_application(registration_id):
    new_status = request.form['status']
    
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    

    cursor.execute("SELECT id FROM charity_profiles WHERE user_id = %s", (session['user_id'],))
    charity = cursor.fetchone()
    charity_id = charity['id']
    

    cursor.execute("""
    SELECT er.*, e.id as event_id
    FROM event_registrations er
    JOIN events e ON er.event_id = e.id
    WHERE er.id = %s AND e.charity_id = %s
    """, (registration_id, charity_id))
    
    registration = cursor.fetchone()
    
    if not registration:
        cursor.close()
        connection.close()
        flash('Registration not found or you do not have permission to update it', 'error')
        return redirect(url_for('charity_manage_events'))
    

    cursor.execute("""
    UPDATE event_registrations
    SET status = %s
    WHERE id = %s
    """, (new_status, registration_id))
    
    connection.commit()
    

    if new_status == 'completed':
        cursor.execute("""
        SELECT e.*, TIMESTAMPDIFF(HOUR, e.start_datetime, e.end_datetime) as duration
        FROM events e
        WHERE e.id = %s AND e.end_datetime <= NOW()
        """, (registration['event_id'],))
        
        event = cursor.fetchone()
        
        if event:

            cursor.execute("""
            UPDATE volunteer_profiles
            SET hours_contributed = hours_contributed + %s
            WHERE id = %s
            """, (event['duration'], registration['volunteer_id']))
            
            connection.commit()
    
    cursor.close()
    connection.close()
    
    flash(f'Volunteer application updated to {new_status}', 'success')
    return redirect(url_for('charity_event_volunteers', event_id=registration['event_id']))

if __name__ == '__main__':
    app.run(debug=True)
