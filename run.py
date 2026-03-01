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
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)  # Farklı port - 5001
