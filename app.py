import os
from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from waitress import serve
app = Flask(__name__)

# Fetch configuration from environment variables
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST', 'localhost')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD', 'Speed@2607')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB', 'contactdb')
app.secret_key = os.getenv('SECRET_KEY', 'Speed@2607')

mysql = MySQL(app)

# Middleware to check if logged in
def is_logged_in():
    return 'user_id' in session

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


@app.route('/notification/<int:notification_id>')
def view_notification(notification_id):
    if not is_logged_in():
        return redirect(url_for('signin'))
    
    cursor = mysql.connection.cursor()
    
    # Fetch the specific notification details
    cursor.execute('''SELECT * FROM important_dates 
                      WHERE id = %s AND user_id = %s''', 
                   (notification_id, session['user_id']))
    notification = cursor.fetchone()
    print(notification)
    if notification:
        # Mark the notification as seen
        cursor.execute('''UPDATE important_dates 
                          SET seen = 1 
                          WHERE id = %s AND user_id = %s''', 
                       (notification_id, session['user_id']))
        mysql.connection.commit()  # Commit the changes to the database
    
    cursor.close()
    
    if notification:
        # Render a template to show the details of the specific notification
        return render_template('notification_detail.html', notification=notification)
    else:
        # If no such notification is found, redirect to the notifications page
        return redirect(url_for('get_notifications'))


# Delete outdated important dates
@app.before_request
def delete_outdated_dates():
    cursor = mysql.connection.cursor()
    cursor.execute('''DELETE FROM important_dates WHERE important_date < CURDATE()''')
    mysql.connection.commit()
    cursor.close()

# Other existing routes like update_contact, get_contacts, etc. go here...

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

# In the contacts route
@app.route('/contacts/list')
def get_contacts():
    if not is_logged_in():
        return redirect(url_for('signin'))

    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM contact WHERE user_id = %s', (session['user_id'],))
    contacts = cursor.fetchall()
    cursor.close()
    cursor = mysql.connection.cursor()
    cursor.execute('''SELECT * FROM important_dates 
                      WHERE user_id = %s AND important_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)''', 
                   (session['user_id'],))
    upcoming_dates = cursor.fetchall()
    cursor.close()

    # Fetch notifications for important dates
   # You can modify this to return the actual data
  
    return render_template('contact_list.html', contacts=contacts, notifications=upcoming_dates)

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
    cursor.execute('''SELECT * FROM important_dates 
                      WHERE user_id = %s AND important_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 7 DAY)''', 
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

    return render_template('view_contacts.html', contacts=contacts)

# View contacts of a group by ID
@app.route('/group/<int:group_id>', methods=['GET'])
def view_group_contacts(group_id):
    group_contacts = fetch_contacts_by_group(group_id)  # Replace with your actual logic to fetch contacts in the group
    return render_template('group_contacts.html', group_contacts=group_contacts)

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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # Use PORT environment variable or default to 5000
    app.run(host='0.0.0.0', port=port)
    
