"""
PharmaPOS Pro - Complete Backend API
Flask + SQLite + JWT Authentication
"""
import sqlite3, bcrypt, jwt, os, json
from datetime import datetime, timedelta, date
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, g
from flask_cors import CORS
import uuid

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)

SECRET_KEY = "pharmapos-secret-2025-xk9p"
DB_PATH = r"C:\Application\PharmaPOS_Pro\pharmapos.db"

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────
def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db

def query(sql, params=(), one=False, commit=False):
    db = get_db()
    try:
        cur = db.execute(sql, params)
        if commit:
            db.commit()
            return cur.lastrowid
        rv = cur.fetchone() if one else cur.fetchall()
        return [dict(r) for r in rv] if not one else (dict(rv) if rv else None)
    finally:
        db.close()

def init_db():
    db = get_db()
    cur = db.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS stores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        address TEXT,
        phone TEXT,
        license_no TEXT,
        vat_rate REAL DEFAULT 7.5,
        currency TEXT DEFAULT 'BDT',
        low_stock_threshold INTEGER DEFAULT 10,
        expiry_alert_days INTEGER DEFAULT 30,
        receipt_footer TEXT DEFAULT 'Thank you! Stay healthy.',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id INTEGER DEFAULT 1,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'cashier',
        is_active INTEGER DEFAULT 1,
        last_login TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(store_id) REFERENCES stores(id)
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        entity TEXT,
        entity_id INTEGER,
        detail TEXT,
        ip TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT
    );

    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id INTEGER DEFAULT 1,
        name TEXT NOT NULL,
        contact_person TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        trade_license TEXT,
        payment_terms INTEGER DEFAULT 30,
        credit_limit REAL DEFAULT 0,
        discount_pct REAL DEFAULT 0,
        outstanding_balance REAL DEFAULT 0,
        rating REAL DEFAULT 5.0,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS medicines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id INTEGER DEFAULT 1,
        sku TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        generic_name TEXT,
        brand_name TEXT,
        manufacturer TEXT,
        category_id INTEGER,
        dosage_form TEXT DEFAULT 'Tablet',
        strength TEXT,
        purchase_unit TEXT DEFAULT 'Box',
        selling_unit TEXT DEFAULT 'Strip',
        strips_per_box INTEGER DEFAULT 10,
        tablets_per_strip INTEGER DEFAULT 10,
        purchase_price REAL DEFAULT 0,
        selling_price REAL DEFAULT 0,
        reorder_level INTEGER DEFAULT 10,
        vat_rate REAL DEFAULT 7.5,
        is_rx INTEGER DEFAULT 0,
        is_controlled INTEGER DEFAULT 0,
        is_temp_sensitive INTEGER DEFAULT 0,
        storage_notes TEXT,
        barcode TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(category_id) REFERENCES categories(id)
    );

    CREATE TABLE IF NOT EXISTS batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        medicine_id INTEGER NOT NULL,
        supplier_id INTEGER,
        batch_no TEXT NOT NULL,
        manufacturing_date TEXT,
        expiry_date TEXT NOT NULL,
        purchase_price REAL DEFAULT 0,
        selling_price REAL DEFAULT 0,
        quantity INTEGER DEFAULT 0,
        remaining_quantity INTEGER DEFAULT 0,
        is_blocked INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(medicine_id) REFERENCES medicines(id),
        FOREIGN KEY(supplier_id) REFERENCES suppliers(id)
    );

    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        medicine_id INTEGER NOT NULL UNIQUE,
        total_quantity INTEGER DEFAULT 0,
        reserved_quantity INTEGER DEFAULT 0,
        damaged_quantity INTEGER DEFAULT 0,
        unit TEXT DEFAULT 'Strip',
        last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(medicine_id) REFERENCES medicines(id)
    );

    CREATE TABLE IF NOT EXISTS stock_adjustments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        medicine_id INTEGER NOT NULL,
        batch_id INTEGER,
        adjustment_type TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        unit TEXT,
        reason TEXT,
        approved_by INTEGER,
        status TEXT DEFAULT 'pending',
        created_by INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(medicine_id) REFERENCES medicines(id)
    );

    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id INTEGER DEFAULT 1,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        address TEXT,
        date_of_birth TEXT,
        gender TEXT,
        chronic_condition TEXT,
        doctor_name TEXT,
        allergies TEXT,
        loyalty_points INTEGER DEFAULT 0,
        total_spent REAL DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS purchase_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_number TEXT UNIQUE NOT NULL,
        store_id INTEGER DEFAULT 1,
        supplier_id INTEGER NOT NULL,
        expected_delivery TEXT,
        notes TEXT,
        subtotal REAL DEFAULT 0,
        vat_amount REAL DEFAULT 0,
        discount_amount REAL DEFAULT 0,
        total_amount REAL DEFAULT 0,
        status TEXT DEFAULT 'pending',
        created_by INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(supplier_id) REFERENCES suppliers(id)
    );

    CREATE TABLE IF NOT EXISTS purchase_order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_id INTEGER NOT NULL,
        medicine_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        unit TEXT,
        unit_price REAL DEFAULT 0,
        total_price REAL DEFAULT 0,
        received_quantity INTEGER DEFAULT 0,
        FOREIGN KEY(po_id) REFERENCES purchase_orders(id),
        FOREIGN KEY(medicine_id) REFERENCES medicines(id)
    );

    CREATE TABLE IF NOT EXISTS grn (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grn_number TEXT UNIQUE NOT NULL,
        po_id INTEGER,
        supplier_id INTEGER NOT NULL,
        received_date TEXT,
        supplier_invoice_no TEXT,
        received_by INTEGER,
        notes TEXT,
        total_amount REAL DEFAULT 0,
        status TEXT DEFAULT 'draft',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(po_id) REFERENCES purchase_orders(id)
    );

    CREATE TABLE IF NOT EXISTS grn_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grn_id INTEGER NOT NULL,
        medicine_id INTEGER NOT NULL,
        batch_no TEXT NOT NULL,
        expiry_date TEXT NOT NULL,
        ordered_quantity INTEGER DEFAULT 0,
        received_quantity INTEGER DEFAULT 0,
        unit TEXT,
        unit_price REAL DEFAULT 0,
        total_price REAL DEFAULT 0,
        condition TEXT DEFAULT 'good',
        FOREIGN KEY(grn_id) REFERENCES grn(id),
        FOREIGN KEY(medicine_id) REFERENCES medicines(id)
    );

    CREATE TABLE IF NOT EXISTS purchase_returns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        return_number TEXT UNIQUE NOT NULL,
        po_id INTEGER,
        supplier_id INTEGER NOT NULL,
        reason TEXT NOT NULL,
        total_amount REAL DEFAULT 0,
        status TEXT DEFAULT 'pending',
        created_by INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_number TEXT UNIQUE NOT NULL,
        store_id INTEGER DEFAULT 1,
        customer_id INTEGER,
        cashier_id INTEGER NOT NULL,
        subtotal REAL DEFAULT 0,
        discount_pct REAL DEFAULT 0,
        discount_amount REAL DEFAULT 0,
        vat_amount REAL DEFAULT 0,
        total_amount REAL DEFAULT 0,
        paid_amount REAL DEFAULT 0,
        change_amount REAL DEFAULT 0,
        payment_method TEXT DEFAULT 'cash',
        prescription_ref TEXT,
        notes TEXT,
        status TEXT DEFAULT 'completed',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(customer_id) REFERENCES customers(id),
        FOREIGN KEY(cashier_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS sale_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER NOT NULL,
        medicine_id INTEGER NOT NULL,
        batch_id INTEGER,
        quantity REAL NOT NULL,
        unit TEXT,
        unit_price REAL NOT NULL,
        discount_pct REAL DEFAULT 0,
        total_price REAL NOT NULL,
        FOREIGN KEY(sale_id) REFERENCES sales(id),
        FOREIGN KEY(medicine_id) REFERENCES medicines(id)
    );

    CREATE TABLE IF NOT EXISTS sale_returns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        return_number TEXT UNIQUE NOT NULL,
        sale_id INTEGER NOT NULL,
        reason TEXT,
        refund_amount REAL DEFAULT 0,
        refund_method TEXT DEFAULT 'cash',
        status TEXT DEFAULT 'pending',
        created_by INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(sale_id) REFERENCES sales(id)
    );

    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id INTEGER DEFAULT 1,
        category TEXT NOT NULL,
        description TEXT,
        amount REAL NOT NULL,
        expense_date TEXT,
        created_by INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS held_invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id INTEGER DEFAULT 1,
        cashier_id INTEGER NOT NULL,
        customer_id INTEGER,
        items_json TEXT NOT NULL,
        subtotal REAL DEFAULT 0,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    db.commit()
    db.close()
    print("✅ Database initialized")

