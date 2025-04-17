from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash
from app import db, mail
from app.models.user import User, PasswordResetToken, UserRole
from app.forms.auth_forms import (
    LoginForm, PasswordResetRequestForm, PasswordResetForm, ChangePasswordForm, RegisterUserForm
)
from flask_mail import Message
from datetime import datetime, timedelta
import secrets
import string

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        user_type = request.form.get('userType')
        
        if user and user.check_password(form.password.data):
            # Check if user has the selected role
            if user_type == 'admin' and user.role != UserRole.ADMIN:
                flash('You do not have admin privileges.', 'danger')
                return render_template('auth/login.html', form=form)
            elif user_type == 'project_manager' and user.role != UserRole.PROJECT_MANAGER:
                flash('You do not have project manager privileges.', 'danger')
                return render_template('auth/login.html', form=form)
            elif user_type == 'team_member' and user.role != UserRole.TEAM_MEMBER:
                # This is more flexible - admins and PMs can also login as team members
                if user.role not in [UserRole.ADMIN, UserRole.PROJECT_MANAGER]:
                    flash('Invalid role selection.', 'danger')
                    return render_template('auth/login.html', form=form)
            
            login_user(user, remember=form.remember.data)
            
            # Check if this is first login - redirect to change password
            if user.is_first_login:
                flash('Please change your password for first-time login.', 'info')
                return redirect(url_for('auth.change_password'))
            
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/request-password-reset', methods=['GET', 'POST'])
def request_password_reset():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            # Generate token
            token = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
            reset_token = PasswordResetToken(
                user_id=user.id,
                token=token,
                expires_at=datetime.utcnow() + timedelta(hours=1)
            )
            db.session.add(reset_token)
            db.session.commit()
            
            # Send email
            msg = Message(
                'Password Reset Request',
                recipients=[user.email]
            )
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            msg.body = f'''To reset your password, visit the following link:
{reset_url}

If you did not make this request, simply ignore this email and no changes will be made.
'''
            mail.send(msg)
            
            flash('An email has been sent with instructions to reset your password.', 'info')
            return redirect(url_for('auth.login'))
    
    return render_template('auth/request_password_reset.html', form=form)

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    # Verify token
    token_record = PasswordResetToken.query.filter_by(
        token=token,
        used=False
    ).first()
    
    if not token_record or token_record.expires_at < datetime.utcnow():
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.request_password_reset'))
    
    form = PasswordResetForm()
    if form.validate_on_submit():
        user = User.query.get(token_record.user_id)
        user.set_password(form.password.data)
        user.is_first_login = False
        
        # Mark token as used
        token_record.used = True
        
        db.session.commit()
        flash('Your password has been updated! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', form=form)

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.check_password(form.current_password.data):
            current_user.set_password(form.new_password.data)
            current_user.is_first_login = False
            db.session.commit()
            flash('Your password has been updated!', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            flash('Current password is incorrect.', 'danger')
    
    return render_template('auth/change_password.html', form=form)

@auth_bp.route('/register-user', methods=['GET', 'POST'])
@login_required
def register_user():
    # Only admins can register new users
    if current_user.role != UserRole.ADMIN:
        flash('You do not have permission to register new users.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    form = RegisterUserForm()
    if form.validate_on_submit():
        # Generate a random initial password
        initial_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
        
        # Create new user
        user = User(
            username=form.username.data,
            email=form.email.data,
            password=initial_password,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            role=UserRole[form.role.data]
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Send email with credentials
        msg = Message(
            'Your Account has been created',
            recipients=[user.email]
        )
        msg.body = f'''Your account has been created in the Project Management System.

Username: {user.username}
Email: {user.email}
Temporary Password: {initial_password}

Please login and change your password.
'''
        mail.send(msg)
        
        flash(f'User {user.username} has been registered! An email with credentials has been sent.', 'success')
        return redirect(url_for('user.list_users'))
    
    return render_template('auth/register_user.html', form=form)