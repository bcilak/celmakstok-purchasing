with open('app/templates/base.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Ekleme yapalim nav linklere
old_prices = '''                    <li class=\"nav-item\">\n                        <a class=\"nav-link {% if request.endpoint == 'purchasing.manage_prices' %}active{% endif %}\" href=\"{{ url_for('purchasing.manage_prices') }}\">\n                            <i class=\"bi bi-currency-dollar\"></i> Fiyat Yönetimi\n                        </a>\n                    </li>'''
new_prices = '''                    {% if current_user.role in ['admin', 'manager'] %}
                    <li class=\"nav-item\">
                        <a class=\"nav-link {% if request.endpoint == 'purchasing.manage_prices' %}active{% endif %}\" href=\"{{ url_for('purchasing.manage_prices') }}\">
                            <i class=\"bi bi-currency-dollar\"></i> Fiyat Yönetimi
                        </a>
                    </li>
                    {% endif %}'''

if old_prices in text:
    text = text.replace(old_prices, new_prices)
    
# Menu'ye Admin panel linki ekleyelim
admin_link = '''                    {% if current_user.role == 'admin' %}
                    <li class=\"nav-item\">
                        <a class=\"nav-link {% if request.endpoint == 'admin_bp.manage_users' %}active{% endif %}\" href=\"{{ url_for('admin_bp.manage_users') }}\">
                            <i class=\"bi bi-shield-lock\"></i> Kullanıcı Yönetimi
                        </a>
                    </li>
                    {% endif %}'''

if admin_link not in text:
    # Tedarikçiler'den sonraya ekleyelim
    supplier_link = '''                    <li class=\"nav-item\">\n                        <a class=\"nav-link {% if request.endpoint == 'suppliers.index' %}active{% endif %}\" href=\"{{ url_for('suppliers.index') }}\">\n                            <i class=\"bi bi-building\"></i> Tedarikçiler\n                        </a>\n                    </li>'''
    text = text.replace(supplier_link, supplier_link + '\n' + admin_link)

with open('app/templates/base.html', 'w', encoding='utf-8') as f:
    f.write(text)
