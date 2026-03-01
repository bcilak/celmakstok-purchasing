"""
Veritabanını başlat ve test kullanıcısı ekle
"""
from app import create_app, db
from app.models import User, Supplier

def init_database():
    app = create_app()
    
    with app.app_context():
        # Tabloları oluştur
        print("Veritabanı tabloları oluşturuluyor...")
        db.create_all()
        
        # Test kullanıcısı ekle
        if not User.query.filter_by(username='satinalma').first():
            user = User(
                name='Satın Alma Personeli',
                username='satinalma',
                email='satinalma@example.com',
                role='purchasing'
            )
            user.set_password('12345')
            db.session.add(user)
            print("✓ Test kullanıcısı eklendi: satinalma / 12345")
        
        # Admin kullanıcısı ekle
        if not User.query.filter_by(username='admin').first():
            admin = User(
                name='Sistem Yöneticisi',
                username='admin',
                email='admin@example.com',
                role='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            print("✓ Admin kullanıcısı eklendi: admin / admin123")
        
        # Örnek tedarikçi ekle
        if not Supplier.query.filter_by(code='TED001').first():
            supplier = Supplier(
                code='TED001',
                name='Örnek Tedarikçi A.Ş.',
                contact_person='Ahmet Yılmaz',
                phone='0212 555 0001',
                email='info@tedarikciornek.com',
                address='İstanbul, Türkiye',
                tax_number='1234567890',
                rating=4
            )
            db.session.add(supplier)
            print("✓ Örnek tedarikçi eklendi")
        
        db.session.commit()
        print("\n✅ Veritabanı başarıyla oluşturuldu!")
        print("\nGiriş bilgileri:")
        print("  Kullanıcı: satinalma")
        print("  Şifre: 12345")
        print("\nUygulamayı başlatmak için: python run.py")

if __name__ == '__main__':
    init_database()
