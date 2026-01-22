import sys
import mysql.connector

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTabWidget, QTableWidget, QTableWidgetItem,
    QPushButton, QFileDialog, QMessageBox
)
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrinter


# =========================
# KONFIG DB (ubah sesuai XAMPP kamu)
# =========================
DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "",     # isi kalau root kamu pakai password
    "database": "ojol",
    "port": 3306
}


def get_conn():
    return mysql.connector.connect(**DB_CONFIG)


def fetch_all(query: str, params=None):
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(query, params or ())
        return cur.fetchall()
    finally:
        conn.close()


def html_escape(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


class ReportTab(QWidget):
    def __init__(self, title: str, query: str):
        super().__init__()
        self.title = title
        self.query = query

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)

        self.btnRefresh = QPushButton("Refresh")
        self.btnExport = QPushButton("Export PDF")

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(self.btnRefresh)
        btn_row.addWidget(self.btnExport)

        layout = QVBoxLayout(self)
        layout.addLayout(btn_row)
        layout.addWidget(self.table)

        self.btnRefresh.clicked.connect(self.load_data)
        self.btnExport.clicked.connect(self.export_pdf)

        self.load_data()

    def load_data(self):
        try:
            rows = fetch_all(self.query)
        except Exception as e:
            QMessageBox.critical(self, "DB Error", f"Gagal mengambil data:\n{e}")
            return

        if not rows:
            self.table.clear()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return

        headers = list(rows[0].keys())
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(rows))

        for r, row in enumerate(rows):
            for c, h in enumerate(headers):
                val = row.get(h, "")
                item = QTableWidgetItem("" if val is None else str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, c, item)

        self.table.resizeColumnsToContents()

    def export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Simpan PDF", f"{self.title}.pdf", "PDF Files (*.pdf)"
        )
        if not path:
            return

        # ambil data dari table widget
        col_count = self.table.columnCount()
        row_count = self.table.rowCount()
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(col_count)]

        # buat HTML
        html = []
        html.append(f"<h2>{html_escape(self.title)}</h2>")
        html.append("<table border='1' cellspacing='0' cellpadding='4'>")
        html.append("<tr>")
        for h in headers:
            html.append(f"<th>{html_escape(h)}</th>")
        html.append("</tr>")

        for r in range(row_count):
            html.append("<tr>")
            for c in range(col_count):
                it = self.table.item(r, c)
                html.append(f"<td>{html_escape(it.text() if it else '')}</td>")
            html.append("</tr>")

        html.append("</table>")
        html_str = "\n".join(html)

        try:
            doc = QTextDocument()
            doc.setHtml(html_str)

            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(path)

            doc.print_(printer)
            QMessageBox.information(self, "Sukses", f"PDF tersimpan:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal export PDF:\n{e}")


class DashboardReport(QMainWindow):
    """
    Dashboard report dengan 10 tab (7–12 report terpenuhi).
    """

    def refresh_all(self):
        # refresh semua tab
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if hasattr(tab, "load_data"):
                tab.load_data()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dashboard")

        root = QWidget()
        self.setCentralWidget(root)

        main_layout = QVBoxLayout(root)

        # Judul atas: "Dashboard" hitam tengah
        title = QLabel("Dashboard")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: 800; color: black;")
        main_layout.addWidget(title)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # =========================
        # 10 REPORT QUERIES (sesuai DB ojol)
        # =========================
        reports = [
            ("1. Data Users", """
                SELECT user_id, nama, email, no_hp
                FROM users
                ORDER BY user_id;
            """),

            ("2. Data Admin", """
                SELECT admin_id, nama, email, no_hp
                FROM admin
                ORDER BY admin_id;
            """),

            ("3. Data Drivers", """
                SELECT d.driver_id,
                       d.user_id,
                       u.nama AS nama_driver,
                       u.no_hp AS hp_driver,
                       d.plat_nomor,
                       d.jenis_motor
                FROM drivers d
                JOIN users u ON u.user_id = d.user_id
                ORDER BY d.driver_id;
            """),

            ("4. Data Pesanan", """
                SELECT pesanan_id, pelanggan_id, driver_id, titik_awal, titik_tujuan, jarak, biaya
                FROM orders
                ORDER BY pesanan_id DESC;
            """),

            ("5. Data Pembayaran", """
                SELECT payment_id, pesanan_id, metode, jumlah
                FROM payments
                ORDER BY payment_id DESC;
            """),

            ("6. Detail Pesanan", """
                SELECT o.pesanan_id,
                       u_pel.nama AS pelanggan,
                       u_drv.nama AS driver,
                       o.titik_awal,
                       o.titik_tujuan,
                       o.jarak,
                       o.biaya
                FROM orders o
                JOIN users u_pel ON u_pel.user_id = o.pelanggan_id
                JOIN drivers d ON d.driver_id = o.driver_id
                JOIN users u_drv ON u_drv.user_id = d.user_id
                ORDER BY o.pesanan_id DESC;
            """),

            ("7. Detail Pembayaran", """
                SELECT p.payment_id,
                       p.pesanan_id,
                       u_pel.nama AS pelanggan,
                       u_drv.nama AS driver,
                       p.metode,
                       p.jumlah
                FROM payments p
                JOIN orders o ON o.pesanan_id = p.pesanan_id
                JOIN users u_pel ON u_pel.user_id = o.pelanggan_id
                JOIN drivers d ON d.driver_id = o.driver_id
                JOIN users u_drv ON u_drv.user_id = d.user_id
                ORDER BY p.payment_id DESC;
            """),

            ("8. Pesanan Belum Dibayar", """
                SELECT o.pesanan_id,
                       u_pel.nama AS pelanggan,
                       u_drv.nama AS driver,
                       o.biaya
                FROM orders o
                JOIN users u_pel ON u_pel.user_id = o.pelanggan_id
                JOIN drivers d ON d.driver_id = o.driver_id
                JOIN users u_drv ON u_drv.user_id = d.user_id
                LEFT JOIN payments p ON p.pesanan_id = o.pesanan_id
                WHERE p.payment_id IS NULL
                ORDER BY o.pesanan_id DESC;
            """),

            ("9. Rekap Pesanan per Driver", """
                SELECT u_drv.nama AS driver,
                       COUNT(*) AS total_pesanan,
                       SUM(o.biaya) AS total_biaya
                FROM orders o
                JOIN drivers d ON d.driver_id = o.driver_id
                JOIN users u_drv ON u_drv.user_id = d.user_id
                GROUP BY u_drv.nama
                ORDER BY total_pesanan DESC;
            """),

            ("10. Rekap Pembayaran per Metode", """
                SELECT metode,
                       COUNT(*) AS jumlah_transaksi,
                       SUM(jumlah) AS total_pembayaran
                FROM payments
                GROUP BY metode
                ORDER BY total_pembayaran DESC;
            """),
        ]

        for tab_title, q in reports:
            tab = ReportTab(tab_title, q)
            self.tabs.addTab(tab, tab_title)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = DashboardReport()
    w.resize(1100, 650)
    w.show()
    sys.exit(app.exec())
