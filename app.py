from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, IntegerField, FloatField, SelectField, BooleanField, HiddenField
from wtforms.validators import DataRequired, Length, Email, EqualTo, NumberRange, Optional
import pandas as pd
import os
import re
import requests
from datetime import datetime
from urllib.parse import urlparse
import concurrent.futures
from database import Database, User, Cart, Order, Review

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Required for flashing messages

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Initialize database
db = Database()

@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(int(user_id))

# Forms
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    first_name = StringField('First Name', validators=[Optional(), Length(max=100)])
    last_name = StringField('Last Name', validators=[Optional(), Length(max=100)])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    address = TextAreaField('Address', validators=[Optional()])
    city = StringField('City', validators=[Optional(), Length(max=100)])
    state = StringField('State', validators=[Optional(), Length(max=100)])
    postal_code = StringField('Postal Code', validators=[Optional(), Length(max=20)])

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')

class ReviewForm(FlaskForm):
    rating = SelectField('Rating', choices=[(1, '1 Star'), (2, '2 Stars'), (3, '3 Stars'), (4, '4 Stars'), (5, '5 Stars')], coerce=int)
    review_text = TextAreaField('Review', validators=[Optional(), Length(max=1000)])

class AddToCartForm(FlaskForm):
    product_id = HiddenField('Product ID')
    quantity = IntegerField('Quantity', default=1, validators=[DataRequired(), NumberRange(min=1)])

class CheckoutForm(FlaskForm):
    shipping_address = TextAreaField('Shipping Address', validators=[DataRequired()])
    payment_method = SelectField('Payment Method', choices=[('cod', 'Cash on Delivery'), ('card', 'Credit/Debit Card'), ('upi', 'UPI')], validators=[DataRequired()])

def validate_image_url(url):
    """Validate if a URL points to a valid image"""
    try:
        # Check if URL is valid
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return False
        
        # Send HEAD request to check content type
        response = requests.head(url, timeout=5)
        content_type = response.headers.get('content-type', '')
        return 'image' in content_type.lower()
    except:
        return False

