from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import User, ActivityLog
from app import db
from app.utils.decorators import roles_required

admin_bp = Blueprint('admin_bp', __name__, url_prefix='/admin')

@admin_bp.route('/users')
@login_required
@roles_required('admin')
def manage_users():
    """Kullanıcı yönetimi sayfası (Sadece Admin)"""
    users = User.query.order_by(User.id.desc()).all()
    recent_activities = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(20).all()
    
    return render_template('admin/users.html', users=users, activities=recent_activities)

@admin_bp.route('/users/edit/<int:user_id>', methods=['POST'])
@login_required
@roles_required('admin')
def edit_user(user_id):
    """Kullanıcı rol ve durum güncelleme (Sadece Admin)"""
    user = User.query.get_or_404(user_id)
    
    role = request.form.get('role')
    is_active = request.form.get('is_active') == 'on'
    
    if role in ['admin', 'manager', 'purchasing']:
        user.role = role
        user.is_active = is_active
        
        # Log this admin action
        log = ActivityLog(
            user_id=current_user.id,
            action='edit_user',
            details=f"Admin {user.username} kullanıcısının rolünü '{role}', durumunu '{is_active}' olarak güncelledi.",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f"{user.username} başarıyla güncellendi.", "success")
    else:
        flash("Geçersiz rol.", "danger")
        
    return redirect(url_for('admin_bp.manage_users'))

@admin_bp.route('/audit')
@login_required
@roles_required('admin')
def audit_logs():
    """Tüm sistem hareketleri dökümü ve filtreleme"""
    page = request.args.get('page', 1, type=int)
    user_id = request.args.get('user_id', '')
    search_term = request.args.get('search', '')
    
    query = ActivityLog.query
    
    if user_id:
        query = query.filter_by(user_id=int(user_id))
        
    if search_term:
        search = f"%{search_term}%"
        query = query.filter(db.or_(
            ActivityLog.action.ilike(search),
            ActivityLog.details.ilike(search),
            ActivityLog.ip_address.ilike(search)
        ))
        
    logs = query.order_by(ActivityLog.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    users = User.query.order_by(User.name).all()
    
    return render_template('admin/audit.html', logs=logs, users=users, selected_user=user_id, search_term=search_term)
