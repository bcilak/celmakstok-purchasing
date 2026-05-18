from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager

class User(UserMixin, db.Model):
    """Satın Alma Personeli"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='purchasing')  # purchasing, manager, admin
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))


class ActivityLog(db.Model):
    """Kullanıcı Hareketleri Log Tablosu"""
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)  # örn: 'login', 'price_update', 'order_create'
    details = db.Column(db.Text)  # JSON veya metin
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('activities', lazy='dynamic'))

class Supplier(db.Model):
    """Tedarikçi Bilgileri"""
    __tablename__ = 'suppliers'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    contact_person = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    tax_number = db.Column(db.String(50))
    notes = db.Column(db.Text)
    rating = db.Column(db.Integer, default=0)  # 0-5 yıldız
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Yeni Alanlar
    tax_office = db.Column(db.String(100))
    iban = db.Column(db.String(50))
    payment_terms = db.Column(db.String(100))
    supplier_category = db.Column(db.String(50))
    status = db.Column(db.String(20), default='approved') # pending, approved, blacklisted
    
    # İlişkiler
    purchase_orders = db.relationship('PurchaseOrder', backref='supplier', lazy='dynamic')
    contacts = db.relationship('SupplierContact', backref='supplier', lazy='dynamic', cascade='all, delete-orphan')
    documents = db.relationship('SupplierDocument', backref='supplier', lazy='dynamic', cascade='all, delete-orphan')

class SupplierContact(db.Model):
    """Tedarikçi İlgili Kişileri"""
    __tablename__ = 'supplier_contacts'
    
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(100))  # Örn: Muhasebe, Satış Müdürü
    phone = db.Column(db.String(50))
    email = db.Column(db.String(120))
    is_primary = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SupplierDocument(db.Model):
    """Tedarikçi Belgeleri ve Sözleşmeler"""
    __tablename__ = 'supplier_documents'
    
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    document_type = db.Column(db.String(50)) # sözleşme, sertifika, imza_sirküsü vb.
    file_path = db.Column(db.String(255), nullable=False) # uploads klasöründeki yol
    valid_until = db.Column(db.DateTime) # Geçerlilik bitiş tarihi (varsa)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    uploaded_by = db.relationship('User', backref='supplier_documents')

    @property
    def is_expired(self):
        if self.valid_until:
            return datetime.utcnow() > self.valid_until
        return False


class PurchaseOrder(db.Model):
    """Satın Alma Siparişi"""
    __tablename__ = 'purchase_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    
    # Tedarikçi
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    
    # Ürün bilgileri (Ana stok uygulamasından)
    product_code = db.Column(db.String(50), nullable=False)  # Ana stok uygulamasındaki ürün kodu
    product_name = db.Column(db.String(200), nullable=False)
    
    # Miktar ve fiyat
    quantity = db.Column(db.Float, nullable=False)
    unit_type = db.Column(db.String(20))
    unit_price = db.Column(db.Float, default=0)
    total_price = db.Column(db.Float, default=0)
    currency = db.Column(db.String(10), default='TRY')
    
    # Durumlar
    status = db.Column(db.String(20), default='pending')  # pending, approved, ordered, received, cancelled
    priority = db.Column(db.String(20), default='normal')  # low, normal, high, urgent
    
    # Tarihler
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    expected_delivery_date = db.Column(db.DateTime)
    actual_delivery_date = db.Column(db.DateTime)
    
    # Notlar ve takip
    notes = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişkiler
    created_by = db.relationship('User', backref='purchase_orders')
    
    @property
    def is_overdue(self):
        """Teslimat gecikmesi var mı?"""
        if self.expected_delivery_date and self.status not in ['received', 'cancelled']:
            return datetime.utcnow() > self.expected_delivery_date
        return False
    
    @property
    def days_until_delivery(self):
        """Teslimata kaç gün kaldı?"""
        if self.expected_delivery_date and self.status not in ['received', 'cancelled']:
            delta = self.expected_delivery_date - datetime.utcnow()
            return delta.days
        return None


class SupplierProduct(db.Model):
    """Tedarikçi-Ürün Fiyat Listesi (Seçenek 1)"""
    __tablename__ = 'supplier_products'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # İlişkiler
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    product_code = db.Column(db.String(50), nullable=False)  # Ana stok uygulamasındaki kod
    
    # Fiyat bilgileri
    unit_price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='TRY')
    minimum_order_quantity = db.Column(db.Float, default=1)
    lead_time_days = db.Column(db.Integer)  # Tedarik süresi (gün)
    
    # Geçerlilik
    valid_from = db.Column(db.DateTime, default=datetime.utcnow)
    valid_until = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # Notlar
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # İlişki
    supplier = db.relationship('Supplier', backref='product_prices')
    
    # Unique constraint: Bir tedarikçi için bir ürün kodu birden fazla olamaz (aktif olanlar için)
    __table_args__ = (
        db.Index('idx_supplier_product', 'supplier_id', 'product_code'),
    )
    
    @staticmethod
    def get_best_price(product_code):
        """Bir ürün için en iyi (en düşük) fiyatı döndür"""
        from sqlalchemy import func
        return db.session.query(
            SupplierProduct.supplier_id,
            func.min(SupplierProduct.unit_price).label('best_price')
        ).filter(
            SupplierProduct.product_code == product_code,
            SupplierProduct.is_active == True,
            db.or_(
                SupplierProduct.valid_until == None,
                SupplierProduct.valid_until > datetime.utcnow()
            )
        ).group_by(SupplierProduct.supplier_id).first()
    
    @staticmethod
    def get_supplier_price(supplier_id, product_code):
        """Belirli bir tedarikçinin belirli bir ürün için fiyatını döndür"""
        return SupplierProduct.query.filter_by(
            supplier_id=supplier_id,
            product_code=product_code,
            is_active=True
        ).filter(
            db.or_(
                SupplierProduct.valid_until == None,
                SupplierProduct.valid_until > datetime.utcnow()
            )
        ).first()

class ProductPrice(db.Model):
    """Lokal Ürün Fiyatları"""
    __tablename__ = 'product_prices'
    
    id = db.Column(db.Integer, primary_key=True)
    product_code = db.Column(db.String(50), unique=True, nullable=False)
    unit_price = db.Column(db.Float, default=0.0)
    vat_rate = db.Column(db.Float, default=20.0)  # KDV oranı (%)
    currency = db.Column(db.String(10), default='TRY')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

