from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
from app.models import Supplier, SupplierProduct, PurchaseOrder, SupplierContact, SupplierDocument
from app import db
import os
from werkzeug.utils import secure_filename
from datetime import datetime

suppliers_bp = Blueprint('suppliers', __name__)

@suppliers_bp.route('/')
@login_required
def index():
    """Tedarikçi Listesi"""
    
    search = request.args.get('search', '')
    
    query = Supplier.query.filter_by(is_active=True)
    
    if search:
        query = query.filter(
            (Supplier.name.ilike(f'%{search}%')) |
            (Supplier.code.ilike(f'%{search}%'))
        )
    
    suppliers = query.order_by(Supplier.name).all()
    
    return render_template('suppliers/index.html',
                         suppliers=suppliers,
                         search=search)

@suppliers_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Yeni Tedarikçi Ekle"""
    
    if request.method == 'POST':
        try:
            supplier = Supplier(
                code=request.form.get('code'),
                name=request.form.get('name'),
                contact_person=request.form.get('contact_person'),
                phone=request.form.get('phone'),
                email=request.form.get('email'),
                address=request.form.get('address'),
                tax_number=request.form.get('tax_number'),
                notes=request.form.get('notes'),
                rating=int(request.form.get('rating', 0))
            )
            
            db.session.add(supplier)
            db.session.commit()
            
            flash(f'Tedarikçi {supplier.name} başarıyla eklendi!', 'success')
            return redirect(url_for('suppliers.index'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Tedarikçi eklenemedi: {str(e)}', 'danger')
    
    return render_template('suppliers/add.html')

@suppliers_bp.route('/<int:id>')
@login_required
def view(id):
    """Tedarikçi Detayı"""
    supplier = Supplier.query.get_or_404(id)
    
    # Tedarikçinin siparişleri
    orders = PurchaseOrder.query.filter_by(supplier_id=id).order_by(PurchaseOrder.created_at.desc()).all()
    
    # Tedarikçinin fiyat listesi
    price_list = SupplierProduct.query.filter_by(
        supplier_id=id,
        is_active=True
    ).order_by(SupplierProduct.product_code).all()
    
    return render_template('suppliers/view.html',
                         supplier=supplier,
                         orders=orders,
                         price_list=price_list)

@suppliers_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    """Tedarikçi Düzenle"""
    supplier = Supplier.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            supplier.code = request.form.get('code')
            supplier.name = request.form.get('name')
            supplier.contact_person = request.form.get('contact_person')
            supplier.phone = request.form.get('phone')
            supplier.email = request.form.get('email')
            supplier.address = request.form.get('address')
            supplier.tax_number = request.form.get('tax_number')
            supplier.notes = request.form.get('notes')
            supplier.tax_office = request.form.get('tax_office')
            supplier.iban = request.form.get('iban')
            supplier.payment_terms = request.form.get('payment_terms')
            supplier.supplier_category = request.form.get('supplier_category')
            if request.form.get('status'):
                supplier.status = request.form.get('status')
            
            db.session.commit()
            
            flash('Tedarikçi güncellendi!', 'success')
            return redirect(url_for('suppliers.view', id=id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Güncelleme başarısız: {str(e)}', 'danger')
    
    return render_template('suppliers/edit.html', supplier=supplier)


@suppliers_bp.route('/<int:id>/prices', methods=['GET', 'POST'])
@login_required
def manage_prices(id):
    """Tedarikçi Fiyat Listesi Yönetimi"""
    supplier = Supplier.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            # Yeni fiyat ekle veya güncelle
            product_code = request.form.get('product_code')
            
            # Mevcut fiyatı kontrol et
            existing = SupplierProduct.query.filter_by(
                supplier_id=id,
                product_code=product_code,
                is_active=True
            ).first()
            
            if existing:
                # Güncelle
                existing.unit_price = float(request.form.get('unit_price'))
                existing.minimum_order_quantity = float(request.form.get('minimum_order_quantity', 1))
                existing.lead_time_days = int(request.form.get('lead_time_days', 0)) if request.form.get('lead_time_days') else None
                existing.notes = request.form.get('notes')
                existing.updated_at = datetime.utcnow()
                
                flash('Fiyat güncellendi!', 'success')
            else:
                # Yeni ekle
                supplier_product = SupplierProduct(
                    supplier_id=id,
                    product_code=product_code,
                    unit_price=float(request.form.get('unit_price')),
                    currency=request.form.get('currency', 'TRY'),
                    minimum_order_quantity=float(request.form.get('minimum_order_quantity', 1)),
                    lead_time_days=int(request.form.get('lead_time_days', 0)) if request.form.get('lead_time_days') else None,
                    notes=request.form.get('notes')
                )
                db.session.add(supplier_product)
                flash('Fiyat eklendi!', 'success')
            
            db.session.commit()
            return redirect(url_for('suppliers.view', id=id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Hata: {str(e)}', 'danger')
    
    return redirect(url_for('suppliers.view', id=id))


@suppliers_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    """Tedarikçi Sil"""
    supplier = Supplier.query.get_or_404(id)
    
    try:
        # Soft delete - sadece is_active'i False yap
        supplier.is_active = False
        db.session.commit()
        flash(f'{supplier.name} tedarikçisi silindi!', 'success')
        return redirect(url_for('suppliers.index'))
    except Exception as e:
        db.session.rollback()
        flash(f'Hata: {str(e)}', 'danger')
        return redirect(url_for('suppliers.edit', id=id))

@suppliers_bp.route('/<int:id>/prices/<int:price_id>/delete', methods=['POST'])
@login_required
def delete_price(id, price_id):
    """Fiyat Sil"""
    price = SupplierProduct.query.get_or_404(price_id)
    
    if price.supplier_id != id:
        flash('Geçersiz işlem!', 'danger')
        return redirect(url_for('suppliers.view', id=id))
    
    try:
        price.is_active = False
        db.session.commit()
        flash('Fiyat silindi!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Hata: {str(e)}', 'danger')
    
    return redirect(url_for('suppliers.view', id=id))

# --- İletişim Kişileri (Contacts) Endpoint'leri ---

@suppliers_bp.route('/<int:id>/contacts/add', methods=['POST'])
@login_required
def add_contact(id):
    supplier = Supplier.query.get_or_404(id)
    try:
        contact = SupplierContact(
            supplier_id=id,
            name=request.form.get('name'),
            title=request.form.get('title'),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            is_primary=bool(request.form.get('is_primary')),
            notes=request.form.get('notes')
        )
        
        # Eğer yeni kişi birincil ise, diğerlerini ikincil yap
        if contact.is_primary:
            SupplierContact.query.filter_by(supplier_id=id).update({'is_primary': False})
            
        db.session.add(contact)
        db.session.commit()
        flash('İlgili kişi başarıyla eklendi.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Hata: {str(e)}', 'danger')
        
    return redirect(url_for('suppliers.view', id=id) + '#contacts')

@suppliers_bp.route('/<int:id>/contacts/<int:contact_id>/delete', methods=['POST'])
@login_required
def delete_contact(id, contact_id):
    contact = SupplierContact.query.get_or_404(contact_id)
    if contact.supplier_id != id:
        flash('Geçersiz işlem!', 'danger')
        return redirect(url_for('suppliers.view', id=id))
        
    try:
        db.session.delete(contact)
        db.session.commit()
        flash('İlgili kişi silindi.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Hata: {str(e)}', 'danger')
        
    return redirect(url_for('suppliers.view', id=id) + '#contacts')

# --- Belgeler (Documents) Endpoint'leri ---

@suppliers_bp.route('/<int:id>/documents/upload', methods=['POST'])
@login_required
def upload_document(id):
    supplier = Supplier.query.get_or_404(id)
    
    if 'document' not in request.files:
        flash('Dosya seçilmedi!', 'danger')
        return redirect(url_for('suppliers.view', id=id) + '#documents')
        
    file = request.files['document']
    if file.filename == '':
        flash('Dosya seçilmedi!', 'danger')
        return redirect(url_for('suppliers.view', id=id) + '#documents')
        
    try:
        # Güvenli dosya adı oluştur
        filename = secure_filename(file.filename)
        # Benzersiz olması için timestamp ekle
        from datetime import datetime
        base_name, ext = os.path.splitext(filename)
        safe_name = f"{base_name}_{int(datetime.now().timestamp())}{ext}"
        
        # Yükleme klasörünü oluştur (yoksa)
        upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'suppliers', str(id))
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, safe_name)
        file.save(file_path)
        
        # DB kaydı oluştur
        valid_until_str = request.form.get('valid_until')
        valid_until = datetime.strptime(valid_until_str, '%Y-%m-%d') if valid_until_str else None
        
        doc = SupplierDocument(
            supplier_id=id,
            title=request.form.get('title', filename),
            document_type=request.form.get('document_type', 'Diğer'),
            file_path=os.path.join('suppliers', str(id), safe_name), # Göreceli yol
            valid_until=valid_until,
            notes=request.form.get('notes'),
            uploaded_by_id=current_user.id
        )
        
        db.session.add(doc)
        db.session.commit()
        flash('Belge başarıyla yüklendi.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Yükleme hatası: {str(e)}', 'danger')
        
    return redirect(url_for('suppliers.view', id=id) + '#documents')

@suppliers_bp.route('/<int:id>/documents/<int:doc_id>/download')
@login_required
def download_document(id, doc_id):
    doc = SupplierDocument.query.get_or_404(doc_id)
    if doc.supplier_id != id:
        flash('Geçersiz işlem!', 'danger')
        return redirect(url_for('suppliers.view', id=id))
        
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], doc.file_path, as_attachment=True)

@suppliers_bp.route('/<int:id>/documents/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete_document(id, doc_id):
    doc = SupplierDocument.query.get_or_404(doc_id)
    if doc.supplier_id != id:
        flash('Geçersiz işlem!', 'danger')
        return redirect(url_for('suppliers.view', id=id))
        
    try:
        # Fiziksel dosyayı sil
        full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.file_path)
        if os.path.exists(full_path):
            os.remove(full_path)
            
        # Veritabanından sil
        db.session.delete(doc)
        db.session.commit()
        flash('Belge silindi.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Hata: {str(e)}', 'danger')
        
    return redirect(url_for('suppliers.view', id=id) + '#documents')