def seed_db():
    """Seed demo data"""
    db = get_db()
    cur = db.cursor()

    # Store
    cur.execute("SELECT COUNT(*) as c FROM stores")
    if cur.fetchone()[0] > 0:
        db.close()
        return

    cur.execute("""INSERT INTO stores(name,address,phone,license_no,vat_rate) VALUES
        ('City Medical Hall','123 Main Road, Dhaka-1000','02-9876543','DGDA-BD-2024-4521',7.5)""")

    # Users
    pw = bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode()
    pw2 = bcrypt.hashpw(b'cashier123', bcrypt.gensalt()).decode()
    pw3 = bcrypt.hashpw(b'manager123', bcrypt.gensalt()).decode()
    cur.execute("INSERT INTO users(store_id,name,email,phone,password_hash,role) VALUES(1,'Dr. Ahmed Rahman','admin@citymedical.com','01711-000001',?,'admin')",(pw,))
    cur.execute("INSERT INTO users(store_id,name,email,phone,password_hash,role) VALUES(1,'Fatema Khatun','cashier@citymedical.com','01711-000002',?,'cashier')",(pw2,))
    cur.execute("INSERT INTO users(store_id,name,email,phone,password_hash,role) VALUES(1,'Rahim Manager','manager@citymedical.com','01711-000003',?,'manager')",(pw3,))

    # Categories
    cats = ['Analgesic','Antibiotic','Antacid','Diabetic','Cardiac','Syrup','Vitamin','Respiratory','Dermatology','Ophthalmology']
    for c in cats:
        cur.execute("INSERT INTO categories(name) VALUES(?)",(c,))

    # Suppliers
    sups = [
        ('Square Pharmaceuticals','Karim Ahmed','01700-111222','sq@squarepharma.com','Dhaka','SQ-2024-001',30,500000,0,45000,4.8),
        ('Beximco Pharma','Rahim Khan','01700-222333','rahim@beximco.com','Dhaka','BX-2024-002',45,300000,0,22000,4.5),
        ('ACI Limited','Nasrin Akter','01700-333444','nasrin@aci.com','Dhaka','ACI-2024-003',30,400000,0,0,4.9),
        ('Incepta Pharma','Jamal Hossain','01700-444555','jamal@incepta.com','Dhaka','INC-2024-004',30,200000,0,18000,4.1),
    ]
    for s in sups:
        cur.execute("""INSERT INTO suppliers(name,contact_person,phone,email,address,trade_license,payment_terms,credit_limit,discount_pct,outstanding_balance,rating)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",s)

    # Medicines
    meds = [
        ('MED-001','Napa 500mg','Paracetamol','Napa','Beximco Pharma',1,'Tablet','500mg','Box','Strip',10,10,6.0,8.0,50,7.5,0,0,0),
        ('MED-002','Amlodipine 5mg','Amlodipine','Amlodipine','Square Pharma',5,'Tablet','5mg','Box','Strip',10,10,25.0,35.0,30,7.5,1,0,0),
        ('MED-003','Metformin 500mg','Metformin HCl','Glucomin','ACI Limited',4,'Tablet','500mg','Box','Strip',10,10,32.0,45.0,40,7.5,1,0,0),
        ('MED-004','Pantoprazole 40mg','Pantoprazole','Pantonix','Incepta Pharma',3,'Tablet','40mg','Box','Strip',10,10,20.0,28.0,20,7.5,0,0,0),
        ('MED-005','Cetirizine 10mg','Cetirizine HCl','Alatrol','Square Pharma',1,'Tablet','10mg','Box','Strip',10,10,10.0,15.0,50,7.5,0,0,0),
        ('MED-006','Amoxicillin 500mg','Amoxicillin','Moxacil','Beximco Pharma',2,'Capsule','500mg','Box','Strip',10,10,40.0,55.0,30,7.5,1,0,0),
        ('MED-007','Metronidazole 400mg','Metronidazole','Amodis','ACI Limited',2,'Tablet','400mg','Box','Strip',10,10,14.0,20.0,30,7.5,0,0,0),
        ('MED-008','Paracetamol Syrup','Paracetamol','Napa Syrup','Beximco Pharma',6,'Syrup','120mg/5ml','Box','Bottle',1,1,25.0,35.0,10,7.5,0,0,0),
        ('MED-009','Vitamin C 500mg','Ascorbic Acid','Cevit','Square Pharma',7,'Tablet','500mg','Box','Strip',10,10,8.0,12.0,50,7.5,0,0,0),
        ('MED-010','Atorvastatin 20mg','Atorvastatin','Lipicard','Incepta Pharma',5,'Tablet','20mg','Box','Strip',10,10,48.0,65.0,20,7.5,1,0,0),
        ('MED-011','Omeprazole 20mg','Omeprazole','Losectil','Beximco Pharma',3,'Capsule','20mg','Box','Strip',10,10,16.0,22.0,30,7.5,0,0,0),
        ('MED-012','Losartan 50mg','Losartan Potassium','Losacar','ACI Limited',5,'Tablet','50mg','Box','Strip',10,10,30.0,42.0,25,7.5,1,0,0),
        ('MED-013','Diclofenac 50mg','Diclofenac Sodium','Voltaren','Incepta Pharma',1,'Tablet','50mg','Box','Strip',10,10,12.0,18.0,40,7.5,0,0,0),
        ('MED-014','Azithromycin 500mg','Azithromycin','Zithromax','Square Pharma',2,'Tablet','500mg','Box','Strip',10,3,60.0,85.0,20,7.5,1,0,0),
        ('MED-015','Insulin Glargine','Insulin Glargine','Lantus','Sanofi BD',4,'Injection','100IU/ml','Box','Vial',1,1,380.0,450.0,10,7.5,1,0,1),
    ]
    for m in meds:
        cur.execute("""INSERT INTO medicines(sku,name,generic_name,brand_name,manufacturer,category_id,dosage_form,strength,
            purchase_unit,selling_unit,strips_per_box,tablets_per_strip,purchase_price,selling_price,
            reorder_level,vat_rate,is_rx,is_controlled,is_temp_sensitive) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",m)

    # Batches and inventory
    today = date.today()
    batch_data = [
        (1,1,'B2501','2024-01-01','2027-06-30',6.0,8.0,500,500),
        (2,1,'B2502','2024-03-01','2027-03-31',25.0,35.0,200,200),
        (3,2,'B2503','2024-02-01','2026-12-31',32.0,45.0,150,150),
        (4,3,'B2504','2024-04-01','2026-08-31',20.0,28.0,8,8),
        (5,1,'B2505','2024-05-01','2027-09-30',10.0,15.0,300,300),
        (6,2,'B2201','2022-01-01','2025-05-10',40.0,55.0,0,0),   # expired
        (7,3,'B2204','2024-04-01','2025-05-25',14.0,20.0,48,48), # near expiry
        (8,1,'B2506','2024-06-01','2026-10-31',25.0,35.0,5,5),
        (9,1,'B2507','2024-07-01','2028-01-31',8.0,12.0,400,400),
        (10,4,'B2508','2024-08-01','2027-11-30',48.0,65.0,3,3),
        (11,2,'B2509','2024-09-01','2027-07-31',16.0,22.0,180,180),
        (12,3,'B2510','2024-10-01','2027-05-31',30.0,42.0,120,120),
        (13,4,'B2511','2024-11-01','2027-08-31',12.0,18.0,250,250),
        (14,1,'B2512','2024-12-01','2027-04-30',60.0,85.0,60,60),
        (15,4,'B2513','2025-01-01','2026-06-30',380.0,450.0,40,40),
    ]
    for b in batch_data:
        cur.execute("""INSERT INTO batches(medicine_id,supplier_id,batch_no,manufacturing_date,expiry_date,
            purchase_price,selling_price,quantity,remaining_quantity) VALUES(?,?,?,?,?,?,?,?,?)""",b)
        cur.execute("""INSERT OR REPLACE INTO inventory(medicine_id,total_quantity,unit)
            VALUES(?,?,?)""",(b[0],b[7],'Strip'))

    # Customers
    custs = [
        (1,'Rahim Uddin','01711-234567','rahim@example.com','Gulshan, Dhaka','1975-03-15','Male','Diabetes','Dr. Karim',None,420,48200.0),
        (1,'Fatema Begum','01812-345678','fatema@example.com','Dhanmondi, Dhaka','1980-07-22','Female','Hypertension','Dr. Ahmed',None,215,32600.0),
        (1,'Karim Ali','01912-456789',None,'Mirpur, Dhaka','1990-11-10','Male',None,None,None,88,8400.0),
        (1,'Nasrin Akter','01611-567890',None,'Uttara, Dhaka','1968-05-30','Female','Asthma','Dr. Rahman','Penicillin',650,72100.0),
        (1,'Jamal Hossain','01511-678901',None,'Banani, Dhaka','1962-09-14','Male','Cardiac',None,None,180,24500.0),
    ]
    for c in custs:
        cur.execute("""INSERT INTO customers(store_id,name,phone,email,address,date_of_birth,gender,
            chronic_condition,doctor_name,allergies,loyalty_points,total_spent) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",c)

    # Purchase Orders
    cur.execute("""INSERT INTO purchase_orders(po_number,store_id,supplier_id,expected_delivery,subtotal,total_amount,status,created_by)
        VALUES('PO-0042',1,1,'2025-05-20',45000,45000,'pending',1)""")
    cur.execute("""INSERT INTO purchase_orders(po_number,store_id,supplier_id,expected_delivery,subtotal,total_amount,status,created_by)
        VALUES('PO-0041',1,2,'2025-05-15',28500,28500,'received',1)""")
    cur.execute("""INSERT INTO purchase_orders(po_number,store_id,supplier_id,expected_delivery,subtotal,total_amount,status,created_by)
        VALUES('PO-0040',1,3,'2025-05-12',62000,62000,'received',1)""")
    cur.execute("""INSERT INTO purchase_orders(po_number,store_id,supplier_id,expected_delivery,subtotal,total_amount,status,created_by)
        VALUES('PO-0039',1,4,'2025-05-10',18200,18200,'partial',1)""")

    # Demo sales
    sale_data = [
        ('INV-0280','2025-05-18 09:45:00',None,2,'cash',1250,0,93.75,1343.75,'completed'),
        ('INV-0281','2025-05-18 10:12:00',1,2,'bkash',450,0,33.75,483.75,'completed'),
        ('INV-0282','2025-05-17 14:30:00',2,2,'credit',3800,5,285,3800,'completed'),
        ('INV-0283','2025-05-17 16:00:00',None,2,'cash',680,0,51,731,'completed'),
        ('INV-0284','2025-05-17 17:45:00',3,2,'card',220,0,16.5,236.5,'completed'),
    ]
    for s in sale_data:
        cur.execute("""INSERT INTO sales(invoice_number,created_at,customer_id,cashier_id,payment_method,
            subtotal,discount_amount,vat_amount,total_amount,status) VALUES(?,?,?,?,?,?,?,?,?,?)""",s)

    db.commit()
    db.close()
    print("✅ Database seeded with demo data")

# ─────────────────────────────────────────────
# AUTH MIDDLEWARE
# ─────────────────────────────────────────────
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization','').replace('Bearer ','')
        if not token:
            return jsonify({'error':'Token required'}), 401
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            g.user = data
        except jwt.ExpiredSignatureError:
            return jsonify({'error':'Token expired'}), 401
        except:
            return jsonify({'error':'Invalid token'}), 401
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if g.user.get('role') not in roles:
                return jsonify({'error':'Insufficient permissions'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

def log_action(action, entity=None, entity_id=None, detail=None):
    try:
        query("INSERT INTO audit_logs(user_id,action,entity,entity_id,detail,ip) VALUES(?,?,?,?,?,?)",
              (g.user.get('id'), action, entity, entity_id, detail, request.remote_addr), commit=True)
    except: pass

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def gen_invoice():
    last = query("SELECT invoice_number FROM sales ORDER BY id DESC LIMIT 1", one=True)
    if last:
        n = int(last['invoice_number'].split('-')[-1]) + 1
    else:
        n = 1001
    return f"INV-{n:04d}"

def gen_po():
    last = query("SELECT po_number FROM purchase_orders ORDER BY id DESC LIMIT 1", one=True)
    if last:
        n = int(last['po_number'].split('-')[-1]) + 1
    else:
        n = 1
    return f"PO-{n:04d}"

def gen_grn():
    last = query("SELECT grn_number FROM grn ORDER BY id DESC LIMIT 1", one=True)
    if last:
        n = int(last['grn_number'].split('-')[-1]) + 1
    else:
        n = 1
    return f"GRN-{n:04d}"

# ─────────────────────────────────────────────
# ROUTES - AUTH
# ─────────────────────────────────────────────
@app.route('/api/auth/login', methods=['POST'])
def login():
    d = request.json
    user = query("SELECT * FROM users WHERE email=? AND is_active=1", (d.get('email'),), one=True)
    if not user or not bcrypt.checkpw(d.get('password','').encode(), user['password_hash'].encode()):
        return jsonify({'error':'Invalid email or password'}), 401
    query("UPDATE users SET last_login=? WHERE id=?", (datetime.now().isoformat(), user['id']), commit=True)
    token = jwt.encode({
        'id': user['id'], 'email': user['email'],
        'name': user['name'], 'role': user['role'],
        'store_id': user['store_id'],
        'exp': datetime.utcnow() + timedelta(hours=12)
    }, SECRET_KEY, algorithm='HS256')
    return jsonify({'token': token, 'user': {k:user[k] for k in ['id','name','email','role','store_id']}})

@app.route('/api/auth/me', methods=['GET'])
@token_required
def me():
    user = query("SELECT id,name,email,role,store_id,phone,last_login FROM users WHERE id=?", (g.user['id'],), one=True)
    return jsonify(user)

@app.route('/api/auth/change-password', methods=['POST'])
@token_required
def change_password():
    d = request.json
    user = query("SELECT * FROM users WHERE id=?", (g.user['id'],), one=True)
    if not bcrypt.checkpw(d.get('current_password','').encode(), user['password_hash'].encode()):
        return jsonify({'error':'Current password incorrect'}), 400
    new_hash = bcrypt.hashpw(d.get('new_password','').encode(), bcrypt.gensalt()).decode()
    query("UPDATE users SET password_hash=? WHERE id=?", (new_hash, g.user['id']), commit=True)
    return jsonify({'message':'Password changed successfully'})

# ─────────────────────────────────────────────
# ROUTES - DASHBOARD
# ─────────────────────────────────────────────
@app.route('/api/dashboard', methods=['GET'])
@token_required
def dashboard():
    today = date.today().isoformat()
    # Today sales
    today_sales = query("SELECT COUNT(*) as cnt, COALESCE(SUM(total_amount),0) as rev FROM sales WHERE DATE(created_at)=? AND status='completed'",(today,), one=True)
    # Yesterday
    yest = (date.today() - timedelta(days=1)).isoformat()
    yest_rev = query("SELECT COALESCE(SUM(total_amount),0) as rev FROM sales WHERE DATE(created_at)=? AND status='completed'",(yest,), one=True)
    # Week revenue (last 7 days)
    week_data = []
    for i in range(6,-1,-1):
        d = (date.today() - timedelta(days=i)).isoformat()
        r = query("SELECT COALESCE(SUM(total_amount),0) as rev FROM sales WHERE DATE(created_at)=? AND status='completed'",(d,), one=True)
        week_data.append({'date':d,'revenue':r['rev']})
    # Low stock
    low_stock = query("""SELECT m.name, i.total_quantity, m.reorder_level FROM inventory i
        JOIN medicines m ON m.id=i.medicine_id
        WHERE i.total_quantity <= m.reorder_level AND m.is_active=1 ORDER BY i.total_quantity ASC LIMIT 10""")
    # Expiry alerts
    in30 = (date.today() + timedelta(days=30)).isoformat()
    expiry_alerts = query("""SELECT m.name, b.batch_no, b.expiry_date, b.remaining_quantity,
        CAST(julianday(b.expiry_date) - julianday('now') AS INTEGER) as days_left
        FROM batches b JOIN medicines m ON m.id=b.medicine_id
        WHERE b.expiry_date <= ? AND b.remaining_quantity > 0 AND b.is_blocked=0
        ORDER BY b.expiry_date ASC LIMIT 10""", (in30,))
    # Top medicines
    top_meds = query("""SELECT m.name, COALESCE(SUM(si.quantity),0) as qty, COALESCE(SUM(si.total_price),0) as revenue
        FROM sale_items si JOIN medicines m ON m.id=si.medicine_id
        JOIN sales s ON s.id=si.sale_id WHERE DATE(s.created_at)=? AND s.status='completed'
        GROUP BY m.id ORDER BY revenue DESC LIMIT 5""", (today,))
    # Supplier dues
    sup_dues = query("SELECT name, outstanding_balance FROM suppliers WHERE outstanding_balance > 0 ORDER BY outstanding_balance DESC LIMIT 5")
    # Month stats
    month_start = date.today().replace(day=1).isoformat()
    month_stats = query("SELECT COALESCE(SUM(total_amount),0) as rev, COUNT(*) as cnt FROM sales WHERE DATE(created_at)>=? AND status='completed'",(month_start,), one=True)

    today_rev = today_sales['rev']
    yest_rev_val = yest_rev['rev']
    rev_change = ((today_rev - yest_rev_val) / yest_rev_val * 100) if yest_rev_val else 0

    return jsonify({
        'today': {'revenue': today_rev, 'invoices': today_sales['cnt'], 'rev_change_pct': round(rev_change,1)},
        'month': {'revenue': month_stats['rev'], 'invoices': month_stats['cnt']},
        'week_chart': week_data,
        'low_stock': low_stock,
        'expiry_alerts': expiry_alerts,
        'top_medicines': top_meds,
        'supplier_dues': sup_dues,
        'low_stock_count': len(low_stock),
        'expiry_count': len(expiry_alerts),
    })

# ─────────────────────────────────────────────
# ROUTES - MEDICINES
# ─────────────────────────────────────────────
@app.route('/api/medicines', methods=['GET'])
@token_required
def get_medicines():
    q = request.args.get('q','')
    cat = request.args.get('category','')
    stock_filter = request.args.get('stock','')
    sql = """SELECT m.*, c.name as category_name,
        COALESCE(i.total_quantity,0) as stock_qty
        FROM medicines m
        LEFT JOIN categories c ON c.id=m.category_id
        LEFT JOIN inventory i ON i.medicine_id=m.id
        WHERE m.is_active=1"""
    params = []
    if q:
        sql += " AND (m.name LIKE ? OR m.generic_name LIKE ? OR m.sku LIKE ? OR m.barcode LIKE ?)"
        params += [f'%{q}%']*4
    if cat:
        sql += " AND c.name=?"
        params.append(cat)
    if stock_filter == 'low':
        sql += " AND i.total_quantity <= m.reorder_level AND i.total_quantity > 0"
    elif stock_filter == 'out':
        sql += " AND (i.total_quantity IS NULL OR i.total_quantity = 0)"
    sql += " ORDER BY m.name"
    return jsonify(query(sql, params))

@app.route('/api/medicines/<int:mid>', methods=['GET'])
@token_required
def get_medicine(mid):
    m = query("""SELECT m.*, c.name as category_name, COALESCE(i.total_quantity,0) as stock_qty
        FROM medicines m LEFT JOIN categories c ON c.id=m.category_id
        LEFT JOIN inventory i ON i.medicine_id=m.id WHERE m.id=?""", (mid,), one=True)
    if not m: return jsonify({'error':'Not found'}), 404
    batches = query("SELECT * FROM batches WHERE medicine_id=? ORDER BY expiry_date ASC", (mid,))
    m['batches'] = batches
    return jsonify(m)

@app.route('/api/medicines', methods=['POST'])
@token_required
def create_medicine():
    d = request.json
    # Generate SKU
    last = query("SELECT sku FROM medicines ORDER BY id DESC LIMIT 1", one=True)
    if last:
        n = int(last['sku'].split('-')[-1]) + 1
    else:
        n = 1
    sku = f"MED-{n:03d}"
    mid = query("""INSERT INTO medicines(sku,name,generic_name,brand_name,manufacturer,category_id,
        dosage_form,strength,purchase_unit,selling_unit,strips_per_box,tablets_per_strip,
        purchase_price,selling_price,reorder_level,vat_rate,is_rx,is_controlled,is_temp_sensitive,storage_notes,barcode)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (sku,d['name'],d.get('generic_name'),d.get('brand_name'),d.get('manufacturer'),
         d.get('category_id'),d.get('dosage_form','Tablet'),d.get('strength'),
         d.get('purchase_unit','Box'),d.get('selling_unit','Strip'),
         d.get('strips_per_box',10),d.get('tablets_per_strip',10),
         d.get('purchase_price',0),d.get('selling_price',0),d.get('reorder_level',10),
         d.get('vat_rate',7.5),d.get('is_rx',0),d.get('is_controlled',0),
         d.get('is_temp_sensitive',0),d.get('storage_notes'),d.get('barcode')), commit=True)
    query("INSERT INTO inventory(medicine_id,total_quantity,unit) VALUES(?,0,?)",(mid,d.get('selling_unit','Strip')),commit=True)
    log_action('CREATE_MEDICINE','medicine',mid,d['name'])
    return jsonify({'id':mid,'sku':sku,'message':'Medicine created'}), 201

@app.route('/api/medicines/<int:mid>', methods=['PUT'])
@token_required
def update_medicine(mid):
    d = request.json
    query("""UPDATE medicines SET name=?,generic_name=?,brand_name=?,manufacturer=?,category_id=?,
        dosage_form=?,strength=?,purchase_unit=?,selling_unit=?,strips_per_box=?,tablets_per_strip=?,
        purchase_price=?,selling_price=?,reorder_level=?,vat_rate=?,is_rx=?,is_controlled=?,
        is_temp_sensitive=?,storage_notes=?,barcode=? WHERE id=?""",
        (d['name'],d.get('generic_name'),d.get('brand_name'),d.get('manufacturer'),d.get('category_id'),
         d.get('dosage_form'),d.get('strength'),d.get('purchase_unit'),d.get('selling_unit'),
         d.get('strips_per_box',10),d.get('tablets_per_strip',10),d.get('purchase_price',0),
         d.get('selling_price',0),d.get('reorder_level',10),d.get('vat_rate',7.5),
         d.get('is_rx',0),d.get('is_controlled',0),d.get('is_temp_sensitive',0),
         d.get('storage_notes'),d.get('barcode'),mid), commit=True)
    log_action('UPDATE_MEDICINE','medicine',mid,d['name'])
    return jsonify({'message':'Updated'})

# ─────────────────────────────────────────────
# ROUTES - INVENTORY
# ─────────────────────────────────────────────
@app.route('/api/inventory', methods=['GET'])
@token_required
def get_inventory():
    q = request.args.get('q','')
    sql = """SELECT m.id,m.sku,m.name,m.generic_name,m.manufacturer,m.purchase_price,m.selling_price,
        m.reorder_level,m.is_rx,m.is_controlled,c.name as category,
        COALESCE(i.total_quantity,0) as stock_qty, i.unit,
        b.batch_no, b.expiry_date,
        CAST(julianday(b.expiry_date)-julianday('now') AS INTEGER) as days_to_expiry
        FROM medicines m
        LEFT JOIN categories c ON c.id=m.category_id
        LEFT JOIN inventory i ON i.medicine_id=m.id
        LEFT JOIN batches b ON b.medicine_id=m.id AND b.remaining_quantity=(
            SELECT MAX(remaining_quantity) FROM batches WHERE medicine_id=m.id AND expiry_date > date('now')
        )
        WHERE m.is_active=1"""
    params = []
    if q:
        sql += " AND (m.name LIKE ? OR m.generic_name LIKE ? OR m.sku LIKE ?)"
        params += [f'%{q}%']*3
    sql += " GROUP BY m.id ORDER BY m.name"
    return jsonify(query(sql, params))

@app.route('/api/inventory/adjust', methods=['POST'])
@token_required
def adjust_stock():
    d = request.json
    adj_id = query("""INSERT INTO stock_adjustments(medicine_id,batch_id,adjustment_type,quantity,unit,reason,created_by,status)
        VALUES(?,?,?,?,?,?,?,'pending')""",
        (d['medicine_id'],d.get('batch_id'),d['adjustment_type'],d['quantity'],d.get('unit'),d.get('reason'),g.user['id']),commit=True)
    log_action('STOCK_ADJUSTMENT','medicine',d['medicine_id'],f"{d['adjustment_type']} qty:{d['quantity']}")
    return jsonify({'id':adj_id,'message':'Adjustment submitted for approval'})

@app.route('/api/inventory/adjust/<int:aid>/approve', methods=['POST'])
@token_required
def approve_adjustment(aid):
    adj = query("SELECT * FROM stock_adjustments WHERE id=?", (aid,), one=True)
    if not adj: return jsonify({'error':'Not found'}), 404
    # Apply to inventory
    query("UPDATE inventory SET total_quantity=MAX(0,total_quantity-?), last_updated=? WHERE medicine_id=?",
          (adj['quantity'], datetime.now().isoformat(), adj['medicine_id']), commit=True)
    if adj.get('batch_id'):
        query("UPDATE batches SET remaining_quantity=MAX(0,remaining_quantity-?) WHERE id=?",
              (adj['quantity'], adj['batch_id']), commit=True)
    query("UPDATE stock_adjustments SET status='approved',approved_by=? WHERE id=?",(g.user['id'],aid),commit=True)
    log_action('APPROVE_ADJUSTMENT','adjustment',aid)
    return jsonify({'message':'Adjustment approved and applied'})

@app.route('/api/inventory/adjustments', methods=['GET'])
@token_required
def get_adjustments():
    return jsonify(query("""SELECT sa.*, m.name as medicine_name, u.name as created_by_name
        FROM stock_adjustments sa JOIN medicines m ON m.id=sa.medicine_id
        LEFT JOIN users u ON u.id=sa.created_by ORDER BY sa.created_at DESC LIMIT 50"""))

# ─────────────────────────────────────────────
# ROUTES - BATCHES
# ─────────────────────────────────────────────
@app.route('/api/batches', methods=['GET'])
@token_required
def get_batches():
    mid = request.args.get('medicine_id')
    sql = """SELECT b.*, m.name as medicine_name, s.name as supplier_name,
        CAST(julianday(b.expiry_date)-julianday('now') AS INTEGER) as days_to_expiry
        FROM batches b JOIN medicines m ON m.id=b.medicine_id
        LEFT JOIN suppliers s ON s.id=b.supplier_id WHERE b.remaining_quantity >= 0"""
    params = []
    if mid:
        sql += " AND b.medicine_id=?"
        params.append(mid)
    sql += " ORDER BY b.expiry_date ASC"
    return jsonify(query(sql, params))

@app.route('/api/batches/expiry', methods=['GET'])
@token_required
def get_expiry():
    days = int(request.args.get('days', 90))
    cutoff = (date.today() + timedelta(days=days)).isoformat()
    return jsonify(query("""SELECT b.*, m.name as medicine_name, m.selling_price,
        s.name as supplier_name,
        CAST(julianday(b.expiry_date)-julianday('now') AS INTEGER) as days_to_expiry,
        ROUND(b.remaining_quantity * m.selling_price, 2) as stock_value
        FROM batches b JOIN medicines m ON m.id=b.medicine_id
        LEFT JOIN suppliers s ON s.id=b.supplier_id
        WHERE b.expiry_date <= ? AND b.remaining_quantity > 0
        ORDER BY b.expiry_date ASC""", (cutoff,)))

# ─────────────────────────────────────────────
# ROUTES - SALES / POS
# ─────────────────────────────────────────────
@app.route('/api/sales', methods=['GET'])
@token_required
def get_sales():
    page = int(request.args.get('page', 1))
    per = int(request.args.get('per_page', 20))
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    q = request.args.get('q', '')
    offset = (page - 1) * per
    sql = """SELECT s.*, c.name as customer_name, u.name as cashier_name
        FROM sales s LEFT JOIN customers c ON c.id=s.customer_id
        LEFT JOIN users u ON u.id=s.cashier_id WHERE 1=1"""
    params = []
    if date_from: sql += " AND DATE(s.created_at)>=?"; params.append(date_from)
    if date_to: sql += " AND DATE(s.created_at)<=?"; params.append(date_to)
    if q: sql += " AND (s.invoice_number LIKE ? OR c.name LIKE ?)"; params += [f'%{q}%']*2
    total = query(f"SELECT COUNT(*) as c FROM ({sql})",params,one=True)['c']
    sql += f" ORDER BY s.created_at DESC LIMIT {per} OFFSET {offset}"
    return jsonify({'sales': query(sql, params), 'total': total, 'page': page, 'per_page': per})

@app.route('/api/sales/<int:sid>', methods=['GET'])
@token_required
def get_sale(sid):
    sale = query("""SELECT s.*, c.name as customer_name, c.phone as customer_phone,
        u.name as cashier_name FROM sales s
        LEFT JOIN customers c ON c.id=s.customer_id
        LEFT JOIN users u ON u.id=s.cashier_id WHERE s.id=?""", (sid,), one=True)
    if not sale: return jsonify({'error':'Not found'}), 404
    items = query("""SELECT si.*, m.name as medicine_name, m.generic_name, b.batch_no, b.expiry_date
        FROM sale_items si JOIN medicines m ON m.id=si.medicine_id
        LEFT JOIN batches b ON b.id=si.batch_id WHERE si.sale_id=?""", (sid,))
    sale['items'] = items
    return jsonify(sale)

@app.route('/api/sales', methods=['POST'])
@token_required
def create_sale():
    d = request.json
    items = d.get('items', [])
    if not items:
        return jsonify({'error': 'No items in cart'}), 400

    sub = sum(i['quantity'] * i['unit_price'] for i in items)
    disc_pct = d.get('discount_pct', 0)
    disc_amt = sub * (disc_pct / 100)
    after_disc = sub - disc_amt
    vat = after_disc * 0.075
    total = after_disc + vat
    inv_no = gen_invoice()

    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""INSERT INTO sales(invoice_number,customer_id,cashier_id,subtotal,discount_pct,
            discount_amount,vat_amount,total_amount,paid_amount,change_amount,payment_method,notes,status,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,'completed',?)""",
            (inv_no, d.get('customer_id'), g.user['id'], sub, disc_pct, disc_amt, vat, total,
             d.get('paid_amount', total), max(0, d.get('paid_amount', total) - total),
             d.get('payment_method','cash'), d.get('notes'), datetime.now().isoformat()))
        sale_id = cur.lastrowid

        for item in items:
            # Find FEFO batch
            batch = None
            if item.get('batch_id'):
                batch = db.execute("SELECT * FROM batches WHERE id=?", (item['batch_id'],)).fetchone()
            else:
                batch = db.execute("""SELECT * FROM batches WHERE medicine_id=? AND remaining_quantity>0
                    AND expiry_date>date('now') AND is_blocked=0 ORDER BY expiry_date ASC LIMIT 1""",
                    (item['medicine_id'],)).fetchone()

            batch_id = dict(batch)['id'] if batch else None
            item_total = item['quantity'] * item['unit_price'] * (1 - item.get('discount_pct', 0)/100)

            cur.execute("""INSERT INTO sale_items(sale_id,medicine_id,batch_id,quantity,unit,unit_price,discount_pct,total_price)
                VALUES(?,?,?,?,?,?,?,?)""",
                (sale_id, item['medicine_id'], batch_id, item['quantity'],
                 item.get('unit','Strip'), item['unit_price'], item.get('discount_pct',0), item_total))

            # Deduct stock
            cur.execute("UPDATE inventory SET total_quantity=MAX(0,total_quantity-?), last_updated=? WHERE medicine_id=?",
                (item['quantity'], datetime.now().isoformat(), item['medicine_id']))
            if batch_id:
                cur.execute("UPDATE batches SET remaining_quantity=MAX(0,remaining_quantity-?) WHERE id=?",
                    (item['quantity'], batch_id))

        # Update customer loyalty
        if d.get('customer_id'):
            pts = int(total / 10)
            cur.execute("UPDATE customers SET loyalty_points=loyalty_points+?, total_spent=total_spent+? WHERE id=?",
                (pts, total, d['customer_id']))

        db.commit()
    except Exception as e:
        db.rollback()
        db.close()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()

    log_action('CREATE_SALE','sale',sale_id,f"{inv_no} ৳{total:.2f}")
    return jsonify({'id': sale_id, 'invoice_number': inv_no, 'total': total, 'message': 'Sale completed'})

@app.route('/api/sales/stats', methods=['GET'])
@token_required
def sales_stats():
    today = date.today().isoformat()
    month_start = date.today().replace(day=1).isoformat()
    week_start = (date.today() - timedelta(days=6)).isoformat()
    t = query("SELECT COALESCE(SUM(total_amount),0) as r,COUNT(*) as c FROM sales WHERE DATE(created_at)=? AND status='completed'",(today,),one=True)
    w = query("SELECT COALESCE(SUM(total_amount),0) as r,COUNT(*) as c FROM sales WHERE DATE(created_at)>=? AND status='completed'",(week_start,),one=True)
    m = query("SELECT COALESCE(SUM(total_amount),0) as r,COUNT(*) as c FROM sales WHERE DATE(created_at)>=? AND status='completed'",(month_start,),one=True)
    ret = query("SELECT COALESCE(SUM(refund_amount),0) as r,COUNT(*) as c FROM sale_returns WHERE DATE(created_at)=?",(today,),one=True)
    pay_breakdown = query("""SELECT payment_method, COUNT(*) as cnt, SUM(total_amount) as total
        FROM sales WHERE DATE(created_at)>=? AND status='completed' GROUP BY payment_method""",(month_start,))
    return jsonify({'today':t,'week':w,'month':m,'returns':ret,'payment_breakdown':pay_breakdown})

# Hold invoice
@app.route('/api/sales/hold', methods=['POST'])
@token_required
def hold_invoice():
    d = request.json
    hid = query("INSERT INTO held_invoices(cashier_id,customer_id,items_json,subtotal,notes) VALUES(?,?,?,?,?)",
        (g.user['id'],d.get('customer_id'),json.dumps(d.get('items',[])),d.get('subtotal',0),d.get('notes')),commit=True)
    return jsonify({'id':hid,'message':'Invoice held'})

@app.route('/api/sales/held', methods=['GET'])
@token_required
def get_held():
    return jsonify(query("""SELECT h.*,c.name as customer_name FROM held_invoices h
        LEFT JOIN customers c ON c.id=h.customer_id WHERE h.cashier_id=? ORDER BY h.created_at DESC""",
        (g.user['id'],)))

@app.route('/api/sales/held/<int:hid>', methods=['DELETE'])
@token_required
def delete_held(hid):
    query("DELETE FROM held_invoices WHERE id=? AND cashier_id=?",(hid,g.user['id']),commit=True)
    return jsonify({'message':'Removed'})

# Sale Returns
@app.route('/api/sales/returns', methods=['POST'])
@token_required
def create_return():
    d = request.json
    sale = query("SELECT * FROM sales WHERE id=?", (d['sale_id'],), one=True)
    if not sale: return jsonify({'error':'Sale not found'}), 404
    rn = f"RET-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    rid = query("INSERT INTO sale_returns(return_number,sale_id,reason,refund_amount,refund_method,status,created_by) VALUES(?,?,?,?,?,'completed',?)",
        (rn,d['sale_id'],d.get('reason'),d.get('refund_amount',0),d.get('refund_method','cash'),g.user['id']),commit=True)
    # Re-add to inventory
    items = query("SELECT * FROM sale_items WHERE sale_id=?", (d['sale_id'],))
    for item in items:
        query("UPDATE inventory SET total_quantity=total_quantity+? WHERE medicine_id=?",
              (item['quantity'],item['medicine_id']),commit=True)
        if item['batch_id']:
            query("UPDATE batches SET remaining_quantity=remaining_quantity+? WHERE id=?",
                  (item['quantity'],item['batch_id']),commit=True)
    log_action('SALE_RETURN','sale',d['sale_id'],f"Refund ৳{d.get('refund_amount',0)}")
    return jsonify({'id':rid,'return_number':rn,'message':'Return processed'})

# ─────────────────────────────────────────────
# ROUTES - CUSTOMERS
# ─────────────────────────────────────────────
@app.route('/api/customers', methods=['GET'])
@token_required
def get_customers():
    q = request.args.get('q','')
    sql = "SELECT * FROM customers WHERE is_active=1"
    params = []
    if q:
        sql += " AND (name LIKE ? OR phone LIKE ?)"
        params += [f'%{q}%']*2
    sql += " ORDER BY name"
    return jsonify(query(sql,params))

@app.route('/api/customers/<int:cid>', methods=['GET'])
@token_required
def get_customer(cid):
    c = query("SELECT * FROM customers WHERE id=?", (cid,), one=True)
    if not c: return jsonify({'error':'Not found'}), 404
    history = query("""SELECT s.invoice_number, s.created_at, s.total_amount, s.payment_method, s.status
        FROM sales s WHERE s.customer_id=? ORDER BY s.created_at DESC LIMIT 20""", (cid,))
    c['purchase_history'] = history
    return jsonify(c)

@app.route('/api/customers', methods=['POST'])
@token_required
def create_customer():
    d = request.json
    cid = query("""INSERT INTO customers(name,phone,email,address,date_of_birth,gender,
        chronic_condition,doctor_name,allergies) VALUES(?,?,?,?,?,?,?,?,?)""",
        (d['name'],d.get('phone'),d.get('email'),d.get('address'),d.get('date_of_birth'),
         d.get('gender'),d.get('chronic_condition'),d.get('doctor_name'),d.get('allergies')),commit=True)
    log_action('CREATE_CUSTOMER','customer',cid,d['name'])
    return jsonify({'id':cid,'message':'Customer created'}), 201

@app.route('/api/customers/<int:cid>', methods=['PUT'])
@token_required
def update_customer(cid):
    d = request.json
    query("""UPDATE customers SET name=?,phone=?,email=?,address=?,date_of_birth=?,gender=?,
        chronic_condition=?,doctor_name=?,allergies=? WHERE id=?""",
        (d['name'],d.get('phone'),d.get('email'),d.get('address'),d.get('date_of_birth'),
         d.get('gender'),d.get('chronic_condition'),d.get('doctor_name'),d.get('allergies'),cid),commit=True)
    return jsonify({'message':'Updated'})

# ─────────────────────────────────────────────
# ROUTES - SUPPLIERS
# ─────────────────────────────────────────────
@app.route('/api/suppliers', methods=['GET'])
@token_required
def get_suppliers():
    return jsonify(query("SELECT * FROM suppliers WHERE is_active=1 ORDER BY name"))

@app.route('/api/suppliers/<int:sid>', methods=['GET'])
@token_required
def get_supplier(sid):
    s = query("SELECT * FROM suppliers WHERE id=?", (sid,), one=True)
    if not s: return jsonify({'error':'Not found'}), 404
    pos = query("SELECT * FROM purchase_orders WHERE supplier_id=? ORDER BY created_at DESC LIMIT 10", (sid,))
    s['purchase_orders'] = pos
    return jsonify(s)

@app.route('/api/suppliers', methods=['POST'])
@token_required
def create_supplier():
    d = request.json
    sid = query("""INSERT INTO suppliers(name,contact_person,phone,email,address,trade_license,
        payment_terms,credit_limit,discount_pct) VALUES(?,?,?,?,?,?,?,?,?)""",
        (d['name'],d.get('contact_person'),d.get('phone'),d.get('email'),d.get('address'),
         d.get('trade_license'),d.get('payment_terms',30),d.get('credit_limit',0),d.get('discount_pct',0)),commit=True)
    log_action('CREATE_SUPPLIER','supplier',sid,d['name'])
    return jsonify({'id':sid,'message':'Supplier created'}), 201

@app.route('/api/suppliers/<int:sid>', methods=['PUT'])
@token_required
def update_supplier(sid):
    d = request.json
    query("""UPDATE suppliers SET name=?,contact_person=?,phone=?,email=?,address=?,trade_license=?,
        payment_terms=?,credit_limit=?,discount_pct=? WHERE id=?""",
        (d['name'],d.get('contact_person'),d.get('phone'),d.get('email'),d.get('address'),
         d.get('trade_license'),d.get('payment_terms',30),d.get('credit_limit',0),d.get('discount_pct',0),sid),commit=True)
    return jsonify({'message':'Updated'})

# ─────────────────────────────────────────────
# ROUTES - PURCHASE ORDERS
# ─────────────────────────────────────────────
@app.route('/api/purchase-orders', methods=['GET'])
@token_required
def get_pos():
    return jsonify(query("""SELECT po.*, s.name as supplier_name
        FROM purchase_orders po JOIN suppliers s ON s.id=po.supplier_id
        ORDER BY po.created_at DESC LIMIT 50"""))

@app.route('/api/purchase-orders', methods=['POST'])
@token_required
def create_po():
    d = request.json
    po_no = gen_po()
    items = d.get('items', [])
    subtotal = sum(i.get('quantity', 0) * i.get('unit_price', 0) for i in items)
    po_id = query("""INSERT INTO purchase_orders(po_number,supplier_id,expected_delivery,notes,subtotal,total_amount,status,created_by)
        VALUES(?,?,?,?,?,?,'pending',?)""",
        (po_no,d['supplier_id'],d.get('expected_delivery'),d.get('notes'),subtotal,subtotal,g.user['id']),commit=True)
    for item in items:
        query("""INSERT INTO purchase_order_items(po_id,medicine_id,quantity,unit,unit_price,total_price)
            VALUES(?,?,?,?,?,?)""",
            (po_id,item['medicine_id'],item['quantity'],item.get('unit'),item.get('unit_price',0),
             item.get('quantity',0)*item.get('unit_price',0)),commit=True)
    log_action('CREATE_PO','purchase_order',po_id,po_no)
    return jsonify({'id':po_id,'po_number':po_no,'message':'Purchase order created'}), 201

# ─────────────────────────────────────────────
# ROUTES - GRN
# ─────────────────────────────────────────────
@app.route('/api/grn', methods=['POST'])
@token_required
def create_grn():
    d = request.json
    grn_no = gen_grn()
    items = d.get('items', [])
    total = sum(i.get('received_quantity',0)*i.get('unit_price',0) for i in items)
    db = get_db()
    try:
        cur = db.cursor()
        cur.execute("""INSERT INTO grn(grn_number,po_id,supplier_id,received_date,supplier_invoice_no,
            received_by,notes,total_amount,status) VALUES(?,?,?,?,?,?,?,?,'confirmed')""",
            (grn_no,d.get('po_id'),d['supplier_id'],d.get('received_date',date.today().isoformat()),
             d.get('supplier_invoice_no'),g.user['id'],d.get('notes'),total))
        grn_id = cur.lastrowid
        for item in items:
            cur.execute("""INSERT INTO grn_items(grn_id,medicine_id,batch_no,expiry_date,ordered_quantity,
                received_quantity,unit,unit_price,total_price,condition) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (grn_id,item['medicine_id'],item['batch_no'],item['expiry_date'],
                 item.get('ordered_quantity',0),item['received_quantity'],item.get('unit','Strip'),
                 item.get('unit_price',0),item['received_quantity']*item.get('unit_price',0),
                 item.get('condition','good')))
            if item.get('condition','good') == 'good':
                # Add batch
                cur.execute("""INSERT INTO batches(medicine_id,supplier_id,batch_no,expiry_date,
                    purchase_price,selling_price,quantity,remaining_quantity)
                    SELECT ?,?,?,?,purchase_price,selling_price,?,? FROM medicines WHERE id=?""",
                    (item['medicine_id'],d['supplier_id'],item['batch_no'],item['expiry_date'],
                     item['received_quantity'],item['received_quantity'],item['medicine_id']))
                cur.execute("UPDATE inventory SET total_quantity=total_quantity+?,last_updated=? WHERE medicine_id=?",
                    (item['received_quantity'],datetime.now().isoformat(),item['medicine_id']))
        if d.get('po_id'):
            cur.execute("UPDATE purchase_orders SET status='received' WHERE id=?", (d['po_id'],))
        db.commit()
    except Exception as e:
        db.rollback(); db.close()
        return jsonify({'error':str(e)}), 500
    finally:
        db.close()
    log_action('CREATE_GRN','grn',grn_id,grn_no)
    return jsonify({'id':grn_id,'grn_number':grn_no,'message':'GRN created and stock updated'})

