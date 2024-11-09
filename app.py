import os
from datetime import timedelta,datetime
from flask import Flask, request, jsonify, session, render_template, redirect, url_for,flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
app = Flask(__name__)
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST', '127.0.0.1')

app.config['MYSQL_USER'] = os.getenv('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD', 'Speed@2607')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB', 'contactdb')
app.config['MYSQL_PORT'] = 3306 
app.secret_key = os.getenv('SECRET_KEY', 'Speed@2607')


mysql = MySQL(app)

# Middleware to check if logged in
# Middleware to check if logged in and session expiry
def is_logged_in():
    # Check if user_id exists in session
    if 'user_id' not in session:
        return False

    # Check if the session has expired (24-hour check)
    login_time = session.get('login_time')
    if login_time:
        login_time = datetime.strptime(login_time, '%Y-%m-%d %H:%M:%S')
        if datetime.now() > login_time + timedelta(hours=24):
            # If 24 hours have passed, clear the session and return False
            session.clear()
            return False

    return True



@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        identifier = request.form['identifier']
        new_password = request.form['new_password']

        # Hash the new password for security
        hashed_password = generate_password_hash(new_password)

        # Update the password in the signup table based on email or username
        cursor = mysql.connection.cursor()
        query = '''UPDATE signup 
                   SET password = %s 
                   WHERE email = %s OR username = %s'''
        cursor.execute(query, (hashed_password, identifier, identifier))
        mysql.connection.commit()
        cursor.close()

        flash("Your password has been successfully updated!", "success")
        return redirect(url_for('forgot_password'))  # Redirect to display the success message

    return render_template('forgot_password.html')



# Login route
@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        identifier = request.form['identifier']  # Email or username
        password = request.form['password']

        cursor = mysql.connection.cursor()
        cursor.execute('''SELECT * FROM signup WHERE email = %s OR username = %s''', (identifier, identifier))
        user = cursor.fetchone()
        cursor.close()

        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            return redirect(url_for('get_contacts'))
        else:
            return render_template('signin.html', error="Invalid email/username or password")

    return render_template('signin.html')

