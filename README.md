# 🏛 SVPCET Nagpur - Department of Industrial IoT (IIoT)
## Laboratory Inventory & Equipment Management System

An enterprise-grade laboratory inventory, consumable tracking, and equipment checkout web application built for the **Department of Industrial IoT (Embedded Systems, IoT & Robotics Laboratories)** at **St. Vincent Pallotti College of Engineering & Technology (SVPCET), Nagpur**.

![SVPCET Logo](static/svpcet_logo.png)

---

## 🌟 Key Features

### 1. 🏢 Multi-Lab Architecture & Role-Based Access Control
* **HOD Master View:** Real-time visibility and management across all department laboratories (Embedded Systems Lab, IoT & Sensor Lab, Robotics Lab).
* **Lab-Specific Isolations:** Lab assistants log in directly to their assigned laboratory with isolated inventory, checkouts, and records.
* **HOD Lab Management Portal (`/manage-labs`):** Live rename labs, add new laboratories, and reset lab passwords on the fly.

### 2. 🛒 Multi-Item Equipment Checkout (Batch Cart System)
* **Dynamic Cart:** Issue multiple components in a single transaction with individual quantities and returnable/consumable flags.
* **Smart Validation:** Atomic stock verification prevents over-issuance and duplicate selections.
* **Recipient Support:** Supports Students (UID verification), Faculty / Staff, and Inter-Lab transfers.

### 3. 📱 Instant WhatsApp Receipts & Notifications
* Automated generation of official WhatsApp receipts for both **Single** and **Multi-Item** issues.
* Clear itemized bullet list with dates, purpose, and laboratory signature.
* One-click direct opening in WhatsApp Web or Desktop application.

### 4. 🔍 Detailed Equipment Return & Audit System
* Tri-condition return tracking: **Good/Working**, **Damaged**, and **Missing/Lost**.
* Automatically calculates and logs laboratory component losses and defects.
* Instant WhatsApp return acknowledgement receipts.

### 5. 📊 Excel Bulk Upload & Template Management
* One-click download of styled Excel templates for Components and Students.
* Bulk import with intelligent upsert (updates existing records, adds new ones without duplicates).

### 6. 📄 Official Transaction Register & PDF / Print Reports
* Comprehensive audit trail with date filters, status filters, and search.
* Official printable report formatted with SVPCET institutional branding.

---

## 🔐 Default Access Credentials

| Role | Username | Password | Default Lab |
| :--- | :--- | :--- | :--- |
| **HOD / Department Admin** | `hod_iiot` | `admin123` | All Department Laboratories |
| **Embedded Systems Lab** | `embedded_lab` | `lab123` | Embedded Systems Lab |
| **IoT & Sensor Lab** | `iot_lab` | `lab123` | IoT & Sensor Lab |
| **Robotics Lab** | `robotics_lab` | `lab123` | Robotics Lab |

---

## 🚀 Quick Start Guide

### Prerequisites
* Python 3.10+
* Git (or GitHub Desktop)

### Installation & Setup

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/drshyamp19/svpcet-iiot-lab-inventory.git
   cd svpcet-iiot-lab-inventory
   ```

2. **Install Required Packages:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the Application:**
   * **Windows (One-Click):** Double-click `run_lab.bat`
   * **Terminal:**
     ```bash
     python app.py
     ```

4. **Access the Portal:**
   Open your browser and navigate to:
   👉 **http://127.0.0.1:5000**

---

## 🛠 Tech Stack
* **Backend:** Python / Flask
* **Database:** SQLite3 with relational foreign keys and dynamic migrations
* **Frontend:** HTML5, CSS3, JavaScript, Bootstrap 5, FontAwesome 6, TomSelect
* **Spreadsheet Processing:** OpenPyXL
* **Messaging:** WhatsApp Click-to-Chat API

---

## 🏫 Institution
**Department of Industrial IoT (IIoT)**  
**St. Vincent Pallotti College of Engineering & Technology (SVPCET)**  
Gavsi Manapur, Wardha Road, Nagpur, Maharashtra, India.  
Website: [https://www.stvincentngp.edu.in/](https://www.stvincentngp.edu.in/)
