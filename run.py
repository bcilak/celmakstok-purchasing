from app import create_app, db
from app.models import User, Supplier, PurchaseOrder

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'Supplier': Supplier,
        'PurchaseOrder': PurchaseOrder
    }

if __name__ == '__main__':
    import os
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=True, port=port)
