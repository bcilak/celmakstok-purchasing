from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file, make_response
from flask_login import login_required, current_user
from app.utils.decorators import roles_required
from app.models import PurchaseOrder, Supplier, SupplierProduct, ProductPrice, OrderTemplate
from app.stock_api import StockAPIClient
from app.utils.price_helper import PriceHelper
from app import db
from datetime import datetime, timedelta
import io
import csv
import re
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

purchasing_bp = Blueprint('purchasing', __name__)

@purchasing_bp.route('/')
@login_required
def index():
    """Satın Alma Ana Sayfa - Kritik Ürünler"""
    
    # API'den kritik ürünleri çek
    api_client = StockAPIClient()
    critical_data = api_client.get_critical_products()
    
    # Filtreleme parametreleri
    category_filter = request.args.get('category', '')
    search = request.args.get('search', '')
    priority_filter = request.args.get('priority', '')
    sort_by = request.args.get('sort', 'priority')
    
    products = critical_data.get('products', [])
    
    # Lokal fiyatları çek ve merge et
    local_prices = {p.product_code: {'price': p.unit_price, 'vat': p.vat_rate} for p in ProductPrice.query.all()}
    
    # Her ürün için kritiklik analizi ekle
    for product in products:
        # Fiyatı ve KDV'yi güncelle
        if product['code'] in local_prices:
            product['unit_price'] = local_prices[product['code']]['price']
            product['vat_rate'] = local_prices[product['code']]['vat']
        else:
            product['vat_rate'] = 20.0  # Varsayılan KDV
            
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
        
        # Stok yüzdesi
        stock_percentage = (current / minimum * 100) if minimum > 0 else 0
        product['stock_percentage'] = stock_percentage
        
        # Kritiklik seviyesi
        if stock_percentage <= 20:
            product['priority'] = 'urgent'
            product['priority_label'] = 'Acil'
            product['priority_color'] = 'danger'
            product['priority_score'] = 4
        elif stock_percentage <= 50:
            product['priority'] = 'high'
            product['priority_label'] = 'Yüksek'
            product['priority_color'] = 'warning'
            product['priority_score'] = 3
        elif stock_percentage <= 75:
            product['priority'] = 'normal'
            product['priority_label'] = 'Normal'
            product['priority_color'] = 'info'
            product['priority_score'] = 2
        else:
            product['priority'] = 'low'
            product['priority_label'] = 'Düşük'
            product['priority_color'] = 'secondary'
            product['priority_score'] = 1
        
        # Eksik miktar
        product['shortage'] = max(0, minimum - current)
        product['is_critical'] = product['shortage'] > 0
        
        # Önerilen sipariş (Eksik miktar kadar)
        product['suggested_order'] = int(product['shortage'])
        
        # Tahmini maliyet (KDV'siz)
        try:
            unit_price = float(product.get('unit_price', 0))
        except (ValueError, TypeError):
            unit_price = 0.0
            
        try:
            vat_rate = float(product.get('vat_rate', 20.0))
        except (ValueError, TypeError):
            vat_rate = 20.0
            
        product['unit_price'] = unit_price
        product['vat_rate'] = vat_rate
        
        estimated_cost = product['suggested_order'] * unit_price
        product['estimated_cost'] = estimated_cost
        product['total_with_vat'] = estimated_cost * (1 + (vat_rate / 100.0))
    
    # Filtreleme uygula
    if category_filter:
        products = [p for p in products if p.get('category') == category_filter]
    
    if priority_filter:
        products = [p for p in products if p.get('priority') == priority_filter]
    
    if search:
        search_lower = search.lower()
        products = [p for p in products if 
                   search_lower in p.get('name', '').lower() or 
                   search_lower in p.get('code', '').lower()]
    
    # Sıralama
    if sort_by == 'priority':
        products.sort(key=lambda x: x.get('priority_score', 0), reverse=True)
    elif sort_by == 'shortage':
        products.sort(key=lambda x: x.get('shortage', 0), reverse=True)
    elif sort_by == 'cost':
        products.sort(key=lambda x: x.get('estimated_cost', 0), reverse=True)
    elif sort_by == 'name':
        products.sort(key=lambda x: x.get('name', ''))
    
    # Kategorileri al (unique)
    categories = list(set([p.get('category') for p in critical_data.get('products', []) if p.get('category')]))
    categories.sort()
    
    # Maliyet analizi
    total_cost = sum(p.get('estimated_cost', 0) for p in products)
    total_cost_vat = sum(p.get('total_with_vat', 0) for p in products)
    urgent_products = [p for p in products if p.get('priority') == 'urgent']
    urgent_cost_vat = sum(p.get('total_with_vat', 0) for p in urgent_products)
    
    # Kategori bazlı maliyet dağılımı
    category_costs = {}
    for product in products:
        cat = product.get('category', 'Diğer')
        category_costs[cat] = category_costs.get(cat, 0) + product.get('total_with_vat', 0)
    
    # Akıllı öneriler
    suggestions = []
    
    # 3 gündür kritik olan ürünleri kontrol et (simüle)
    if len(urgent_products) > 0:
        suggestions.append({
            'type': 'warning',
            'icon': 'exclamation-triangle',
            'message': f'{len(urgent_products)} ürün acil seviyede! Hemen sipariş verilmeli.'
        })
    
    # Yüksek maliyetli kategoriler
    if category_costs:
        max_cost_cat = max(category_costs.items(), key=lambda x: x[1])
        if max_cost_cat[1] > total_cost * 0.3:
            suggestions.append({
                'type': 'info',
                'icon': 'info-circle',
                'message': f'{max_cost_cat[0]} kategorisi toplam maliyetin %{int(max_cost_cat[1]/total_cost*100)}ini oluşturuyor.'
            })
    
    # Toplu sipariş önerisi
    if len(products) >= 5:
        suggestions.append({
            'type': 'success',
            'icon': 'cart-plus',
            'message': f'{len(products)} kritik ürün için toplu sipariş oluşturabilirsiniz.'
        })
    
    # API mode bilgisini ekle
    api_mode = critical_data.get('mode', 'unknown')
    
    # Summary dict oluştur
    summary = {
        'urgent_count': len(urgent_products),
        'urgent_cost': urgent_cost_vat,
        'total_count': len([p for p in products if p.get('is_critical')]),
        'total_cost': sum(p.get('estimated_cost', 0) for p in products if p.get('is_critical')),
        'total_cost_vat': sum(p.get('total_with_vat', 0) for p in products if p.get('is_critical')),
        'all_products_count': len(products)
    }
    
    return render_template('purchasing/critical_products_new.html',
                         products=products,
                         categories=categories,
                         selected_category=category_filter,
                         selected_priority=priority_filter,
                         search=search,
                         sort_by=sort_by,
                         api_connected=critical_data.get('success', False),
                         api_mode=api_mode,
                         total_cost=total_cost,
                         total_cost_vat=total_cost_vat,
                         urgent_cost=urgent_cost_vat,
                         urgent_count=len(urgent_products),
                         category_costs=category_costs,
                         suggestions=suggestions,
                         summary=summary)

