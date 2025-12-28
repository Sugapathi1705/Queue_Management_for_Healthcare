from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from db import db, init_db, User, Doctor, Appointment, Rating, Message, favorites

app = Flask(__name__)

# Initialize database and login manager
init_db(app)

# Routes
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been successfully logged out.')
    return redirect(url_for('index'))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return render_template('index.html', show_logout_confirm=True)
    return render_template('index.html', show_logout_confirm=False)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid email or password')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        is_doctor = request.form.get('is_doctor') == 'on'
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return redirect(url_for('signup'))
            
        user = User(email=email,
                    password_hash=generate_password_hash(password),
                    name=name,
                    is_doctor=is_doctor)
        db.session.add(user)
        db.session.commit()
        
        if is_doctor:
            doctor = Doctor(
                user_id=user.id,
                specialization=request.form.get('specialization'),
                experience=int(request.form.get('experience', 0)),
                education=request.form.get('education'),
                certifications=request.form.get('certifications'),
                consultation_fee=float(request.form.get('consultation_fee', 0))
            )
            db.session.add(doctor)
            db.session.commit()
            
        login_user(user)
        return redirect(url_for('dashboard'))
    return render_template('signup.html')

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_doctor:
        doctor = Doctor.query.filter_by(user_id=current_user.id).first()
        appointments = db.session.query(Appointment, User.name.label('patient_name')).join(
            User, Appointment.patient_id == User.id
        ).filter(
            Appointment.doctor_id == doctor.id,
            Appointment.date >= datetime.now(),
            Appointment.status != 'visited'
        ).order_by(Appointment.date.asc()).all()
        
        # Convert to list of dictionaries with merged attributes
        appointments_list = [{
            'id': appointment.id,
            'date': appointment.date,
            'status': appointment.status,
            'description': appointment.description,
            'patient_name': patient_name,
            'payment_method': appointment.payment_method,
            'payment_status': appointment.payment_status,
            'payment_details': appointment.payment_details
        } for appointment, patient_name in appointments]
        
        return render_template('dashboard.html', appointments=appointments_list)
    else:
        appointments = db.session.query(Appointment, User.name.label('doctor_name'), Doctor).join(
            Doctor, Appointment.doctor_id == Doctor.id
        ).join(
            User, Doctor.user_id == User.id
        ).filter(
            Appointment.patient_id == current_user.id,
            Appointment.date >= datetime.now(),
            Appointment.status != 'visited'
        ).order_by(Appointment.date.asc()).all()
        
        # Convert to list of dictionaries with merged attributes
        appointments_list = [{
            'id': appointment.id,
            'date': appointment.date,
            'status': appointment.status,
            'description': appointment.description,
            'doctor_name': doctor_name,
            'specialization': doctor.specialization,
            'payment_method': appointment.payment_method,
            'payment_status': appointment.payment_status,
            'payment_details': appointment.payment_details
        } for appointment, doctor_name, doctor in appointments]
        
        return render_template('dashboard.html', appointments=appointments_list)

@app.route('/approve-appointment/<int:appointment_id>')
@login_required
def approve_appointment(appointment_id):
    if not current_user.is_doctor:
        return redirect(url_for('dashboard'))
    
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.doctor_id != Doctor.query.filter_by(user_id=current_user.id).first().id:
        flash('You can only approve your own appointments')
        return redirect(url_for('dashboard'))
    
    appointment.status = 'approved'
    appointment.approved_at = datetime.utcnow()
    db.session.commit()
    flash('Appointment approved successfully')
    return redirect(url_for('dashboard'))

@app.route('/reject-appointment/<int:appointment_id>')
@login_required
def reject_appointment(appointment_id):
    if not current_user.is_doctor:
        return redirect(url_for('dashboard'))
    
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.doctor_id != Doctor.query.filter_by(user_id=current_user.id).first().id:
        flash('You can only reject your own appointments')
        return redirect(url_for('dashboard'))
    
    appointment.status = 'rejected'
    appointment.rejected_at = datetime.utcnow()
    db.session.commit()
    flash('Appointment rejected')
    return redirect(url_for('dashboard'))