# Signup route
@app.route('/', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        cursor = mysql.connection.cursor()
        cursor.execute('''INSERT INTO signup (username, email, password) VALUES (%s, %s, %s)''', 
                       (username, email, password))
        mysql.connection.commit()
        cursor.close()
        return redirect(url_for('signin'))

    return render_template('signup.html')


# Get notifications for upcoming important dates
@app.route('/notifications')
def get_notifications():
    if not is_logged_in():
        return redirect(url_for('signin'))

    # Fetch the upcoming important dates from the database
    cursor = mysql.connection.cursor()
    cursor.execute('''SELECT * FROM important_dates 
                      WHERE user_id = %s AND important_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)''',
                   (session['user_id'],))
    upcoming_dates = cursor.fetchall()
    cursor.close()

    # Render the template with the upcoming important dates
    return render_template('notifications.html', notifications=upcoming_dates)


# Create contact route
@app.route('/contacts', methods=['GET', 'POST'])
def create_contact():
    if not is_logged_in():
        return redirect(url_for('signin'))

    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        phone_number = request.form['phone_number']
        email = request.form['email']
        address = request.form['address']
        is_favorite = 1 if request.form.get('is_favorite') == 'on' else 0
        group_name = request.form.get('group_name')
        blood_group = request.form.get('blood_group')

        cursor = mysql.connection.cursor()
        
        # Check if a contact with the same name and phone number already exists
        cursor.execute('''SELECT * FROM contact WHERE first_name = %s OR last_name = %s OR phone_number = %s''',
                       (first_name, last_name, phone_number))
        existing_contact = cursor.fetchone()

        if existing_contact:
            # Contact with the same name and phone number already exists
            cursor.close()
            error_message = "A contact with the same name and phone number already exists."
            return render_template('create_contact.html', error_message=error_message)
        
        # Insert the new contact
        cursor.execute('''INSERT INTO contact (user_id, first_name, last_name, phone_number, email, address, is_favorite, group_name, blood_group)
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                       (session['user_id'], first_name, last_name, phone_number, email, address, is_favorite, group_name, blood_group))
        mysql.connection.commit()
        cursor.close()
        return redirect(url_for('get_contacts'))

    return render_template('create_contact.html')
# Add important date to contact
@app.route('/contacts/<int:contact_id>/add_important_date', methods=['POST'])
def add_important_date(contact_id):
    if not is_logged_in():
        return redirect(url_for('signin'))

    important_date = request.form['important_date']
    note = request.form['note']

    cursor = mysql.connection.cursor()
    cursor.execute('''INSERT INTO important_dates (contact_id, user_id, important_date, note)
                      VALUES (%s, %s, %s, %s)''',
                   (contact_id, session['user_id'], important_date, note))
    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('get_contacts'))

# Get notifications for upcoming important dates

# Delete outdated important dates
@app.before_request
def delete_outdated_dates():
    cursor = mysql.connection.cursor()
    cursor.execute('DELETE FROM important_dates WHERE important_date < CURDATE()')
    mysql.connection.commit()
    cursor.close()
@app.route('/notification/<int:notification_id>')
def view_notification(notification_id):
    if not is_logged_in():
        return redirect(url_for('signin'))
    
    cursor = mysql.connection.cursor()
    try:
        # Fetch the specific notification details, ensuring it's not outdated
        cursor.execute('''
            SELECT * FROM important_dates 
            WHERE id = %s AND user_id = %s AND important_date >= CURDATE()
        ''', (notification_id, session['user_id']))
        notification = cursor.fetchone()

        if notification:
            # Mark the notification as seen if found
            cursor.execute('''
                UPDATE important_dates 
                SET seen = 1 
                WHERE id = %s AND user_id = %s
            ''', (notification_id, session['user_id']))
            mysql.connection.commit()
            
            # Fetch the associated contact details
            contact_id = notification[1]  # Assuming the contact_id is stored in the notification table
            cursor.execute('SELECT * FROM contact WHERE contact_id = %s AND user_id = %s', 
                           (contact_id, session['user_id']))
            contact = cursor.fetchone()
        else:
            contact = None  # No contact data if notification not found

        cursor.close()

        if notification:
            # Render the template with both notification and contact details
            return render_template('notification_detail.html', notification=notification, contact=contact)
        else:
            # Redirect to notifications page if not found
            return redirect(url_for('get_notifications'))
    except Exception as e:
        print(f"Error: {e}")
        return "Internal Server Error", 500

@app.route('/contacts/update/<int:contact_id>', methods=['GET', 'POST'])
def update_contact(contact_id):
    if not is_logged_in():
        return redirect(url_for('signin'))

    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM contact WHERE contact_id = %s AND user_id = %s', (contact_id, session['user_id']))
    contact = cursor.fetchone()

    if request.method == 'POST':
        is_favorite = 1 if request.form.get('is_favorite') == 'on' else 0
        blood_group = request.form.get('blood_group')  # Get the blood group from form input
        cursor.execute('''UPDATE contact 
                          SET first_name = %s, last_name = %s, phone_number = %s, 
                              email = %s, address = %s, is_favorite = %s, group_name = %s, blood_group = %s
                          WHERE contact_id = %s AND user_id = %s''',
                       (request.form['first_name'], request.form['last_name'],
                        request.form['phone_number'], request.form['email'],
                        request.form['address'], is_favorite, request.form['group_name'], blood_group, contact_id, session['user_id']))
        mysql.connection.commit()
        cursor.close()
        return redirect(url_for('get_contacts'))

    return render_template('update_contact.html', contact=contact)
@app.route('/contacts/list')
def get_contacts():
    if not is_logged_in():
        return redirect(url_for('signin'))

    # Fetching contacts for the current user
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM contact WHERE user_id = %s', (session['user_id'],))
    contacts = cursor.fetchall()
    cursor.close()

    # Fetching upcoming important dates that haven't been seen yet (seen = 0)
    cursor = mysql.connection.cursor()
    cursor.execute('''SELECT * FROM important_dates 
                      WHERE user_id = %s 
                      AND important_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)
                      AND seen = 0''',
                   (session['user_id'],))
    upcoming_dates = cursor.fetchall()
    cursor.close()

    # Fetching user details
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM signup WHERE user_id = %s', (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()

    # Fetching the count of contacts for the user
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT COUNT(*) FROM contact WHERE user_id = %s', (session['user_id'],))
    contact_count = cursor.fetchone()[0]
    cursor.close()

    # Fetching the count of groups for the user
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT COUNT(*) FROM contact_labels WHERE user_id = %s', (session['user_id'],))
    group_count = cursor.fetchone()[0]
    cursor.close()

    # Returning the updated data to the template
    return render_template('contact_list.html',
                           contacts=contacts,
                           notifications=upcoming_dates,
                           user=user,
                           contact_count=contact_count,
                           group_count=group_count)

# Get a single contact by ID
@app.route('/contacts/<int:contact_id>')
def get_contact(contact_id):
    if not is_logged_in():
        return redirect(url_for('signin'))

    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM contact WHERE contact_id = %s AND user_id = %s', (contact_id, session['user_id']))
    contact = cursor.fetchone()
    cursor.close()

    if contact:
        return render_template('contact_detail.html', contact=contact)
    else:
        return jsonify({'message': 'Contact not found'}), 404

# Delete contact by ID
@app.route('/contacts/delete/<int:contact_id>')
def delete_contact(contact_id):
    if not is_logged_in():
        return redirect(url_for('signin'))

    cursor = mysql.connection.cursor()
    cursor.execute('DELETE FROM contact WHERE contact_id = %s AND user_id = %s', (contact_id, session['user_id']))
    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('get_contacts'))
@app.route('/contacts/search', methods=['GET'])
def search_contacts():
    if not is_logged_in():
        return redirect(url_for('signin'))

    query = request.args.get('query', '')
    filter_type = request.args.get('filter', 'name')

    cursor = mysql.connection.cursor()

    # Fetch contacts based on filter type
    if filter_type == 'name':
        cursor.execute('''SELECT * FROM contact WHERE user_id = %s AND 
                          (first_name LIKE %s OR last_name LIKE %s)''',
                       (session['user_id'], f'%{query}%', f'%{query}%'))
    elif filter_type == 'blood_group':
        cursor.execute('''SELECT * FROM contact WHERE user_id = %s AND 
                          blood_group = %s''',
                       (session['user_id'], query))
    elif filter_type == 'place':
        cursor.execute('''SELECT * FROM contact WHERE user_id = %s AND 
                          address LIKE %s''',
                       (session['user_id'], f'%{query}%'))
    else:
        cursor.execute('SELECT * FROM contact WHERE user_id = %s', (session['user_id'],))

    # Fetch all matching contacts
    contacts = cursor.fetchall()

    # Fetch upcoming important dates within the next 7 days
    cursor = mysql.connection.cursor()
    cursor.execute('''SELECT * FROM important_dates 
                      WHERE user_id = %s 
                      AND important_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)
                      AND seen = 0''',  # Filtering to exclude seen notifications
                   (session['user_id'],))
    upcoming_dates = cursor.fetchall()
    cursor.close()

    # Render the contact_list template with contacts and notifications
    return render_template('contact_list.html', contacts=contacts, notifications=upcoming_dates)


@app.route('/groups')
def view_groups():
    if not is_logged_in():
        return redirect(url_for('signin'))

    cursor = mysql.connection.cursor()
    cursor.execute('SELECT label_name FROM contact_labels WHERE user_id = %s', (session['user_id'],))
    groups = cursor.fetchall()
    cursor.close()

    return render_template('groups.html', groups=groups)

# Create a new group
@app.route('/create_group', methods=['POST'])
def create_group():
    if not is_logged_in():
        return jsonify({'message': 'Unauthorized'}), 401

    group_name = request.form.get('group_name')

    if not group_name:
        return jsonify({'message': 'Group name is required'}), 400

    cursor = mysql.connection.cursor()
    cursor.execute('INSERT INTO contact_labels (user_id, label_name) VALUES (%s, %s)', 
                   (session['user_id'], group_name))
    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('view_groups'))
@app.route('/contacts/favorites')
def view_favorites():
    if not is_logged_in():
        return redirect(url_for('signin'))

    cursor = mysql.connection.cursor()
    cursor.execute('''SELECT * FROM contact 
                      WHERE user_id = %s AND is_favorite = 1''', 
                   (session['user_id'],))
    favorite_contacts = cursor.fetchall()
    cursor.close()

    return render_template('favorites.html', contacts=favorite_contacts)
# Assign contacts to a group
@app.route('/groups/assign/<string:group_name>', methods=['GET', 'POST'])
def assign_contacts(group_name):
    if not is_logged_in():
        return redirect(url_for('signin'))

    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM contact WHERE user_id = %s', (session['user_id'],))
    contacts = cursor.fetchall()

    if request.method == 'POST':
        selected_contacts = request.form.getlist('contacts')
        for contact_id in selected_contacts:
            cursor.execute('''UPDATE contact 
                              SET group_name = %s 
                              WHERE contact_id = %s AND user_id = %s''',
                           (group_name, contact_id, session['user_id']))

        mysql.connection.commit()
        cursor.close()
        return redirect(url_for('view_groups'))

    cursor.execute('SELECT * FROM contact_labels WHERE label_name = %s AND user_id = %s', (group_name, session['user_id']))
    group = cursor.fetchone()
    cursor.close()

    return render_template('assign_contacts.html', contacts=contacts, group_name=group_name, group=group)

# View contacts in a specific group
@app.route('/view_contacts/<string:group_name>')
def view_contacts(group_name):
    if not is_logged_in():
        return redirect(url_for('signin'))

    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM contact WHERE group_name = %s AND user_id = %s', (group_name, session['user_id']))
    contacts = cursor.fetchall()
    cursor.close()

    return render_template('view_contacts.html', contacts=contacts,group_name=group_name)
# Create a group and assign contacts
@app.route('/create_group_and_assign', methods=['GET'])
def create_group_and_assign():
    if not is_logged_in():
        return redirect(url_for('signin'))

    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM contact WHERE user_id = %s', (session['user_id'],))
    contacts = cursor.fetchall()
    cursor.close()

    return render_template('create_group_and_assign.html', contacts=contacts)

@app.route('/logout')
def logout():
    if 'user_id' in session:
        user_id = session['user_id']
        session.pop('user_id', None)
        
        # Reset all notifications to unseen for this user
        cursor = mysql.connection.cursor()
        cursor.execute('UPDATE important_dates SET seen = 0 WHERE user_id = %s', (user_id,))
        mysql.connection.commit()
        cursor.close()
    
    return redirect(url_for('signin'))
@app.route('/contacts/remove_favorite/<int:contact_id>', methods=['POST'])
def remove_favorite(contact_id):
    if not is_logged_in():
        return redirect(url_for('signin'))

    cursor = mysql.connection.cursor()
    cursor.execute('''UPDATE contact 
                      SET is_favorite = 0 
                      WHERE contact_id = %s AND user_id = %s''', 
                   (contact_id, session['user_id']))
    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('view_favorites'))
@app.route('/groups/remove_contact/<int:contact_id>/<string:group_name>', methods=['POST'])
def remove_from_group(contact_id, group_name):
    if not is_logged_in():
        return redirect(url_for('signin'))

    cursor = mysql.connection.cursor()
    cursor.execute('''UPDATE contact 
                      SET group_name = '-'
                      WHERE contact_id = %s AND group_name = %s AND user_id = %s''', 
                   (contact_id, group_name, session['user_id']))
    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('view_contacts', group_name=group_name))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # Use PORT environment variable or default to 5000
    app.run(host='0.0.0.0', port=port)
    
