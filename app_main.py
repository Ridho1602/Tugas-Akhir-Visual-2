import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QPushButton, QStackedWidget, QLabel
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, Qt

from report_dashboard import DashboardReport
from crud_pages import UsersPage, DriversPage, AdminPage, OrdersPage, PaymentsPage


def load_ui(path: str, parent=None):
    loader = QUiLoader()
    f = QFile(path)
    if not f.open(QFile.ReadOnly):
        raise RuntimeError(f"Gagal buka UI: {path}")
    w = loader.load(f, parent)
    f.close()
    if w is None:
        raise RuntimeError(f"Gagal load UI: {path}")
    return w


class AppWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Load dashboard shell
        root = load_ui("Dashboard_form.ui", self)
        self.setCentralWidget(root)
        self.setWindowTitle("Aplikasi Ojek Online")

        # ambil komponen wajib
        self.stacked: QStackedWidget = root.findChild(QStackedWidget, "stackedWidget")
        self.titleLabel: QLabel = root.findChild(QLabel, "label")

        if not self.stacked or not self.titleLabel:
            raise RuntimeError("Dashboard_form.ui harus punya objectName: stackedWidget dan label")

        # tombol sidebar utama (dashboard)
        self.btnUser = root.findChild(QPushButton, "btnUser")
        self.btnDriver = root.findChild(QPushButton, "btnDriver")
        self.btnAdmin = root.findChild(QPushButton, "btnAdmin")
        self.btnPembayaran = root.findChild(QPushButton, "btnPembayaran")
        self.btnPesanan = root.findChild(QPushButton, "btnPesanan")
        self.btnReport = root.findChild(QPushButton, "btnReport")  # tombol report HITAM (di luar)

        missing = [n for n, b in [
            ("btnUser", self.btnUser),
            ("btnDriver", self.btnDriver),
            ("btnAdmin", self.btnAdmin),
            ("btnPembayaran", self.btnPembayaran),
            ("btnPesanan", self.btnPesanan),
            ("btnReport", self.btnReport),
        ] if b is None]
        if missing:
            raise RuntimeError(f"Dashboard_form.ui kurang tombol: {', '.join(missing)}")

        # kosongkan halaman default dari designer
        while self.stacked.count():
            w = self.stacked.widget(0)
            self.stacked.removeWidget(w)
            w.deleteLater()

        # halaman-halaman
        self.pageReport = DashboardReport()

        self.pageUsers = UsersPage()
        self.pageDrivers = DriversPage()
        self.pageAdmin = AdminPage()
        self.pageOrders = OrdersPage()
        self.pagePayments = PaymentsPage()

        # tambahkan ke stacked
        self.pages = {
            "Report": self.pageReport,
            "User": self.pageUsers,
            "Driver": self.pageDrivers,
            "Admin": self.pageAdmin,
            "Pesanan": self.pageOrders,
            "Pembayaran": self.pagePayments,
        }
        for name in ["Report", "User", "Driver", "Admin", "Pembayaran", "Pesanan"]:
            self.stacked.addWidget(self.pages[name])

        # hubungkan sidebar utama
        self.btnUser.clicked.connect(lambda: self.show_page("User"))
        self.btnDriver.clicked.connect(lambda: self.show_page("Driver"))
        self.btnAdmin.clicked.connect(lambda: self.show_page("Admin"))
        self.btnPembayaran.clicked.connect(lambda: self.show_page("Pembayaran"))
        self.btnPesanan.clicked.connect(lambda: self.show_page("Pesanan"))
        self.btnReport.clicked.connect(lambda: self.show_page("Report"))  # INI yang dipakai

        # tampilkan report dulu
        self.show_page("Report")

    def show_page(self, name: str):
        w = self.pages.get(name)
        if not w:
            return
        self.stacked.setCurrentWidget(w)
        self.titleLabel.setText(name)

        # kalau masuk report, auto refresh biar update
        if name == "Report":
            try:
                self.pageReport.refresh_all()
            except Exception as e:
                QMessageBox.warning(self, "Warning", f"Gagal refresh report:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = AppWindow()
    win.show()
    sys.exit(app.exec())
