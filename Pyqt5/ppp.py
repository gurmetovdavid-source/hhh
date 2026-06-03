import sys
import os
import pymysql
from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
#product.py from db import run_query
#app.py from db import run_query
#from product import PRODUCT_SQL, price_html, card_style, get_product_pixmap, ProductManager
#main.py from db import auth
#from app import AppWindow

# ─────────────────────────── db.py ───────────────────────────

def get_connection():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='narek123',
        database='shoes',
        cursorclass=pymysql.cursors.DictCursor
    )


def run_query(query, params=(), fetch=None):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            if fetch == 'one': return cursor.fetchone()
            if fetch == 'all': return cursor.fetchall()
            conn.commit()
            return cursor.lastrowid
    finally:
        conn.close()


def auth(login, password):
    query = """
        SELECT u.user_id, u.username, u.first_name, r.role_name 
        FROM Users u 
        JOIN Roles r ON r.role_id = u.role_id
        WHERE u.username = %s AND u.passw = %s
    """
    return run_query(query, (login, password), fetch='one')


# ─────────────────────────── product.py ───────────────────────────

PRODUCT_SQL = """
    SELECT 
        p.*,
        c.name as category,
        m.name as manufacture,
        s.name as supplier
    FROM Products p
    LEFT JOIN Categories c ON p.category_id = c.category_id
    LEFT JOIN Manufacturers m ON p.manufacture_id = m.manufacture_id
    LEFT JOIN Suppliers s ON p.supplier_id = s.supplier_id
"""


def price_html(price, discount):
    price, discount = float(price), float(discount)
    if discount > 0:
        final = round(price * (1 - discount / 100), 2)
        return (
            f'<span style="color: red; text-decoration: line-through"> {price:.0f} Р. </span> '
            f'<span style="color: green; font-weight: bold;">{final:.0f} Р.</span>'
        )
    return f'<b>{price:.0f} Р.</b>'


def card_style(stock, discount):
    discount = float(discount or 0)
    stock = int(stock or 0)
    st = "border-radius: 8px; border: 1px solid #ddd; padding: 6px; "
    if stock <= 0:
        st += "background-color: #B3E5FC;"
    elif discount > 15:
        st += "background-color: #E8F5E9; border: 1px solid #81C784;"
    else:
        st += "background-color: #FFFFFF;"
    return st


def get_product_pixmap(path):
    pix = QPixmap(80, 80)
    if path and os.path.exists(path):
        pix.load(path)
        return pix.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    pix.fill(QColor("#E0E0E0"))
    painter = QPainter(pix)
    painter.setPen(QColor("#757575"))
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "No Photo")
    painter.end()
    return pix


class ProductManager:
    @staticmethod
    def add_product(parent_window):
        name, ok1 = QInputDialog.getText(parent_window, "Добавить", "Название обуви:")
        if not ok1 or not name: return
        price, ok2 = QInputDialog.getDouble(parent_window, "Добавить", "Цена (Р):", 5000, 0, 999999, 2)
        if not ok2: return
        stock, ok3 = QInputDialog.getInt(parent_window, "Добавить", "Остаток на складе:", 10, 0, 99999)
        if ok3:
            run_query(
                "INSERT INTO Products (name, category_id, manufacture_id, supplier_id, price, unit, quantity, discount) "
                "VALUES (%s, 1, 1, 1, %s, 'шт', %s, 0)",
                (name, price, stock),
            )
            parent_window.load_product()

    @staticmethod
    def delete_product(parent_window):
        name, ok = QInputDialog.getText(parent_window, "Удалить товар", "Введите точное название для удаления:")
        if not ok or not name: return
        row = run_query("SELECT product_id FROM Products WHERE name=%s", (name,), fetch='one')
        if not row:
            QMessageBox.warning(parent_window, "Ошибка", "Товар с таким названием не найден")
            return
        cnt = run_query(
            "SELECT COUNT(*) AS c FROM OrderItems WHERE product_id=%s",
            (row['product_id'],), fetch='one'
        )
        if cnt and cnt['c'] > 0:
            QMessageBox.warning(parent_window, "Ошибка", "Нельзя удалить товар, так как он уже есть в заказах!")
            return
        run_query("DELETE FROM Products WHERE product_id = %s", (row['product_id'],))
        QMessageBox.information(parent_window, "Успешно", "Товар удален")
        parent_window.load_product()

    @staticmethod
    def change_product(parent_window):
        name, ok = QInputDialog.getText(parent_window, "Изменить товар", "Введите точное название товара:")
        if not ok or not name: return
        product = run_query("SELECT * FROM Products WHERE name=%s", (name,), fetch='one')
        if not product:
            QMessageBox.warning(parent_window, "Ошибка", "Товар не найден!")
            return
        new_price, ok_p = QInputDialog.getDouble(
            parent_window, "Изменение", f"Старая цена: {product['price']} Р.\nНовая цена:",
            float(product['price']), 0, 999999, 2
        )
        if not ok_p: return
        new_qty, ok_q = QInputDialog.getInt(
            parent_window, "Изменение", f"Текущий остаток: {product['quantity']} шт.\nНовый остаток:",
            int(product['quantity']), 0, 99999
        )
        if not ok_q: return
        run_query(
            "UPDATE Products SET price=%s, quantity=%s WHERE product_id=%s",
            (new_price, new_qty, product['product_id'])
        )
        QMessageBox.information(parent_window, "Успешно", "Данные товара обновлены")
        parent_window.load_product()


