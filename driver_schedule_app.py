import sys
import os
import firebase_admin
from firebase_admin import credentials, firestore
from PyQt6 import QtWidgets, QtGui
from PyQt6.QtCore import Qt, QDate, QDateTime, QTimer
from datetime import datetime
import pytz
from PyQt6.QtGui import QAction

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)

# Initialize Firebase Admin
if not firebase_admin._apps:
    cred_path = resource_path('firebase-adminsdk.json')
    if not os.path.exists(cred_path):
        raise FileNotFoundError("You need to download your Firebase service account JSON key and name it 'firebase-adminsdk.json' in the same folder.")
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Global Constants
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_ABBREVS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
INSPECTION_WEEKS = ["Week 1", "Week 2"]
STATUSES = ["Lease", "Employee"]
LEASE_TYPES = ["Single", "Per Mile"]
VEHICLE_TYPES = ["Regular", "Spare", "Loaner", "Available", "Retired", "Custom"]
CURRENT_DATE = QDate(2025, 4, 4)
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
HOURS = [f"{hour:02d}:00" for hour in range(24)]
YEARS = [str(year) for year in range(2025, 2036)]

###############################################################################
# Hourly Supply Settings Dialog
###############################################################################
class HourlySupplySettingsDialog(QtWidgets.QDialog):
    def __init__(self, current_thresholds, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Hourly Supply Settings")
        self.resize(800, 600)
        self.current_thresholds = current_thresholds.copy()
        self.spin_boxes = {}
        
        main_layout = QtWidgets.QVBoxLayout()
        self.tabs = QtWidgets.QTabWidget()
        for day in DAYS:
            day_widget = QtWidgets.QWidget()
            grid_layout = QtWidgets.QGridLayout()
            for hour in range(24):
                row = (hour // 6) * 2
                col = hour % 6
                hour_label = QtWidgets.QLabel(f"{hour:02d}:00")
                hour_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                spin = QtWidgets.QSpinBox()
                spin.setRange(0, 100)
                default_value = self.current_thresholds.get((day, hour), 3 if 6 <= hour <= 18 else 1)
                spin.setValue(default_value)
                self.spin_boxes[(day, hour)] = spin
                grid_layout.addWidget(hour_label, row, col, alignment=Qt.AlignmentFlag.AlignCenter)
                grid_layout.addWidget(spin, row + 1, col)
            day_widget.setLayout(grid_layout)
            self.tabs.addTab(day_widget, day)
        main_layout.addWidget(self.tabs)
        
        button_layout = QtWidgets.QHBoxLayout()
        copy_button = QtWidgets.QPushButton("Copy Monday to All Days")
        copy_button.clicked.connect(self.copyMonday)
        reset_button = QtWidgets.QPushButton("Reset Defaults")
        reset_button.clicked.connect(self.resetDefaults)
        save_button = QtWidgets.QPushButton("Save")
        save_button.clicked.connect(self.accept)
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(copy_button)
        button_layout.addWidget(reset_button)
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    def copyMonday(self):
        for day in DAYS[1:]:
            for hour in range(24):
                value = self.spin_boxes[("Monday", hour)].value()
                self.spin_boxes[(day, hour)].setValue(value)

    def resetDefaults(self):
        for day in DAYS:
            for hour in range(24):
                default = 3 if 6 <= hour <= 18 else 1
                self.spin_boxes[(day, hour)].setValue(default)

    def getThresholds(self):
        thresholds = {}
        for day in DAYS:
            for hour in range(24):
                thresholds[(day, hour)] = self.spin_boxes[(day, hour)].value()
        return thresholds

###############################################################################
# Edit Vehicle Dialog
###############################################################################
class EditVehicleDialog(QtWidgets.QDialog):
    def __init__(self, vehicle_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Vehicle")
        self.setGeometry(200, 200, 400, 550)
        self.layout = QtWidgets.QVBoxLayout()

        self.vehicle_number_input = QtWidgets.QLineEdit(vehicle_data.get("vehicle_number", ""))
        self.vehicle_number_input.setReadOnly(True)
        self.vehicle_type = QtWidgets.QComboBox()
        self.vehicle_type.addItems(VEHICLE_TYPES)
        idx = self.vehicle_type.findText(vehicle_data.get("vehicle_type", "Regular"))
        if idx != -1:
            self.vehicle_type.setCurrentIndex(idx)
        self.custom_vehicle_input = QtWidgets.QLineEdit()
        self.custom_vehicle_input.setVisible(self.vehicle_type.currentText() == "Custom")
        self.custom_vehicle_input.setText(vehicle_data.get("vehicle_type", "") if vehicle_data.get("vehicle_type") not in VEHICLE_TYPES else "")
        self.vehicle_type.currentTextChanged.connect(self.toggle_custom_input)
        self.year_input = QtWidgets.QSpinBox()
        self.year_input.setRange(1900, 2030)
        self.year_input.setValue(vehicle_data.get("year", 2025))
        self.make_input = QtWidgets.QLineEdit(vehicle_data.get("make", ""))
        self.model_input = QtWidgets.QLineEdit(vehicle_data.get("model", ""))
        self.color_input = QtWidgets.QLineEdit(vehicle_data.get("color", ""))
        self.title_number_input = QtWidgets.QLineEdit(vehicle_data.get("title_number", ""))
        self.license_number_input = QtWidgets.QLineEdit(vehicle_data.get("license_number", ""))
        self.vin_number_input = QtWidgets.QLineEdit(vehicle_data.get("vin_number", ""))

        self.plate_renewal_month = QtWidgets.QComboBox()
        self.plate_renewal_month.addItems(MONTHS)
        self.plate_renewal_year = QtWidgets.QComboBox()
        self.plate_renewal_year.addItems(YEARS)
        plate_renewal = vehicle_data.get("plate_renewal", "")
        if plate_renewal and " " in plate_renewal:
            month, year = plate_renewal.split(" ", 1)
            month_idx = MONTHS.index(month) if month in MONTHS else 0
            year_idx = YEARS.index(year) if year in YEARS else 0
            self.plate_renewal_month.setCurrentIndex(month_idx)
            self.plate_renewal_year.setCurrentIndex(year_idx)
        else:
            self.plate_renewal_month.setCurrentIndex(0)
            self.plate_renewal_year.setCurrentIndex(0)

        self.sts_expiration_date = QtWidgets.QDateEdit()
        self.sts_expiration_date.setCalendarPopup(True)
        sts_exp = vehicle_data.get("sts_expiration")
        if sts_exp and sts_exp != "Needs Adding":
            try:
                dt = datetime.strptime(sts_exp, "%m/%d/%Y")
                self.sts_expiration_date.setDate(QDate(dt.year, dt.month, dt.day))
            except Exception:
                self.sts_expiration_date.setDate(QDate(1900, 1, 1))
        else:
            self.sts_expiration_date.setDate(QDate(1900, 1, 1))
        self.sts_expiration_checkbox = QtWidgets.QCheckBox("Needs Adding")
        if not sts_exp or sts_exp == "Needs Adding":
            self.sts_expiration_checkbox.setChecked(True)
            self.sts_expiration_date.setEnabled(False)
        self.sts_expiration_checkbox.toggled.connect(lambda checked: self.sts_expiration_date.setEnabled(not checked))

        self.inspection_week = QtWidgets.QComboBox()
        self.inspection_week.addItems(INSPECTION_WEEKS)
        self.inspection_day = QtWidgets.QComboBox()
        self.inspection_day.addItems(DAYS)
        self.inspection_hour = QtWidgets.QComboBox()
        self.inspection_hour.addItems(HOURS)
        self.inspection_checkbox = QtWidgets.QCheckBox("Needs Adding")
        inspection = vehicle_data.get("inspection", "")
        if inspection and inspection != "Needs Adding" and " " in inspection:
            parts = inspection.split(" ", 2)
            if len(parts) == 3:
                week, day, hour = parts
                week_idx = INSPECTION_WEEKS.index(week) if week in INSPECTION_WEEKS else 0
                day_idx = DAYS.index(day) if day in DAYS else 0
                hour_idx = HOURS.index(hour) if hour in HOURS else 0
                self.inspection_week.setCurrentIndex(week_idx)
                self.inspection_day.setCurrentIndex(day_idx)
                self.inspection_hour.setCurrentIndex(hour_idx)
            else:
                self.inspection_week.setCurrentIndex(0)
                self.inspection_day.setCurrentIndex(0)
                self.inspection_hour.setCurrentIndex(0)
        else:
            self.inspection_checkbox.setChecked(True)
            self.inspection_week.setEnabled(False)
            self.inspection_day.setEnabled(False)
            self.inspection_hour.setEnabled(False)
        self.inspection_checkbox.toggled.connect(self.toggle_inspection_fields)

        self.assigned_driver = QtWidgets.QComboBox()
        self.assigned_driver.addItem("Unassign")
        drivers = db.collection("drivers").stream()
        driver_ids = [driver.to_dict().get("id", "") for driver in drivers]
        self.assigned_driver.addItems(driver_ids)
        current_driver = vehicle_data.get("assigned_driver", "Unassign")
        if current_driver and current_driver in driver_ids:
            self.assigned_driver.setCurrentText(current_driver)
        else:
            self.assigned_driver.setCurrentText("Unassign")

        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow("Vehicle Number:", self.vehicle_number_input)
        form_layout.addRow("Vehicle Type:", self.vehicle_type)
        form_layout.addRow("Custom Type:", self.custom_vehicle_input)
        form_layout.addRow("Year:", self.year_input)
        form_layout.addRow("Make:", self.make_input)
        form_layout.addRow("Model:", self.model_input)
        form_layout.addRow("Color:", self.color_input)
        form_layout.addRow("Title Number:", self.title_number_input)
        form_layout.addRow("License Number:", self.license_number_input)
        form_layout.addRow("VIN Number:", self.vin_number_input)
        plate_renewal_layout = QtWidgets.QHBoxLayout()
        plate_renewal_layout.addWidget(self.plate_renewal_month)
        plate_renewal_layout.addWidget(self.plate_renewal_year)
        form_layout.addRow("Plate Renewal:", plate_renewal_layout)
        hbox_sts = QtWidgets.QHBoxLayout()
        hbox_sts.addWidget(self.sts_expiration_date)
        hbox_sts.addWidget(self.sts_expiration_checkbox)
        form_layout.addRow("STS Expiration:", hbox_sts)
        hbox_insp = QtWidgets.QHBoxLayout()
        hbox_insp.addWidget(self.inspection_week)
        hbox_insp.addWidget(self.inspection_day)
        hbox_insp.addWidget(self.inspection_hour)
        hbox_insp.addWidget(self.inspection_checkbox)
        form_layout.addRow("Inspection:", hbox_insp)
        form_layout.addRow("Assigned Driver:", self.assigned_driver)

        self.layout.addLayout(form_layout)
        button_layout = QtWidgets.QHBoxLayout()
        save_button = QtWidgets.QPushButton("Save")
        save_button.clicked.connect(self.accept)
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        self.layout.addLayout(button_layout)
        self.setLayout(self.layout)

    def toggle_custom_input(self, text):
        self.custom_vehicle_input.setVisible(text == "Custom")
        if text != "Custom":
            self.custom_vehicle_input.clear()

    def toggle_inspection_fields(self, checked):
        self.inspection_week.setEnabled(not checked)
        self.inspection_day.setEnabled(not checked)
        self.inspection_hour.setEnabled(not checked)

    def get_vehicle_data(self):
        data = {}
        data["vehicle_number"] = self.vehicle_number_input.text().strip()
        vehicle_type = self.vehicle_type.currentText()
        if vehicle_type == "Custom":
            custom_type = self.custom_vehicle_input.text().strip()
            data["vehicle_type"] = custom_type if custom_type else "Custom"
        else:
            data["vehicle_type"] = vehicle_type
        data["year"] = self.year_input.value()
        data["make"] = self.make_input.text().strip()
        data["model"] = self.model_input.text().strip()
        data["color"] = self.color_input.text().strip()
        data["title_number"] = self.title_number_input.text().strip()
        data["license_number"] = self.license_number_input.text().strip()
        data["vin_number"] = self.vin_number_input.text().strip()
        data["plate_renewal"] = f"{self.plate_renewal_month.currentText()} {self.plate_renewal_year.currentText()}"
        if self.sts_expiration_checkbox.isChecked():
            data["sts_expiration"] = "Needs Adding"
        else:
            data["sts_expiration"] = self.sts_expiration_date.date().toString("MM/dd/yyyy")
        if self.inspection_checkbox.isChecked():
            data["inspection"] = "Needs Adding"
        else:
            data["inspection"] = f"{self.inspection_week.currentText()} {self.inspection_day.currentText()} {self.inspection_hour.currentText()}"
        assigned_driver = self.assigned_driver.currentText()
        data["assigned_driver"] = assigned_driver if assigned_driver != "Unassign" else None
        return data

###############################################################################
# Add Vehicle Dialog
###############################################################################
class AddVehicleDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Vehicle")
        self.setGeometry(200, 200, 400, 500)
        self.layout = QtWidgets.QVBoxLayout()

        self.vehicle_number_input = QtWidgets.QLineEdit()
        self.vehicle_type = QtWidgets.QComboBox()
        self.vehicle_type.addItems(VEHICLE_TYPES)
        self.custom_vehicle_input = QtWidgets.QLineEdit()
        self.custom_vehicle_input.setVisible(False)
        self.vehicle_type.currentTextChanged.connect(self.toggle_custom_input)
        self.year_input = QtWidgets.QSpinBox()
        self.year_input.setRange(1900, 2030)
        self.year_input.setValue(2025)
        self.make_input = QtWidgets.QLineEdit()
        self.model_input = QtWidgets.QLineEdit()
        self.color_input = QtWidgets.QLineEdit()
        self.title_number_input = QtWidgets.QLineEdit()
        self.license_number_input = QtWidgets.QLineEdit()
        self.vin_number_input = QtWidgets.QLineEdit()

        self.plate_renewal_month = QtWidgets.QComboBox()
        self.plate_renewal_month.addItems(MONTHS)
        self.plate_renewal_year = QtWidgets.QComboBox()
        self.plate_renewal_year.addItems(YEARS)
        self.plate_renewal_month.setCurrentIndex(0)
        self.plate_renewal_year.setCurrentIndex(0)

        self.sts_expiration_date = QtWidgets.QDateEdit()
        self.sts_expiration_date.setCalendarPopup(True)
        self.sts_expiration_date.setDate(QDate(1900, 1, 1))
        self.sts_expiration_checkbox = QtWidgets.QCheckBox("Needs Adding")
        self.sts_expiration_checkbox.setChecked(True)
        self.sts_expiration_date.setEnabled(False)
        self.sts_expiration_checkbox.toggled.connect(lambda checked: self.sts_expiration_date.setEnabled(not checked))

        self.inspection_week = QtWidgets.QComboBox()
        self.inspection_week.addItems(INSPECTION_WEEKS)
        self.inspection_day = QtWidgets.QComboBox()
        self.inspection_day.addItems(DAYS)
        self.inspection_hour = QtWidgets.QComboBox()
        self.inspection_hour.addItems(HOURS)
        self.inspection_checkbox = QtWidgets.QCheckBox("Needs Adding")
        self.inspection_checkbox.setChecked(True)
        self.inspection_week.setEnabled(False)
        self.inspection_day.setEnabled(False)
        self.inspection_hour.setEnabled(False)
        self.inspection_checkbox.toggled.connect(self.toggle_inspection_fields)

        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow("Vehicle Number:", self.vehicle_number_input)
        form_layout.addRow("Vehicle Type:", self.vehicle_type)
        form_layout.addRow("Custom Type:", self.custom_vehicle_input)
        form_layout.addRow("Year:", self.year_input)
        form_layout.addRow("Make:", self.make_input)
        form_layout.addRow("Model:", self.model_input)
        form_layout.addRow("Color:", self.color_input)
        form_layout.addRow("Title Number:", self.title_number_input)
        form_layout.addRow("License Number:", self.license_number_input)
        form_layout.addRow("VIN Number:", self.vin_number_input)
        plate_renewal_layout = QtWidgets.QHBoxLayout()
        plate_renewal_layout.addWidget(self.plate_renewal_month)
        plate_renewal_layout.addWidget(self.plate_renewal_year)
        form_layout.addRow("Plate Renewal:", plate_renewal_layout)
        hbox_sts = QtWidgets.QHBoxLayout()
        hbox_sts.addWidget(self.sts_expiration_date)
        hbox_sts.addWidget(self.sts_expiration_checkbox)
        form_layout.addRow("STS Expiration:", hbox_sts)
        hbox_insp = QtWidgets.QHBoxLayout()
        hbox_insp.addWidget(self.inspection_week)
        hbox_insp.addWidget(self.inspection_day)
        hbox_insp.addWidget(self.inspection_hour)
        hbox_insp.addWidget(self.inspection_checkbox)
        form_layout.addRow("Inspection:", hbox_insp)

        self.layout.addLayout(form_layout)

        button_layout = QtWidgets.QHBoxLayout()
        save_button = QtWidgets.QPushButton("Save")
        save_button.clicked.connect(self.accept)
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        self.layout.addLayout(button_layout)
        self.setLayout(self.layout)

    def toggle_custom_input(self, text):
        self.custom_vehicle_input.setVisible(text == "Custom")
        if text != "Custom":
            self.custom_vehicle_input.clear()

    def toggle_inspection_fields(self, checked):
        self.inspection_week.setEnabled(not checked)
        self.inspection_day.setEnabled(not checked)
        self.inspection_hour.setEnabled(not checked)

    def get_vehicle_data(self):
        data = {}
        data["vehicle_number"] = self.vehicle_number_input.text().strip()
        vehicle_type = self.vehicle_type.currentText()
        if vehicle_type == "Custom":
            custom_type = self.custom_vehicle_input.text().strip()
            data["vehicle_type"] = custom_type if custom_type else "Custom"
        else:
            data["vehicle_type"] = vehicle_type
        data["year"] = self.year_input.value()
        data["make"] = self.make_input.text().strip()
        data["model"] = self.model_input.text().strip()
        data["color"] = self.color_input.text().strip()
        data["title_number"] = self.title_number_input.text().strip()
        data["license_number"] = self.license_number_input.text().strip()
        data["vin_number"] = self.vin_number_input.text().strip()
        data["plate_renewal"] = f"{self.plate_renewal_month.currentText()} {self.plate_renewal_year.currentText()}"
        if self.sts_expiration_checkbox.isChecked():
            data["sts_expiration"] = "Needs Adding"
        else:
            data["sts_expiration"] = self.sts_expiration_date.date().toString("MM/dd/yyyy")
        if self.inspection_checkbox.isChecked():
            data["inspection"] = "Needs Adding"
        else:
            data["inspection"] = f"{self.inspection_week.currentText()} {self.inspection_day.currentText()} {self.inspection_hour.currentText()}"
        return data

###############################################################################
# Edit Driver Dialog
###############################################################################
class EditDriverDialog(QtWidgets.QDialog):
    def __init__(self, driver_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Driver")
        self.setGeometry(200, 200, 400, 500)
        self.layout = QtWidgets.QVBoxLayout()

        self.driver_id_input = QtWidgets.QLineEdit(driver_data.get("id", ""))
        self.driver_id_input.setReadOnly(True)
        self.driver_name_input = QtWidgets.QLineEdit(driver_data.get("name", ""))
        self.phone_number_input = QtWidgets.QLineEdit(driver_data.get("phone_number", ""))
        self.extra_driver_toggle = QtWidgets.QCheckBox("Extra/Part-Time Driver")
        self.extra_driver_toggle.setChecked(driver_data.get("driver_type") == "Extra")
        self.extra_driver_toggle.toggled.connect(self.toggle_extra_driver)

        self.start_hour_input = QtWidgets.QSpinBox()
        self.start_hour_input.setRange(0, 23)
        self.start_hour_input.setValue(driver_data.get("start", 0))
        self.end_hour_input = QtWidgets.QSpinBox()
        self.end_hour_input.setRange(0, 23)
        self.end_hour_input.setValue(driver_data.get("end", 0))
        self.day_buttons = {}
        days_layout = QtWidgets.QHBoxLayout()
        for day in DAYS:
            btn = QtWidgets.QPushButton(day)
            btn.setCheckable(True)
            btn.setChecked(day in driver_data.get("days", []))
            self.day_buttons[day] = btn
            days_layout.addWidget(btn)
        self.toggle_extra_driver(self.extra_driver_toggle.isChecked())

        self.vehicle_selector = QtWidgets.QComboBox()
        self.vehicle_selector.addItem("None")
        vehicles = db.collection("vehicles").stream()
        for vehicle in vehicles:
            self.vehicle_selector.addItem(vehicle.to_dict().get("vehicle_number", ""))
        current_vehicle = driver_data.get("vehicle_number", "None")
        self.vehicle_selector.setCurrentText(current_vehicle)

        self.status = QtWidgets.QComboBox()
        self.status.addItems(STATUSES)
        self.status.setCurrentText(driver_data.get("status", "Employee"))
        self.lease_type = QtWidgets.QComboBox()
        self.lease_type.addItems(LEASE_TYPES)
        self.lease_type.setCurrentText(driver_data.get("lease_type", "Single"))
        self.lease_type.setVisible(self.status.currentText() == "Lease")
        self.lease_type_label = QtWidgets.QLabel("Lease Type:")
        self.lease_type_label.setVisible(self.status.currentText() == "Lease")
        self.status.currentTextChanged.connect(self.toggle_lease_type)

        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow("Driver ID:", self.driver_id_input)
        form_layout.addRow("Driver Name:", self.driver_name_input)
        form_layout.addRow("Phone Number:", self.phone_number_input)
        form_layout.addRow("", self.extra_driver_toggle)
        shift_layout = QtWidgets.QHBoxLayout()
        shift_layout.addWidget(QtWidgets.QLabel("Start:"))
        shift_layout.addWidget(self.start_hour_input)
        shift_layout.addWidget(QtWidgets.QLabel("End:"))
        shift_layout.addWidget(self.end_hour_input)
        form_layout.addRow("Shift Hours:", shift_layout)
        form_layout.addRow("Working Days:", days_layout)
        form_layout.addRow("Assign Vehicle:", self.vehicle_selector)
        form_layout.addRow("Status:", self.status)
        form_layout.addRow(self.lease_type_label, self.lease_type)

        self.layout.addLayout(form_layout)
        button_layout = QtWidgets.QHBoxLayout()
        save_button = QtWidgets.QPushButton("Save")
        save_button.clicked.connect(self.accept)
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        self.layout.addLayout(button_layout)
        self.setLayout(self.layout)

    def toggle_extra_driver(self, checked):
        is_extra = checked
        self.start_hour_input.setEnabled(not is_extra)
        self.end_hour_input.setEnabled(not is_extra)
        for btn in self.day_buttons.values():
            btn.setEnabled(not is_extra)
            if is_extra:
                btn.setChecked(False)

    def toggle_lease_type(self, text):
        is_lease = (text == "Lease")
        self.lease_type_label.setVisible(is_lease)
        self.lease_type.setVisible(is_lease)

    def get_driver_data(self):
        data = {}
        data["id"] = self.driver_id_input.text().strip()
        data["name"] = self.driver_name_input.text().strip()
        data["phone_number"] = self.phone_number_input.text().strip()
        data["driver_type"] = "Extra" if self.extra_driver_toggle.isChecked() else "Regular"
        data["start"] = None if self.extra_driver_toggle.isChecked() else self.start_hour_input.value()
        data["end"] = None if self.extra_driver_toggle.isChecked() else self.end_hour_input.value()
        data["days"] = [] if self.extra_driver_toggle.isChecked() else [day for day, btn in self.day_buttons.items() if btn.isChecked()]
        vehicle_number = self.vehicle_selector.currentText()
        data["vehicle_number"] = vehicle_number if vehicle_number != "None" else None
        data["status"] = self.status.currentText()
        data["lease_type"] = self.lease_type.currentText() if data["status"] == "Lease" else None
        return data

###############################################################################
# Main Application: DriverScheduleApp
###############################################################################
class DriverScheduleApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Driver Schedule App")
        self.setGeometry(100, 100, 1200, 800)
        self.layout = QtWidgets.QVBoxLayout()
        self.hourly_thresholds = {}
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # Tab 0: Dashboard
        self.dashboard_tab = QtWidgets.QWidget()
        self.dashboard_layout = QtWidgets.QGridLayout()
        self.time_label = QtWidgets.QLabel()
        self.time_label.setFont(QtGui.QFont("Arial", 16, QtGui.QFont.Weight.Bold))
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.driver_count_label = QtWidgets.QLabel()
        self.driver_count_label.setFont(QtGui.QFont("Arial", 14))
        self.driver_count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.driver_list_table = QtWidgets.QTableWidget()
        self.driver_list_table.setColumnCount(4)
        self.driver_list_table.setHorizontalHeaderLabels(["Driver ID", "Shift Hours", "Days", "Phone Number"])
        self.driver_list_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.dashboard_layout.addWidget(self.time_label, 0, 0, 1, 2)
        self.dashboard_layout.addWidget(self.driver_count_label, 1, 0, 1, 2)
        self.dashboard_layout.addWidget(self.driver_list_table, 2, 0, 1, 2)
        self.dashboard_tab.setLayout(self.dashboard_layout)
        self.tabs.addTab(self.dashboard_tab, "Dashboard")

        # Timers for live clock and auto-update
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)  # Update every second
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.show_dashboard)
        self.update_timer.start(600000)  # Update every 10 minutes (600,000 ms)

        # Tab 1: Add Driver
        self.add_driver_tab = QtWidgets.QWidget()
        self.add_driver_layout = QtWidgets.QVBoxLayout()
        title_label = QtWidgets.QLabel("Add a New Driver")
        title_label.setFont(QtGui.QFont("Arial", 18, QtGui.QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.add_driver_layout.addWidget(title_label)
        form_widget = QtWidgets.QWidget()
        form_layout = QtWidgets.QGridLayout()
        self.driver_id_input = QtWidgets.QLineEdit()
        self.driver_name_input = QtWidgets.QLineEdit()
        self.phone_number_input = QtWidgets.QLineEdit()
        self.extra_driver_toggle = QtWidgets.QCheckBox("Extra/Part-Time Driver")
        self.extra_driver_toggle.stateChanged.connect(self.toggle_extra_driver)
        shift_layout = QtWidgets.QHBoxLayout()
        self.start_hour_input = QtWidgets.QSpinBox()
        self.start_hour_input.setRange(0, 23)
        self.end_hour_input = QtWidgets.QSpinBox()
        self.end_hour_input.setRange(0, 23)
        shift_layout.addWidget(QtWidgets.QLabel("Start:"))
        shift_layout.addWidget(self.start_hour_input)
        shift_layout.addWidget(QtWidgets.QLabel("End:"))
        shift_layout.addWidget(self.end_hour_input)
        self.day_buttons = {}
        days_layout = QtWidgets.QHBoxLayout()
        for day in DAYS:
            btn = QtWidgets.QPushButton(day)
            btn.setCheckable(True)
            self.day_buttons[day] = btn
            days_layout.addWidget(btn)
        self.vehicle_selector = QtWidgets.QComboBox()
        self.vehicle_selector.addItem("None")
        self.update_vehicle_selector()
        self.status = QtWidgets.QComboBox()
        self.status.addItems(STATUSES)
        self.lease_type = QtWidgets.QComboBox()
        self.lease_type.addItems(LEASE_TYPES)
        self.lease_type.setVisible(False)
        self.lease_type_label = QtWidgets.QLabel("Lease Type:")
        self.lease_type_label.setVisible(False)
        self.status.currentTextChanged.connect(self.toggle_lease_type)
        form_layout.addWidget(QtWidgets.QLabel("Driver ID:"), 0, 0)
        form_layout.addWidget(self.driver_id_input, 0, 1)
        form_layout.addWidget(QtWidgets.QLabel("Driver Name:"), 1, 0)
        form_layout.addWidget(self.driver_name_input, 1, 1)
        form_layout.addWidget(QtWidgets.QLabel("Phone Number:"), 2, 0)
        form_layout.addWidget(self.phone_number_input, 2, 1)
        form_layout.addWidget(self.extra_driver_toggle, 3, 0, 1, 2)
        form_layout.addWidget(QtWidgets.QLabel("Shift Hours:"), 4, 0)
        form_layout.addLayout(shift_layout, 4, 1)
        form_layout.addWidget(QtWidgets.QLabel("Working Days:"), 5, 0)
        form_layout.addLayout(days_layout, 5, 1)
        form_layout.addWidget(QtWidgets.QLabel("Assign Vehicle:"), 6, 0)
        form_layout.addWidget(self.vehicle_selector, 6, 1)
        form_layout.addWidget(QtWidgets.QLabel("Status:"), 7, 0)
        form_layout.addWidget(self.status, 7, 1)
        form_layout.addWidget(self.lease_type_label, 8, 0)
        form_layout.addWidget(self.lease_type, 8, 1)
        form_widget.setLayout(form_layout)
        self.add_driver_layout.addWidget(form_widget)
        self.add_button = QtWidgets.QPushButton("Add Driver")
        self.add_button.clicked.connect(self.add_driver)
        self.add_driver_layout.addWidget(self.add_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.add_driver_layout.addStretch()
        self.add_driver_tab.setLayout(self.add_driver_layout)
        self.tabs.addTab(self.add_driver_tab, "Add Driver")

        # Tab 2: Hourly Supply
        self.hourly_supply_tab = QtWidgets.QWidget()
        self.hourly_supply_layout = QtWidgets.QVBoxLayout()
        supply_controls_layout = QtWidgets.QHBoxLayout()
        self.settings_button = QtWidgets.QPushButton("Settings")
        self.settings_button.clicked.connect(self.open_supply_settings)
        supply_controls_layout.addWidget(self.settings_button)
        supply_controls_layout.addStretch()
        self.hourly_supply_layout.addLayout(supply_controls_layout)
        self.hourly_supply_table = QtWidgets.QTableWidget()
        self.hourly_supply_table.setRowCount(len(DAYS))
        self.hourly_supply_table.setColumnCount(24)
        self.hourly_supply_table.setHorizontalHeaderLabels([f"{hour:02d}:00" for hour in range(24)])
        self.hourly_supply_table.setVerticalHeaderLabels(DAYS)
        self.hourly_supply_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.hourly_supply_table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.hourly_supply_layout.addWidget(self.hourly_supply_table)
        self.hourly_supply_tab.setLayout(self.hourly_supply_layout)
        self.tabs.addTab(self.hourly_supply_tab, "Hourly Supply")

        # Tab 3: All Drivers
        self.all_drivers_tab = QtWidgets.QWidget()
        self.all_drivers_layout = QtWidgets.QVBoxLayout()
        filter_layout = QtWidgets.QHBoxLayout()
        self.filter_day = QtWidgets.QComboBox()
        self.filter_day.addItem("All Days")
        self.filter_day.addItems(DAYS)
        self.filter_day.currentTextChanged.connect(self.show_all_drivers)  # Auto-update on change
        self.filter_shift_hour = QtWidgets.QComboBox()
        self.filter_shift_hour.addItem("All Hours")
        for hour in range(24):
            self.filter_shift_hour.addItem(f"{hour:02d}:00")
        self.filter_shift_hour.currentTextChanged.connect(self.show_all_drivers)  # Auto-update on change
        self.sort_toggle = QtWidgets.QCheckBox("Sort Night to Midnight")
        self.sort_toggle.stateChanged.connect(self.show_all_drivers)  # Auto-update on change
        reset_filters_button = QtWidgets.QPushButton("Reset Filters")
        reset_filters_button.clicked.connect(self.reset_filters)
        filter_layout.addWidget(QtWidgets.QLabel("Filter by Day:"))
        filter_layout.addWidget(self.filter_day)
        filter_layout.addWidget(QtWidgets.QLabel("Shift Hour:"))
        filter_layout.addWidget(self.filter_shift_hour)
        filter_layout.addWidget(self.sort_toggle)
        filter_layout.addWidget(reset_filters_button)
        filter_layout.addStretch()
        self.all_drivers_table = QtWidgets.QTableWidget()
        self.all_drivers_table.setColumnCount(11)
        self.all_drivers_table.setHorizontalHeaderLabels([
            "ID", "Name", "Phone Number", "Driver Type", "Shift Start", "Shift End", "Days", 
            "Vehicle Number", "Status", "Lease Type", "Actions"
        ])
        self.all_drivers_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.all_drivers_layout.addLayout(filter_layout)
        self.all_drivers_layout.addWidget(self.all_drivers_table)
        self.all_drivers_tab.setLayout(self.all_drivers_layout)
        self.tabs.addTab(self.all_drivers_tab, "All Drivers")

        # Tab 4: Vehicles
        self.vehicles_tab = QtWidgets.QWidget()
        self.vehicles_layout = QtWidgets.QVBoxLayout()
        top_panel = QtWidgets.QHBoxLayout()
        self.add_vehicle_button = QtWidgets.QPushButton("Add Vehicle")
        self.add_vehicle_button.clicked.connect(self.open_add_vehicle_dialog)
        top_panel.addWidget(self.add_vehicle_button)
        top_panel.addStretch()
        self.vehicles_layout.addLayout(top_panel)
        self.assign_vehicle_driver = QtWidgets.QComboBox()
        self.assign_vehicle_driver.addItem("Select Driver")
        self.assign_vehicle_vehicle = QtWidgets.QComboBox()
        self.assign_vehicle_vehicle.addItem("Select Vehicle")
        self.assign_vehicle_button = QtWidgets.QPushButton("Assign Vehicle to Driver")
        self.assign_vehicle_button.clicked.connect(self.assign_vehicle)
        assign_layout = QtWidgets.QHBoxLayout()
        assign_layout.addWidget(self.assign_vehicle_driver)
        assign_layout.addWidget(self.assign_vehicle_vehicle)
        assign_layout.addWidget(self.assign_vehicle_button)
        self.vehicles_layout.addLayout(assign_layout)
        self.vehicles_table = QtWidgets.QTableWidget()
        self.vehicles_table.setColumnCount(15)
        self.vehicles_table.setHorizontalHeaderLabels([
            "Vehicle Number", "Vehicle Type", "Year", "Make", "Model", "Color", "Title Number",
            "License Number", "VIN Number", "Plate Renewal", "STS Expiration", "STS Status",
            "Inspection", "Assigned Driver", "Actions"
        ])
        self.vehicles_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.vehicles_layout.addWidget(self.vehicles_table)
        self.vehicles_tab.setLayout(self.vehicles_layout)
        self.tabs.addTab(self.vehicles_tab, "Vehicles")

        # Tab 5: Spares & Loaners
        self.spares_loaners_tab = QtWidgets.QWidget()
        self.spares_loaners_layout = QtWidgets.QVBoxLayout()
        self.spares_loaners_table = QtWidgets.QTableWidget()
        self.spares_loaners_table.setColumnCount(13)
        self.spares_loaners_table.setHorizontalHeaderLabels([
            "Vehicle Number", "Vehicle Type", "Year", "Make", "Model", "Color", "Title Number",
            "License Number", "VIN Number", "Plate Renewal", "STS Expiration", "STS Status", "Inspection"
        ])
        self.spares_loaners_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        assign_widget = QtWidgets.QWidget()
        assign_layout = QtWidgets.QVBoxLayout()
        self.assign_spare_driver = QtWidgets.QComboBox()
        self.assign_spare_driver.addItem("Select Driver")
        self.assign_spare_vehicle = QtWidgets.QComboBox()
        self.assign_spare_vehicle.addItem("Select Vehicle")
        self.update_spare_vehicle_selector()
        self.assign_time = QtWidgets.QDateTimeEdit()
        self.assign_time.setCalendarPopup(True)
        fargo_tz = pytz.timezone("America/Chicago")
        current_time = datetime.now(fargo_tz)
        self.assign_time.setDateTime(QDateTime(current_time.year, current_time.month, current_time.day, current_time.hour, current_time.minute))
        self.due_time = QtWidgets.QDateTimeEdit()
        self.due_time.setCalendarPopup(True)
        self.due_time.setDateTime(QDateTime(current_time.year, current_time.month, current_time.day, current_time.hour, current_time.minute))
        self.assigned_by = QtWidgets.QLineEdit()
        self.returned_keys = QtWidgets.QCheckBox("Returned Keys")
        self.returned_tablet = QtWidgets.QCheckBox("Returned Tablet/Phone")
        self.gas_filled = QtWidgets.QCheckBox("Gas Filled Up")
        self.vehicle_cleaned = QtWidgets.QCheckBox("Vehicle Cleaned")
        self.fleetio_inspection_done = QtWidgets.QCheckBox("Fleetio Inspection Done")
        self.completed_by = QtWidgets.QLineEdit()
        self.assign_spare_button = QtWidgets.QPushButton("Assign Spare/Loaner")
        self.assign_spare_button.clicked.connect(self.assign_spare_loaner)
        assign_layout.addWidget(QtWidgets.QLabel("Assign Driver to Spare/Loaner Vehicle"))
        assign_driver_vehicle_layout = QtWidgets.QHBoxLayout()
        assign_driver_vehicle_layout.addWidget(self.assign_spare_driver)
        assign_driver_vehicle_layout.addWidget(self.assign_spare_vehicle)
        assign_layout.addLayout(assign_driver_vehicle_layout)
        assign_layout.addWidget(QtWidgets.QLabel("Assignment Time (Fargo, ND):"))
        assign_layout.addWidget(self.assign_time)
        assign_layout.addWidget(QtWidgets.QLabel("Due Time:"))
        assign_layout.addWidget(self.due_time)
        assign_layout.addWidget(QtWidgets.QLabel("Assigned By:"))
        assign_layout.addWidget(self.assigned_by)
        assign_layout.addWidget(QtWidgets.QLabel("Checklist (All Required):"))
        assign_layout.addWidget(self.returned_keys)
        assign_layout.addWidget(self.returned_tablet)
        assign_layout.addWidget(self.gas_filled)
        assign_layout.addWidget(self.vehicle_cleaned)
        assign_layout.addWidget(self.fleetio_inspection_done)
        assign_layout.addWidget(QtWidgets.QLabel("Completed By:"))
        assign_layout.addWidget(self.completed_by)
        assign_layout.addWidget(self.assign_spare_button)
        assign_widget.setLayout(assign_layout)
        self.spare_loaner_log_table = QtWidgets.QTableWidget()
        self.spare_loaner_log_table.setColumnCount(10)
        self.spare_loaner_log_table.setHorizontalHeaderLabels([
            "Timestamp", "Action", "Vehicle Number", "Driver ID", "Assignment Time", "Due Time",
            "Assigned By", "Completed By", "Checklist", "Status"
        ])
        self.spare_loaner_log_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.spares_loaners_layout.addWidget(QtWidgets.QLabel("Spare/Loaner Vehicles"))
        self.spares_loaners_layout.addWidget(self.spares_loaners_table)
        self.spares_loaners_layout.addWidget(assign_widget)
        self.spares_loaners_layout.addWidget(QtWidgets.QLabel("Assignment Log"))
        self.spares_loaners_layout.addWidget(self.spare_loaner_log_table)
        self.spares_loaners_tab.setLayout(self.spares_loaners_layout)
        self.tabs.addTab(self.spares_loaners_tab, "Spares & Loaners")

        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)
        self.show_dashboard()  # Initial dashboard display

    def update_clock(self):
        fargo_tz = pytz.timezone("America/Chicago")
        current_time = datetime.now(fargo_tz)
        self.time_label.setText(f"Current Time in Fargo, ND: {current_time.strftime('%I:%M:%S %p')}")

    def toggle_extra_driver(self, state):
        is_extra = state == Qt.CheckState.Checked.value
        self.start_hour_input.setEnabled(not is_extra)
        self.end_hour_input.setEnabled(not is_extra)
        for btn in self.day_buttons.values():
            btn.setEnabled(not is_extra)
            if is_extra:
                btn.setChecked(False)

    def toggle_lease_type(self, text):
        is_lease = (text == "Lease")
        self.lease_type_label.setVisible(is_lease)
        self.lease_type.setVisible(is_lease)

    def open_add_vehicle_dialog(self):
        dialog = AddVehicleDialog(self)
        if dialog.exec():
            vehicle_data = dialog.get_vehicle_data()
            db.collection("vehicles").document(vehicle_data["vehicle_number"]).set(vehicle_data)
            QtWidgets.QMessageBox.information(self, "Success", f"Vehicle {vehicle_data['vehicle_number']} added.")
            self.update_vehicle_selector()
            self.update_spare_vehicle_selector()
            self.show_vehicles()

    def open_supply_settings(self):
        dialog = HourlySupplySettingsDialog(self.hourly_thresholds, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.hourly_thresholds = dialog.getThresholds()
            self.show_hourly_supply()

    def show_dashboard(self):
        fargo_tz = pytz.timezone("America/Chicago")
        current_time = datetime.now(fargo_tz)
        current_day = current_time.strftime("%A")
        current_hour = current_time.hour

        drivers = db.collection("drivers").stream()
        working_drivers = []
        for driver in drivers:
            driver_data = driver.to_dict()
            driver_type = driver_data.get('driver_type', "Regular")
            if driver_type == "Extra":
                continue
            start_hour = driver_data['start']
            end_hour = driver_data['end']
            working_days = driver_data['days']
            if current_day in working_days:
                if start_hour < end_hour:
                    if start_hour <= current_hour < end_hour:  # End hour is exclusive
                        working_drivers.append(driver_data)
                else:  # Overnight shift
                    if current_hour >= start_hour or current_hour < end_hour:
                        working_drivers.append(driver_data)

        self.driver_count_label.setText(f"Current Number of Drivers: {len(working_drivers)}")
        self.driver_list_table.setRowCount(len(working_drivers))
        for row, driver in enumerate(working_drivers):
            driver_id = QtWidgets.QTableWidgetItem(driver["id"])
            shift_hours = QtWidgets.QTableWidgetItem(f"{driver['start']:02d}:00 - {driver['end']:02d}:00")
            days_abbrev = ", ".join([DAY_ABBREVS[DAYS.index(day)] for day in driver["days"]])
            days_item = QtWidgets.QTableWidgetItem(days_abbrev)
            phone_item = QtWidgets.QTableWidgetItem(driver.get("phone_number", "N/A"))
            for item in [driver_id, shift_hours, days_item, phone_item]:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.driver_list_table.setItem(row, 0, driver_id)
            self.driver_list_table.setItem(row, 1, shift_hours)
            self.driver_list_table.setItem(row, 2, days_item)
            self.driver_list_table.setItem(row, 3, phone_item)

        self.driver_list_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.driver_list_table.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, pos):
        index = self.driver_list_table.indexAt(pos)
        if not index.isValid() or index.column() != 3:  # Only on Phone Number column
            return
        menu = QtWidgets.QMenu(self)
        copy_action = QAction("Copy Phone Number", self)
        copy_action.triggered.connect(lambda: self.copy_phone_number(index))
        menu.addAction(copy_action)
        menu.exec(self.driver_list_table.viewport().mapToGlobal(pos))

    def copy_phone_number(self, index):
        phone_number = self.driver_list_table.item(index.row(), 3).text()
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(phone_number)
        QtWidgets.QMessageBox.information(self, "Copied", f"Phone number {phone_number} copied to clipboard.")

    def show_hourly_supply(self):
        drivers = db.collection("drivers").stream()
        hourly_supply = {day: {hour: 0 for hour in range(24)} for day in DAYS}
        for driver in drivers:
            driver_data = driver.to_dict()
            if driver_data.get('driver_type') == "Extra":
                continue
            start_hour = driver_data['start']
            end_hour = driver_data['end']
            working_days = driver_data['days']
            for day in working_days:
                if start_hour < end_hour:
                    for hour in range(start_hour, end_hour):  # End hour is exclusive
                        hourly_supply[day][hour] += 1
                else:  # Overnight shift
                    day_idx = DAYS.index(day)
                    next_day = DAYS[(day_idx + 1) % 7]
                    for hour in range(start_hour, 24):  # Up to 23:00
                        hourly_supply[day][hour] += 1
                    for hour in range(0, end_hour):  # Up to end_hour - 1
                        hourly_supply[next_day][hour] += 1
        for day_idx, day in enumerate(DAYS):
            for hour in range(24):
                count = hourly_supply[day][hour]
                key = (day, hour)
                min_required = self.hourly_thresholds.get(key, 0)
                item = QtWidgets.QTableWidgetItem(str(count) if count > 0 else "")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if count < min_required:
                    item.setBackground(QtGui.QColor("red"))
                elif count == min_required:
                    item.setBackground(QtGui.QColor("yellow"))
                elif count > min_required:
                    item.setBackground(QtGui.QColor("green"))
                item.setToolTip(f"{count} drivers scheduled. Minimum required: {min_required}")
                self.hourly_supply_table.setItem(day_idx, hour, item)

    def show_all_drivers(self):
        drivers = list(db.collection("drivers").stream())
        regular_drivers = []
        extra_drivers = []
        selected_day = self.filter_day.currentText()
        shift_text = self.filter_shift_hour.currentText()
        if shift_text == "All Hours":
            selected_hour = -1
        else:
            selected_hour = int(shift_text.split(":")[0])

        for driver in drivers:
            driver_data = driver.to_dict()
            driver_type = driver_data.get('driver_type', "Regular")
            if driver_type == "Extra":
                extra_drivers.append(driver_data)
                continue
            days = driver_data.get('days', [])
            start = driver_data.get('start')
            end = driver_data.get('end')
            prev_day = DAYS[(DAYS.index(selected_day) - 1) % 7] if selected_day != "All Days" else None
            is_relevant = (selected_day == "All Days" or selected_day in days or (prev_day in days and start > end))
            if not is_relevant:
                continue
            if selected_hour != -1:
                if start < end:
                    if not (start <= selected_hour < end):  # End hour is exclusive
                        continue
                else:  # Overnight shift
                    if not (selected_hour >= start or selected_hour < end):
                        continue
            regular_drivers.append(driver_data)

        reverse_sort = self.sort_toggle.isChecked()
        regular_drivers.sort(key=lambda x: (x['start'], x['end']), reverse=reverse_sort)
        all_drivers = regular_drivers + extra_drivers  # Regular drivers on top, extra at bottom

        self.all_drivers_table.setRowCount(len(all_drivers))
        for row, driver_data in enumerate(all_drivers):
            driver_id = driver_data['id']
            name = driver_data['name']
            phone_number = driver_data.get('phone_number', "N/A")
            driver_type = driver_data.get('driver_type', "Regular")
            start_str = "Extra" if driver_type == "Extra" else f"{driver_data['start']:02d}:00"
            end_str = "Extra" if driver_type == "Extra" else f"{driver_data['end']:02d}:00"
            days_str = "Extra" if driver_type == "Extra" else ", ".join(driver_data['days'])
            vehicle_number = driver_data.get('vehicle_number', "None")
            status = driver_data.get('status', "N/A")
            lease_type = driver_data.get('lease_type', "") if status == "Lease" else ""
            items = [
                QtWidgets.QTableWidgetItem(driver_id),
                QtWidgets.QTableWidgetItem(name),
                QtWidgets.QTableWidgetItem(phone_number),
                QtWidgets.QTableWidgetItem(driver_type),
                QtWidgets.QTableWidgetItem(start_str),
                QtWidgets.QTableWidgetItem(end_str),
                QtWidgets.QTableWidgetItem(days_str),
                QtWidgets.QTableWidgetItem(vehicle_number),
                QtWidgets.QTableWidgetItem(status),
                QtWidgets.QTableWidgetItem(lease_type)
            ]
            if driver_data in extra_drivers:
                for item in items:
                    item.setBackground(QtGui.QColor("lightgray"))  # Light gray for extra drivers
            for col, item in enumerate(items):
                self.all_drivers_table.setItem(row, col, item)
            actions_widget = QtWidgets.QWidget()
            actions_layout = QtWidgets.QHBoxLayout()
            actions_layout.setContentsMargins(0, 0, 0, 0)
            edit_button = QtWidgets.QPushButton("Edit")
            edit_button.clicked.connect(lambda _, d=driver_data: self.edit_driver(d))
            actions_layout.addWidget(edit_button)
            actions_widget.setLayout(actions_layout)
            self.all_drivers_table.setCellWidget(row, 10, actions_widget)

    def reset_filters(self):
        self.filter_day.setCurrentIndex(0)
        self.filter_shift_hour.setCurrentIndex(0)
        self.sort_toggle.setChecked(False)
        self.show_all_drivers()

    def edit_driver(self, driver_data):
        dialog = EditDriverDialog(driver_data, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            updated_data = dialog.get_driver_data()
            old_vehicle = driver_data.get("vehicle_number")
            new_vehicle = updated_data.get("vehicle_number")
            db.collection("drivers").document(updated_data["id"]).update(updated_data)
            if old_vehicle != new_vehicle:
                if old_vehicle:
                    db.collection("vehicles").document(old_vehicle).update({"assigned_driver": None})
                if new_vehicle:
                    db.collection("vehicles").document(new_vehicle).update({"assigned_driver": updated_data["id"]})
            QtWidgets.QMessageBox.information(self, "Success", f"Driver {updated_data['name']} updated.")
            self.show_all_drivers()
            self.show_dashboard()

    def show_vehicles(self):
        vehicles = list(db.collection("vehicles").stream())
        drivers = list(db.collection("drivers").stream())
        assigned_map = {}
        for d in drivers:
            d_data = d.to_dict()
            veh_num = d_data.get("vehicle_number")
            if veh_num:
                if veh_num in assigned_map:
                    assigned_map[veh_num] += ", " + d_data["id"]
                else:
                    assigned_map[veh_num] = d_data["id"]
        self.vehicles_table.setRowCount(len(vehicles))
        for row, vehicle in enumerate(vehicles):
            vehicle_data = vehicle.to_dict()
            vehicle_number = vehicle_data.get("vehicle_number", "")
            self.vehicles_table.setItem(row, 0, QtWidgets.QTableWidgetItem(vehicle_number))
            self.vehicles_table.setItem(row, 1, QtWidgets.QTableWidgetItem(vehicle_data.get("vehicle_type", "Regular")))
            self.vehicles_table.setItem(row, 2, QtWidgets.QTableWidgetItem(str(vehicle_data.get("year", ""))))
            self.vehicles_table.setItem(row, 3, QtWidgets.QTableWidgetItem(vehicle_data.get("make", "")))
            self.vehicles_table.setItem(row, 4, QtWidgets.QTableWidgetItem(vehicle_data.get("model", "")))
            self.vehicles_table.setItem(row, 5, QtWidgets.QTableWidgetItem(vehicle_data.get("color", "")))
            self.vehicles_table.setItem(row, 6, QtWidgets.QTableWidgetItem(vehicle_data.get("title_number", "")))
            self.vehicles_table.setItem(row, 7, QtWidgets.QTableWidgetItem(vehicle_data.get("license_number", "")))
            self.vehicles_table.setItem(row, 8, QtWidgets.QTableWidgetItem(vehicle_data.get("vin_number", "")))
            self.vehicles_table.setItem(row, 9, QtWidgets.QTableWidgetItem(vehicle_data.get("plate_renewal", "")))
            sts_exp = vehicle_data.get("sts_expiration")
            sts_exp_str = sts_exp if sts_exp and sts_exp != "" else "Needs Adding"
            self.vehicles_table.setItem(row, 10, QtWidgets.QTableWidgetItem(sts_exp_str))
            sts_status_item = QtWidgets.QTableWidgetItem()
            if sts_exp and sts_exp != "Needs Adding":
                try:
                    exp_date = datetime.strptime(sts_exp, "%m/%d/%Y")
                    current_date_obj = datetime(2025, 4, 4)
                    status_text = "Active" if exp_date >= current_date_obj else "Expired"
                except Exception:
                    status_text = "Add"
            else:
                status_text = "Add"
            sts_status_item.setText(status_text)
            if status_text == "Expired":
                sts_status_item.setBackground(QtGui.QColor("red"))
            elif status_text == "Add":
                sts_status_item.setBackground(QtGui.QColor("blue"))
            self.vehicles_table.setItem(row, 11, sts_status_item)
            insp = vehicle_data.get("inspection")
            insp_str = insp if insp and insp != "" else "Needs Adding"
            self.vehicles_table.setItem(row, 12, QtWidgets.QTableWidgetItem(insp_str))
            assigned_driver = vehicle_data.get("assigned_driver", assigned_map.get(vehicle_number, "None"))
            self.vehicles_table.setItem(row, 13, QtWidgets.QTableWidgetItem(assigned_driver))
            actions_widget = QtWidgets.QWidget()
            actions_layout = QtWidgets.QHBoxLayout()
            actions_layout.setContentsMargins(0, 0, 0, 0)
            edit_button = QtWidgets.QPushButton("Edit")
            edit_button.clicked.connect(lambda _, vn=vehicle_number, vd=vehicle_data: self.edit_vehicle(vn, vd))
            delete_button = QtWidgets.QPushButton("Delete")
            delete_button.clicked.connect(lambda _, vn=vehicle_number: self.delete_vehicle(vn))
            actions_layout.addWidget(edit_button)
            actions_layout.addWidget(delete_button)
            actions_widget.setLayout(actions_layout)
            self.vehicles_table.setCellWidget(row, 14, actions_widget)

    def edit_vehicle(self, vehicle_number, vehicle_data):
        dialog = EditVehicleDialog(vehicle_data, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            updated_data = dialog.get_vehicle_data()
            new_assigned_driver = updated_data.get("assigned_driver")
            old_assigned_driver = vehicle_data.get("assigned_driver")
            db.collection("vehicles").document(vehicle_number).update(updated_data)
            if new_assigned_driver != old_assigned_driver:
                if old_assigned_driver:
                    db.collection("drivers").document(old_assigned_driver).update({"vehicle_number": None})
                if new_assigned_driver:
                    db.collection("drivers").document(new_assigned_driver).update({"vehicle_number": vehicle_number})
            QtWidgets.QMessageBox.information(self, "Success", f"Vehicle {vehicle_number} updated.")
            self.update_vehicle_selector()
            self.update_spare_vehicle_selector()
            self.show_vehicles()
            self.show_all_drivers()

    def delete_vehicle(self, vehicle_number):
        reply = QtWidgets.QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete vehicle {vehicle_number}?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            vehicle_data = db.collection("vehicles").document(vehicle_number).get().to_dict()
            assigned_driver = vehicle_data.get("assigned_driver")
            if assigned_driver:
                db.collection("drivers").document(assigned_driver).update({"vehicle_number": None})
            db.collection("vehicles").document(vehicle_number).delete()
            QtWidgets.QMessageBox.information(self, "Deleted", f"Vehicle {vehicle_number} has been deleted.")
            self.update_vehicle_selector()
            self.update_spare_vehicle_selector()
            self.show_vehicles()

    def show_spares_loaners(self):
        vehicles = list(db.collection("vehicles").stream())
        spares_loaners = [v for v in vehicles if v.to_dict().get('vehicle_type') in ["Spare", "Loaner"]]
        self.spares_loaners_table.setRowCount(len(spares_loaners))
        for row, vehicle in enumerate(spares_loaners):
            vehicle_data = vehicle.to_dict()
            sts_exp = vehicle_data.get("sts_expiration")
            sts_status = "Add"
            if sts_exp and sts_exp != "Needs Adding":
                try:
                    exp_date = datetime.strptime(sts_exp, "%m/%d/%Y")
                    current_date_obj = datetime(2025, 4, 4)
                    sts_status = "Active" if exp_date >= current_date_obj else "Expired"
                except Exception:
                    sts_status = "Add"
            self.spares_loaners_table.setItem(row, 0, QtWidgets.QTableWidgetItem(vehicle_data.get("vehicle_number", "")))
            self.spares_loaners_table.setItem(row, 1, QtWidgets.QTableWidgetItem(vehicle_data.get("vehicle_type", "Regular")))
            self.spares_loaners_table.setItem(row, 2, QtWidgets.QTableWidgetItem(str(vehicle_data.get("year", ""))))
            self.spares_loaners_table.setItem(row, 3, QtWidgets.QTableWidgetItem(vehicle_data.get("make", "")))
            self.spares_loaners_table.setItem(row, 4, QtWidgets.QTableWidgetItem(vehicle_data.get("model", "")))
            self.spares_loaners_table.setItem(row, 5, QtWidgets.QTableWidgetItem(vehicle_data.get("color", "")))
            self.spares_loaners_table.setItem(row, 6, QtWidgets.QTableWidgetItem(vehicle_data.get("title_number", "")))
            self.spares_loaners_table.setItem(row, 7, QtWidgets.QTableWidgetItem(vehicle_data.get("license_number", "")))
            self.spares_loaners_table.setItem(row, 8, QtWidgets.QTableWidgetItem(vehicle_data.get("vin_number", "")))
            self.spares_loaners_table.setItem(row, 9, QtWidgets.QTableWidgetItem(vehicle_data.get("plate_renewal", "")))
            sts_exp_str = sts_exp if sts_exp and sts_exp != "" else "Needs Adding"
            self.spares_loaners_table.setItem(row, 10, QtWidgets.QTableWidgetItem(sts_exp_str))
            sts_item = QtWidgets.QTableWidgetItem(sts_status)
            if sts_status == "Expired":
                sts_item.setBackground(QtGui.QColor("red"))
            elif sts_status == "Add":
                sts_item.setBackground(QtGui.QColor("blue"))
            self.spares_loaners_table.setItem(row, 11, sts_item)
            insp = vehicle_data.get("inspection")
            insp_str = insp if insp and insp != "" else "Needs Adding"
            self.spares_loaners_table.setItem(row, 12, QtWidgets.QTableWidgetItem(insp_str))
        assignments = list(db.collection("spare_loaner_assignments").stream())
        self.spare_loaner_log_table.setRowCount(len(assignments))
        fargo_tz = pytz.timezone("America/Chicago")
        current_time = datetime.now(fargo_tz)
        for row, assignment in enumerate(assignments):
            assignment_data = assignment.to_dict()
            vehicle_number = assignment_data.get("vehicle_number", "")
            driver_id = assignment_data.get("driver_id", "")
            assign_time = assignment_data.get("assign_time", "")
            due_time = assignment_data.get("due_time", "")
            assigned_by = assignment_data.get("assigned_by", "")
            completed_by = assignment_data.get("completed_by", "")
            checklist = assignment_data.get("checklist", {})
            checklist_str = ", ".join([k for k, v in checklist.items() if v])
            due_datetime = datetime.strptime(due_time, "%m/%d/%Y %I:%M %p")
            due_datetime = fargo_tz.localize(due_datetime)
            status = "Active"
            if current_time > due_datetime and assignment_data.get("status") != "Completed":
                status = "Past Due"
                QtWidgets.QMessageBox.warning(self, "Past Due Alert", f"Vehicle {vehicle_number} assigned to {driver_id} is past due (Due: {due_time}).")
                db.collection("spare_loaner_assignments").document(assignment.id).update({'status': "Past Due"})
            self.spare_loaner_log_table.setItem(row, 0, QtWidgets.QTableWidgetItem(assign_time))
            self.spare_loaner_log_table.setItem(row, 1, QtWidgets.QTableWidgetItem("Assignment"))
            self.spare_loaner_log_table.setItem(row, 2, QtWidgets.QTableWidgetItem(vehicle_number))
            self.spare_loaner_log_table.setItem(row, 3, QtWidgets.QTableWidgetItem(driver_id))
            self.spare_loaner_log_table.setItem(row, 4, QtWidgets.QTableWidgetItem(assign_time))
            self.spare_loaner_log_table.setItem(row, 5, QtWidgets.QTableWidgetItem(due_time))
            self.spare_loaner_log_table.setItem(row, 6, QtWidgets.QTableWidgetItem(assigned_by))
            self.spare_loaner_log_table.setItem(row, 7, QtWidgets.QTableWidgetItem(completed_by))
            self.spare_loaner_log_table.setItem(row, 8, QtWidgets.QTableWidgetItem(checklist_str))
            status_item = QtWidgets.QTableWidgetItem(status)
            if status == "Past Due":
                status_item.setBackground(QtGui.QColor("red"))
            self.spare_loaner_log_table.setItem(row, 9, status_item)
        self.update_driver_selector()

    def on_tab_changed(self, index):
        if index == 0:
            self.show_dashboard()
        elif index == 1:
            self.show_hourly_supply()
        elif index == 2:
            self.show_all_drivers()
        elif index == 3:
            self.show_vehicles()
        elif index == 4:
            self.show_spares_loaners()

    def update_vehicle_selector(self):
        self.vehicle_selector.clear()
        self.vehicle_selector.addItem("None")
        if hasattr(self, "assign_vehicle_vehicle"):
            self.assign_vehicle_vehicle.clear()
            self.assign_vehicle_vehicle.addItem("Select Vehicle")
        vehicles = db.collection("vehicles").stream()
        for vehicle in vehicles:
            vehicle_data = vehicle.to_dict()
            veh_num = vehicle_data.get("vehicle_number", "")
            self.vehicle_selector.addItem(veh_num)
            if hasattr(self, "assign_vehicle_vehicle"):
                self.assign_vehicle_vehicle.addItem(veh_num)

    def update_driver_selector(self):
        if hasattr(self, "assign_vehicle_driver"):
            self.assign_vehicle_driver.clear()
            self.assign_vehicle_driver.addItem("Select Driver")
        if hasattr(self, "assign_spare_driver"):
            self.assign_spare_driver.clear()
            self.assign_spare_driver.addItem("Select Driver")
        drivers = db.collection("drivers").stream()
        for driver in drivers:
            d_data = driver.to_dict()
            driver_id = d_data.get("id", "")
            if hasattr(self, "assign_vehicle_driver"):
                self.assign_vehicle_driver.addItem(driver_id)
            if hasattr(self, "assign_spare_driver"):
                self.assign_spare_driver.addItem(driver_id)

    def update_spare_vehicle_selector(self):
        if hasattr(self, "assign_spare_vehicle"):
            self.assign_spare_vehicle.clear()
            self.assign_spare_vehicle.addItem("Select Vehicle")
            vehicles = db.collection("vehicles").stream()
            for vehicle in vehicles:
                v_data = vehicle.to_dict()
                if v_data.get("vehicle_type") in ["Spare", "Loaner"]:
                    self.assign_spare_vehicle.addItem(v_data.get("vehicle_number", ""))

    def add_driver(self):
        driver_id = self.driver_id_input.text().strip()
        name = self.driver_name_input.text().strip()
        phone_number = self.phone_number_input.text().strip()
        is_extra = self.extra_driver_toggle.isChecked()
        start = None if is_extra else self.start_hour_input.value()
        end = None if is_extra else self.end_hour_input.value()
        selected_days = [] if is_extra else [day for day, btn in self.day_buttons.items() if btn.isChecked()]
        vehicle_number = self.vehicle_selector.currentText()
        status = self.status.currentText()
        lease_type = self.lease_type.currentText() if status == "Lease" else None
        if not driver_id or not name or (not is_extra and not selected_days):
            QtWidgets.QMessageBox.warning(self, "Input Error", "Please fill all fields.")
            return
        driver_data = {
            'id': driver_id,
            'name': name,
            'phone_number': phone_number,
            'driver_type': "Extra" if is_extra else "Regular",
            'start': start,
            'end': end,
            'days': selected_days,
            'vehicle_number': vehicle_number if vehicle_number != "None" else None,
            'status': status,
            'lease_type': lease_type
        }
        db.collection("drivers").document(driver_id).set(driver_data)
        if vehicle_number != "None":
            db.collection("vehicles").document(vehicle_number).update({"assigned_driver": driver_id})
        self.log_action("Added Driver", f"Driver {driver_id} added", driver_id=driver_id)
        QtWidgets.QMessageBox.information(self, "Success", f"Driver {name} added.")
        self.driver_id_input.clear()
        self.driver_name_input.clear()
        self.phone_number_input.clear()
        self.start_hour_input.setValue(0)
        self.end_hour_input.setValue(0)
        self.extra_driver_toggle.setChecked(False)
        for btn in self.day_buttons.values():
            btn.setChecked(False)
        self.vehicle_selector.setCurrentIndex(0)
        self.status.setCurrentIndex(0)
        self.lease_type.setCurrentIndex(0)
        self.lease_type.setVisible(False)
        self.lease_type_label.setVisible(False)
        if self.tabs.currentIndex() == 0:
            self.show_dashboard()
        elif self.tabs.currentIndex() == 1:
            self.show_hourly_supply()
        elif self.tabs.currentIndex() == 2:
            self.show_all_drivers()
        elif self.tabs.currentIndex() == 3:
            self.show_vehicles()
        elif self.tabs.currentIndex() == 4:
            self.show_spares_loaners()

    def assign_vehicle(self):
        driver_id = self.assign_vehicle_driver.currentText()
        vehicle_number = self.assign_vehicle_vehicle.currentText()
        if driver_id == "Select Driver" or vehicle_number == "Select Vehicle":
            QtWidgets.QMessageBox.warning(self, "Input Error", "Please select a driver and a vehicle.")
            return
        db.collection("drivers").document(driver_id).update({'vehicle_number': vehicle_number})
        db.collection("vehicles").document(vehicle_number).update({"assigned_driver": driver_id})
        self.log_action("Assigned Vehicle", f"Vehicle {vehicle_number} assigned to driver {driver_id}", vehicle_number=vehicle_number, driver_id=driver_id)
        QtWidgets.QMessageBox.information(self, "Success", f"Vehicle {vehicle_number} assigned to driver {driver_id}.")
        if self.tabs.currentIndex() == 0:
            self.show_dashboard()
        elif self.tabs.currentIndex() == 2:
            self.show_all_drivers()
        elif self.tabs.currentIndex() == 3:
            self.show_vehicles()

    def assign_spare_loaner(self):
        driver_id = self.assign_spare_driver.currentText()
        vehicle_number = self.assign_spare_vehicle.currentText()
        assign_time = self.assign_time.dateTime().toString("MM/dd/yyyy hh:mm AP")
        due_time = self.due_time.dateTime().toString("MM/dd/yyyy hh:mm AP")
        assigned_by = self.assigned_by.text().strip()
        completed_by = self.completed_by.text().strip()
        if not (self.returned_keys.isChecked() and self.returned_tablet.isChecked() and self.gas_filled.isChecked() and self.vehicle_cleaned.isChecked() and self.fleetio_inspection_done.isChecked()):
            QtWidgets.QMessageBox.warning(self, "Input Error", "All checklist items must be checked.")
            return
        if driver_id == "Select Driver" or vehicle_number == "Select Vehicle" or not assigned_by or not completed_by:
            QtWidgets.QMessageBox.warning(self, "Input Error", "Please fill all fields.")
            return
        assignment_data = {
            'driver_id': driver_id,
            'vehicle_number': vehicle_number,
            'assign_time': assign_time,
            'due_time': due_time,
            'assigned_by': assigned_by,
            'completed_by': completed_by,
            'checklist': {
                'returned_keys': self.returned_keys.isChecked(),
                'returned_tablet': self.returned_tablet.isChecked(),
                'gas_filled': self.gas_filled.isChecked(),
                'vehicle_cleaned': self.vehicle_cleaned.isChecked(),
                'fleetio_inspection_done': self.fleetio_inspection_done.isChecked()
            },
            'status': "Active"
        }
        assignment_id = f"{vehicle_number}_{driver_id}_{assign_time.replace('/', '_').replace(' ', '_')}"
        db.collection("spare_loaner_assignments").document(assignment_id).set(assignment_data)
        db.collection("vehicles").document(vehicle_number).update({"assigned_driver": driver_id})
        self.log_action("Assigned Spare/Loaner", f"Vehicle {vehicle_number} assigned to driver {driver_id}", vehicle_number=vehicle_number, driver_id=driver_id)
        QtWidgets.QMessageBox.information(self, "Success", f"Vehicle {vehicle_number} assigned to driver {driver_id}.")
        self.assign_spare_driver.setCurrentIndex(0)
        self.assign_spare_vehicle.setCurrentIndex(0)
        fargo_tz = pytz.timezone("America/Chicago")
        current_time = datetime.now(fargo_tz)
        self.assign_time.setDateTime(QDateTime(current_time.year, current_time.month, current_time.day, current_time.hour, current_time.minute))
        self.due_time.setDateTime(QDateTime(current_time.year, current_time.month, current_time.day, current_time.hour, current_time.minute))
        self.assigned_by.clear()
        self.completed_by.clear()
        self.returned_keys.setChecked(False)
        self.returned_tablet.setChecked(False)
        self.gas_filled.setChecked(False)
        self.vehicle_cleaned.setChecked(False)
        self.fleetio_inspection_done.setChecked(False)
        self.show_spares_loaners()

    def log_action(self, action, description, vehicle_number=None, driver_id=None):
        fargo_tz = pytz.timezone("America/Chicago")
        timestamp = datetime.now(fargo_tz).strftime("%m/%d/%Y %I:%M %p")
        log_data = {
            'timestamp': timestamp,
            'action': action,
            'description': description,
            'vehicle_number': vehicle_number,
            'driver_id': driver_id
        }
        db.collection("spare_loaner_logs").add(log_data)

def run_app():
    app = QtWidgets.QApplication(sys.argv)
    window = DriverScheduleApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    run_app()