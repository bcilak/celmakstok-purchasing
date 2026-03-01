import requests
from flask import current_app
from datetime import datetime, timedelta
import os

class StockAPIClient:
    """Ana Stok Uygulaması ile İletişim"""
    
    def __init__(self):
        self.base_url = current_app.config['STOCK_API_URL']
        self.api_key = current_app.config.get('STOCK_API_KEY', '')
        self.use_local_mode = current_app.config.get('USE_LOCAL_MODE', False)
    
    def _get_headers(self):
        """API request headers"""
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['X-API-Key'] = self.api_key
        return headers
    
    def _get_mock_critical_products(self):
        """Local mode için örnek kritik ürün verileri"""
        return {
            'success': True,
            'products': [
                {
                    'code': 'URN-001',
                    'name': 'Çelik Vida 5x50mm',
                    'category': 'Hırdavat',
                    'current_stock': 500,
                    'minimum_stock': 1000,
                    'unit': 'Adet',
                    'supplier': 'Hırdavatçı AŞ',
                    'unit_price': 1.50
                },
                {
                    'code': 'URN-002',
                    'name': 'Sanayi Tipi Rulman 6204',
                    'category': 'Mekanik',
                    'current_stock': 12,
                    'minimum_stock': 50,
                    'unit': 'Adet',
                    'supplier': 'Rulsan Ltd',
                    'unit_price': 45.00
                },
                {
                    'code': 'URN-003',
                    'name': 'Alüminyum Profil 40x40',
                    'category': 'Metal',
                    'current_stock': 25,
                    'minimum_stock': 100,
                    'unit': 'Mt',
                    'supplier': 'Alüminyum AŞ',
                    'unit_price': 85.00
                },
                {
                    'code': 'KIM-015',
                    'name': 'Endüstriyel Temizleyici',
                    'category': 'Kimyasal',
                    'current_stock': 5,
                    'minimum_stock': 20,
                    'unit': 'Lt',
                    'supplier': 'Kimya Sanayi',
                    'unit_price': 120.00
                },
                {
                    'code': 'ELK-042',
                    'name': 'Kablo 3x2.5 TTR (Siyah)',
                    'category': 'Elektrik',
                    'current_stock': 80,
                    'minimum_stock': 250,
                    'unit': 'Mt',
                    'supplier': 'ElektroKablo',
                    'unit_price': 22.50
                },
                {
                    'code': 'PLST-078',
                    'name': 'Plastik Kutu X-Small',
                    'category': 'Ambalaj',
                    'current_stock': 1500,
                    'minimum_stock': 5000,
                    'unit': 'Adet',
                    'supplier': 'Plastikçi AŞ',
                    'unit_price': 4.50
                },
                {
                    'code': 'HRD-102',
                    'name': 'Matkap Ucu 8mm',
                    'category': 'Hırdavat',
                    'current_stock': 3,
                    'minimum_stock': 25,
                    'unit': 'Adet',
                    'supplier': 'Hırdavatçı AŞ',
                    'unit_price': 35.00
                },
                {
                    'code': 'HRD-103',
                    'name': 'Pul M8 Geniş',
                    'category': 'Hırdavat',
                    'current_stock': 400,
                    'minimum_stock': 2000,
                    'unit': 'Kg',
                    'supplier': 'Civata Dünyası',
                    'unit_price': 65.00
                },
                {
                    'code': 'CEL-201',
                    'name': 'Paslanmaz Çelik Sac 2mm',
                    'category': 'Metal',
                    'current_stock': 400,
                    'minimum_stock': 1000,
                    'unit': 'Kg',
                    'supplier': 'Çelik Yatakları',
                    'unit_price': 120.00
                }
            ],
            'count': 9,
            'mode': 'local'
        }
    
    def get_critical_products(self):
        """Kritik stok seviyesindeki ürünleri getir"""
        # Local mode kontrolü
        if self.use_local_mode:
            return self._get_mock_critical_products()
        
        try:
            url = f"{self.base_url}/api/v1/purchasing/critical-products"
            response = requests.get(url, headers=self._get_headers(), timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # API formatı {'products': [...]} veya {'data': [...]} olabilir
                product_list = data.get('products', data.get('data', []))
                return {
                    'success': True,
                    'products': product_list,
                    'count': data.get('count', len(product_list)),
                    'mode': 'api'
                }
            else:
                # API hatası durumunda mock data dön
                print(f"API Error: {response.status_code}, falling back to local mode")
                return self._get_mock_critical_products()
        except Exception as e:
            # Bağlantı hatası durumunda mock data dön
            print(f"Connection Error: {str(e)}, falling back to local mode")
            return self._get_mock_critical_products()

    def get_all_products(self):
        """Tüm ürünleri getir (Arama ve yeni sipariş için)"""
        if self.use_local_mode:
            return self._get_mock_critical_products() # mockup returns critical ones as ALL for now

        try:
            # /critical-products endpoint'i mevcut ana uygulamada tüm aktif ürünleri dönüyor
            # Hata olasılığına karşı kullanıcıda çalıştığını bildiğimiz endpointi kullanıyoruz.
            url = f"{self.base_url}/api/v1/purchasing/critical-products"
            response = requests.get(url, headers=self._get_headers(), timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                product_list = data.get('products', data.get('data', []))
                return {
                    'success': True,
                    'products': product_list,
                    'count': data.get('count', len(product_list)),
                    'mode': 'api'
                }
            else:
                print(f"API Error in get_all_products: {response.status_code}, falling back")
                return self._get_mock_critical_products()
        except Exception as e:
            print(f"Connection Error in get_all_products: {str(e)}")
            return self._get_mock_critical_products()
    
    def get_product_detail(self, product_code):
        """Belirli bir ürünün detaylı bilgisini getir"""
        # Local mode kontrolü
        if self.use_local_mode:
            # Mock data'dan ürünü bul
            mock_data = self._get_mock_critical_products()
            for product in mock_data['products']:
                if product['code'] == product_code:
                    return {
                        'success': True,
                        'product': product,
                        'mode': 'local'
                    }
            return {
                'success': False,
                'error': 'Product not found',
                'mode': 'local'
            }
        
        try:
            # Önce kritik ürünler listesinden çek
            url = f"{self.base_url}/api/v1/purchasing/critical-products"
            response = requests.get(url, headers=self._get_headers(), timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                products = data.get('products', [])
                
                # Ürünü listede bul
                for product in products:
                    if product.get('code') == product_code:
                        return {
                            'success': True,
                            'product': product,
                            'mode': 'api'
                        }
            
            # Ürün bulunamadıysa fallback olarak mock data'dan dene
            print(f"Product {product_code} not found in API, trying mock data")
            mock_data = self._get_mock_critical_products()
            for product in mock_data['products']:
                if product['code'] == product_code:
                    return {
                        'success': True,
                        'product': product,
                        'mode': 'local'
                    }
            
            return {
                'success': False,
                'error': 'Product not found',
                'mode': 'api'
            }
        except Exception as e:
            print(f"API Error in get_product_detail: {str(e)}")
            # Hata durumunda mock data'dan dene
            mock_data = self._get_mock_critical_products()
            for product in mock_data['products']:
                if product['code'] == product_code:
                    return {
                        'success': True,
                        'product': product,
                        'mode': 'local'
                    }
            return {
                'success': False,
                'error': str(e)
            }
    
    def check_connection(self):
        """API bağlantısını test et"""
        try:
            url = f"{self.base_url}/api/health"
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except:
            return False

    def notify_in_transit_stock(self, order_data):
        """Sipariş verildiğinde ana sisteme 'Yoldaki Stok' bilgisini gönder"""
        if self.use_local_mode:
            print(f"[LOCAL MODE] In-Transit Stock Notification: {order_data}")
            return {'success': True, 'mode': 'local'}
            
        try:
            url = f"{self.base_url}/api/v1/stock/in-transit"
            response = requests.post(url, headers=self._get_headers(), json=order_data, timeout=10)
            
            if response.status_code == 200:
                return {'success': True, 'data': response.json(), 'mode': 'api'}
            print(f"API Error (notify_in_transit_stock): {response.status_code} - {response.text}")
            return {'success': False, 'error': f"HTTP {response.status_code}", 'mode': 'api'}
        except Exception as e:
            print(f"Connection Error (notify_in_transit_stock): {str(e)}")
            return {'success': False, 'error': str(e), 'mode': 'api'}

    def update_stock_receipt(self, receipt_data):
        """Sipariş teslim alındığında ana sisteme depo giriş/stok artırma fişi gönder"""
        if self.use_local_mode:
            print(f"[LOCAL MODE] Stock Receipt Push: {receipt_data}")
            return {'success': True, 'mode': 'local'}
            
        try:
            url = f"{self.base_url}/api/v1/stock/receipt"
            response = requests.post(url, headers=self._get_headers(), json=receipt_data, timeout=10)
            
            if response.status_code == 200:
                return {'success': True, 'data': response.json(), 'mode': 'api'}
            print(f"API Error (update_stock_receipt): {response.status_code} - {response.text}")
            return {'success': False, 'error': f"HTTP {response.status_code}", 'mode': 'api'}
        except Exception as e:
            print(f"Connection Error (update_stock_receipt): {str(e)}")
            return {'success': False, 'error': str(e), 'mode': 'api'}

    def update_product_price(self, product_code, new_price, vat_rate=None, currency='TRY'):
        """Satınalma tarafında fiyat güncellendiğinde ana sistemdeki unit_cost'u senkronize et"""
        if self.use_local_mode:
            print(f"[LOCAL MODE] Product Price Sync - {product_code}: {new_price} {currency} (VAT: {vat_rate})")
            return {'success': True, 'mode': 'local'}
            
        try:
            url = f"{self.base_url}/api/v1/products/sync-cost"
            payload = {
                'product_code': product_code,
                'unit_cost': new_price,
                'currency': currency
            }
            if vat_rate is not None:
                payload['vat_rate'] = vat_rate
                
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=10)
            
            if response.status_code == 200:
                return {'success': True, 'data': response.json(), 'mode': 'api'}
            print(f"API Error (update_product_price): {response.status_code} - {response.text}")
            return {'success': False, 'error': f"HTTP {response.status_code}", 'mode': 'api'}
        except Exception as e:
            print(f"Connection Error (update_product_price): {str(e)}")
            return {'success': False, 'error': str(e), 'mode': 'api'}
