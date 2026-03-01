"""
Bu dosyayı sunucudaki app/routes/api.py dosyasına ekleyin veya mevcut kodu güncelleyin

KULLANIM:
1. SSH ile sunucuya bağlanın
2. cd /var/www/celmakstok/app/routes
3. Bu dosyanın içeriğini api.py'ye ekleyin
4. sudo systemctl restart gunicorn (veya apache2)
"""

from flask import Blueprint, jsonify, request, current_app
from functools import wraps
import os

# ÖNEMLİ: Bu import'ların dosyanın başında olduğundan emin olun
from app.models import Product, Supplier, db
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta

api_bp = Blueprint('api', __name__, url_prefix='/api')

# API Key doğrulama decorator
def require_api_key(f):
    """API Key gereksinimi için decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Header'dan API key al
        api_key = request.headers.get('X-API-Key')
        
        # Config'den beklenen key'i al
        expected_key = current_app.config.get('API_KEY')
        if not expected_key:
            expected_key = os.environ.get('API_KEY', 'sk_live_3102591Ab.')
        
        # Key kontrolü
        if not api_key:
            return jsonify({
                'error': 'API key gerekli',
                'message': 'X-API-Key header\'ı eksik'
            }), 401
        
        if api_key != expected_key:
            current_app.logger.warning(f"Invalid API key attempt: {api_key}")
            return jsonify({
                'error': 'Geçersiz veya eksik API key',
                'message': 'API key doğrulanamadı'
            }), 401
        
        return f(*args, **kwargs)
    return decorated_function

# Health Check Endpoint
@api_bp.route('/v1/health', methods=['GET'])
def health_check():
    """API sağlık kontrolü"""
    try:
        # Database bağlantısını test et
        db.session.execute('SELECT 1')
        db_status = 'connected'
    except Exception as e:
        db_status = f'error: {str(e)}'
    
    return jsonify({
        'status': 'healthy',
        'database': db_status,
        'timestamp': datetime.now().isoformat()
    }), 200

# Critical Products Endpoint (DÜZELTİLMİŞ VERSİYON)
@api_bp.route('/v1/purchasing/critical-products', methods=['GET'])
@require_api_key
def get_critical_products():
    """
    Kritik stok seviyesindeki ürünleri döndürür
    
    Returns:
        JSON: {
            'success': bool,
            'products': list,
            'count': int
        }
    """
    try:
        # Log: API çağrısı yapıldı
        current_app.logger.info("Critical products API called")
        
        # Kritik ürünleri getir
        # current_stock < minimum_stock olan ürünler
        critical_products = Product.query.filter(
            Product.current_stock < Product.minimum_stock
        ).order_by(
            Product.category,
            Product.name
        ).all()
        
        # Log: Kaç ürün bulundu
        current_app.logger.info(f"Found {len(critical_products)} critical products")
        
        # Ürünleri JSON formatına çevir
        products_data = []
        for product in critical_products:
            try:
                product_dict = {
                    'code': product.code,
                    'name': product.name,
                    'category': product.category if hasattr(product, 'category') else 'Kategori Yok',
                    'current_stock': float(product.current_stock) if product.current_stock else 0.0,
                    'minimum_stock': float(product.minimum_stock) if product.minimum_stock else 0.0,
                    'unit': product.unit if hasattr(product, 'unit') else 'Adet',
                    'supplier': None,
                    'last_order_date': None,
                    'unit_price': 0.0
                }
                
                # Supplier bilgisi varsa ekle
                if hasattr(product, 'supplier') and product.supplier:
                    product_dict['supplier'] = product.supplier.name
                
                # Son sipariş tarihi varsa ekle
                if hasattr(product, 'last_order_date') and product.last_order_date:
                    product_dict['last_order_date'] = product.last_order_date.isoformat()
                
                # Birim fiyat varsa ekle
                if hasattr(product, 'unit_price') and product.unit_price:
                    product_dict['unit_price'] = float(product.unit_price)
                
                products_data.append(product_dict)
                
            except Exception as e:
                # Bir üründe hata olsa bile devam et
                current_app.logger.error(f"Error serializing product {product.code}: {str(e)}")
                continue
        
        # Başarılı response
        return jsonify({
            'success': True,
            'products': products_data,
            'count': len(products_data),
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        # Hata durumunda detaylı log
        current_app.logger.error(f"Critical products API error: {str(e)}", exc_info=True)
        
        # Hata response
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# Tek Ürün Detay Endpoint
@api_bp.route('/v1/purchasing/product/<product_code>', methods=['GET'])
@require_api_key
def get_product_detail(product_code):
    """Belirli bir ürünün detaylı bilgisini döndürür"""
    try:
        product = Product.query.filter_by(code=product_code).first()
        
        if not product:
            return jsonify({
                'success': False,
                'error': 'Product not found',
                'message': f'Ürün kodu bulunamadı: {product_code}'
            }), 404
        
        product_dict = {
            'code': product.code,
            'name': product.name,
            'category': product.category if hasattr(product, 'category') else None,
            'current_stock': float(product.current_stock) if product.current_stock else 0.0,
            'minimum_stock': float(product.minimum_stock) if product.minimum_stock else 0.0,
            'unit': product.unit if hasattr(product, 'unit') else 'Adet',
            'supplier': product.supplier.name if hasattr(product, 'supplier') and product.supplier else None,
            'last_order_date': product.last_order_date.isoformat() if hasattr(product, 'last_order_date') and product.last_order_date else None,
            'unit_price': float(product.unit_price) if hasattr(product, 'unit_price') and product.unit_price else 0.0
        }
        
        return jsonify({
            'success': True,
            'product': product_dict
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Product detail API error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Blueprint'i app'e kaydet
# Ana __init__.py dosyasında:
# from app.routes.api import api_bp
# app.register_blueprint(api_bp)
