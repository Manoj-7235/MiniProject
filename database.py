import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

class Database:
    def __init__(self, db_path='laptopshop.db'):
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        # Create Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(80) UNIQUE NOT NULL,
                email VARCHAR(120) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                first_name VARCHAR(100),
                last_name VARCHAR(100),
                phone VARCHAR(20),
                address TEXT,
                city VARCHAR(100),
                state VARCHAR(100),
                postal_code VARCHAR(20),
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create Shopping Carts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shopping_carts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(user_id, product_id)
            )
        ''')

        # Create Orders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                order_number VARCHAR(50) UNIQUE NOT NULL,
                total_amount DECIMAL(10,2) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                shipping_address TEXT NOT NULL,
                payment_method VARCHAR(50),
                payment_status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # Create Order Items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                product_name VARCHAR(255) NOT NULL,
                quantity INTEGER NOT NULL,
                price DECIMAL(10,2) NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders (id)
            )
        ''')

        # Create Product Reviews table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                rating INTEGER CHECK(rating >= 1 AND rating <= 5),
                review_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(product_id, user_id)
            )
        ''')

        # Create Products table to store laptop data from CSV
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                brand VARCHAR(100) NOT NULL,
                product_name VARCHAR(255) NOT NULL,
                price DECIMAL(10,2) NOT NULL,
                ram_size INTEGER,
                storage_capacity INTEGER,
                screen_size REAL,
                processor_brand VARCHAR(100),
                processor_model VARCHAR(255),
                weight REAL,
                image_url TEXT,
                type_name VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def execute_query(self, query, params=()):
        conn = self.get_connection()
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        conn.commit()
        conn.close()

    def fetch_one(self, query, params=()):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchone()
        conn.close()
        return result

    def fetch_all(self, query, params=()):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchall()
        conn.close()
        return result

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username, email, password_hash, first_name=None, last_name=None,
                 phone=None, address=None, city=None, state=None, postal_code=None,
                 is_admin=False, created_at=None, updated_at=None):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.first_name = first_name
        self.last_name = last_name
        self.phone = phone
        self.address = address
        self.city = city
        self.state = state
        self.postal_code = postal_code
        self.is_admin = bool(is_admin)
        self.created_at = created_at
        self.updated_at = updated_at

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        else:
            return self.username

    @classmethod
    def get_by_id(cls, user_id):
        db = Database()
        result = db.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
        if result:
            return cls(*result)
        return None

    @classmethod
    def get_by_email(cls, email):
        db = Database()
        result = db.fetch_one("SELECT * FROM users WHERE email = ?", (email,))
        if result:
            return cls(*result)
        return None

    @classmethod
    def get_by_username(cls, username):
        db = Database()
        result = db.fetch_one("SELECT * FROM users WHERE username = ?", (username,))
        if result:
            return cls(*result)
        return None

    def save(self):
        db = Database()
        if self.id:
            # Update existing user
            db.execute_query('''
                UPDATE users SET username=?, email=?, password_hash=?, first_name=?,
                last_name=?, phone=?, address=?, city=?, state=?, postal_code=?,
                is_admin=?, updated_at=CURRENT_TIMESTAMP WHERE id=?
            ''', (self.username, self.email, self.password_hash, self.first_name,
                  self.last_name, self.phone, self.address, self.city, self.state,
                  self.postal_code, self.is_admin, self.id))
        else:
            # Create new user
            db.execute_query('''
                INSERT INTO users (username, email, password_hash, first_name, last_name,
                phone, address, city, state, postal_code, is_admin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (self.username, self.email, self.password_hash, self.first_name,
                  self.last_name, self.phone, self.address, self.city, self.state,
                  self.postal_code, self.is_admin))
            # Get the new user ID
            result = db.fetch_one("SELECT last_insert_rowid()")
            self.id = result[0] if result else None

    @classmethod
    def create_user(cls, username, email, password, first_name=None, last_name=None,
                    phone=None, address=None, city=None, state=None, postal_code=None):
        user = cls(None, username, email, None, first_name, last_name, phone,
                  address, city, state, postal_code)
        user.set_password(password)
        user.save()
        return user

