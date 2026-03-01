from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app.models import PurchaseOrder, Supplier, ProductPrice
from app.stock_api import StockAPIClient
from app import db
from sqlalchemy import func
from datetime import datetime, timedelta

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def dashboard():
    """Ana Dashboard - Kritik ürünler ve sipariş özeti"""
    
    # API'den tüm ürünleri çek
    api_client = StockAPIClient()
    critical_data = api_client.get_critical_products()
    all_products = critical_data.get('products', [])
    
    # Lokal fiyatları çek ve merge et
    local_prices = {p.product_code: {'price': p.unit_price, 'vat': p.vat_rate} for p in ProductPrice.query.all()}
    
    critical_products = []
    
    for product in all_products:
        # Fiyatı ve KDV'yi güncelle
        if product['code'] in local_prices:
            product['unit_price'] = local_prices[product['code']]['price']
            product['vat_rate'] = local_prices[product['code']]['vat']
        else:
            product['vat_rate'] = 20.0
            
        current_val = product.get('current_stock', 0)
        minimum_val = product.get('minimum_stock', 1)
        
        try:
            current = float(current_val)
        except (ValueError, TypeError):
            current = 0.0
            
        try:
            minimum = float(minimum_val)
        except (ValueError, TypeError):
            minimum = 1.0
            
        shortage = max(0, minimum - current)
        product['current_stock'] = current
        product['minimum_stock'] = minimum
        product['shortage'] = shortage
        
        try:
            unit_price = float(product.get('unit_price', 0))
        except (ValueError, TypeError):
            unit_price = 0.0
            
        try:
            vat_rate_val = product.get('vat_rate', 20.0)
            if vat_rate_val is None:
                vat_rate = 20.0
            else:
                vat_rate = float(vat_rate_val)
        except (ValueError, TypeError):
            vat_rate = 20.0
            
        product['unit_price'] = unit_price
        product['vat_rate'] = vat_rate
        
        product['estimated_cost'] = shortage * unit_price
        product['total_with_vat'] = product['estimated_cost'] * (1 + (vat_rate / 100.0))
        
        if shortage > 0:
            critical_products.append(product)
            
    critical_count = len(critical_products)
    
    # Sipariş istatistikleri
    pending_orders = PurchaseOrder.query.filter_by(status='pending').count()
    ordered_count = PurchaseOrder.query.filter_by(status='ordered').count()
    
    # Bugünün tarihi için
    today = datetime.utcnow().date()
    
    # Bugün teslim edilmesi gereken siparişler
    due_today = PurchaseOrder.query.filter(
        PurchaseOrder.status == 'ordered',
        func.date(PurchaseOrder.expected_delivery_date) == today
    ).count()
    
    # Gecikmiş siparişler
    overdue_orders = PurchaseOrder.query.filter(
        PurchaseOrder.status == 'ordered',
        PurchaseOrder.expected_delivery_date < datetime.utcnow()
    ).count()
    
    # Son siparişler
    recent_orders = PurchaseOrder.query.order_by(
        PurchaseOrder.created_at.desc()
    ).limit(10).all()
    
    return render_template('dashboard.html',
                         critical_products=critical_products,
                         critical_count=critical_count,
                         pending_orders=pending_orders,
                         ordered_count=ordered_count,
                         due_today=due_today,
                         overdue_orders=overdue_orders,
                         recent_orders=recent_orders,
                         api_connected=critical_data.get('success', False))

@main_bp.route('/about')
@login_required
def about():
    """Hakkında sayfası"""
    return render_template('about.html')

@main_bp.route('/api/v1/products/prices', methods=['GET'])
def get_prices():
    """Tüm yerel ürün fiyatlarını döndür (Dış API kullanımı için)"""
    prices = ProductPrice.query.all()
    price_data = {p.product_code: {
        "price": p.unit_price, 
        "vat_rate": p.vat_rate, 
        "currency": p.currency, 
        "updated_at": p.updated_at.isoformat()
    } for p in prices}
    return jsonify({
        "success": True,
        "prices": price_data
    })

@main_bp.route('/api/v1/products/prices', methods=['POST'])
@login_required
def update_price():
    """Kullanıcının girdiği yerel ürün fiyatını güncelle"""
    data = request.json
    product_code = data.get('product_code')
    unit_price = data.get('unit_price')
    vat_rate = data.get('vat_rate')
    
    if not product_code or unit_price is None:
        return jsonify({"success": False, "error": "Eksik parametre"}), 400
        
    try:
        unit_price = float(unit_price)
    except ValueError:
        return jsonify({"success": False, "error": "Geçersiz fiyat formatı"}), 400
        
    try:
        vat_rate_val = float(vat_rate) if vat_rate is not None else 20.0
    except ValueError:
        vat_rate_val = 20.0
        
    price_record = ProductPrice.query.filter_by(product_code=product_code).first()
    if price_record:
        price_record.unit_price = unit_price
        price_record.vat_rate = vat_rate_val
    else:
        price_record = ProductPrice(product_code=product_code, unit_price=unit_price, vat_rate=vat_rate_val)
        db.session.add(price_record)
        
    db.session.commit()
    
    # API Entegrasyonu: Ana sistemdeki unit_cost değerini senkronize et
    api_client = StockAPIClient()
    api_client.update_product_price(
        product_code=product_code,
        new_price=unit_price,
        vat_rate=vat_rate_val,
        currency='TRY'
    )
    
    return jsonify({"success": True, "message": "Fiyat güncellendi"})