# ─────────────────────────────────────────────
# ROUTES - REPORTS
# ─────────────────────────────────────────────
@app.route('/api/reports/sales', methods=['GET'])
@token_required
def report_sales():
    date_from = request.args.get('from', date.today().replace(day=1).isoformat())
    date_to = request.args.get('to', date.today().isoformat())
    summary = query("""SELECT
        COALESCE(SUM(total_amount),0) as gross_revenue,
        COALESCE(SUM(discount_amount),0) as total_discounts,
        COALESCE(SUM(vat_amount),0) as total_vat,
        COUNT(*) as invoice_count,
        COALESCE(AVG(total_amount),0) as avg_invoice
        FROM sales WHERE DATE(created_at) BETWEEN ? AND ? AND status='completed'""",
        (date_from, date_to), one=True)
    by_day = query("""SELECT DATE(created_at) as day, COUNT(*) as cnt, SUM(total_amount) as revenue
        FROM sales WHERE DATE(created_at) BETWEEN ? AND ? AND status='completed'
        GROUP BY day ORDER BY day""", (date_from,date_to))
    by_payment = query("""SELECT payment_method, COUNT(*) as cnt, SUM(total_amount) as total
        FROM sales WHERE DATE(created_at) BETWEEN ? AND ? AND status='completed'
        GROUP BY payment_method""", (date_from,date_to))
    top_meds = query("""SELECT m.name, SUM(si.quantity) as qty, SUM(si.total_price) as revenue
        FROM sale_items si JOIN medicines m ON m.id=si.medicine_id
        JOIN sales s ON s.id=si.sale_id
        WHERE DATE(s.created_at) BETWEEN ? AND ? AND s.status='completed'
        GROUP BY m.id ORDER BY revenue DESC LIMIT 10""", (date_from,date_to))
    by_cashier = query("""SELECT u.name, COUNT(s.id) as cnt, SUM(s.total_amount) as revenue
        FROM sales s JOIN users u ON u.id=s.cashier_id
        WHERE DATE(s.created_at) BETWEEN ? AND ? AND s.status='completed'
        GROUP BY u.id ORDER BY revenue DESC""", (date_from,date_to))
    return jsonify({'summary':summary,'by_day':by_day,'by_payment':by_payment,'top_medicines':top_meds,'by_cashier':by_cashier})

@app.route('/api/reports/inventory', methods=['GET'])
@token_required
def report_inventory():
    total_value = query("""SELECT COALESCE(SUM(i.total_quantity * m.selling_price),0) as val
        FROM inventory i JOIN medicines m ON m.id=i.medicine_id WHERE m.is_active=1""", one=True)
    low_stock = query("""SELECT m.name, i.total_quantity, m.reorder_level
        FROM inventory i JOIN medicines m ON m.id=i.medicine_id
        WHERE i.total_quantity <= m.reorder_level AND m.is_active=1 ORDER BY i.total_quantity""")
    dead_stock = query("""SELECT m.name, i.total_quantity,
        COALESCE((SELECT MAX(s.created_at) FROM sale_items si JOIN sales s ON s.id=si.sale_id WHERE si.medicine_id=m.id),'Never') as last_sold
        FROM inventory i JOIN medicines m ON m.id=i.medicine_id
        WHERE i.total_quantity > 0 AND m.is_active=1
        AND (SELECT COUNT(*) FROM sale_items si JOIN sales s ON s.id=si.sale_id
            WHERE si.medicine_id=m.id AND s.created_at >= date('now','-90 days')) = 0
        ORDER BY i.total_quantity DESC LIMIT 20""")
    fast_moving = query("""SELECT m.name, SUM(si.quantity) as sold_qty
        FROM sale_items si JOIN medicines m ON m.id=si.medicine_id
        JOIN sales s ON s.id=si.sale_id
        WHERE s.created_at >= date('now','-30 days') AND s.status='completed'
        GROUP BY m.id ORDER BY sold_qty DESC LIMIT 10""")
    return jsonify({'total_value':total_value['val'],'low_stock':low_stock,'dead_stock':dead_stock,'fast_moving':fast_moving})

@app.route('/api/reports/financial', methods=['GET'])
@token_required
def report_financial():
    date_from = request.args.get('from', date.today().replace(day=1).isoformat())
    date_to = request.args.get('to', date.today().isoformat())
    revenue = query("SELECT COALESCE(SUM(total_amount),0) as r FROM sales WHERE DATE(created_at) BETWEEN ? AND ? AND status='completed'",(date_from,date_to),one=True)['r']
    cogs = query("""SELECT COALESCE(SUM(si.quantity * m.purchase_price),0) as c
        FROM sale_items si JOIN medicines m ON m.id=si.medicine_id
        JOIN sales s ON s.id=si.sale_id WHERE DATE(s.created_at) BETWEEN ? AND ? AND s.status='completed'""",(date_from,date_to),one=True)['c']
    expenses = query("SELECT COALESCE(SUM(amount),0) as e FROM expenses WHERE DATE(expense_date) BETWEEN ? AND ?",(date_from,date_to),one=True)['e']
    vat_collected = query("SELECT COALESCE(SUM(vat_amount),0) as v FROM sales WHERE DATE(created_at) BETWEEN ? AND ? AND status='completed'",(date_from,date_to),one=True)['v']
    purchase_total = query("SELECT COALESCE(SUM(total_amount),0) as p FROM purchase_orders WHERE DATE(created_at) BETWEEN ? AND ?",(date_from,date_to),one=True)['p']
    gross_profit = revenue - cogs
    net_profit = gross_profit - expenses
    margin = (net_profit / revenue * 100) if revenue else 0
    return jsonify({'revenue':revenue,'cogs':cogs,'gross_profit':gross_profit,'expenses':expenses,'net_profit':net_profit,'margin':round(margin,2),'vat_collected':vat_collected,'purchase_total':purchase_total})

