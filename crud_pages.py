from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QDialog, QFormLayout,
    QLineEdit, QComboBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt

from db import select_rows, execute


# ---------- helpers FK ----------
def load_users_options():
    rows = select_rows("SELECT user_id, nama, no_hp FROM users ORDER BY user_id;")
    return [(r["user_id"], f'{r["user_id"]} - {r["nama"]} ({r["no_hp"]})') for r in rows]

def load_drivers_options():
    rows = select_rows("""
        SELECT d.driver_id, u.nama, u.no_hp, d.plat_nomor
        FROM drivers d
        JOIN users u ON u.user_id = d.user_id
        ORDER BY d.driver_id;
    """)
    return [(r["driver_id"], f'{r["driver_id"]} - {r["nama"]} ({r["no_hp"]}) | {r["plat_nomor"]}') for r in rows]

def load_orders_options():
    rows = select_rows("""
        SELECT o.pesanan_id, p.nama AS pelanggan, o.titik_awal, o.titik_tujuan, o.biaya
        FROM orders o
        JOIN users p ON p.user_id = o.pelanggan_id
        ORDER BY o.pesanan_id DESC;
    """)
    return [(r["pesanan_id"], f'{r["pesanan_id"]} - {r["pelanggan"]} | {r["titik_awal"]} -> {r["titik_tujuan"]} | Rp{r["biaya"]}') for r in rows]