@purchasing_bp.route('/prices')
@login_required
@roles_required('admin', 'manager')
def manage_prices():
    """Tüm Ürünlerin Fiyat ve KDV Yönetimi Sayfası"""
    api_client = StockAPIClient()
    api_response = api_client.get_critical_products()
    all_products = api_response.get('products', [])
    
    local_prices = {p.product_code: {'price': p.unit_price, 'vat': p.vat_rate} for p in ProductPrice.query.all()}
    
    products_with_prices = []
    
    for product in all_products:
        code = product.get('code')
        if code in local_prices:
            product['unit_price'] = local_prices[code]['price']
            product['vat_rate'] = local_prices[code]['vat']
        else:
            product['unit_price'] = 0.0
            product['vat_rate'] = 20.0
            
        products_with_prices.append(product)
        
    # Sıralama: İsim
    products_with_prices.sort(key=lambda x: x.get('name', ''))
    
    return render_template('purchasing/prices.html',
                           products=products_with_prices,
                           api_connected=api_response.get('success', False))

@purchasing_bp.route('/product/<product_code>')
@login_required
def product_detail(product_code):
    """Ürün detayı ve sipariş geçmişi"""
    
    # API'den ürün detayını çek
    api_client = StockAPIClient()
    product_data = api_client.get_product_detail(product_code)
    
    if not product_data.get('success'):
        flash('Ürün bilgisi alınamadı!', 'danger')
        return redirect(url_for('purchasing.index'))
    
    # Bu ürün için geçmiş siparişler
    orders = PurchaseOrder.query.filter_by(
        product_code=product_code
    ).order_by(PurchaseOrder.created_at.desc()).all()
    
    # Tedarikçi listesi (sipariş için)
    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()
    
    return render_template('purchasing/product_detail.html',
                         product=product_data.get('product'),
                         orders=orders,
                         suppliers=suppliers)

