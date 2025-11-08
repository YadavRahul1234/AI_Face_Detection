SMART GATE AI ATTENDANCE SYSTEM
----------------------------------

📌 Description:
This is an AI-based Face Recognition Attendance System built using Python, OpenCV, and Tkinter.
It allows adding new employees, capturing attendance automatically, and managing attendance records
(update, delete, and export to CSV).

----------------------------------
📂 Folder Structure:
SmartGateApp/
├── Face_Detection.py
├── employee_data/          (stores captured face images)
├── encodings.pkl           (saved face encodings)
├── attendance.db           (SQLite database)
├── requirements.txt
└── README.txt

----------------------------------
⚙️ Installation Steps (for Developer use):
1. Install Python 3.8+ (if not already installed)
2. Open Terminal or CMD inside this folder
3. Create virtual environment (optional but recommended)
   > python -m venv myenv
   > myenv\Scripts\activate      (on Windows)
   > source myenv/bin/activate   (on Linux/Mac)

4. Install required packages:
   > pip install -r requirements.txt

5. Run the app:
   > python Face_Detection.py

----------------------------------
🎯 Features:
✅ Add New Employee (via webcam)
✅ Face Detection & Recognition for Attendance
✅ Auto Attendance Logging to SQLite
✅ View, Update, Delete Attendance Records
✅ Export Attendance to CSV
✅ Works Offline – No Internet Required

----------------------------------
🔧 Troubleshooting:
- If camera not detected:
   > Check camera permissions or USB device
- If tkinter missing:
   > sudo apt install python3-tk
- If face_recognition fails:
   > pip install cmake dlib face_recognition --force-reinstall

----------------------------------
👨‍💻 Developer Info:
Project: Smart Gate AI System  
Author: Rahul Yadav  
Language: Python 3  
Framework: Tkinter (GUI)  
Database: SQLite  
Version: 1.0.0
