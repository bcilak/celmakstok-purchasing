from flask import Blueprint, current_app, render_template, jsonify, request
from flask_login import login_required, current_user
from app.models import PurchaseOrder, Supplier, ProductPrice
from app.stock_api import StockAPIClient
from app import db
from sqlalchemy import func
from datetime import datetime, timedelta
import os

main_bp = Blueprint('main', __name__)

def _api_key_is_valid():
    expected_key = current_app.config.get('PURCHASING_API_KEY') or os.environ.get('PURCHASING_API_KEY')
    if not expected_key:
        return True

    provided_key = request.headers.get('X-API-Key') or request.args.get('api_key')
    auth_header = request.headers.get('Authorization', '')
    if not provided_key and auth_header.startswith('Bearer '):
        provided_key = auth_header[len('Bearer '):].strip()

    return provided_key == expected_key

def _json_auth_error(*roles):
    if not current_user.is_authenticated:
        return jsonify({"success": False, "error": "Oturum suresi dolmus. Sayfayi yenileyip tekrar giris yapin."}), 401

    if roles and current_user.role not in roles:
        return jsonify({"success": False, "error": "Bu islem icin yetkiniz yok."}), 403

    return None

def _product_price_payload(price_record):
    return {
        "success": True,
        "product_code": price_record.product_code,
        "unit_cost": price_record.unit_price,
        "unit_price": price_record.unit_price,
        "price": price_record.unit_price,
        "cost": price_record.unit_price,
        "currency": price_record.currency or "TRY",
        "vat_rate": price_record.vat_rate,
        "updated_at": price_record.updated_at.isoformat() if price_record.updated_at else None,
        "data": {
            "unit_cost": price_record.unit_price,
            "unit_price": price_record.unit_price,
            "price": price_record.unit_price,
            "cost": price_record.unit_price,
            "currency": price_record.currency or "TRY",
            "vat_rate": price_record.vat_rate
        }
    }

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

@main_bp.route('/api/v1/products/<path:product_code>/price', methods=['GET'])
@main_bp.route('/api/v1/purchasing/product/<path:product_code>', methods=['GET'])
@main_bp.route('/api/products/<path:product_code>/price', methods=['GET'])
def get_product_price(product_code):
    """Stok sisteminin urun koduna gore guncel satin alma fiyatini cekmesi icin API."""
    if not _api_key_is_valid():
        return jsonify({"success": False, "error": "Gecersiz API anahtari"}), 401

    price_record = ProductPrice.query.filter_by(product_code=product_code).first()

    if not price_record:
        return jsonify({
            "success": False,
            "error": "Urun icin kayitli fiyat bulunamadi",
            "product_code": product_code
        }), 404

    return jsonify(_product_price_payload(price_record))

@main_bp.route('/api/v1/products/prices', methods=['POST'])
def update_price():
    """Kullanıcının girdiği yerel ürün fiyatını güncelle"""
    auth_error = _json_auth_error()
    if auth_error:
        return auth_error

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

@main_bp.route('/api/v1/products/prices/bulk', methods=['POST'])
def update_prices_bulk():
    """Birden fazla urun fiyatini tek istekte guncelle."""
    auth_error = _json_auth_error('admin', 'manager')
    if auth_error:
        return auth_error

    data = request.get_json(silent=True) or {}
    items = data.get('items') or []

    if not isinstance(items, list) or not items:
        return jsonify({"success": False, "error": "Guncellenecek urun listesi bos"}), 400

    results = []
    changed_records = []

    for item in items:
        product_code = str(item.get('product_code') or '').strip()
        unit_price_raw = item.get('unit_price')
        vat_rate_raw = item.get('vat_rate')
        currency = str(item.get('currency') or 'TRY').strip().upper()[:10] or 'TRY'

        if not product_code or unit_price_raw is None:
            results.append({"product_code": product_code, "success": False, "error": "Urun kodu veya fiyat eksik"})
            continue

        try:
            unit_price = float(unit_price_raw)
        except (TypeError, ValueError):
            results.append({"product_code": product_code, "success": False, "error": "Gecersiz fiyat formati"})
            continue

        if unit_price < 0:
            results.append({"product_code": product_code, "success": False, "error": "Fiyat negatif olamaz"})
            continue

        try:
            vat_rate = float(vat_rate_raw) if vat_rate_raw is not None else 20.0
        except (TypeError, ValueError):
            vat_rate = 20.0

        price_record = ProductPrice.query.filter_by(product_code=product_code).first()
        if price_record:
            price_record.unit_price = unit_price
            price_record.vat_rate = vat_rate
            price_record.currency = currency
        else:
            price_record = ProductPrice(
                product_code=product_code,
                unit_price=unit_price,
                vat_rate=vat_rate,
                currency=currency
            )
            db.session.add(price_record)

        changed_records.append((product_code, unit_price, vat_rate, currency))
        results.append({
            "product_code": product_code,
            "success": True,
            "unit_price": unit_price,
            "vat_rate": vat_rate,
            "currency": currency
        })

    if changed_records:
        db.session.commit()
    else:
        db.session.rollback()

    api_client = StockAPIClient()
    sync_errors = []
    for product_code, unit_price, vat_rate, currency in changed_records:
        sync_result = api_client.update_product_price(
            product_code=product_code,
            new_price=unit_price,
            vat_rate=vat_rate,
            currency=currency
        )
        if not sync_result.get('success'):
            sync_errors.append({
                "product_code": product_code,
                "error": sync_result.get('error', 'Ana stok senkronizasyon hatasi')
            })

    updated = sum(1 for result in results if result.get('success'))
    failed = len(results) - updated

    return jsonify({
        "success": failed == 0,
        "message": f"{updated} fiyat guncellendi",
        "total": len(items),
        "updated": updated,
        "failed": failed,
        "results": results,
        "sync_errors": sync_errors[:20]
    }), 200 if failed == 0 else 207

@main_bp.route('/api/v1/products/prices/sync-all', methods=['POST'])
def sync_all_prices():
    """Kayitli tum yerel fiyatlari ana stok sistemine toplu olarak yansit."""
    auth_error = _json_auth_error('admin', 'manager')
    if auth_error:
        return auth_error

    prices = ProductPrice.query.order_by(ProductPrice.product_code).all()

    if not prices:
        return jsonify({
            "success": False,
            "error": "Senkronize edilecek kayitli fiyat bulunamadi",
            "total": 0,
            "synced": 0,
            "failed": 0,
            "errors": []
        }), 400

    api_client = StockAPIClient()
    synced = 0
    errors = []

    for price in prices:
        result = api_client.update_product_price(
            product_code=price.product_code,
            new_price=price.unit_price,
            vat_rate=price.vat_rate,
            currency=price.currency or 'TRY'
        )

        if result.get('success'):
            synced += 1
        else:
            errors.append({
                "product_code": price.product_code,
                "error": result.get('error', 'Bilinmeyen hata')
            })

    failed = len(errors)
    return jsonify({
        "success": failed == 0,
        "message": f"{synced} fiyat ana sisteme yansitildi",
        "total": len(prices),
        "synced": synced,
        "failed": failed,
        "errors": errors[:20]
    }), 200 if failed == 0 else 207
