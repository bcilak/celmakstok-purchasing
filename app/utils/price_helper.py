"""Fiyat Yönetimi Yardımcı Fonksiyonlar"""
from datetime import datetime
from sqlalchemy import func
from app import db
from app.models import SupplierProduct, PurchaseOrder, Supplier


class PriceHelper:
    """Ürün fiyatlarını yönetmek için yardımcı sınıf"""
    
    @staticmethod
    def get_best_supplier_for_product(product_code):
        """
        Bir ürün için en iyi tedarikçiyi öner
        
        Öncelik:
        1. En düşük fiyatlı aktif tedarikçi (SupplierProduct'tan)
        2. Geçmişte en çok sipariş verilen tedarikçi
        3. None (ürün hiçbir tedarikçide yok)
        """
        # 1. Fiyat listesinden en ucuz tedarikçi
        best_price = SupplierProduct.query.filter_by(
            product_code=product_code,
            is_active=True
        ).filter(
            db.or_(
                SupplierProduct.valid_until == None,
                SupplierProduct.valid_until > datetime.utcnow()
            )
        ).order_by(SupplierProduct.unit_price.asc()).first()
        
        if best_price:
            return {
                'supplier_id': best_price.supplier_id,
                'supplier_name': best_price.supplier.name,
                'unit_price': best_price.unit_price,
                'currency': best_price.currency,
                'source': 'catalog',
                'lead_time_days': best_price.lead_time_days,
                'minimum_order_quantity': best_price.minimum_order_quantity
            }
        
        # 2. Geçmiş siparişlerden en sık kullanılan tedarikçi
        recent_order = PurchaseOrder.query.filter_by(
            product_code=product_code,
            status='received'
        ).order_by(PurchaseOrder.created_at.desc()).first()
        
        if recent_order:
            return {
                'supplier_id': recent_order.supplier_id,
                'supplier_name': recent_order.supplier.name,
                'unit_price': recent_order.unit_price,
                'currency': recent_order.currency,
                'source': 'historical',
                'lead_time_days': None,
                'minimum_order_quantity': None
            }
        
        # 3. Ürün hiçbir yerde yok
        return None
    
    @staticmethod
    def group_products_by_supplier(product_list):
        """
        Ürünleri tedarikçilere göre grupla (toplu sipariş için)
        
        Args:
            product_list: List of dicts with 'product_code' and 'quantity'
        
        Returns:
            Dict: {supplier_id: [products]}
        """
        grouped = {}
        unassigned = []
        
        for item in product_list:
            product_code = item.get('product_code')
            quantity = item.get('quantity', 0)
            
            # En iyi tedarikçiyi bul
            best_supplier = PriceHelper.get_best_supplier_for_product(product_code)
            
            if best_supplier:
                supplier_id = best_supplier['supplier_id']
                
                if supplier_id not in grouped:
                    grouped[supplier_id] = {
                        'supplier_name': best_supplier['supplier_name'],
                        'products': []
                    }
                
                grouped[supplier_id]['products'].append({
                    'product_code': product_code,
                    'product_name': item.get('product_name', product_code),
                    'quantity': quantity,
                    'unit_price': best_supplier['unit_price'],
                    'currency': best_supplier['currency'],
                    'total_price': quantity * best_supplier['unit_price'],
                    'lead_time_days': best_supplier['lead_time_days']
                })
            else:
                unassigned.append({
                    'product_code': product_code,
                    'product_name': item.get('product_name', product_code),
                    'quantity': quantity,
                    'reason': 'Tedarikçi bulunamadı'
                })
        
        return {
            'grouped': grouped,
            'unassigned': unassigned
        }
    
    @staticmethod
    def get_suggested_price(product_code, supplier_id=None):
        """
        Ürün için önerilen fiyatı hesapla (3 seçenek kombinasyonu)
        
        Öncelik sırası:
        1. Tedarikçi-ürün fiyat listesi (Seçenek 1)
        2. Geçmiş sipariş ortalaması (Seçenek 2)
        3. API'den gelen fiyat (Seçenek 3)
        """
        result = {
            'suggested_price': 0,
            'source': 'none',
            'alternatives': []
        }
        
        # Seçenek 1: Tedarikçi fiyat listesinden
        if supplier_id:
            supplier_price = SupplierProduct.get_supplier_price(supplier_id, product_code)
            if supplier_price:
                result['suggested_price'] = supplier_price.unit_price
                result['source'] = 'supplier_catalog'
                result['lead_time'] = supplier_price.lead_time_days
                return result
        
        # Tüm tedarikçilerin fiyatlarını al (alternatifler için)
        all_supplier_prices = SupplierProduct.query.filter_by(
            product_code=product_code,
            is_active=True
        ).filter(
            db.or_(
                SupplierProduct.valid_until == None,
                SupplierProduct.valid_until > datetime.utcnow()
            )
        ).order_by(SupplierProduct.unit_price.asc()).all()
        
        if all_supplier_prices:
            result['alternatives'] = [{
                'supplier_id': sp.supplier_id,
                'supplier_name': sp.supplier.name,
                'price': sp.unit_price,
                'lead_time': sp.lead_time_days
            } for sp in all_supplier_prices]
            
            # En düşük fiyatı öner
            if not result['suggested_price']:
                result['suggested_price'] = all_supplier_prices[0].unit_price
                result['source'] = 'best_supplier_price'
        
        # Seçenek 2: Geçmiş sipariş ortalaması
        if not result['suggested_price'] or result['source'] == 'best_supplier_price':
            avg_price = PriceHelper.get_average_historical_price(product_code, supplier_id)
            if avg_price:
                if not result['suggested_price']:
                    result['suggested_price'] = avg_price
                    result['source'] = 'historical_average'
                result['historical_average'] = avg_price
        
        return result
    
    @staticmethod
    def get_average_historical_price(product_code, supplier_id=None, limit=5):
        """
        Seçenek 2: Geçmiş siparişlerden ortalama fiyat hesapla
        
        Args:
            product_code: Ürün kodu
            supplier_id: Tedarikçi ID (opsiyonel)
            limit: Kaç sipariş ortalaması alınacak
        """
        query = PurchaseOrder.query.filter_by(
            product_code=product_code,
            status='received'  # Sadece teslim alınan siparişler
        )
        
        if supplier_id:
            query = query.filter_by(supplier_id=supplier_id)
        
        # Son N siparişin ortalaması
        recent_orders = query.order_by(
            PurchaseOrder.created_at.desc()
        ).limit(limit).all()
        
        if recent_orders:
            total = sum(order.unit_price for order in recent_orders)
            return total / len(recent_orders)
        
        return None
    
    @staticmethod
    def get_price_trend(product_code, months=6):
        """
        Ürün fiyat trendini döndür (grafik için)
        """
        from datetime import timedelta
        start_date = datetime.utcnow() - timedelta(days=months*30)
        
        orders = PurchaseOrder.query.filter(
            PurchaseOrder.product_code == product_code,
            PurchaseOrder.created_at >= start_date,
            PurchaseOrder.status.in_(['received', 'ordered'])
        ).order_by(PurchaseOrder.created_at.asc()).all()
        
        trend_data = []
        for order in orders:
            trend_data.append({
                'date': order.created_at.strftime('%Y-%m'),
                'price': order.unit_price,
                'supplier': order.supplier.name
            })
        
        return trend_data
    
    @staticmethod
    def compare_supplier_prices(product_code):
        """
        Tüm tedarikçilerin fiyatlarını karşılaştır
        """
        suppliers_data = []
        
        # Aktif fiyat listelerinden
        catalog_prices = SupplierProduct.query.filter_by(
            product_code=product_code,
            is_active=True
        ).filter(
            db.or_(
                SupplierProduct.valid_until == None,
                SupplierProduct.valid_until > datetime.utcnow()
            )
        ).all()
        
        for sp in catalog_prices:
            # Geçmiş sipariş ortalamasını da ekle
            historical_avg = PriceHelper.get_average_historical_price(
                product_code, 
                sp.supplier_id
            )
            
            suppliers_data.append({
                'supplier_id': sp.supplier_id,
                'supplier_name': sp.supplier.name,
                'catalog_price': sp.unit_price,
                'historical_avg': historical_avg,
                'lead_time': sp.lead_time_days,
                'last_updated': sp.updated_at
            })
        
        # En ucuzdan pahalıya sırala
        suppliers_data.sort(key=lambda x: x['catalog_price'])
        
        return suppliers_data
