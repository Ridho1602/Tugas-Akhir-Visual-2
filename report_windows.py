import sys
import pandas as pd
import mysql.connector

from PySide6.QtCore import Qt, QAbstractTableModel
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTabWidget, QTableView, QFileDialog, QMessageBox, QLabel
)
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtGui import QTextDocument

DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "",
    "database": "ojol",
    "port": 3306
}

def fetch_df(query: str, params=None) -> pd.DataFrame:
    conn = mysql.connector.connect(**DB_CONFIG)
    try:
        return pd.read_sql(query, conn, params=params)
    finally:
        conn.close()

class DataFrameModel(QAbstractTableModel):
    def __init__(self, df=pd.DataFrame()):
        super().__init__()
        self._df = df.copy()

    def set_df(self, df: pd.DataFrame):
        self.beginResetModel()
        self._df = df.copy()
        self.endResetModel()

    def rowCount(self, parent=None):
        return 0 if self._df is None else len(self._df.index)

    def columnCount(self, parent=None):
        return 0 if self._df is None else len(self._df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or self._df is None:
            return None
        if role == Qt.DisplayRole:
            val = self._df.iat[index.row(), index.column()]
            return "" if pd.isna(val) else str(val)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if self._df is None:
            return None
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._df.columns[section])
            return str(section + 1)
        return None

def df_to_html(title: str, df: pd.DataFrame) -> str:
    table_html = df.to_html(index=False, border=1)
    return f"""
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: Arial, sans-serif; font-size: 10pt; }}
        h2 {{ margin-bottom: 10px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ padding: 6px; }}
        th {{ background: #f2f2f2; }}
      </style>
    </head>
    <body>
      <h2>{title}</h2>
      {table_html}
    </body>
    </html>
    """

class ReportTab(QWidget):
    def __init__(self, title: str, query: str):
        super().__init__()
        self.title = title
        self.query = query
        self.df = pd.DataFrame()
        self.model = DataFrameModel(self.df)

        self.view = QTableView()
        self.view.setModel(self.model)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_pdf = QPushButton("Export PDF")

        top = QHBoxLayout()
        top.addWidget(QLabel(title))
        top.addStretch()
        top.addWidget(self.btn_refresh)
        top.addWidget(self.btn_pdf)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.view)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_pdf.clicked.connect(self.export_pdf)

        self.refresh()

    def refresh(self):
        try:
            self.df = fetch_df(self.query)
            self.model.set_df(self.df)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal load report:\n{e}")

    def export_pdf(self):
        if self.df is None or self.df.empty:
            QMessageBox.information(self, "Info", "Data kosong, tidak bisa export.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Simpan PDF", f"{self.title}.pdf", "PDF Files (*.pdf)")
        if not path:
            return

        try:
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(path)

            doc = QTextDocument()
            doc.setHtml(df_to_html(self.title, self.df))
            doc.print_(printer)

            QMessageBox.information(self, "Sukses", f"Berhasil export PDF:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal export PDF:\n{e}")

class ReportsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Reports - Aplikasi Ojek Online")
        self.resize(1100, 650)

        self.tabs = QTabWidget()
        self.report_tabs = []

        reports = [
            ("Report 1 - Data Users", "SELECT user_id, nama, email, no_hp FROM users ORDER BY user_id;"),
            ("Report 2 - Data Admin", "SELECT admin_id, nama, email, no_hp FROM admin ORDER BY admin_id;"),
            ("Report 3 - Data Drivers", """
                SELECT d.driver_id, d.user_id, u.nama AS nama_driver, u.no_hp AS hp_driver, d.plat_nomor, d.jenis_motor
                FROM drivers d JOIN users u ON u.user_id=d.user_id
                ORDER BY d.driver_id;
            """),
            ("Report 4 - Detail Pesanan", """
                SELECT o.pesanan_id, p.nama AS pelanggan, u.nama AS driver,
                       o.titik_awal, o.titik_tujuan, o.jarak, o.biaya
                FROM orders o
                JOIN users p ON p.user_id=o.pelanggan_id
                JOIN drivers d ON d.driver_id=o.driver_id
                JOIN users u ON u.user_id=d.user_id
                ORDER BY o.pesanan_id DESC;
            """),
            ("Report 5 - Detail Pembayaran", """
                SELECT pay.payment_id, pay.pesanan_id, p.nama AS pelanggan, u.nama AS driver,
                       pay.metode, pay.jumlah
                FROM payments pay
                JOIN orders o ON o.pesanan_id=pay.pesanan_id
                JOIN users p ON p.user_id=o.pelanggan_id
                JOIN drivers d ON d.driver_id=o.driver_id
                JOIN users u ON u.user_id=d.user_id
                ORDER BY pay.payment_id DESC;
            """),
        ]

        for title, query in reports:
            tab = ReportTab(title, query)
            self.report_tabs.append(tab)
            self.tabs.addTab(tab, title.split(" - ")[0])

        root = QWidget()
        lay = QVBoxLayout(root)
        lay.addWidget(self.tabs)
        self.setCentralWidget(root)

    def refresh_all(self):
        for t in self.report_tabs:
            t.refresh()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = ReportsWindow()
    w.show()
    sys.exit(app.exec())