@purchasing_bp.route('/orders')
@login_required
def orders():
    """Tüm Siparişler - batch'lere göre gruplu gösterim"""
    from collections import OrderedDict

    # Filtreleme
    status_filter = request.args.get('status', '')
    supplier_filter = request.args.get('supplier', '')

    query = PurchaseOrder.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    if supplier_filter:
        query = query.filter_by(supplier_id=int(supplier_filter))

    all_orders = query.order_by(PurchaseOrder.created_at.desc()).all()

    # batch_number'a göre grupla; eski siparişlerde batch_number yoksa order_number'u key kullan
    batches_dict = OrderedDict()
    for order in all_orders:
        key = order.batch_number or order.order_number
        if key not in batches_dict:
            batches_dict[key] = []
        batches_dict[key].append(order)

    # Her batch için özet bilgi hesapla
    STATUS_PRIORITY = {'pending': 0, 'approved': 1, 'ordered': 2, 'received': 3, 'cancelled': 4}

    batch_list = []
    for key, order_items in batches_dict.items():
        statuses = [o.status for o in order_items]
        unique_statuses = set(statuses)
        dominant = min(unique_statuses, key=lambda s: STATUS_PRIORITY.get(s, 99))

        totals = {}
        for o in order_items:
            totals[o.currency] = totals.get(o.currency, 0) + o.total_price

        batch_list.append({
            'batch_number': key,
            'supplier': order_items[0].supplier,
            'orders': order_items,
            'item_count': len(order_items),
            'status': dominant,
            'mixed_status': len(unique_statuses) > 1,
            'totals': totals,
            'created_at': order_items[-1].created_at,  # en eski (ilk oluşturulan)
            'expected_delivery_date': order_items[0].expected_delivery_date,
            'is_overdue': any(o.is_overdue for o in order_items),
            'first_order_id': order_items[0].id,
        })

    # Manuel sayfalama (batch bazında)
    page = request.args.get('page', 1, type=int)
    per_page = 15
    total_batches = len(batch_list)
    total_pages = max(1, (total_batches + per_page - 1) // per_page)
    start = (page - 1) * per_page
    page_batches = batch_list[start:start + per_page]

    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()

    return render_template('purchasing/orders.html',
                           batches=page_batches,
                           suppliers=suppliers,
                           status_filter=status_filter,
                           supplier_filter=supplier_filter,
                           page=page,
                           total_pages=total_pages,
                           has_prev=page > 1,
                           has_next=page < total_pages,
                           prev_num=page - 1,
                           next_num=page + 1)

@purchasing_bp.route('/approvals')
@login_required
@roles_required('admin', 'manager')
def approvals():
    """Onay Bekleyen Siparişler"""
    pending_orders = PurchaseOrder.query.filter_by(status='pending').order_by(PurchaseOrder.created_at.desc()).all()
    return render_template('purchasing/approvals.html', orders=pending_orders)


@purchasing_bp.route('/batch/<batch_number>/update-status', methods=['POST'])
@login_required
def batch_update_status(batch_number):
    """Sipariş grubunun (batch) durumunu toplu güncelle"""
    new_status = request.form.get('status')

    if new_status not in ['pending', 'approved', 'ordered', 'received', 'cancelled']:
        flash('Geçersiz durum!', 'danger')
        return redirect(url_for('purchasing.orders'))

    if new_status == 'approved' and current_user.role not in ['admin', 'manager']:
        flash('Siparişleri onaylama yetkiniz bulunmamaktadır!', 'danger')
        return redirect(url_for('purchasing.orders'))

    # batch_number veya order_number ile siparişleri bul
    batch_orders = PurchaseOrder.query.filter_by(batch_number=batch_number).all()
    if not batch_orders:
        batch_orders = PurchaseOrder.query.filter_by(order_number=batch_number).all()

    if not batch_orders:
        flash('Sipariş grubu bulunamadı!', 'danger')
        return redirect(url_for('purchasing.orders'))

    api_client = StockAPIClient()
    for order in batch_orders:
        order.status = new_status
        if new_status == 'received' and not order.actual_delivery_date:
            order.actual_delivery_date = datetime.utcnow()
            api_client.update_stock_receipt({
                'order_number': order.order_number,
                'product_code': order.product_code,
                'quantity': order.quantity,
                'receipt_date': order.actual_delivery_date.isoformat(),
                'unit_price': order.unit_price,
                'currency': order.currency
            })

    db.session.commit()
    count = len(batch_orders)
    flash(f'{count} kalem siparişin durumu güncellendi.', 'success')
    return redirect(url_for('purchasing.orders'))

@purchasing_bp.route('/order/new', methods=['GET', 'POST'])
@login_required
def new_order():
    """Yeni Sipariş Oluştur"""
    
    if request.method == 'POST':
        try:
            # Çoklu ürün satırlarını al
            product_codes = request.form.getlist('product_code[]')
            product_names = request.form.getlist('product_name[]')
            quantities = request.form.getlist('quantity[]')
            unit_types = request.form.getlist('unit_type[]')
            unit_prices = request.form.getlist('unit_price[]')
            currencies = request.form.getlist('currency[]')

            supplier_id = int(request.form.get('supplier_id'))
            priority = request.form.get('priority', 'normal')
            notes = request.form.get('notes')
            delivery_str = request.form.get('expected_delivery_date')
            expected_delivery_date = datetime.strptime(delivery_str, '%Y-%m-%d') if delivery_str else None

            # Boş satırları filtrele
            items = [
                (product_codes[i].strip(), product_names[i].strip(), quantities[i],
                 unit_types[i] if unit_types else 'Adet',
                 unit_prices[i] if unit_prices else '0',
                 currencies[i] if currencies else 'TRY')
                for i in range(len(product_codes))
                if product_codes[i].strip() and product_names[i].strip() and quantities[i]
            ]

            if not items:
                flash('En az bir geçerli ürün satırı girmelisiniz.', 'danger')
                raise ValueError('Boş sipariş')

            created_orders = []
            api_client = StockAPIClient()
            batch_number = None  # İlk order_number batch kimliği olur

            for code, name, qty_str, unit, price_str, currency in items:
                last_order = PurchaseOrder.query.order_by(PurchaseOrder.id.desc()).first()
                order_number = f"PO-{datetime.utcnow().year}-{(last_order.id + 1) if last_order else 1:05d}"

                if batch_number is None:
                    batch_number = order_number  # İlk kalemin numarası grup kimliği

                quantity = float(qty_str)
                unit_price = float(price_str)
                total_price = quantity * unit_price

                order = PurchaseOrder(
                    order_number=order_number,
                    batch_number=batch_number,
                    supplier_id=supplier_id,
                    product_code=code,
                    product_name=name,
                    quantity=quantity,
                    unit_type=unit,
                    unit_price=unit_price,
                    total_price=total_price,
                    currency=currency,
                    priority=priority,
                    expected_delivery_date=expected_delivery_date,
                    notes=notes,
                    created_by_id=current_user.id
                )
                db.session.add(order)
                db.session.flush()  # ID'yi şimdi al
                created_orders.append(order)

            db.session.commit()

            # API: Her kalem için "yoldaki stok" bildirimi
            for order in created_orders:
                api_client.notify_in_transit_stock({
                    'order_number': order.order_number,
                    'product_code': order.product_code,
                    'quantity': order.quantity,
                    'expected_date': order.expected_delivery_date.isoformat() if order.expected_delivery_date else None,
                    'supplier_id': order.supplier_id
                })

            order_nums = ', '.join(o.order_number for o in created_orders)
            flash(f'{len(created_orders)} kalem için sipariş oluşturuldu: {order_nums}', 'success')
            return redirect(url_for('purchasing.orders'))

        except ValueError:
            db.session.rollback()
        except Exception as e:
            db.session.rollback()
            flash(f'Sipariş oluşturulamadı: {str(e)}', 'danger')
    
    # GET isteği - Form göster
    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()
    
    # Tüm ürünleri getir (Arama ve doğrulama için)
    api_client = StockAPIClient()
    products_response = api_client.get_all_products()
    all_products = products_response.get('products', []) if products_response.get('success') else []
    
    # Eğer product_code parametresi varsa, fiyat önerisi al
    product_code = request.args.get('product_code')
    price_suggestions = None
    
    if product_code:
        price_suggestions = PriceHelper.get_suggested_price(product_code)
        
        # Tedarikçi karşılaştırması
        if suppliers:
            supplier_prices = PriceHelper.compare_supplier_prices(product_code)
            price_suggestions['supplier_comparison'] = supplier_prices
    
    return render_template('purchasing/new_order.html', 
                         suppliers=suppliers,
                         all_products=all_products,
                         product_code=product_code,
                         price_suggestions=price_suggestions)

@purchasing_bp.route('/order/<int:id>/update-status', methods=['POST'])
@login_required
def update_order_status(id):
    """Sipariş durumunu güncelle"""
    
    order = PurchaseOrder.query.get_or_404(id)
    new_status = request.form.get('status')
    source = request.form.get('source', 'orders')
    
    if new_status in ['pending', 'approved', 'ordered', 'received', 'cancelled']:
        # Yetki kontrolü: Onaylama işlemini sadece admin veya manager yapabilir
        if new_status == 'approved' and current_user.role not in ['admin', 'manager']:
            flash('Siparişleri onaylama yetkiniz bulunmamaktadır!', 'danger')
            return redirect(url_for('purchasing.orders'))
            
        order.status = new_status
        
        # Teslim alındıysa tarihi kaydet ve ana sisteme gönder
        if new_status == 'received' and not order.actual_delivery_date:
            order.actual_delivery_date = datetime.utcnow()
            
            # API Entegrasyonu: Depo Girişi (Stok Artırma)
            api_client = StockAPIClient()
            api_client.update_stock_receipt({
                'order_number': order.order_number,
                'product_code': order.product_code,
                'quantity': order.quantity,
                'receipt_date': order.actual_delivery_date.isoformat(),
                'unit_price': order.unit_price,
                'currency': order.currency
            })
        
        db.session.commit()
        flash('Sipariş durumu güncellendi!', 'success')
    else:
        flash('Geçersiz durum!', 'danger')
    
    if source == 'approvals':
        return redirect(url_for('purchasing.approvals'))
    return redirect(url_for('purchasing.orders'))

@purchasing_bp.route('/bulk-order/preview', methods=['POST'])
@login_required
def preview_bulk_order():
    """Toplu sipariş önizlemesi - Tedarikçi gruplama"""
    try:
        selected_products = request.json.get('products', [])
        
        if not selected_products:
            return jsonify({'success': False, 'error': 'Ürün seçilmedi'}), 400
        
        # Ürünleri tedarikçilere göre grupla
        grouping_result = PriceHelper.group_products_by_supplier(selected_products)
        
        return jsonify({
            'success': True,
            'grouped': grouping_result['grouped'],
            'unassigned': grouping_result['unassigned']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@purchasing_bp.route('/bulk-order', methods=['POST'])
@login_required
def create_bulk_order():
    """Toplu sipariş oluştur - Akıllı tedarikçi gruplama"""
    try:
        selected_products = request.json.get('products', [])
        
        if not selected_products:
            return jsonify({'success': False, 'error': 'Ürün seçilmedi'}), 400
        
        # Ürünleri tedarikçilere göre grupla
        grouping_result = PriceHelper.group_products_by_supplier(selected_products)
        grouped = grouping_result['grouped']
        unassigned = grouping_result['unassigned']
        
        created_orders = []
        total_cost = 0
        failed_products = []
        
        # Her tedarikçi için ayrı siparişler oluştur
        for supplier_id, supplier_data in grouped.items():
            supplier_name = supplier_data['supplier_name']
            
            for product in supplier_data['products']:
                try:
                    # Sipariş numarası oluştur
                    last_order = PurchaseOrder.query.order_by(PurchaseOrder.id.desc()).first()
                    order_number = f"PO-{datetime.now().year}-{(last_order.id + 1) if last_order else 1:05d}"
                    
                    order = PurchaseOrder(
                        order_number=order_number,
                        supplier_id=supplier_id,
                        product_code=product['product_code'],
                        product_name=product['product_name'],
                        quantity=product['quantity'],
                        unit_type=product.get('unit_type', 'Adet'),
                        unit_price=product['unit_price'],
                        total_price=product['total_price'],
                        currency=product.get('currency', 'TRY'),
                        priority=product.get('priority', 'normal'),
                        status='pending',
                        created_by_id=current_user.id,
                        expected_delivery_date=datetime.now() + timedelta(
                            days=product.get('lead_time_days', 7)
                        )
                    )
                    
                    db.session.add(order)
                    created_orders.append({
                        'order_number': order_number,
                        'supplier': supplier_name,
                        'product': product['product_name']
                    })
                    total_cost += order.total_price
                    
                except Exception as e:
                    failed_products.append({
                        'product': product['product_name'],
                        'error': str(e)
                    })
        
        # Değişiklikleri kaydet
        if created_orders:
            db.session.commit()
        
        # Atanmamış ürünler varsa uyar
        warnings = []
        if unassigned:
            warnings.append(f"{len(unassigned)} ürün için tedarikçi bulunamadı")
        if failed_products:
            warnings.append(f"{len(failed_products)} ürün için sipariş oluşturulamadı")
        
        return jsonify({
            'success': True,
            'message': f'{len(created_orders)} sipariş oluşturuldu',
            'created_orders': created_orders,
            'total_cost': total_cost,
            'unassigned_products': unassigned,
            'failed_products': failed_products,
            'warnings': warnings,
            'supplier_count': len(grouped)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@purchasing_bp.route('/export/excel')
@login_required
def export_excel():
    """Kritik ürünleri Excel olarak indir"""
    api_client = StockAPIClient()
    critical_data = api_client.get_critical_products()
    products = critical_data.get('products', [])
    
    # CSV oluştur
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Başlıklar
    writer.writerow(['Ürün Kodu', 'Ürün Adı', 'Kategori', 'Mevcut Stok', 'Minimum Stok', 
                     'Eksik Miktar', 'Önerilen Sipariş', 'Birim Fiyat', 'Tahmini Maliyet', 'Öncelik'])
    
    # Veriler
    for product in products:
        try:
            current = float(product.get('current_stock', 0))
        except (ValueError, TypeError):
            current = 0.0
            
        try:
            minimum = float(product.get('minimum_stock', 0))
        except (ValueError, TypeError):
            minimum = 0.0
            
        shortage = max(0, minimum - current)
        suggested = int(shortage)
        
        try:
            unit_price = float(product.get('unit_price', 0))
        except (ValueError, TypeError):
            unit_price = 0.0
            
        try:
            vat_rate = float(product.get('vat_rate', 20.0))
        except (ValueError, TypeError):
            vat_rate = 20.0
            
        cost = suggested * unit_price
        total_with_vat = cost * (1 + (vat_rate / 100))
        
        stock_pct = (current / minimum * 100) if minimum > 0 else 0
        if stock_pct <= 20:
            priority = 'Acil'
        elif stock_pct <= 50:
            priority = 'Yüksek'
        elif stock_pct <= 75:
            priority = 'Normal'
        else:
            priority = 'Düşük'
        
        writer.writerow([
            product.get('code', ''),
            product.get('name', ''),
            product.get('category', ''),
            current,
            minimum,
            shortage,
            suggested,
            unit_price,
            vat_rate,
            total_with_vat,
            priority
        ])
    
    # Response oluştur
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=kritik_urunler_{datetime.now().strftime("%Y%m%d")}.csv'
    response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'
    
    return response

@purchasing_bp.route('/delivery-timeline')
@login_required
def delivery_timeline():
    """Teslimat takvimi"""
    # Gelecek 30 gün için siparişler
    start_date = datetime.now()
    end_date = start_date + timedelta(days=30)
    
    orders = PurchaseOrder.query.filter(
        PurchaseOrder.expected_delivery_date.between(start_date, end_date),
        PurchaseOrder.status.in_(['approved', 'ordered'])
    ).order_by(PurchaseOrder.expected_delivery_date).all()
    
    # Geciken siparişler
    overdue_orders = PurchaseOrder.query.filter(
        PurchaseOrder.expected_delivery_date < datetime.now(),
        PurchaseOrder.status.in_(['approved', 'ordered'])
    ).order_by(PurchaseOrder.expected_delivery_date).all()
    
    return render_template('purchasing/delivery_timeline.html',
                         orders=orders,
                         overdue_orders=overdue_orders)

@purchasing_bp.route('/export/pdf')
@login_required
def export_pdf():
    """Kritik ürünleri PDF olarak indir"""
    api_client = StockAPIClient()
    critical_data = api_client.get_critical_products()
    products = critical_data.get('products', [])
    
    # PDF buffer
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    
    # Başlık
    styles = getSampleStyleSheet()
    title = Paragraph('<b>Kritik Stok Raporu</b>', styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 0.3*inch))
    
    # Tarih
    date_text = Paragraph(f'Tarih: {datetime.now().strftime("%d.%m.%Y %H:%M")}', styles['Normal'])
    elements.append(date_text)
    elements.append(Spacer(1, 0.2*inch))
    
    # Tablo verisi
    data = [['Kod', 'Ürün Adı', 'Mevcut', 'Min', 'Eksik', 'Fiyat', 'Maliyet']]
    
    for product in products[:50]:  # İlk 50 ürün
        try:
            current = float(product.get('current_stock', 0))
        except (ValueError, TypeError):
            current = 0.0
            
        try:
            minimum = float(product.get('minimum_stock', 0))
        except (ValueError, TypeError):
            minimum = 0.0
            
        shortage = max(0, minimum - current)
        suggested = int(shortage)
        
        try:
            unit_price = float(product.get('unit_price', 0))
        except (ValueError, TypeError):
            unit_price = 0.0
        
        try:
            vat_rate = float(product.get('vat_rate', 20.0))
        except (ValueError, TypeError):
            vat_rate = 20.0
            
        cost = suggested * unit_price
        total_with_vat = cost * (1 + (vat_rate / 100))
        
        data.append([
            product.get('code', '')[:10],
            product.get('name', '')[:30],
            str(current),
            str(minimum),
            str(shortage),
            f"₺{unit_price:.0f} (+%{int(vat_rate)} KDV)",
            f"₺{total_with_vat:.0f}"
        ])
    
    # Tablo oluştur
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    doc.build(elements)
    
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f'kritik_urunler_{datetime.now().strftime("%Y%m%d")}.pdf', mimetype='application/pdf')

@purchasing_bp.route('/api/suppliers')
@login_required
def api_suppliers():
    """Tedarikçi listesini JSON olarak döndür"""
    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()
    
    return jsonify({
        'suppliers': [{
            'id': s.id,
            'name': s.name,
            'contact_person': s.contact_person,
            'phone': s.phone
        } for s in suppliers]
    })

@purchasing_bp.route('/order/<int:order_id>/document', methods=['GET', 'POST'])
@login_required
def order_document(order_id):
    """Sipariş için şablondan belge oluştur/düzenle"""
    order = PurchaseOrder.query.get_or_404(order_id)
    templates = OrderTemplate.query.filter_by(is_active=True).order_by(OrderTemplate.name).all()

    selected_template_id = request.args.get('template_id', type=int)
    if not selected_template_id and templates:
        default_t = next((t for t in templates if 'VARSAYILAN' in t.name.upper()), templates[0])
        selected_template_id = default_t.id

    content = ''

    if selected_template_id:
        template_obj = OrderTemplate.query.get_or_404(selected_template_id)
        content = template_obj.content

        # Batch'teki tüm kalemleri getir
        if order.batch_number:
            batch_orders = PurchaseOrder.query.filter_by(
                batch_number=order.batch_number
            ).order_by(PurchaseOrder.id).all()
        else:
            batch_orders = [order]

        # --- Sipariş düzeyi değişkenler (ilk kalemden) ---
        content = content.replace('{{ order_number }}', order.order_number or '')
        content = content.replace('{{ order_date }}',
            order.order_date.strftime('%d.%m.%Y') if order.order_date else '')
        content = content.replace('{{ expected_delivery_date }}',
            order.expected_delivery_date.strftime('%d.%m.%Y') if order.expected_delivery_date else '')

        # --- Tedarikçi değişkenler ---
        if order.supplier:
            tax_info = ''
            if order.supplier.tax_office and order.supplier.tax_number:
                tax_info = f'{order.supplier.tax_office} / {order.supplier.tax_number}'
            elif order.supplier.tax_number:
                tax_info = order.supplier.tax_number
            content = content.replace('{{ supplier_name }}', order.supplier.name or '')
            content = content.replace('{{ supplier_contact }}', order.supplier.contact_person or '')
            content = content.replace('{{ supplier_address }}', order.supplier.address or '')
            content = content.replace('{{ supplier_tax }}', tax_info)
        else:
            for v in ['{{ supplier_name }}', '{{ supplier_contact }}',
                      '{{ supplier_address }}', '{{ supplier_tax }}']:
                content = content.replace(v, '')

        # --- Ürün değişkenler: çoklu kalem desteği ---
        PRODUCT_VARS = [
            '{{ product_code }}', '{{ product_name }}', '{{ quantity }}',
            '{{ unit_type }}', '{{ unit_price }}', '{{ total_price }}', '{{ currency }}'
        ]

        def _fill_item(tmpl, bo, idx):
            """Bir şablon metnindeki ürün değişkenlerini tek bir kalemle doldurur."""
            tmpl = tmpl.replace('{{ product_code }}', bo.product_code or '')
            tmpl = tmpl.replace('{{ product_name }}', bo.product_name or '')
            tmpl = tmpl.replace('{{ quantity }}', str(bo.quantity) if bo.quantity else '0')
            tmpl = tmpl.replace('{{ unit_type }}', bo.unit_type or '')
            tmpl = tmpl.replace('{{ unit_price }}', f'{bo.unit_price:,.2f}' if bo.unit_price else '0.00')
            tmpl = tmpl.replace('{{ total_price }}', f'{bo.total_price:,.2f}' if bo.total_price else '0.00')
            tmpl = tmpl.replace('{{ currency }}', bo.currency or 'TRY')
            return tmpl

        # 1) {{ items_table }} varsa hazır HTML tablo ile değiştir
        if '{{ items_table }}' in content:
            td = 'style="border:1px solid #ccc;padding:4px 8px;"'
            th = 'style="border:1px solid #ccc;padding:4px 8px;background:#f0f0f0;"'
            rows_html = ''.join(
                f'<tr>'
                f'<td {td} style="border:1px solid #ccc;padding:4px 8px;text-align:center;">{i}</td>'
                f'<td {td}>{bo.product_code or ""}</td>'
                f'<td {td}>{bo.product_name or ""}</td>'
                f'<td {td} style="border:1px solid #ccc;padding:4px 8px;text-align:center;">{bo.quantity or 0} {bo.unit_type or ""}</td>'
                f'<td {td} style="border:1px solid #ccc;padding:4px 8px;text-align:right;">{bo.unit_price:,.2f} {bo.currency}</td>'
                f'<td {td} style="border:1px solid #ccc;padding:4px 8px;text-align:right;">{bo.total_price:,.2f} {bo.currency}</td>'
                f'</tr>'
                for i, bo in enumerate(batch_orders, 1)
            )
            grand_total = sum(bo.total_price or 0 for bo in batch_orders)
            currency0 = batch_orders[0].currency if batch_orders else 'TRY'
            items_table_html = (
                f'<table style="width:100%;border-collapse:collapse;font-size:11pt;">'
                f'<thead><tr>'
                f'<th {th}>S/N</th><th {th}>Stok Kodu</th><th {th}>Malın Tanımı</th>'
                f'<th {th}>Miktar</th><th {th}>Birim Fiyat</th><th {th}>Toplam</th>'
                f'</tr></thead><tbody>{rows_html}</tbody>'
                f'<tfoot><tr><td colspan="5" style="text-align:right;padding:4px 8px;"><strong>Genel Toplam</strong></td>'
                f'<td style="border:1px solid #ccc;padding:4px 8px;text-align:right;"><strong>{grand_total:,.2f} {currency0}</strong></td></tr></tfoot>'
                f'</table>'
            )
            content = content.replace('{{ items_table }}', items_table_html)

        # 2) Şablonda <tr> içinde ürün değişkeni varsa:
        #    - Ürün değişkeni içeren TÜM satırları bul
        #    - İlk N tanesini ürün verileriyle doldur, kalanları boşalt
        elif any(v in content for v in PRODUCT_VARS):
            tr_re = re.compile(
                r'<tr(?:\s[^>]*)?>(?:(?!</tr>).)*?(?:' +
                '|'.join(re.escape(v) for v in PRODUCT_VARS) +
                r')(?:(?!</tr>).)*?</tr>',
                re.DOTALL | re.IGNORECASE
            )
            all_matches = list(tr_re.finditer(content))
            if all_matches:
                # İçeriği parçalara bölerek değiştir (sondan başa doğru ki offset bozulmasın)
                for idx, m in reversed(list(enumerate(all_matches))):
                    if idx < len(batch_orders):
                        # Bu satıra karşılık gelen ürün verisini doldur
                        replacement = _fill_item(m.group(0), batch_orders[idx], idx + 1)
                    else:
                        # Fazla satır: tüm ürün değişkenlerini boşalt
                        row = m.group(0)
                        for v in PRODUCT_VARS:
                            row = row.replace(v, '')
                        replacement = row
                    content = content[:m.start()] + replacement + content[m.end():]
            else:
                content = _fill_item(content, batch_orders[0], 1)

    return render_template('purchasing/document.html',
                           order=order,
                           templates=templates,
                           selected_template_id=selected_template_id,
                           content=content)

