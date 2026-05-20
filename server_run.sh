#!/bin/bash

# ÇELMAK Satınalma Yönetim Sistemi - Sunucu Yeniden Başlatma ve Güncelleme Betiği
# Bu betik sunucudaki en son değişiklikleri çeker, çalışan eski süreçleri sonlandırır ve uygulamayı yeniler.

echo "=========================================="
echo "🔄 ÇELMAK Satınalma Yönetim Uygulaması Güncelleniyor..."
echo "=========================================="

# 1. Kodları Güncelle (Git Pull)
echo "📥 Git üzerinden en son kodlar çekiliyor..."
git pull
if [ $? -ne 0 ]; then
    echo "❌ HATA: git pull başarısız oldu! İnternet bağlantısını veya git durumunu kontrol edin."
    exit 1
fi

echo "✅ Kodlar başarıyla güncellendi."

# 2. Çalışan gunicorn sürecini kontrol et ve yeniden başlat
echo "⚙️ Uygulama yeniden başlatılıyor..."

# Eğer systemd servisi aktifse ve kullanıcının yetkisi varsa systemctl restart deneyelim
if systemctl is-active --quiet celmakstok-purchasing.service 2>/dev/null; then
    echo "🔄 systemd servisi (celmakstok-purchasing.service) yeniden başlatılıyor..."
    sudo systemctl restart celmakstok-purchasing.service
    
    if [ $? -eq 0 ]; then
        echo "✅ Uygulama systemd aracılığıyla başarıyla yeniden başlatıldı."
        echo "=========================================="
        exit 0
    else
        echo "⚠️ systemd servisi yetki veya başka bir nedenle yeniden başlatılamadı, manuel yönteme geçiliyor..."
    fi
fi

# Manuel yöntem: Çalışan eski gunicorn süreçlerini sonlandır
echo "🛑 Çalışan eski süreçler aranıyor ve sonlandırılıyor..."

# Port 5001'i dinleyen süreci bulup sonlandır
PID=$(lsof -t -i:5001 2>/dev/null)
if [ -n "$PID" ]; then
    echo "Port 5001 üzerinde çalışan süreç bulundu (PID: $PID). Sonlandırılıyor..."
    kill -9 $PID 2>/dev/null
    sleep 2
else
    # Alternatif olarak gunicorn adına göre sonlandır (5001 portunu kullanan)
    pkill -9 -f "gunicorn.*127.0.0.1:5001" 2>/dev/null
    sleep 2
fi

# Yeni gunicorn sürecini başlat
echo "🚀 Gunicorn ile yeni uygulama süreci başlatılıyor..."
if [ -d ".venv" ]; then
    VENV_PATH=".venv"
elif [ -d "venv" ]; then
    VENV_PATH="venv"
else
    echo "❌ HATA: Sanal ortam (.venv veya venv) bulunamadı!"
    exit 1
fi

# Gunicorn'u arka planda başlat ve logları gunicorn.log dosyasına yaz
nohup $VENV_PATH/bin/gunicorn --workers 4 --bind 127.0.0.1:5001 --timeout 120 run:app > gunicorn.log 2>&1 &

# Başlatma kontrolü
sleep 3
NEW_PID=$(lsof -t -i:5001 2>/dev/null)
if [ -n "$NEW_PID" ]; then
    echo "✅ Uygulama başarıyla başlatıldı ve arka planda çalışıyor (PID: $NEW_PID)."
else
    # Gunicorn adı ile arayalım (lsof olmaması durumuna karşı)
    NEW_GUNICORN_PID=$(pgrep -f "gunicorn.*127.0.0.1:5001")
    if [ -n "$NEW_GUNICORN_PID" ]; then
         echo "✅ Uygulama başarıyla başlatıldı ve arka planda çalışıyor (PID: $NEW_GUNICORN_PID)."
    else
         echo "❌ HATA: Uygulama başlatılamadı! Lütfen 'gunicorn.log' dosyasını kontrol edin."
         exit 1
    fi
fi

echo "=========================================="