@app.route('/doctors')
@login_required
def doctors():
    doctors = db.session.query(Doctor, User.name, Doctor.rating).join(User, Doctor.user_id == User.id).all()
    # Convert to list of dictionaries with merged attributes
    doctors_list = [{
        'id': doctor.id,
        'name': name,
        'specialization': doctor.specialization,
        'experience': doctor.experience,
        'rating': rating
    } for doctor, name, rating in doctors]
    return render_template('doctors.html', doctors=doctors_list)

@app.route('/profile')
@login_required
def profile():
    doctor_info = None
    if current_user.is_doctor:
        doctor_info = Doctor.query.filter_by(user_id=current_user.id).first()
    return render_template('profile.html', doctor_info=doctor_info)

@app.route('/book-appointment/<int:doctor_id>', methods=['GET', 'POST'])
@login_required
def book_appointment(doctor_id):
    if request.method == 'POST':
        date_str = request.form.get('date')
        description = request.form.get('description')
        payment_method = request.form.get('payment_method')
        
        # Validate required fields
        if not date_str:
            flash('Please select a date and time for your appointment')
            return redirect(url_for('book_appointment', doctor_id=doctor_id))
            
        if not description:
            flash('Please provide a description for your appointment')
            return redirect(url_for('book_appointment', doctor_id=doctor_id))
            
        if not payment_method:
            flash('Please select a payment method')
            return redirect(url_for('book_appointment', doctor_id=doctor_id))
        
        try:
            date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d %H:%M')
            except ValueError:
                flash('Invalid date format. Please try again.')
                return redirect(url_for('book_appointment', doctor_id=doctor_id))
        
        # Check if the time slot is already booked
        existing_appointment = Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            Appointment.date == date
        ).first()
        
        if existing_appointment:
            flash('Sorry, this time slot is already booked. Please choose another time.')
            return redirect(url_for('book_appointment', doctor_id=doctor_id))
        
        # Get payment details based on payment method
        payment_details = None
        if payment_method == 'upi':
            payment_details = request.form.get('upi_id')
            if not payment_details:
                flash('Please enter UPI ID')
                return redirect(url_for('book_appointment', doctor_id=doctor_id))
        elif payment_method == 'card':
            card_number = request.form.get('card_number')
            expiry = request.form.get('expiry')
            cvv = request.form.get('cvv')
            if not all([card_number, expiry, cvv]):
                flash('Please fill in all card details')
                return redirect(url_for('book_appointment', doctor_id=doctor_id))
            # Store only last 4 digits of card number for security
            payment_details = f"Card ending with {card_number[-4:]}"
        
        appointment = Appointment(
            patient_id=current_user.id,
            doctor_id=doctor_id,
            date=date,
            description=description,
            payment_method=payment_method,
            payment_details=payment_details,
            payment_status='pending'
        )
        db.session.add(appointment)
        db.session.commit()
        flash('Appointment booked successfully', 'success')
        return redirect(url_for('dashboard'))
    
    # Join Doctor and User tables to get doctor's information
    doctor = db.session.query(Doctor, User).join(
        User, Doctor.user_id == User.id
    ).filter(Doctor.id == doctor_id).first()
    
    if not doctor:
        flash('Doctor not found')
        return redirect(url_for('doctors'))
    
    doctor_obj, user_obj = doctor  # Unpack the query result
    
    # Get booked time slots
    booked_slots = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.date >= datetime.now()
    ).all()
    
    # Convert booked slots to a format suitable for JavaScript
    booked_times = [slot.date.strftime('%Y-%m-%dT%H:%M') for slot in booked_slots]
    
    return render_template('book_appointment.html', 
                         doctor=doctor_obj, 
                         doctor_user=user_obj,
                         booked_times=booked_times,
                         now=datetime.now())