# ─────────────────────────── app.py ───────────────────────────

class AppWindow(QMainWindow):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.role = self.user['role_name']
        self.sort_asc = True
        self.resize(900, 600)
        self.setWindowTitle(f"Магазин — Панель: {self.role.upper()}")

        if os.path.exists("logo.png"):
            self.setWindowIcon(QIcon("logo.png"))

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.menu_tab = QWidget()
        self.tabs.addTab(self.menu_tab, 'Меню товаров')
        self.setup_menu()

    def logout(self):
        os.execl(sys.executable, sys.executable, *sys.argv)

    def add_btn(self, text, func, layout):
        btn = QPushButton(text)
        btn.clicked.connect(func)
        layout.addWidget(btn)
        return btn

    def setup_menu(self):
        layout = QVBoxLayout(self.menu_tab)
        admin_layout = QHBoxLayout()

        exit_btn = self.menuBar().addAction("Выйти")
        exit_btn.triggered.connect(self.logout)

        if self.role == 'admin':
            self.add_btn('Добавить товар', lambda: ProductManager.add_product(self), admin_layout)
            self.add_btn('Удалить товар', lambda: ProductManager.delete_product(self), admin_layout)
            self.add_btn('Изменить цену/остаток', lambda: ProductManager.change_product(self), admin_layout)
        if self.role in ['admin', 'manager']:
            self.add_btn('Управление заказами', self.manage_orders, admin_layout)

        layout.addLayout(admin_layout)

        self.search = None
        self.supplier_cb = None
        self.sort_btn = None
        if self.role != 'client':
            filt = QHBoxLayout()
            self.search = QLineEdit()
            self.search.setPlaceholderText("Поиск...")
            self.search.textChanged.connect(self.load_product)

            self.supplier_cb = QComboBox()
            self.supplier_cb.addItem('Все поставщики', None)
            for s in run_query("SELECT supplier_id, name FROM Suppliers", fetch='all') or []:
                self.supplier_cb.addItem(s['name'], s['supplier_id'])
            self.supplier_cb.currentIndexChanged.connect(self.load_product)

            self.sort_btn = QPushButton("Склад: По возрастанию")
            self.sort_btn.clicked.connect(self.toggle_sort)

            filt.addWidget(QLabel('Поиск:'))
            filt.addWidget(self.search)
            filt.addWidget(QLabel('Поставщик:'))
            filt.addWidget(self.supplier_cb)
            filt.addWidget(self.sort_btn)
            layout.addLayout(filt)

        scroll = QScrollArea(widgetResizable=True)
        self.grid_w = QWidget()
        self.grid = QGridLayout(self.grid_w)
        scroll.setWidget(self.grid_w)
        layout.addWidget(scroll)
        self.load_product()

    def toggle_sort(self):
        if not self.sort_btn:
            return
        self.sort_asc = not self.sort_asc
        self.sort_btn.setText(f"Склад: {'По возрастанию' if self.sort_asc else 'По убыванию'}")
        self.load_product()

    def load_product(self):
        for i in reversed(range(self.grid.count())):
            self.grid.itemAt(i).widget().setParent(None)

        products = run_query(PRODUCT_SQL, fetch='all') or []
        search = self.search.text().strip().lower() if self.search else ''
        sup_id = self.supplier_cb.currentData() if self.supplier_cb else None

        filtered = []
        for p in products:
            if sup_id and p.get('supplier_id') != sup_id:
                continue
            if search:
                text = ' '.join(str(p.get(k) or '') for k in ('name', 'category', 'manufacture')).lower()
                if search not in text:
                    continue
            filtered.append(p)

        if self.role != 'client':
            filtered.sort(key=lambda x: int(x.get('quantity') or 0), reverse=not self.sort_asc)

        for i, p in enumerate(filtered):
            card = QFrame()
            card.setStyleSheet(card_style(p['quantity'], p['discount']))
            card.setFixedHeight(120)
            h = QHBoxLayout(card)

            img_lbl = QLabel()
            img_lbl.setPixmap(get_product_pixmap(p.get('image_path')))
            img_lbl.setFixedSize(80, 80)

            info = QLabel(
                f"<span style='font-size:14px;'><b>{p['name']}</b></span><br>"
                f"Категория: {p.get('category') or '-'} | Бренд: {p.get('manufacture') or '-'}<br>"
                f"Наличие: <b>{p['quantity']} {p['unit']}</b><br>"
                f"Цена: {price_html(p['price'], p['discount'])}"
            )

            discount_box = QLabel(f"Скидка\n{float(p.get('discount') or 0):.0f}%")
            discount_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            discount_box.setFixedSize(80, 50)
            discount_box.setStyleSheet(
                "background-color: #FFF3CD; border: 1px solid #FFC107; "
                "border-radius: 6px; font-weight: bold; color: #6D4C00;"
            )

            h.addWidget(img_lbl)
            h.addWidget(info)
            h.addStretch()
            h.addWidget(discount_box)
            self.grid.addWidget(card, i, 0)

    def manage_orders(self):
        d = QDialog(self)
        d.setWindowTitle("Управление заказами")
        d.resize(700, 450)

        lay = QVBoxLayout(d)

        db_statuses = run_query("SELECT status_id, name FROM Status", fetch='all') or []
        status_map = {s['name']: s['status_id'] for s in db_statuses}

        filter_options = ["Все"] + [s['name'] for s in db_statuses]
        cb = QComboBox()
        cb.addItems(filter_options)

        top = QHBoxLayout()
        top.addWidget(QLabel("<b>Фильтр по статусу заказа:</b>"))
        top.addWidget(cb)
        if self.role == 'admin':
            add_order_btn = QPushButton("Добавить заказ")
            top.addWidget(add_order_btn)
        lay.addLayout(top)
        lst = QListWidget()
        lay.addWidget(lst)

        def load():
            lst.clear()
            sql = """
                SELECT o.order_id, o.status_id, o.address, o.order_date,
                       u.last_name, u.first_name, s.name as status_name
                FROM Orders o
                LEFT JOIN Users u ON o.user_id = u.user_id
                INNER JOIN Status s ON o.status_id = s.status_id
                ORDER BY o.order_id DESC
            """
            for r in run_query(sql, fetch='all') or []:
                if cb.currentText() != "Все" and r['status_name'] != cb.currentText():
                    continue
                buyer = f"{r.get('last_name') or ''} {r.get('first_name') or ''}".strip() or "Гость"
                item_text = f"Заказ #{r['order_id']} от {str(r['order_date'])} | Клиент: {buyer} | Статус: [{r['status_name']}]"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, r)
                lst.addItem(item)

        def change(item):
            if self.role != 'admin':
                QMessageBox.warning(d, "Отказ", "Изменять статус заказов может только Администратор!")
                return
            order_data = item.data(Qt.ItemDataRole.UserRole)
            current_status_name = order_data['status_name']
            statuses_list = [s['name'] for s in db_statuses]
            try:
                current_idx = statuses_list.index(current_status_name)
            except ValueError:
                current_idx = 0
            res, ok = QInputDialog.getItem(d, "Изменение статуса",
                                           f"Новый статус для заказа #{order_data['order_id']}:",
                                           statuses_list, current_idx, False)
            if ok and res:
                run_query("UPDATE Orders SET status_id=%s WHERE order_id=%s",
                          (status_map[res], order_data['order_id']))
                QMessageBox.information(d, "Успешно", "Статус заказа обновлен")
                load()

        def add_order():
            if self.role != 'admin':
                QMessageBox.warning(d, "Отказ", "Добавлять заказы может только Администратор!")
                return
            clients = run_query(
                """SELECT u.user_id, u.username, u.last_name, u.first_name
                   FROM Users u INNER JOIN Roles r ON r.role_id = u.role_id
                   WHERE r.role_name = 'client' ORDER BY u.last_name, u.first_name, u.username""",
                fetch='all') or []
            products = run_query(
                "SELECT product_id, name, quantity FROM Products WHERE quantity > 0 ORDER BY name",
                fetch='all') or []

            if not clients:
                QMessageBox.warning(d, "Ошибка", "Нет клиентов для оформления заказа"); return
            if not products:
                QMessageBox.warning(d, "Ошибка", "Нет товаров в наличии"); return
            if not db_statuses:
                QMessageBox.warning(d, "Ошибка", "Нет статусов заказа"); return

            client_items = {}
            for client in clients:
                full_name = f"{client.get('last_name') or ''} {client.get('first_name') or ''}".strip()
                label = f"{full_name or client['username']} (ID {client['user_id']})"
                client_items[label] = client

            product_items = {}
            for product in products:
                label = f"{product['name']} - остаток {product['quantity']} шт. (ID {product['product_id']})"
                product_items[label] = product

            client_label, ok = QInputDialog.getItem(d, "Добавить заказ", "Клиент:", list(client_items.keys()), 0, False)
            if not ok or not client_label: return

            product_label, ok = QInputDialog.getItem(d, "Добавить заказ", "Товар:", list(product_items.keys()), 0, False)
            if not ok or not product_label: return

            product = product_items[product_label]
            qty, ok = QInputDialog.getInt(d, "Добавить заказ", "Количество:", 1, 1, int(product['quantity']))
            if not ok: return

            address, ok = QInputDialog.getText(d, "Добавить заказ", "Адрес доставки:", text="-")
            if not ok: return
            address = address.strip() or "-"

            statuses_list = [s['name'] for s in db_statuses]
            default_status = status_map.get("Новый", db_statuses[0]['status_id'])
            default_idx = next((i for i, s in enumerate(db_statuses) if s['status_id'] == default_status), 0)
            status_name, ok = QInputDialog.getItem(d, "Добавить заказ", "Статус:", statuses_list, default_idx, False)
            if not ok or not status_name: return

            order_id = run_query(
                "INSERT INTO Orders (user_id, status_id, address, order_date) VALUES (%s, %s, %s, CURDATE())",
                (client_items[client_label]['user_id'], status_map[status_name], address))
            run_query("INSERT INTO OrderItems (order_id, product_id, quantity) VALUES (%s, %s, %s)",
                      (order_id, product['product_id'], qty))
            run_query("UPDATE Products SET quantity = quantity - %s WHERE product_id = %s",
                      (qty, product['product_id']))

            QMessageBox.information(d, "Успешно", f"Заказ #{order_id} добавлен")
            self.load_product()
            load()

        cb.currentTextChanged.connect(load)
        lst.itemDoubleClicked.connect(change)
        if self.role == 'admin':
            add_order_btn.clicked.connect(add_order)
        load()
        d.exec()