def validate_urls_parallel(urls):
    """Validate multiple URLs in parallel"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(validate_image_url, urls)
        return list(results)

# Load laptop data from data/laptop_dataset_with_images.csv
CSV_PATH = os.path.join('data', 'laptop_dataset_with_images.csv')
df = pd.read_csv(CSV_PATH)

# Clean and prepare data
df['Price_Rs'] = df['Price_Rs'].round(2)
df['Weight'] = df['Weight'].round(2)
df['Inches'] = df['Inches'].round(2)
df['CPU_freq'] = df['CPU_freq'].round(2)

# Add ID column
df['ID'] = range(1, len(df) + 1)

# Add default brand images for missing URLs
default_brand_images = {
    'HP': 'https://m.media-amazon.com/images/I/71gE7D4x3-L._SL1500_.jpg',
    'Dell': 'https://m.media-amazon.com/images/I/61gGtqfZFlL._SL1500_.jpg',
    'Acer': 'https://m.media-amazon.com/images/I/71CZcP2FRoL._SL1500_.jpg',
    'Asus': 'https://m.media-amazon.com/images/I/71S8U9VzLTL._SL1500_.jpg',
    'Lenovo': 'https://m.media-amazon.com/images/I/71eXNIDUGjL._SL1500_.jpg',
    'MSI': 'https://m.media-amazon.com/images/I/71tH6wz5jUL._SL1500_.jpg',
    'Apple': 'https://m.media-amazon.com/images/I/61L1ItFgFHL._SL1500_.jpg',
    'Microsoft': 'https://m.media-amazon.com/images/I/71y4JtEdWYL._SL1500_.jpg'
}
@app.route('/monitors')
def monitors():
    """Monitors page - shows external monitor recommendations"""
    return render_template('monitors.html')


# Fill missing image URLs with brand defaults and validate URLs
# First rename the Image_URL column if it exists
if 'Image_URL' in df.columns:
    # Get unique non-null URLs
    unique_urls = df['Image_URL'].dropna().unique()
    valid_urls = dict(zip(unique_urls, validate_urls_parallel(unique_urls)))
    
    # Update invalid URLs with brand defaults
    df['image_url'] = df.apply(lambda row: 
        row['Image_URL'] if pd.notna(row['Image_URL']) and valid_urls.get(row['Image_URL'], False)
        else default_brand_images.get(row['Company'], None), axis=1)
else:
    # If no Image_URL column, create image_url column with defaults
    df['image_url'] = df['Company'].map(default_brand_images)

# Rename columns for consistency
df = df.rename(columns={
    'Price_Rs': 'Price',
    'Company': 'Brand',
    'Ram': 'RAM_Size',
    'PrimaryStorage': 'Storage_Capacity',
    'Inches': 'Screen_Size',
    'CPU_freq': 'Processor_Speed',
    'CPU_model': 'Processor_Model',
    'CPU_company': 'Processor_Brand'
})

# Load laptop data into products table if not already loaded
def load_laptops_to_database():
    cursor = db.get_connection().cursor()
    cursor.execute("SELECT COUNT(*) FROM products")
    product_count = cursor.fetchone()[0]

    if product_count == 0:
        # Load products from CSV to database
        for index, row in df.iterrows():
            cursor.execute('''
                INSERT OR REPLACE INTO products
                (id, brand, product_name, price, ram_size, storage_capacity, screen_size,
                 processor_brand, processor_model, weight, image_url, type_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                row['ID'], row['Brand'], row.get('Product', ''), row['Price'],
                row.get('RAM_Size'), row.get('Storage_Capacity'), row.get('Inches'),
                row.get('Processor_Brand', ''), row.get('Processor_Model', ''),
                row.get('Weight'), row.get('image_url', ''), row.get('TypeName', '')
            ))
        db.get_connection().commit()

# Load products on startup
load_laptops_to_database()

# Authentication Routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if username or email already exists
        if User.get_by_username(form.username.data):
            flash('Username already exists. Please choose a different one.', 'danger')
        elif User.get_by_email(form.email.data):
            flash('Email already registered. Please log in.', 'danger')
        else:
            user = User.create_user(
                username=form.username.data,
                email=form.email.data,
                password=form.password.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                phone=form.phone.data,
                address=form.address.data,
                city=form.city.data,
                state=form.state.data,
                postal_code=form.postal_code.data
            )
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))

    return render_template('auth/register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.get_by_email(form.email.data)
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            flash(f'Welcome back, {user.get_full_name()}!', 'success')

            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Invalid email or password', 'danger')

    return render_template('auth/login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('home'))

@app.route('/profile')
@login_required
def profile():
    # Get user's orders
    orders = Order.get_user_orders(current_user.id)
    return render_template('auth/profile.html', user=current_user, orders=orders)

# Shopping Cart Routes
@app.route('/cart')
@login_required
def cart():
    cart_items = Cart.get_user_cart(current_user.id)
    total = sum(item[2] * item[4] for item in cart_items)  # quantity * price
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/cart/add', methods=['POST'])
def add_to_cart():
    product_id = request.form.get('product_id')
    quantity = int(request.form.get('quantity', 1))

    if current_user.is_authenticated:
        Cart.add_item(current_user.id, product_id, quantity)
        flash('Product added to cart!', 'success')
    else:
        # For guest users, store in session
        if 'cart' not in session:
            session['cart'] = {}
        if product_id in session['cart']:
            session['cart'][product_id] += quantity
        else:
            session['cart'][product_id] = quantity
        flash('Product added to cart! Please log in to checkout', 'info')

    return redirect(url_for('cart'))

@app.route('/cart/update', methods=['POST'])
@login_required
def update_cart():
    cart_id = request.form.get('cart_id')
    quantity = int(request.form.get('quantity', 1))
    Cart.update_quantity(cart_id, quantity)
    return redirect(url_for('cart'))

@app.route('/cart/remove', methods=['POST'])
@login_required
def remove_from_cart():
    cart_id = request.form.get('cart_id')
    Cart.remove_item(cart_id)
    flash('Item removed from cart', 'info')
    return redirect(url_for('cart'))

# Checkout Routes
@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart_items = Cart.get_user_cart(current_user.id)
    if not cart_items:
        flash('Your cart is empty', 'warning')
        return redirect(url_for('cart'))

    form = CheckoutForm()
    if form.validate_on_submit():
        # Prepare order items
        items = []
        for item in cart_items:
            items.append({
                'product_id': item[1],
                'product_name': item[3] + ' ' + item[4],  # brand + product_name
                'quantity': item[2],
                'price': item[5]  # price
            })

        # Create order
        order_id, order_number = Order.create_order(
            current_user.id,
            items,
            form.shipping_address.data,
            form.payment_method.data
        )

        if order_id:
            flash(f'Order placed successfully! Order number: {order_number}', 'success')
            return redirect(url_for('order_confirmation', order_id=order_id))
        else:
            flash('Failed to place order. Please try again.', 'danger')

    # Pre-fill shipping address if available
    if current_user.address:
        form.shipping_address.data = f"{current_user.address}\n{current_user.city}, {current_user.state} {current_user.postal_code}"

    total = sum(item[2] * item[5] for item in cart_items)  # quantity * price
    return render_template('checkout.html', cart_items=cart_items, total=total, form=form)

@app.route('/order/confirmation/<int:order_id>')
@login_required
def order_confirmation(order_id):
    order = Order.get_user_orders(current_user.id)
    order = next((o for o in order if o[0] == order_id), None)
    if not order:
        return "Order not found", 404

    order_items = Order.get_order_items(order_id)
    return render_template('order_confirmation.html', order=order, order_items=order_items)

@app.route('/orders')
@login_required
def orders():
    user_orders = Order.get_user_orders(current_user.id)
    return render_template('orders.html', orders=user_orders)

# Review Routes
@app.route('/product/<int:product_id>/review', methods=['POST'])
@login_required
def add_review(product_id):
    form = ReviewForm()
    if form.validate_on_submit():
        # Check if user has already reviewed
        existing_review = Review.get_user_review(product_id, current_user.id)
        if existing_review:
            Review.update_review(product_id, current_user.id, form.rating.data, form.review_text.data)
            flash('Review updated successfully!', 'success')
        else:
            Review.add_review(product_id, current_user.id, form.rating.data, form.review_text.data)
            flash('Review added successfully!', 'success')

    return redirect(url_for('product_detail', product_id=product_id))

# 🧠 Chatbot knowledge base
def get_chatbot_response(user_message):
    message = user_message.lower().strip()

    greetings = ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening']
    if any(greeting in message for greeting in greetings):
        return {'response': "Hello! 👋 Welcome to LaptopShop! I'm here to help you find the perfect laptop.", 'type': 'greeting'}

    if 'brand' in message or 'brands' in message:
        brands = df['Brand'].unique()
        brands_list = ", ".join(brands)
        return {'response': f"We offer laptops from {len(brands)} top brands:\n\n{brands_list}", 'type': 'brands'}

    if 'price' in message or 'cost' in message:
        min_price = df['Price'].min()
        max_price = df['Price'].max()
        return {'response': f"Our laptops range from ₹{min_price:,.2f} to ₹{max_price:,.2f}.", 'type': 'price'}

    if 'ram' in message:
        ram_options = sorted(df['RAM_Size'].unique())
        return {'response': f"Available RAM options: {', '.join(map(str, ram_options))} GB.", 'type': 'specs'}

    if 'storage' in message:
        storage_options = sorted(df['Storage_Capacity'].unique())
        return {'response': f"Available storage options: {', '.join(map(str, storage_options))} GB SSD.", 'type': 'specs'}

    if 'warranty' in message:
        return {'response': "🔧 All laptops come with a 1-year warranty by default.", 'type': 'warranty'}

    if 'contact' in message:
        return {'response': "📞 Contact us at support@laptopshop.com or call +91-1800-123-4567", 'type': 'contact'}

    return {'response': "I'm here to help! Ask me about prices, brands, or warranty.", 'type': 'default'}


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '')
    if not user_message:
        return jsonify({'error': 'No message provided'}), 400
    response = get_chatbot_response(user_message)
    return jsonify(response)


@app.route('/products')
def products():
    brand = request.args.get('brand', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    ram = request.args.get('ram', type=int)
    storage = request.args.get('storage', type=int)

    filtered_df = df.copy()

    if brand and brand != 'all':
        filtered_df = filtered_df[filtered_df['Brand'] == brand]
    if min_price:
        filtered_df = filtered_df[filtered_df['Price'] >= min_price]
    if max_price:
        filtered_df = filtered_df[filtered_df['Price'] <= max_price]
    if ram:
        filtered_df = filtered_df[filtered_df['RAM_Size'] == ram]
    if storage:
        filtered_df = filtered_df[filtered_df['Storage_Capacity'] == storage]

    sort_by = request.args.get('sort', 'price_asc')
    if sort_by == 'price_asc':
        filtered_df = filtered_df.sort_values('Price')
    elif sort_by == 'price_desc':
        filtered_df = filtered_df.sort_values('Price', ascending=False)

    brands = sorted(df['Brand'].unique())
    ram_options = sorted(df['RAM_Size'].unique())
    storage_options = sorted(df['Storage_Capacity'].unique())
    laptops = filtered_df.to_dict('records')

    return render_template(
        'products.html',
        laptops=laptops,
        brands=brands,
        ram_options=ram_options,
        storage_options=storage_options,
        current_brand=brand,
        current_ram=ram,
        current_storage=storage
    )


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    # Get product from database
    product = db.fetch_one("SELECT * FROM products WHERE id = ?", (product_id,))
    if not product:
        return "Product not found", 404

    # Convert to dict for template compatibility
    laptop = {
        'ID': product[0],
        'Brand': product[1],
        'Product': product[2],
        'Price': product[3],
        'RAM_Size': product[4],
        'Storage_Capacity': product[5],
        'Inches': product[6],
        'Processor_Brand': product[7],
        'Processor_Model': product[8],
        'Weight': product[9],
        'image_url': product[10],
        'TypeName': product[11]
    }

    # Get product reviews
    reviews = Review.get_product_reviews(product_id)
    average_rating = Review.get_average_rating(product_id)
    user_review = None
    if current_user.is_authenticated:
        user_review = Review.get_user_review(product_id, current_user.id)

    # Create forms
    add_to_cart_form = AddToCartForm()
    add_to_cart_form.product_id.data = product_id
    review_form = ReviewForm()

    # Pre-fill review form if user has already reviewed
    if user_review:
        review_form.rating.data = user_review[0]
        review_form.review_text.data = user_review[1]

    return render_template('product_detail.html',
                         laptop=laptop,
                         reviews=reviews,
                         average_rating=average_rating,
                         user_review=user_review,
                         add_to_cart_form=add_to_cart_form,
                         review_form=review_form)


@app.route('/about')
def about():
    # Basic stats
    total_laptops = len(df)
    brands = sorted(df['Brand'].unique())
    avg_price = df['Price'].mean()
    
    # Brand distribution
    brand_counts = df['Brand'].value_counts()
    brand_labels = brand_counts.index.tolist()
    brand_counts = brand_counts.values.tolist()

    # Trending laptops (based on most common RAM and price range combinations)
    trending_models = df.groupby('Product')['Price'].count().sort_values(ascending=False).head(5)
    trending_labels = trending_models.index.tolist()
    trending_counts = trending_models.values.tolist()

    # Price range distribution
    price_ranges = [0, 30000, 50000, 80000, 100000, float('inf')]
    price_labels = ['Under ₹30K', '₹30K-50K', '₹50K-80K', '₹80K-100K', 'Above ₹100K']
    price_counts = []
    for i in range(len(price_ranges)-1):
        count = len(df[(df['Price'] >= price_ranges[i]) & (df['Price'] < price_ranges[i+1])])
        price_counts.append(count)

    # Stock status by brand (simulated data - you'll need to modify this based on your actual stock tracking)
    stock_labels = brands
    stock_available = [len(df[df['Brand'] == brand]) for brand in brands]
    stock_sold = [int(count * 0.3) for count in stock_available]  # Simulated 30% sold
    available_laptops = sum(stock_available)

    stats = {
        'total_laptops': total_laptops,
        'brands': brands,
        'avg_price': round(avg_price, 2),
        'num_brands': len(brands),
        'available_laptops': available_laptops,
        
        # Chart data
        'brand_labels': brand_labels,
        'brand_counts': brand_counts,
        'trending_labels': trending_labels,
        'trending_counts': trending_counts,
        'price_range_labels': price_labels,
        'price_range_counts': price_counts,
        'stock_labels': stock_labels,
        'stock_available': stock_available,
        'stock_sold': stock_sold
    }
    
    return render_template('about.html', stats=stats)


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        subject = request.form['subject']
        message = request.form['message']

        with open("messages.txt", "a") as f:
            f.write(f"\n--- New Message ---\n"
                    f"Time: {datetime.now()}\n"
                    f"Name: {name}\n"
                    f"Email: {email}\n"
                    f"Subject: {subject}\n"
                    f"Message: {message}\n")

        flash('✅ Thank you! Your message has been sent successfully.', 'success')
        return redirect(url_for('contact'))

    return render_template('contact.html')


# ✅ Fixed Warranty Route
@app.route('/warranty', methods=['GET', 'POST'])
def warranty():
    result = None

    if request.method == 'POST':
        product_id = request.form['product_id'].strip().lower()
        mobile = request.form['mobile'].strip()
        email = request.form['email'].strip()

        # Normalize the column for comparison
        df['TypeName'] = df['TypeName'].astype(str).str.strip().str.lower()

        # Allow partial or exact match
        record = df[df['TypeName'].str.contains(product_id, case=False, na=False)]

        if not record.empty:
            row = record.iloc[0]
            result = {
                "ProductID": row['TypeName'],
                "Brand": row['Brand'],  # Renamed from Company
                "Price": row['Price'],  # Renamed from Price_Rs
                "RAM": row['RAM_Size'],  # Renamed from Ram
                "Processor": f"{row.get('Processor_Brand', '')} {row.get('Processor_Model', '')}",  # Using proper processor info
                "WarrantyStatus": row.get('warranty_status', 'Under Warranty')  # Default to Under Warranty if not specified
            }
        else:
            flash("❌ No product found with the given Product ID. Please check and try again.", "danger")

    return render_template("warranty.html", result=result)

@app.route('/accessories')
def accessories():
    """Accessories page"""
    return render_template('accessories.html')

@app.route('/antivirus')
def antivirus():
    """Antivirus page"""
    antiviruses = [
        {
            "id": 1,
            "name": "Kaspersky Total Security",
            "price": 799,
            "validity": "1 Year - 1 Device",
            "features": ["Real-time protection", "Anti-phishing", "Parental controls"],
            "image": "images/antivirus/kaspersky.jpg"
        },
        {
            "id": 2,
            "name": "Quick Heal Total Security",
            "price": 699,
            "validity": "1 Year - 1 Device",
            "features": ["Ransomware protection", "Web security", "Performance optimizer"],
            "image": "images/antivirus/quickheal.jpg"
        },
        {
            "id": 3,
            "name": "McAfee Antivirus Plus",
            "price": 899,
            "validity": "1 Year - 3 Devices",
            "features": ["VPN included", "Password manager", "Multi-device support"],
            "image": "images/antivirus/mcafee.jpg"
        },
        {
            "id": 4,
            "name": "Norton 360 Deluxe",
            "price": 999,
            "validity": "1 Year - 5 Devices",
            "features": ["Cloud backup", "Smart firewall", "Dark web monitoring"],
            "image": "images/antivirus/norton.jpg"
        }
    ]

    return render_template('antivirus.html', antiviruses=antiviruses)



@app.route('/buy-antivirus/<int:av_id>')
def buy_antivirus(av_id):
    """Buy antivirus page"""
    # Find the antivirus by ID
    antivirus = next((av for av in [
        {
            "id": 1,
            "name": "Kaspersky Total Security",
            "price": 799,
            "validity": "1 Year - 1 Device"
        },
        {
            "id": 2,
            "name": "Quick Heal Total Security",
            "price": 699,
            "validity": "1 Year - 1 Device"
        },
        {
            "id": 3,
            "name": "McAfee Antivirus Plus",
            "price": 899,
            "validity": "1 Year - 3 Devices"
        },
        {
            "id": 4,
            "name": "Norton 360 Deluxe",
            "price": 999,
            "validity": "1 Year - 5 Devices"
        }
    ] if av['id'] == av_id), None)

    if antivirus:
        return render_template('buy_antivirus.html', antivirus=antivirus)
    else:
        return "Antivirus not found", 404

@app.route('/api/laptops')
def api_laptops():
    laptops = df.to_dict('records')
    return jsonify(laptops)

@app.route('/gaming-info')
def gaming_info():
    """Gaming Laptop Information Page"""
    # Select a few gaming laptops from dataset
    gaming_df = df[df['TypeName'].str.contains('gaming', case=False, na=False)]
    
    if gaming_df.empty and 'Product' in df.columns:
        gaming_df = df[df['Product'].str.contains('gaming', case=False, na=False)]
    
    sample_laptops = gaming_df.head(3).to_dict('records') if not gaming_df.empty else [
        {
            "Brand": "Asus",
            "Product": "Asus ROG Strix G15",
            "Price": 89999,
            "RAM_Size": 16,
            "Storage_Capacity": 512,
            "Processor_Model": "Ryzen 7 6800H",
            "Processor_Brand": "AMD",
            "image_url": "https://m.media-amazon.com/images/I/71S8U9VzLTL._SL1500_.jpg"
        },
        {
            "Brand": "Lenovo",
            "Product": "Lenovo Legion 5 Pro",
            "Price": 112999,
            "RAM_Size": 16,
            "Storage_Capacity": 1024,
            "Processor_Model": "Ryzen 7 5800H",
            "Processor_Brand": "AMD",
            "image_url": "https://m.media-amazon.com/images/I/71eXNIDUGjL._SL1500_.jpg"
        },
        {
            "Brand": "HP",
            "Product": "HP Victus 16",
            "Price": 99999,
            "RAM_Size": 16,
            "Storage_Capacity": 512,
            "Processor_Model": "Intel i7-12700H",
            "Processor_Brand": "Intel",
            "image_url": "https://m.media-amazon.com/images/I/71gE7D4x3-L._SL1500_.jpg"
        }
    ]

    return render_template('gaming_info.html', laptops=sample_laptops)



if __name__ == '__main__':
    app.run(debug=True)
