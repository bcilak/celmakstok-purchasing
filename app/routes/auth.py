from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User, ActivityLog
from app import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Giriş sayfası - Sadece satın alma personeli"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username, is_active=True).first()
        
        if user and user.check_password(password):
            login_user(user)
            
            # Log the login activity
            log = ActivityLog(
                user_id=user.id,
                action='login',
                details='Kullanıcı sisteme giriş yaptı.',
                ip_address=request.remote_addr
            )
            db.session.add(log)
            db.session.commit()
            
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))
        
        flash('Kullanıcı adı veya şifre hatalı!', 'danger')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """Çıkış"""
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile')
@login_required
def profile():
    """Profil sayfası"""
    return render_template('auth/profile.html')
