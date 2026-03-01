# Satın Alma Yönetim Sistemi

Ana stok uygulamasından **tamamen bağımsız** satın alma birimi için özel uygulama.

## 🎯 Özellikler

- ✅ **Kritik Stok Takibi**: Ana stok uygulamasından API ile kritik ürünleri alır
- ✅ **Sipariş Yönetimi**: Tedarikçilere sipariş oluşturma ve takip
- ✅ **Tedarikçi Yönetimi**: Tedarikçi bilgileri ve performans takibi
- ✅ **Ayrı Authentication**: Satın alma personeli için özel giriş sistemi
- ✅ **Güvenlik**: Satın alma personeli stok uygulamasını göremez

## 📁 Proje Yapısı

```
celmakstok-purchasing/
├── app/
│   ├── __init__.py
│   ├── models.py              # User, Supplier, PurchaseOrder
│   ├── stock_api.py           # Ana stok API istemcisi
│   ├── routes/
│   │   ├── auth.py            # Giriş/çıkış
│   │   ├── main.py            # Dashboard
│   │   ├── purchasing.py      # Kritik ürünler, siparişler
│   │   └── suppliers.py       # Tedarikçi yönetimi
│   └── templates/
├── config.py
├── run.py
└── requirements.txt
```

## 🚀 Kurulum

### 1. Virtual Environment Oluştur

```bash
cd celmakstok-purchasing
python -m venv venv
venv\Scripts\activate  # Windows
```

### 2. Gereksinimleri Yükle

```bash
pip install -r requirements.txt
```

### 3. Ortam Değişkenlerini Ayarla

`.env.example` dosyasını `.env` olarak kopyalayın ve düzenleyin:

```env
SECRET_KEY=your-secret-key-here
STOCK_API_URL=http://localhost:5000  # Ana stok uygulaması URL'i
STOCK_API_KEY=your-api-key-here      # Ana stok API key (güvenlik için)
```

### 4. Veritabanını Oluştur

```bash
python run.py
```

İlk çalıştırmada veritabanı otomatik oluşturulur.

### 5. İlk Kullanıcıyı Ekle

Python shell'de:

```python
from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    user = User(
        name='Satın Alma Admin',
        username='satinalma',
        role='purchasing'
    )
    user.set_password('12345')
    db.session.add(user)
    db.session.commit()
```

## ▶️ Çalıştırma

```bash
python run.py
```

Uygulama **http://localhost:5001** adresinde çalışacak.

## 🔗 Ana Stok Uygulaması ile Bağlantı

Bu uygulama ana stok sisteminden şu API endpoint'lerini kullanır:

- `GET /api/v1/purchasing/critical-products` - Kritik stokları listele
- `GET /api/v1/purchasing/product/{code}` - Ürün detayı

### API Güvenliği

Ana stok uygulamasında `.env` dosyasına API key ekleyin:

```env
API_KEY=your-secure-api-key
```

Satın alma uygulamasında da aynı key'i kullanın.

## 👥 Kullanıcı Rolleri

- **purchasing**: Normal satın alma personeli
- **manager**: Satın alma müdürü (onay yetkisi)
- **admin**: Sistem yöneticisi

## 📊 Durum Akışı

Siparişler şu durumlardan geçer:

1. **pending** - Bekliyor
2. **approved** - Onaylandı
3. **ordered** - Tedarikçiye sipariş verildi
4. **received** - Teslim alındı
5. **cancelled** - İptal edildi

## 🔒 Güvenlik Notları

- Satın alma personeli **SADECE** bu uygulamayı kullanır
- Ana stok uygulamasına erişim YOK
- Veriler API üzerinden senkronize edilir
- Her uygulamanın kendi veritabanı var

## 🛠️ Geliştirme

### Database Migration

```bash
flask db init
flask db migrate -m "migration message"
flask db upgrade
```

### Debug Mode

Development ortamında otomatik debug aktif. Production için:

```python
app.run(debug=False, port=5001)
```

## 📞 Destek

Herhangi bir sorun için lütfen sistem yöneticisi ile iletişime geçin.
