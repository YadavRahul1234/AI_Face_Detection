SMART GATE AI ATTENDANCE SYSTEM WITH VISITOR MANAGEMENT
----------------------------------

📌 Description:
This is an AI-based Face Recognition Attendance System with Visitor Management built using Python, Flask, OpenCV, and face_recognition.
It allows adding new employees, capturing attendance automatically, managing attendance records, and handling visitor check-ins via chatbot with WhatsApp integration.

----------------------------------
📂 Folder Structure:
SmartGateApp/
├── app.py                     (Flask web application)
├── Face_Detection.py          (Original Tkinter app)
├── employee_data/             (stores captured face images)
├── encodings.pkl              (saved face encodings)
├── attendance.db              (SQLite database)
├── attendance.csv             (exported attendance)
├── templates/                 (HTML templates)
│   ├── home.html              (Live Capture page)
│   ├── hr_dashboard.html      (Admin Dashboard)
│   └── chatbot.html           (Visitor Chatbot)
├── requirements.txt
├── TODO.md                    (Task tracking)
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

5. Run the web app:
   > python app.py

6. Access at http://localhost:5000

----------------------------------
🎯 Features:
✅ Add New Employee (via webcam on web interface)
✅ Face Detection & Recognition for Attendance (≥95% accuracy)
✅ Auto Attendance Logging to SQLite
✅ Live Capture with Real-time Feedback
✅ Visitor Detection and Chatbot Integration
✅ WhatsApp Message Sending for Visitor Approval
✅ Real-time WhatsApp Reply Polling
✅ AI-Powered Visitor Approval Decision
✅ Admin Dashboard for Attendance Management
✅ View, Update, Delete Attendance Records
✅ Export Attendance to CSV
✅ Visitor Records Tracking
✅ Works Offline – No Internet Required (except for WhatsApp)

----------------------------------
🔧 Troubleshooting:
- If camera not detected:
   > Check camera permissions or USB device
- If face_recognition fails:
   > pip install cmake dlib face_recognition --force-reinstall
- For WhatsApp integration:
   > Ensure Twilio credentials are set and ngrok for public URL if needed
- If OpenAI API fails:
   > Check API key and credits

----------------------------------
👨‍💻 Developer Info:
Project: Smart Gate AI System with Visitor Management
Author: Rahul Yadav  
Language: Python 3  
Framework: Flask (Web), 
Database: SQLite  
AI: OpenAI GPT-3.5 for parsing and decisions
WhatsApp: Twilio API
Face Recognition: face_recognition library (≥95% accuracy)
Version: 2.0.0