# ---------- dialog input ----------
class RecordDialog(QDialog):
    """
    fields: list dict:
      - name, label
      - type: text | password | float | enum | fk
      - options: list untuk enum, atau list[(id,label)] untuk fk
    """
    def __init__(self, title, fields, initial=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.fields = fields
        self.initial = initial or {}
        self.widgets = {}

        form = QFormLayout(self)

        for f in fields:
            name = f["name"]
            ftype = f.get("type", "text")

            if ftype == "float":
                w = QDoubleSpinBox()
                w.setRange(0, 10**12)
                w.setDecimals(2)
                w.setValue(float(self.initial.get(name, 0) or 0))

            elif ftype == "enum":
                w = QComboBox()
                for opt in f.get("options", []):
                    w.addItem(opt)
                init_val = self.initial.get(name)
                if init_val in f.get("options", []):
                    w.setCurrentText(init_val)

            elif ftype == "fk":
                w = QComboBox()
                opts = f.get("options", [])
                for _id, _label in opts:
                    w.addItem(_label, _id)

                init_id = self.initial.get(name)
                if init_id is not None:
                    for i in range(w.count()):
                        if w.itemData(i) == int(init_id):
                            w.setCurrentIndex(i)
                            break

            else:
                w = QLineEdit()
                w.setText("" if self.initial.get(name) is None else str(self.initial.get(name)))
                if ftype == "password":
                    w.setEchoMode(QLineEdit.Password)

            self.widgets[name] = w
            form.addRow(f["label"], w)

        row = QHBoxLayout()
        self.btn_save = QPushButton("Simpan")
        self.btn_cancel = QPushButton("Batal")
        row.addStretch()
        row.addWidget(self.btn_save)
        row.addWidget(self.btn_cancel)
        form.addRow(row)

        self.btn_save.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

    def values(self):
        data = {}
        for f in self.fields:
            name = f["name"]
            ftype = f.get("type", "text")
            w = self.widgets[name]

            if ftype == "float":
                data[name] = float(w.value())
            elif ftype == "enum":
                data[name] = w.currentText()
            elif ftype == "fk":
                data[name] = int(w.currentData())
            else:
                data[name] = w.text().strip()
        return data


# ---------- base CRUD page ----------
class CrudPage(QWidget):
    """
    view_query: query tampil
    view_cols : kolom hasil query (kolom pertama wajib PK)
    table     : tabel target
    pk        : primary key
    form_fields: field dialog (tanpa pk)
    insert_cols/update_cols: kolom insert/update
    """
    def __init__(self, title, view_query, view_cols, table, pk,
                 form_fields, insert_cols, update_cols):
        super().__init__()
        self.title = title
        self.view_query = view_query
        self.view_cols = view_cols
        self.table_name = table
        self.pk = pk
        self.form_fields = form_fields
        self.insert_cols = insert_cols
        self.update_cols = update_cols

        self.tbl = QTableWidget()
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl.setSelectionMode(QTableWidget.SingleSelection)

        self.btn_add = QPushButton("Tambah")
        self.btn_edit = QPushButton("Edit")
        self.btn_del = QPushButton("Hapus")
        self.btn_refresh = QPushButton("Refresh")

        top = QHBoxLayout()
        top.addWidget(QLabel(title))
        top.addStretch()
        top.addWidget(self.btn_add)
        top.addWidget(self.btn_edit)
        top.addWidget(self.btn_del)
        top.addWidget(self.btn_refresh)

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.tbl)

        self.btn_refresh.clicked.connect(self.load_data)
        self.btn_add.clicked.connect(self.add_record)
        self.btn_edit.clicked.connect(self.edit_record)
        self.btn_del.clicked.connect(self.delete_record)

        self.load_data()

    def _refresh_fk(self):
        for f in self.form_fields:
            if f.get("type") == "fk":
                if f["name"] in ("user_id", "pelanggan_id"):
                    f["options"] = load_users_options()
                elif f["name"] == "driver_id":
                    f["options"] = load_drivers_options()
                elif f["name"] == "pesanan_id":
                    f["options"] = load_orders_options()

    def load_data(self):
        self._refresh_fk()
        try:
            rows = select_rows(self.view_query)
            self.tbl.setColumnCount(len(self.view_cols))
            self.tbl.setHorizontalHeaderLabels(self.view_cols)
            self.tbl.setRowCount(len(rows))

            for r_idx, r in enumerate(rows):
                for c_idx, col in enumerate(self.view_cols):
                    val = r.get(col)
                    self.tbl.setItem(r_idx, c_idx, QTableWidgetItem("" if val is None else str(val)))

            self.tbl.resizeColumnsToContents()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _selected_pk(self):
        row = self.tbl.currentRow()
        if row < 0:
            return None
        item = self.tbl.item(row, 0)
        return item.text() if item else None

    def _fetch_row_by_pk(self, pk_val):
        cols = [f["name"] for f in self.form_fields]
        sql = f"SELECT {', '.join([f'`{c}`' for c in cols])} FROM `{self.table_name}` WHERE `{self.pk}`=%s;"
        rows = select_rows(sql, (pk_val,))
        return rows[0] if rows else {}

    def add_record(self):
        try:
            dlg = RecordDialog(f"Tambah - {self.title}", self.form_fields, parent=self)
            if dlg.exec() != QDialog.Accepted:
                return
            data = dlg.values()

            cols = self.insert_cols
            placeholders = ", ".join(["%s"] * len(cols))
            col_sql = ", ".join([f"`{c}`" for c in cols])
            sql = f"INSERT INTO `{self.table_name}` ({col_sql}) VALUES ({placeholders});"
            execute(sql, tuple(data[c] for c in cols))

            self.load_data()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def edit_record(self):
        try:
            pk_val = self._selected_pk()
            if not pk_val:
                QMessageBox.information(self, "Info", "Pilih 1 baris dulu.")
                return

            initial = self._fetch_row_by_pk(pk_val)
            dlg = RecordDialog(f"Edit - {self.title}", self.form_fields, initial=initial, parent=self)
            if dlg.exec() != QDialog.Accepted:
                return
            data = dlg.values()

            sets = ", ".join([f"`{c}`=%s" for c in self.update_cols])
            sql = f"UPDATE `{self.table_name}` SET {sets} WHERE `{self.pk}`=%s;"
            execute(sql, tuple(data[c] for c in self.update_cols) + (pk_val,))

            self.load_data()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def delete_record(self):
        try:
            pk_val = self._selected_pk()
            if not pk_val:
                QMessageBox.information(self, "Info", "Pilih 1 baris dulu.")
                return

            if QMessageBox.question(self, "Konfirmasi", f"Hapus data {self.pk}={pk_val}?") != QMessageBox.Yes:
                return

            sql = f"DELETE FROM `{self.table_name}` WHERE `{self.pk}`=%s;"
            execute(sql, (pk_val,))
            self.load_data()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# ---------- concrete pages ----------
class UsersPage(CrudPage):
    def __init__(self):
        super().__init__(
            "Users",
            view_query="SELECT user_id, nama, email, no_hp, password FROM users ORDER BY user_id DESC;",
            view_cols=["user_id", "nama", "email", "no_hp", "password"],
            table="users",
            pk="user_id",
            form_fields=[
                {"name": "nama", "label": "Nama", "type": "text"},
                {"name": "email", "label": "Email", "type": "text"},
                {"name": "no_hp", "label": "No HP", "type": "text"},
                {"name": "password", "label": "Password", "type": "password"},
            ],
            insert_cols=["nama", "email", "no_hp", "password"],
            update_cols=["nama", "email", "no_hp", "password"],
        )

