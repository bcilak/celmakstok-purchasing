from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import OrderTemplate, ActivityLog
from app import db
from app.utils.decorators import roles_required

templates_bp = Blueprint('templates_bp', __name__)

@templates_bp.route('/list')
@login_required
@roles_required('admin', 'manager', 'purchasing')
def list_templates():
    """Tüm şablonları listeler"""
    templates = OrderTemplate.query.order_by(OrderTemplate.name).all()
    return render_template('templates/list.html', templates=templates)

@templates_bp.route('/create', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'manager')
def create_template():
    """Yeni şablon oluşturur"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        content = request.form.get('content', '')
        is_active = request.form.get('is_active') == 'on'

        if not name or not content:
            flash("Şablon adı ve içeriği zorunludur.", "danger")
            return render_template('templates/form.html', action="Yeni")

        if OrderTemplate.query.filter_by(name=name).first():
            flash(f"'{name}' adında bir şablon zaten var.", "danger")
            return render_template('templates/form.html', action="Yeni", name=name, description=description, content=content)

        new_template = OrderTemplate(
            name=name,
            description=description,
            content=content,
            is_active=is_active,
            created_by_id=current_user.id
        )
        db.session.add(new_template)
        
        log = ActivityLog(
            user_id=current_user.id,
            action='create_template',
            details=f"'{name}' adlı çıktı şablonu oluşturuldu.",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()

        flash("Şablon başarıyla oluşturuldu.", "success")
        return redirect(url_for('templates_bp.list_templates'))

    return render_template('templates/form.html', action="Yeni")

@templates_bp.route('/edit/<int:template_id>', methods=['GET', 'POST'])
@login_required
@roles_required('admin', 'manager')
def edit_template(template_id):
    """Mevcut şablonu düzenler"""
    template = OrderTemplate.query.get_or_404(template_id)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        content = request.form.get('content', '')
        is_active = request.form.get('is_active') == 'on'

        if not name or not content:
            flash("Şablon adı ve içeriği zorunludur.", "danger")
            return render_template('templates/form.html', action="Düzenle", template=template)

        # İsim değişmişse ve yeni isim zaten varsa kontrol et
        if name != template.name and OrderTemplate.query.filter_by(name=name).first():
            flash(f"'{name}' adında bir şablon zaten var.", "danger")
            return render_template('templates/form.html', action="Düzenle", template=template)

        template.name = name
        template.description = description
        template.content = content
        template.is_active = is_active

        log = ActivityLog(
            user_id=current_user.id,
            action='edit_template',
            details=f"'{name}' adlı çıktı şablonu güncellendi.",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()

        flash("Şablon başarıyla güncellendi.", "success")
        return redirect(url_for('templates_bp.list_templates'))

    return render_template('templates/form.html', action="Düzenle", template=template)

@templates_bp.route('/delete/<int:template_id>', methods=['POST'])
@login_required
@roles_required('admin', 'manager')
def delete_template(template_id):
    """Şablonu siler"""
    template = OrderTemplate.query.get_or_404(template_id)
    
    name = template.name
    db.session.delete(template)
    
    log = ActivityLog(
        user_id=current_user.id,
        action='delete_template',
        details=f"'{name}' adlı çıktı şablonu silindi.",
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
    
    flash("Şablon başarıyla silindi.", "success")
    return redirect(url_for('templates_bp.list_templates'))
