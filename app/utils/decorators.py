from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user

def roles_required(*roles):
    """
    Kullanıcının belirtilen rollerden en az birine sahip olmasını gerektiren decorator.
    Kullanıcı giriş yapmamışsa login sayfasına,
    yetkisi yoksa dashboard'a gönderilir.
    """
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login', next=request.url))
            
            if current_user.role not in roles:
                flash('Bu sayfayı görüntülemek için yetkiniz bulunmuyor.', 'danger')
                return redirect(url_for('main.dashboard'))
                
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper
