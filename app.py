import os
from datetime import datetime
from functools import wraps

from flask import send_from_directory
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from sqlalchemy import Numeric
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'supersecretkey')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 465))
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

db = SQLAlchemy(app)
mail = Mail(app)

os.makedirs(os.path.join(UPLOAD_FOLDER, 'pdf'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'images'), exist_ok=True)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='buyer')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    price = db.Column(Numeric(10,2), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(30), nullable=False, default='pending')
    total_price = db.Column(Numeric(10,2), nullable=False)
    customer_email = db.Column(db.String(100), nullable=False)

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price_at_time = db.Column(Numeric(10,2), nullable=False)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if user.role != 'author':
            return "Доступ запрещён", 403
        return f(*args, **kwargs)
    return decorated

def send_pdf_files(email, items):
    with app.app_context():
        try:
            msg = Message("Ваши логопедические пособия", recipients=[email])
            msg.body = "Спасибо за покупку! Ваши файлы прикреплены к письму."
            for item in items:
                product = Product.query.get(item['id'])
                if product and os.path.exists(product.file_path):
                    with open(product.file_path, 'rb') as f:
                        msg.attach(product.title + '.pdf', 'application/pdf', f.read())
            mail.send(msg)
            return True
        except Exception as e:
            print(f"Ошибка отправки: {e}")
            return False


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/products')
def api_products():
    products = Product.query.all()
    products_list = []
    for p in products:
        try:
            if p.image_path and p.image_path.strip():
                image = p.image_path.replace('\\', '/')
            else:
                image = '/static/img/placeholder.jpg'
            
            products_list.append({
                'id': p.id,
                'title': p.title or 'Без названия',
                'description': (p.description[:100] if p.description else 'Описание отсутствует'),
                'category': p.category or 'other',
                'price': float(p.price) if p.price else 0,
                'image': image
            })
        except Exception as e:
            print(f"Ошибка при обработке товара {p.id}: {e}")
            continue  
    
    return jsonify(products_list)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Отдача загруженных файлов (PDF и изображений)"""
    return send_from_directory('uploads', filename)

@app.route('/api/user-info')
@login_required
def user_info():
    """Возвращает информацию о текущем пользователе"""
    user = User.query.get(session['user_id'])
    return jsonify({
        'email': user.email,
        'name': session.get('user_name', '')
    })

@app.route('/api/update-profile', methods=['POST'])
@login_required
def update_profile():
    try:
        data = request.get_json()
        email = data.get('email')
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        user = User.query.get(session['user_id'])
        
        if not user.check_password(current_password):
            return jsonify({'error': 'Неверный текущий пароль'}), 400
        
        if email and email != user.email:
            if User.query.filter_by(email=email).first():
                return jsonify({'error': 'Email уже используется'}), 400
            user.email = email
            session['user_name'] = email
        
        if new_password:
            user.set_password(new_password)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Данные обновлены'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/resend-pdf', methods=['POST'])
@login_required
def resend_pdf():
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        order_id = data.get('order_id')
        
        product = Product.query.get(product_id)
        order = Order.query.get(order_id)
        
        if not product or not order:
            return jsonify({'error': 'Данные не найдены'}), 404
        
        items = [{'id': product_id, 'quantity': 1, 'price': product.price}]
        send_pdf_files(order.customer_email, items)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        confirm = request.form['confirm_password']
        if password != confirm:
            return render_template('register.html', error='Пароли не совпадают')
        if User.query.filter_by(email=email).first():
            return render_template('register.html', error='Email уже зарегистрирован')
        user = User(email=email, role='buyer')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
        session['user_name'] = user.email
        session['user_role'] = user.role
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['user_name'] = user.email
            session['user_role'] = user.role
            return redirect(url_for('index'))
        return render_template('login.html', error='Неверный email или пароль')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    user = User.query.get(session['user_id'])
    orders = Order.query.filter_by(user_id=user.id).order_by(Order.order_date.desc()).all()
    order_items = []
    for order in orders:
        items = db.session.query(OrderItem, Product).join(Product, OrderItem.product_id == Product.id).filter(OrderItem.order_id == order.id).all()
        order_items.append((order, items))
    return render_template('profile.html', user=user, orders=order_items)

@app.route('/admin')
@admin_required
def admin():
    products = Product.query.all()
    
    orders_list = []
    
    all_orders = Order.query.order_by(Order.order_date.desc()).all()
    
    for order in all_orders:
        order_dict = {
            'order': order,
            'product_items': []  
        }
        
        order_items = OrderItem.query.filter_by(order_id=order.id).all()
        
        for item in order_items:
            product = Product.query.get(item.product_id)
            if product:
                order_dict['product_items'].append({
                    'product': product,
                    'quantity': item.quantity,
                    'price': item.price_at_time
                })
        
        orders_list.append(order_dict)
    
    return render_template('admin.html', products=products, orders=orders_list)

@app.route('/cart')
def cart():
    return render_template('cart.html')

@app.route('/api/create-order', methods=['POST'])
def create_order():
    try:
        data = request.get_json()
        email = data.get('email')
        items = data.get('items', [])

        if not email or not items:
            return jsonify({'error': 'Не хватает данных'}), 400

        total = sum(item['price'] * item.get('quantity', 1) for item in items)
        user_id = session.get('user_id')

        order = Order(
            user_id=user_id,
            total_price=total,
            customer_email=email,
            status='paid'
        )
        db.session.add(order)
        db.session.flush()

        for item in items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item['id'],
                quantity=item.get('quantity', 1),
                price_at_time=item['price']
            )
            db.session.add(order_item)

        db.session.commit()

        send_pdf_files(email, items)  

        return jsonify({
            'success': True,
            'order_id': order.id,
            'message': f'Заказ оформлен! Файлы отправлены на {email}'
        })
    except Exception as e:
        print(f"Ошибка: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/products', methods=['GET', 'POST', 'PUT', 'DELETE'])
@admin_required
def admin_products_api():
    if request.method == 'GET':
        products = Product.query.all()
        return jsonify([{
            'id': p.id,
            'title': p.title,
            'description': p.description,
            'category': p.category,
            'price': float(p.price),
            'image_path': p.image_path,
            'file_path': p.file_path
        } for p in products])

    elif request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')
        price = float(request.form.get('price'))
        pdf_file = request.files.get('pdf_file')
        image_file = request.files.get('image_file')
        
        pdf_path, image_path = '', ''
        
        if pdf_file and pdf_file.filename:
            pdf_filename = secure_filename(f"product_{datetime.now().timestamp()}.pdf")
            pdf_path = os.path.join(UPLOAD_FOLDER, 'pdf', pdf_filename)
            pdf_file.save(pdf_path)
        
        if image_file and image_file.filename:
            img_filename = secure_filename(f"product_{datetime.now().timestamp()}.jpg")
            image_path = os.path.join(UPLOAD_FOLDER, 'images', img_filename)
            image_file.save(image_path)
        
        product = Product(
            title=title, description=description, category=category,
            price=price, file_path=pdf_path, image_path=image_path
        )
        db.session.add(product)
        db.session.commit()
        return jsonify({'success': True, 'id': product.id})

    elif request.method == 'PUT':
        data = request.form
        product_id = data.get('id')
        product = Product.query.get(product_id)
        
        if not product:
            return jsonify({'error': 'Товар не найден'}), 404
        
        product.title = data.get('title', product.title)
        product.description = data.get('description', product.description)
        product.category = data.get('category', product.category)
        product.price = float(data.get('price', product.price))
        
        pdf_file = request.files.get('pdf_file')
        if pdf_file and pdf_file.filename:
            if product.file_path and os.path.exists(product.file_path):
                os.remove(product.file_path)
            pdf_filename = secure_filename(f"product_{datetime.now().timestamp()}.pdf")
            pdf_path = os.path.join(UPLOAD_FOLDER, 'pdf', pdf_filename)
            pdf_file.save(pdf_path)
            product.file_path = pdf_path
        
        image_file = request.files.get('image_file')
        if image_file and image_file.filename:
            if product.image_path and os.path.exists(product.image_path):
                os.remove(product.image_path)
            img_filename = secure_filename(f"product_{datetime.now().timestamp()}.jpg")
            image_path = os.path.join(UPLOAD_FOLDER, 'images', img_filename)
            image_file.save(image_path)
            product.image_path = image_path
        
        product.updated_at = datetime.now()
        db.session.commit()
        return jsonify({'success': True})

    elif request.method == 'DELETE':
        product_id = request.args.get('id')
        product = Product.query.get(product_id)
        if product:
            if product.file_path and os.path.exists(product.file_path):
                os.remove(product.file_path)
            if product.image_path and os.path.exists(product.image_path):
                os.remove(product.image_path)
            db.session.delete(product)
            db.session.commit()
        return jsonify({'success': True})

@app.route('/create-tables')
def create_tables():
    try:
        db.create_all()
        return "Таблицы успешно созданы!"
    except Exception as e:
        return f"Ошибка: {e}"

@app.route('/create-admin')
def create_admin():
    try:
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        if 'users' not in inspector.get_table_names():
            return "Сначала создайте таблицы через /create-tables"
        
        user = User.query.filter_by(role='author').first()
        if not user:
            user = User(email="mari.novoselova.0@mail.ru", role="author")
            user.set_password("admin123")
            db.session.add(user)
            db.session.commit()
            return "Автор создан"
        else:
            return f"Автор уже существует: {user.email}"
    except Exception as e:
        return f"Ошибка: {e}"

if __name__ == '__main__':
    create_tables()
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