# Shopping Cart Functions
class Cart:
    @staticmethod
    def add_item(user_id, product_id, quantity=1):
        db = Database()
        # Check if item already exists in cart
        existing = db.fetch_one(
            "SELECT id, quantity FROM shopping_carts WHERE user_id = ? AND product_id = ?",
            (user_id, product_id)
        )

        if existing:
            # Update quantity
            new_quantity = existing[1] + quantity
            db.execute_query(
                "UPDATE shopping_carts SET quantity = ? WHERE id = ?",
                (new_quantity, existing[0])
            )
        else:
            # Add new item
            db.execute_query(
                "INSERT INTO shopping_carts (user_id, product_id, quantity) VALUES (?, ?, ?)",
                (user_id, product_id, quantity)
            )

    @staticmethod
    def get_user_cart(user_id):
        db = Database()
        cart_items = db.fetch_all('''
            SELECT sc.id, sc.product_id, sc.quantity, p.brand, p.product_name, p.price, p.image_url
            FROM shopping_carts sc
            JOIN products p ON sc.product_id = p.id
            WHERE sc.user_id = ?
        ''', (user_id,))
        return cart_items

    @staticmethod
    def update_quantity(cart_id, quantity):
        db = Database()
        if quantity > 0:
            db.execute_query("UPDATE shopping_carts SET quantity = ? WHERE id = ?", (quantity, cart_id))
        else:
            db.execute_query("DELETE FROM shopping_carts WHERE id = ?", (cart_id,))

    @staticmethod
    def remove_item(cart_id):
        db = Database()
        db.execute_query("DELETE FROM shopping_carts WHERE id = ?", (cart_id,))

    @staticmethod
    def clear_cart(user_id):
        db = Database()
        db.execute_query("DELETE FROM shopping_carts WHERE user_id = ?", (user_id,))

# Order Functions
class Order:
    @staticmethod
    def create_order(user_id, items, shipping_address, payment_method):
        db = Database()

        # Calculate total amount
        total_amount = sum(item['price'] * item['quantity'] for item in items)

        # Generate order number
        order_number = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Create order
        db.execute_query('''
            INSERT INTO orders (user_id, order_number, total_amount, shipping_address, payment_method)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, order_number, total_amount, shipping_address, payment_method))

        # Get order ID
        result = db.fetch_one("SELECT last_insert_rowid()")
        order_id = result[0] if result else None

        if order_id:
            # Add order items
            for item in items:
                db.execute_query('''
                    INSERT INTO order_items (order_id, product_id, product_name, quantity, price)
                    VALUES (?, ?, ?, ?, ?)
                ''', (order_id, item['product_id'], item['product_name'], item['quantity'], item['price']))

            # Clear cart
            Cart.clear_cart(user_id)

        return order_id, order_number

    @staticmethod
    def get_user_orders(user_id):
        db = Database()
        orders = db.fetch_all('''
            SELECT id, order_number, total_amount, status, shipping_address,
                   payment_method, payment_status, created_at, updated_at
            FROM orders WHERE user_id = ? ORDER BY created_at DESC
        ''', (user_id,))
        return orders

    @staticmethod
    def get_order_items(order_id):
        db = Database()
        items = db.fetch_all('''
            SELECT product_id, product_name, quantity, price
            FROM order_items WHERE order_id = ?
        ''', (order_id,))
        return items

    @staticmethod
    def update_order_status(order_id, status):
        db = Database()
        db.execute_query(
            "UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, order_id)
        )

# Product Review Functions
class Review:
    @staticmethod
    def add_review(product_id, user_id, rating, review_text):
        db = Database()
        db.execute_query('''
            INSERT OR REPLACE INTO product_reviews (product_id, user_id, rating, review_text)
            VALUES (?, ?, ?, ?)
        ''', (product_id, user_id, rating, review_text))

    @staticmethod
    def get_product_reviews(product_id):
        db = Database()
        reviews = db.fetch_all('''
            SELECT pr.rating, pr.review_text, pr.created_at, u.username, u.first_name, u.last_name
            FROM product_reviews pr
            JOIN users u ON pr.user_id = u.id
            WHERE pr.product_id = ? ORDER BY pr.created_at DESC
        ''', (product_id,))
        return reviews

    @staticmethod
    def get_average_rating(product_id):
        db = Database()
        result = db.fetch_one(
            "SELECT AVG(rating) FROM product_reviews WHERE product_id = ?",
            (product_id,)
        )
        return round(result[0], 1) if result and result[0] else 0

    @staticmethod
    def get_user_review(product_id, user_id):
        db = Database()
        result = db.fetch_one(
            "SELECT rating, review_text FROM product_reviews WHERE product_id = ? AND user_id = ?",
            (product_id, user_id)
        )
        return result

    @staticmethod
    def update_review(product_id, user_id, rating, review_text):
        db = Database()
        db.execute_query('''
            UPDATE product_reviews
            SET rating = ?, review_text = ?, updated_at = CURRENT_TIMESTAMP
            WHERE product_id = ? AND user_id = ?
        ''', (rating, review_text, product_id, user_id))

    @staticmethod
    def delete_review(product_id, user_id):
        db = Database()
        db.execute_query(
            "DELETE FROM product_reviews WHERE product_id = ? AND user_id = ?",
            (product_id, user_id)
        )