class DriversPage(CrudPage):
    def __init__(self):
        super().__init__(
            "Drivers",
            view_query="""
                SELECT d.driver_id, d.user_id, u.nama AS nama_driver, u.no_hp, d.plat_nomor, d.jenis_motor
                FROM drivers d
                JOIN users u ON u.user_id = d.user_id
                ORDER BY d.driver_id DESC;
            """,
            view_cols=["driver_id", "user_id", "nama_driver", "no_hp", "plat_nomor", "jenis_motor"],
            table="drivers",
            pk="driver_id",
            form_fields=[
                {"name": "user_id", "label": "Pilih User (Driver)", "type": "fk", "options": load_users_options()},
                {"name": "plat_nomor", "label": "Plat Nomor", "type": "text"},
                {"name": "jenis_motor", "label": "Jenis Motor", "type": "text"},
            ],
            insert_cols=["user_id", "plat_nomor", "jenis_motor"],
            update_cols=["user_id", "plat_nomor", "jenis_motor"],
        )

class AdminPage(CrudPage):
    def __init__(self):
        super().__init__(
            "Admin",
            view_query="SELECT admin_id, nama, email, no_hp, password FROM admin ORDER BY admin_id DESC;",
            view_cols=["admin_id", "nama", "email", "no_hp", "password"],
            table="admin",
            pk="admin_id",
            form_fields=[
                {"name": "nama", "label": "Nama", "type": "text"},
                {"name": "email", "label": "Email", "type": "text"},
                {"name": "no_hp", "label": "No HP", "type": "text"},
                {"name": "password", "label": "Password", "type": "password"},
            ],
            insert_cols=["nama", "email", "no_hp", "password"],
            update_cols=["nama", "email", "no_hp", "password"],
        )

class OrdersPage(CrudPage):
    def __init__(self):
        super().__init__(
            "Pesanan",
            view_query="""
                SELECT o.pesanan_id,
                       o.pelanggan_id,
                       p.nama AS pelanggan,
                       o.driver_id,
                       u.nama AS driver,
                       o.titik_awal,
                       o.titik_tujuan,
                       o.jarak,
                       o.biaya
                FROM orders o
                JOIN users p ON p.user_id = o.pelanggan_id
                JOIN drivers d ON d.driver_id = o.driver_id
                JOIN users u ON u.user_id = d.user_id
                ORDER BY o.pesanan_id DESC;
            """,
            view_cols=["pesanan_id", "pelanggan_id", "pelanggan", "driver_id", "driver", "titik_awal", "titik_tujuan", "jarak", "biaya"],
            table="orders",
            pk="pesanan_id",
            form_fields=[
                {"name": "pelanggan_id", "label": "Pilih Pelanggan", "type": "fk", "options": load_users_options()},
                {"name": "driver_id", "label": "Pilih Driver", "type": "fk", "options": load_drivers_options()},
                {"name": "titik_awal", "label": "Titik Awal", "type": "text"},
                {"name": "titik_tujuan", "label": "Titik Tujuan", "type": "text"},
                {"name": "jarak", "label": "Jarak (KM)", "type": "float"},
                {"name": "biaya", "label": "Biaya", "type": "float"},
            ],
            insert_cols=["pelanggan_id", "driver_id", "titik_awal", "titik_tujuan", "jarak", "biaya"],
            update_cols=["pelanggan_id", "driver_id", "titik_awal", "titik_tujuan", "jarak", "biaya"],
        )

class PaymentsPage(CrudPage):
    def __init__(self):
        super().__init__(
            "Pembayaran",
            view_query="""
                SELECT pay.payment_id,
                       pay.pesanan_id,
                       p.nama AS pelanggan,
                       u.nama AS driver,
                       pay.metode,
                       pay.jumlah
                FROM payments pay
                JOIN orders o ON o.pesanan_id = pay.pesanan_id
                JOIN users p ON p.user_id = o.pelanggan_id
                JOIN drivers d ON d.driver_id = o.driver_id
                JOIN users u ON u.user_id = d.user_id
                ORDER BY pay.payment_id DESC;
            """,
            view_cols=["payment_id", "pesanan_id", "pelanggan", "driver", "metode", "jumlah"],
            table="payments",
            pk="payment_id",
            form_fields=[
                {"name": "pesanan_id", "label": "Pilih Pesanan", "type": "fk", "options": load_orders_options()},
                {"name": "metode", "label": "Metode", "type": "enum", "options": ["cash", "e-wallet", "kartu"]},
                {"name": "jumlah", "label": "Jumlah", "type": "float"},
            ],
            insert_cols=["pesanan_id", "metode", "jumlah"],
            update_cols=["pesanan_id", "metode", "jumlah"],
        )
