# crud_widget.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QAbstractTableModel
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableView,
    QMessageBox, QDialog, QFormLayout, QLineEdit, QDialogButtonBox,
    QSpacerItem, QSizePolicy, QLabel
)

from db import get_conn


@dataclass
class ColumnInfo:
    name: str
    is_pk: bool
    is_auto: bool
    nullable: bool
    col_type: str


def _fetch_columns(table: str) -> List[ColumnInfo]:
    conn = get_conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(f"SHOW COLUMNS FROM `{table}`")
        rows = cur.fetchall()

        cols: List[ColumnInfo] = []
        for r in rows:
            name = r["Field"]
            key = r["Key"]  # PRI
            extra = r["Extra"]  # auto_increment
            null = r["Null"]  # YES/NO
            ctype = r["Type"]

            cols.append(
                ColumnInfo(
                    name=name,
                    is_pk=(key == "PRI"),
                    is_auto=("auto_increment" in (extra or "")),
                    nullable=(null == "YES"),
                    col_type=ctype,
                )
            )
        return cols
    finally:
        conn.close()


def _fetch_all(table: str) -> Tuple[List[str], List[List[Any]]]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM `{table}`")
        rows = cur.fetchall()
        headers = [d[0] for d in cur.description]
        return headers, [list(r) for r in rows]
    finally:
        conn.close()


class TableModel(QAbstractTableModel):
    def __init__(self, headers: List[str], data: List[List[Any]]):
        super().__init__()
        self.headers = headers
        self.data_rows = data

    def rowCount(self, parent=None):
        return len(self.data_rows)

    def columnCount(self, parent=None):
        return len(self.headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            v = self.data_rows[index.row()][index.column()]
            return "" if v is None else str(v)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self.headers[section]
        return str(section + 1)


class RecordDialog(QDialog):
    """
    Dialog input generik.
    - Saat add: isi semua kolom kecuali auto_increment PK
    - Saat edit: isi semua kolom kecuali auto_increment PK, nilai awal dari row
    """
    def __init__(self, title: str, columns: List[ColumnInfo], initial: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.setWindowTitle(title)
        self.columns = columns
        self.initial = initial or {}
        self.inputs: Dict[str, QLineEdit] = {}

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        hint = QLabel("Kosongkan jika NULL (untuk kolom yang boleh NULL).")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        for col in self.columns:
            if col.is_auto:
                continue
            le = QLineEdit()
            le.setPlaceholderText(col.col_type)
            if col.name in self.initial and self.initial[col.name] is not None:
                le.setText(str(self.initial[col.name]))
            self.inputs[col.name] = le
            form.addRow(col.name, le)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_values(self) -> Dict[str, Any]:
        vals: Dict[str, Any] = {}
        for name, le in self.inputs.items():
            txt = le.text().strip()
            vals[name] = None if txt == "" else txt
        return vals


class CrudWidget(QWidget):
    def __init__(self, table: str, title: str, on_report=None):
        super().__init__()
        self.table = table
        self.title = title
        self.on_report = on_report

        self.columns = _fetch_columns(table)
        self.pk_col = next((c for c in self.columns if c.is_pk), None)

        root = QVBoxLayout(self)

        # Header row (judul + tombol)
        top = QHBoxLayout()
        top.addWidget(QLabel(f"<b>{self.title}</b>"))
        top.addStretch()

        self.btnTambah = QPushButton("Tambah")
        self.btnEdit = QPushButton("Edit")
        self.btnHapus = QPushButton("Hapus")
        self.btnRefresh = QPushButton("Refresh")

        top.addWidget(self.btnTambah)
        top.addWidget(self.btnEdit)
        top.addWidget(self.btnHapus)
        top.addWidget(self.btnRefresh)

        root.addLayout(top)

        self.tableView = QTableView()
        self.tableView.setSelectionBehavior(QTableView.SelectRows)
        self.tableView.setSelectionMode(QTableView.SingleSelection)
        root.addWidget(self.tableView)

        # Bottom bar: Report di kanan bawah
        bottom = QHBoxLayout()
        bottom.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.btnReport = QPushButton("Report")
        bottom.addWidget(self.btnReport)
        root.addLayout(bottom)

        # Wire
        self.btnRefresh.clicked.connect(self.refresh)
        self.btnTambah.clicked.connect(self.add_row)
        self.btnEdit.clicked.connect(self.edit_row)
        self.btnHapus.clicked.connect(self.delete_row)
        self.btnReport.clicked.connect(self._open_report)

        self.refresh()

    def _open_report(self):
        if callable(self.on_report):
            self.on_report()

    def refresh(self):
        headers, data = _fetch_all(self.table)
        self.model = TableModel(headers, data)
        self.tableView.setModel(self.model)
        self.tableView.resizeColumnsToContents()

    def _current_row_dict(self) -> Optional[Dict[str, Any]]:
        idx = self.tableView.currentIndex()
        if not idx.isValid():
            return None
        row = idx.row()
        d = {}
        for c, name in enumerate(self.model.headers):
            d[name] = self.model.data_rows[row][c]
        return d

    def add_row(self):
        dlg = RecordDialog(f"Tambah {self.title}", self.columns, initial=None)
        if dlg.exec() != QDialog.Accepted:
            return

        vals = dlg.get_values()
        cols = []
        ph = []
        params = []

        for col in self.columns:
            if col.is_auto:
                continue
            cols.append(f"`{col.name}`")
            ph.append("%s")
            params.append(vals.get(col.name))

        q = f"INSERT INTO `{self.table}` ({', '.join(cols)}) VALUES ({', '.join(ph)})"

        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(q, params)
            conn.commit()
            conn.close()
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal tambah data:\n{e}")

    def edit_row(self):
        if not self.pk_col:
            QMessageBox.warning(self, "Info", "Tabel ini tidak punya primary key. Edit otomatis tidak bisa.")
            return

        row = self._current_row_dict()
        if not row:
            QMessageBox.information(self, "Info", "Pilih 1 baris dulu.")
            return

        dlg = RecordDialog(f"Edit {self.title}", self.columns, initial=row)
        if dlg.exec() != QDialog.Accepted:
            return

        vals = dlg.get_values()

        set_parts = []
        params = []
        for col in self.columns:
            if col.is_pk or col.is_auto:
                continue
            set_parts.append(f"`{col.name}`=%s")
            params.append(vals.get(col.name))

        pk_val = row.get(self.pk_col.name)
        params.append(pk_val)

        q = f"UPDATE `{self.table}` SET {', '.join(set_parts)} WHERE `{self.pk_col.name}`=%s"

        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(q, params)
            conn.commit()
            conn.close()
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal edit data:\n{e}")

    def delete_row(self):
        if not self.pk_col:
            QMessageBox.warning(self, "Info", "Tabel ini tidak punya primary key. Hapus otomatis tidak bisa.")
            return

        row = self._current_row_dict()
        if not row:
            QMessageBox.information(self, "Info", "Pilih 1 baris dulu.")
            return

        pk_val = row.get(self.pk_col.name)

        ok = QMessageBox.question(
            self, "Konfirmasi",
            f"Yakin hapus data {self.title}?\n{self.pk_col.name}={pk_val}",
            QMessageBox.Yes | QMessageBox.No
        )
        if ok != QMessageBox.Yes:
            return

        q = f"DELETE FROM `{self.table}` WHERE `{self.pk_col.name}`=%s"

        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(q, (pk_val,))
            conn.commit()
            conn.close()
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal hapus data:\n{e}")