# ─────────────────────────────────────────────
# ROUTES - USERS / SETTINGS
# ─────────────────────────────────────────────
@app.route('/api/users', methods=['GET'])
@token_required
def get_users():
    return jsonify(query("SELECT id,name,email,phone,role,is_active,last_login,created_at FROM users WHERE store_id=? ORDER BY name",(g.user.get('store_id',1),)))

@app.route('/api/users', methods=['POST'])
@token_required
def create_user():
    d = request.json
    pw = bcrypt.hashpw(d.get('password','changeme123').encode(), bcrypt.gensalt()).decode()
    uid = query("INSERT INTO users(store_id,name,email,phone,password_hash,role) VALUES(?,?,?,?,?,?)",
        (g.user.get('store_id',1),d['name'],d['email'],d.get('phone'),pw,d.get('role','cashier')),commit=True)
    log_action('CREATE_USER','user',uid,d['name'])
    return jsonify({'id':uid,'message':'User created'}), 201

@app.route('/api/settings', methods=['GET'])
@token_required
def get_settings():
    return jsonify(query("SELECT * FROM stores WHERE id=?", (g.user.get('store_id',1),), one=True))

@app.route('/api/settings', methods=['PUT'])
@token_required
def update_settings():
    d = request.json
    query("""UPDATE stores SET name=?,address=?,phone=?,license_no=?,vat_rate=?,currency=?,
        low_stock_threshold=?,expiry_alert_days=?,receipt_footer=? WHERE id=?""",
        (d['name'],d.get('address'),d.get('phone'),d.get('license_no'),d.get('vat_rate',7.5),
         d.get('currency','BDT'),d.get('low_stock_threshold',10),d.get('expiry_alert_days',30),
         d.get('receipt_footer'),g.user.get('store_id',1)),commit=True)
    log_action('UPDATE_SETTINGS','store',g.user.get('store_id',1))
    return jsonify({'message':'Settings updated'})

@app.route('/api/categories', methods=['GET'])
@token_required
def get_categories():
    return jsonify(query("SELECT * FROM categories ORDER BY name"))

@app.route('/api/audit-logs', methods=['GET'])
@token_required
def get_audit():
    return jsonify(query("""SELECT al.*, u.name as user_name FROM audit_logs al
        LEFT JOIN users u ON u.id=al.user_id ORDER BY al.created_at DESC LIMIT 100"""))

# ─────────────────────────────────────────────
# SERVE FRONTEND
# ─────────────────────────────────────────────
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    return send_from_directory('static', 'index.html')

# ─────────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    seed_db()
    print("🚀 PharmaPOS Pro running on http://localhost:5000")
    print("   Admin: admin@citymedical.com / admin123")
    print("   Cashier: cashier@citymedical.com / cashier123")
    app.run(debug=True, host='0.0.0.0', port=5000)