@app.route('/chat/<int:user_id>')
@login_required
def chat(user_id):
    # Check if the users have an approved appointment
    if current_user.is_doctor:
        doctor = Doctor.query.filter_by(user_id=current_user.id).first()
        if not doctor:
            flash('Doctor profile not found')
            return redirect(url_for('dashboard'))
        
        # Check if patient has an approved appointment
        appointment = Appointment.query.filter_by(
            doctor_id=doctor.id,
            patient_id=user_id,
            status='approved'
        ).first()
        
        if not appointment:
            flash('You can only chat with patients who have approved appointments')
            return redirect(url_for('doctor_chats'))
    else:
        # Check if doctor has an approved appointment
        appointment = Appointment.query.filter_by(
            patient_id=current_user.id,
            doctor_id=Doctor.query.filter_by(user_id=user_id).first().id,
            status='approved'
        ).first()
        
        if not appointment:
            flash('You can only chat with doctors who have approved your appointment')
            return redirect(url_for('patient_chats'))
    
    # For both doctors and patients, show all messages in their conversation
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp).all()
    
    # Mark messages from the other user as read
    Message.query.filter_by(
        sender_id=user_id,
        receiver_id=current_user.id,
        is_read=False
    ).update({'is_read': True})
    db.session.commit()
    
    # Get the other user's information for display
    other_user = User.query.get_or_404(user_id)
    return render_template('chat.html', messages=messages, receiver_id=user_id, other_user=other_user)

@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    receiver_id = request.form.get('receiver_id')
    content = request.form.get('content')
    
    if not receiver_id or not content:
        return jsonify({'status': 'error', 'message': 'Missing required fields'})
    
    message = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=content
    )
    db.session.add(message)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': {
            'content': message.content,
            'timestamp': message.timestamp.strftime('%H:%M'),
            'sender_id': message.sender_id
        }
    })