# ─────────────────────────── main.py ───────────────────────────

class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.setWindowTitle("Авторизация")
        self.resize(350, 200)

        if os.path.exists("/home/kirill/demo/images/black_row.jpg"):
            self.setWindowIcon(QIcon("/home/kirill/demo/images/black_row.jpg"))

        self.lbl = QLabel("<h3>Авторизация<h3>")
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.login_line = QLineEdit()
        self.login_line.setPlaceholderText("Логин")

        self.passw_line = QLineEdit()
        self.passw_line.setPlaceholderText("Пароль")
        self.passw_line.setEchoMode(QLineEdit.EchoMode.Password)

        self.btn_login = QPushButton("Войти")
        self.btn_guest = QPushButton("Гость")

        for w in (self.lbl, self.login_line, self.passw_line, self.btn_login, self.btn_guest):
            layout.addWidget(w)

        self.btn_login.clicked.connect(self.try_login)
        self.btn_guest.clicked.connect(lambda: self.main_win({'username': 'guest', 'role_name': 'client'}))

    def try_login(self):
        try:
            user = auth(self.login_line.text(), self.passw_line.text())
            if user:
                QMessageBox.information(self, 'Успешно', f'Добро пожаловать, {user["first_name"]}!')
                self.main_win(user)
            else:
                QMessageBox.warning(self, 'Ошибка', 'Неверный логин или пароль')
        except Exception as e:
            QMessageBox.warning(self, 'Ошибка', 'Упс, что-то не так при подключении к БД')
            print(e)

    def main_win(self, user):
        self.win = AppWindow(user)
        self.win.show()
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    sys.exit(app.exec())