@app.route('/doctor-chats')
@login_required
def doctor_chats():
    if not current_user.is_doctor:
        return redirect(url_for('dashboard'))
    
    # Get the doctor's ID
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    if not doctor:
        flash('Doctor profile not found')
        return redirect(url_for('dashboard'))
    
    # Get all unique patients who have appointments with this doctor
    patients = db.session.query(User).join(
        Appointment, User.id == Appointment.patient_id
    ).filter(
        Appointment.doctor_id == doctor.id
    ).distinct().all()
    
    # Get chat information for each patient
    chat_info = []
    for patient in patients:
        # Get the latest message
        latest_message = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == patient.id)) |
            ((Message.sender_id == patient.id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.timestamp.desc()).first()
        
        # Count unread messages
        unread_count = Message.query.filter(
            Message.sender_id == patient.id,
            Message.receiver_id == current_user.id,
            Message.is_read == False
        ).count()
        
        chat_info.append({
            'patient': patient,
            'latest_message': latest_message,
            'unread_count': unread_count
        })
    
    return render_template('doctor_chats.html', chat_info=chat_info)

@app.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        # Update basic user information
        current_user.name = request.form.get('name')
        current_user.email = request.form.get('email')
        
        # Update doctor information if user is a doctor
        if current_user.is_doctor:
            doctor_info = Doctor.query.filter_by(user_id=current_user.id).first()
            if not doctor_info:
                doctor_info = Doctor(user_id=current_user.id)
                db.session.add(doctor_info)
            
            doctor_info.specialization = request.form.get('specialization')
            doctor_info.experience = int(request.form.get('experience', 0))
            doctor_info.education = request.form.get('education')
            doctor_info.certifications = request.form.get('certifications')
            doctor_info.consultation_fee = float(request.form.get('consultation_fee', 0))
        
        db.session.commit()
        flash('Profile updated successfully')
        return redirect(url_for('profile'))
    
    # Get doctor information if user is a doctor
    doctor_info = None
    if current_user.is_doctor:
        doctor_info = Doctor.query.filter_by(user_id=current_user.id).first()
    
    return render_template('edit_profile.html', doctor_info=doctor_info)

@app.route('/rate-doctor/<int:doctor_id>', methods=['GET', 'POST'])
@login_required
def rate_doctor(doctor_id):
    if current_user.is_doctor:
        flash('Doctors cannot rate other doctors')
        return redirect(url_for('doctors'))
    
    # Join Doctor and User tables to get doctor's information
    doctor = db.session.query(Doctor, User).join(
        User, Doctor.user_id == User.id
    ).filter(Doctor.id == doctor_id).first()
    
    if not doctor:
        flash('Doctor not found')
        return redirect(url_for('doctors'))
    
    doctor_obj, user_obj = doctor  # Unpack the query result
    
    if request.method == 'POST':
        rating_value = int(request.form.get('rating'))
        review = request.form.get('review')
        
        # Check if user has already rated this doctor
        existing_rating = Rating.query.filter_by(
            user_id=current_user.id,
            doctor_id=doctor_id
        ).first()
        
        if existing_rating:
            existing_rating.rating = rating_value
            existing_rating.review = review
        else:
            new_rating = Rating(
                user_id=current_user.id,
                doctor_id=doctor_id,
                rating=rating_value,
                review=review
            )
            db.session.add(new_rating)
        
        # Update doctor's average rating
        ratings = Rating.query.filter_by(doctor_id=doctor_id).all()
        if ratings:
            doctor_obj.rating = sum(r.rating for r in ratings) / len(ratings)
        
        db.session.commit()
        flash('Thank you for your rating!')
        return redirect(url_for('doctors'))
    
    # Get existing rating if any
    existing_rating = Rating.query.filter_by(
        user_id=current_user.id,
        doctor_id=doctor_id
    ).first()
    
    return render_template('rate_doctor.html', doctor=doctor_obj, doctor_user=user_obj, existing_rating=existing_rating)

@app.route('/patient-chats')
@login_required
def patient_chats():
    if current_user.is_doctor:
        return redirect(url_for('dashboard'))
    
    # Get all unique doctors who have accepted appointments with this patient
    doctors = db.session.query(Doctor, User).join(
        User, Doctor.user_id == User.id
    ).join(
        Appointment, Doctor.id == Appointment.doctor_id
    ).filter(
        Appointment.patient_id == current_user.id,
        Appointment.status == 'approved'  # Only show doctors with approved appointments
    ).distinct().all()
    
    # Get the latest message and unread count for each doctor
    chat_info = []
    for doctor, user in doctors:
        # Get the latest message
        latest_message = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == user.id)) |
            ((Message.sender_id == user.id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.timestamp.desc()).first()
        
        # Count unread messages
        unread_count = Message.query.filter(
            Message.sender_id == user.id,
            Message.receiver_id == current_user.id,
            Message.is_read == False
        ).count()
        
        chat_info.append({
            'doctor': doctor,
            'user': user,
            'latest_message': latest_message,
            'unread_count': unread_count
        })
    
    return render_template('patient_chats.html', chat_info=chat_info)

@app.route('/mark-visited/<int:appointment_id>')
@login_required
def mark_visited(appointment_id):
    if not current_user.is_doctor:
        return redirect(url_for('dashboard'))
    appointment = Appointment.query.get_or_404(appointment_id)
    doctor = Doctor.query.filter_by(user_id=current_user.id).first()
    if appointment.doctor_id != doctor.id:
        flash('You can only mark your own appointments as visited.', 'danger')
        return redirect(url_for('dashboard'))
    appointment.status = 'visited'
    db.session.commit()
    flash('Appointment marked as visited.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/history')
@login_required
def history():
    if current_user.is_doctor:
        doctor = Doctor.query.filter_by(user_id=current_user.id).first()
        visited_appointments = db.session.query(Appointment, User).join(
            User, Appointment.patient_id == User.id
        ).filter(
            Appointment.doctor_id == doctor.id,
            Appointment.status == 'visited'
        ).order_by(Appointment.date.desc()).all()
        return render_template('history.html', visited_appointments=visited_appointments, is_doctor=True)
    else:
        visited_appointments = db.session.query(Appointment, User, Doctor).join(
            Doctor, Appointment.doctor_id == Doctor.id
        ).join(
            User, Doctor.user_id == User.id
        ).filter(
            Appointment.patient_id == current_user.id,
            Appointment.status == 'visited'
        ).order_by(Appointment.date.desc()).all()
        return render_template('history.html', visited_appointments=visited_appointments, is_doctor=False)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(debug=True, host="0.0.0.0")