CREATE database if not EXISTS shoes;
USE shoes;

CREATE TABLE IF NOT EXISTS Roles(
    role_id INT PRIMARY KEY AUTO_INCREMENT,
    role_name VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS Users(
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(100) NOT NULL,
    passw VARCHAR(100) NOT NULL,
    last_name VARCHAR(100),
    first_name VARCHAR(100),
    patronymic VARCHAR(100),
    role_id INT,

    FOREIGN KEY (role_id) REFERENCES Roles(role_id)
);

CREATE TABLE IF NOT EXISTS Categories(
    category_id INT PRIMARY KEY AUTO_INCREMENT,
    `name` VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS Manufacturers(
    manufacture_id INT PRIMARY KEY AUTO_INCREMENT,
    `name` VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS Suppliers(
    supplier_id INT PRIMARY KEY AUTO_INCREMENT,
    `name` VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS Products(
    product_id INT PRIMARY KEY AUTO_INCREMENT,
    `name` VARCHAR(100),
    category_id INT,
    `description` TEXT,
    manufacture_id INT,
    supplier_id INT,
    price DECIMAL(10, 2),
    unit VARCHAR(50) DEFAULT "шт",
    quantity INT,
    discount DECIMAL(5, 2) DEFAULT 0.00,
    image_path VARCHAR(255),

    FOREIGN KEY (category_id) REFERENCES Categories(category_id),
    FOREIGN KEY (manufacture_id) REFERENCES Manufacturers(manufacture_id),
    FOREIGN KEY (supplier_id) REFERENCES Suppliers(supplier_id)
);

CREATE TABLE IF NOT EXISTS Status(
    status_id INT PRIMARY KEY AUTO_INCREMENT,
    `name` VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS Orders(
    order_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    status_id INT,
    `address` TEXT NOT NULL,
    order_date DATE DEFAULT (current_date),
    issue_date DATE,

    FOREIGN KEY (user_id) REFERENCES Users(user_id),
    FOREIGN KEY (status_id) REFERENCES Status(status_id)
);

CREATE TABLE IF NOT EXISTS OrderItems(
    item_id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT,
    product_id INT,
    quantity INT,

    FOREIGN KEY (order_id) REFERENCES Orders(order_id),
    FOREIGN KEY (product_id) REFERENCES Products(product_id)
);

CREATE TABLE IF NOT EXISTS Payment(
    pay_id INT PRIMARY KEY AUTO_INCREMENT,
    order_id INT,
    pay_method VARCHAR(100),

    FOREIGN KEY (order_id) REFERENCES Orders(order_id)
);

INSERT INTO Roles (role_name) VALUES
("admin"),
("manager"),
("client");

INSERT INTO Users (username, passw, last_name, first_name, patronymic, role_id) VALUES
("admin", "admin", "Абакаров", "Магомед", "Камильевич", 1),
("manager", "manager", "Михаш", "Михаил", "Романович", 2),
("client", "client", "Пучков", "Максим", "Ильич", 3);

INSERT INTO Status (status_id, name) VALUES
(1, 'Новый'),
(2, 'В обработке'),
(3, 'Выдан'),
(4, 'Отменён');
INSERT INTO Categories (name) VALUES
("Туфли"),
("Кроссовки"),
("Сапоги");

INSERT INTO Manufacturers (name) VALUES
("Palermo"),
("Adidas"),
("ECCO");

INSERT INTO Suppliers (name) VALUES
("Италия"),
("Германия"),
("США");

INSERT INTO Products (name, category_id, manufacture_id, supplier_id, price, quantity, discount, image_path) VALUES
("Palermo White", 1, 1, 1, 13000.00, 5, 8.00, "images/palermo.jpg"),
("Adidas Black Row", 2, 2, 2, 7800.00, 12, 0.00, "images/black_row.jpg"),
("ECCO Winter", 3, 3, 3, 35000.00, 1, 35.00, "images/ecco.jpg");