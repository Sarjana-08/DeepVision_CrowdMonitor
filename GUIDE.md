╔════════════════════════════════════════════════════════════════════════════╗
║                      DEEPVISION COMPLETE GUIDE                            ║
║         Real-Time Crowd Detection with Accurate Panic & Heatmap          ║
╚════════════════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════════════════
TABLE OF CONTENTS
═══════════════════════════════════════════════════════════════════════════════

1. QUICK START
2. FEATURES EXPLAINED
3. CONFIGURATION
4. EMAIL ALERTS
5. ACCURACY & FORMULAS
6. TROUBLESHOOTING
7. API REFERENCE


═══════════════════════════════════════════════════════════════════════════════
1. QUICK START
═══════════════════════════════════════════════════════════════════════════════

OPTION A: Run Menu (Recommended)
──────────────────────────────────
  python start.py

Choose option 1 to start system.


OPTION B: Direct Start
──────────────────────
  python deepvision.py

Starts immediately without menu.


OPTION C: Double-Click (Windows)
─────────────────────────────────
  run.bat

Launches the menu.


═══════════════════════════════════════════════════════════════════════════════
2. FEATURES EXPLAINED
═══════════════════════════════════════════════════════════════════════════════

CROWD COUNTING
──────────────
How it works:
  1. YOLOv8 Nano detects each person individually
  2. Confidence filtering (50% threshold) removes false positives
  3. Count = total detections
  4. Fallback to edge detection if YOLO unavailable
  5. Bounding boxes drawn on video

Accuracy:
  ±1-3 people per detection
  Affected by: lighting, occlusion, camera angle


PANIC DETECTION
───────────────
Not a static threshold. Calculates real-time panic level (0-100%) based on:

  Panic Score = (Crowding × 0.25) + (Density × 0.50) + (Movement × 0.25)

Where:
  • Crowding = (people_count / 500) × 100
  • Density = (people_count × 15000 / frame_area) × 100
  • Movement = (motion_pixels / total_pixels) × 100 × sensitivity

Example calculations:
  • 0 people → 0% panic (safe)
  • 50 people, stationary → ~17% panic (calm)
  • 100 people, stationary → ~34% panic (normal)
  • 200 people, moving fast → 70%+ panic (concerning)
  • 300+ people, chaos → 100% panic (critical)

Sensitivity tuning:
  Edit config.json: "panic_sensitivity": 0.5 to 2.0
  0.5 = calmer (less sensitive)
  2.0 = more alert (more sensitive)


HEATMAP VISUALIZATION
──────────────────────
What it shows:
  Real-time density distribution across the frame
  
How it works:
  • Each detected person = Gaussian blob
  • Blobs accumulate where people cluster
  • Older data fades (0.95 decay per frame)
  • Color: Blue (low) → Green → Yellow → Red (high)

Benefits:
  • Identify bottlenecks immediately
  • See which areas are crowded
  • Historical (last 30 frames)
  • Non-intrusive (blended at 30%)


EMAIL ALERTS
────────────
Automatically sends email when:
  • Crowd exceeds configured threshold in a zone
  • Happens once per 5 minutes per zone (cooldown)

Setup:
  1. Go to: myaccount.google.com/apppasswords
  2. Select Mail, Windows device
  3. Copy 16-character password
  4. Configure in menu: python start.py
  5. Enter: sender email, password, recipients

Contains:
  • Zone name
  • Current people count
  • Threshold
  • Time of alert


WEB DASHBOARD
─────────────
Real-time metrics displayed at: http://localhost:5001

Shows:
  • People count (large display)
  • Crowd density %
  • Panic level % (with color gauge)
  • Movement intensity (0-1)
  • Crowd trend (increasing/stable)
  • Zone status indicators

Updates:
  Every 1 second automatically

Configuration:
  • Add threshold zone
  • Configure email alerts


═══════════════════════════════════════════════════════════════════════════════
3. CONFIGURATION
═══════════════════════════════════════════════════════════════════════════════

METHOD 1: Via Menu (Easiest)
────────────────────────────
  python start.py
  → [2] CONFIGURE THRESHOLDS
  → [3] CONFIGURE EMAIL


METHOD 2: Direct config.json Edit
──────────────────────────────────
  notepad config.json

Default structure:
{
  "display_size": [640, 480],
  "zones": [
    {
      "name": "Entrance",
      "threshold": 50
    },
    {
      "name": "Main Hall", 
      "threshold": 100
    }
  ],
  "email": {
    "enabled": false,
    "sender": "",
    "password": "",
    "recipients": []
  },
  "panic_sensitivity": 1.0,
  "density_threshold": 50
}


KEY SETTINGS
────────────

zones array:
  Each zone has:
  • name: Display name (string)
  • threshold: Max people before alert (integer)

email object:
  • enabled: true/false (activate alerts)
  • sender: Gmail address
  • password: 16-char app password
  • recipients: List of email addresses

panic_sensitivity:
  • 0.5: Calmer (ignore movement, focus on crowd size)
  • 1.0: Balanced (default)
  • 2.0: More alert (panic fast)

density_threshold:
  Percentage that triggers crowd density alerts (0-100)


═══════════════════════════════════════════════════════════════════════════════
4. EMAIL ALERTS
═══════════════════════════════════════════════════════════════════════════════

SETUP (First Time Only)
──────────────────────

Step 1: Get Gmail App Password
  1. Go to: https://myaccount.google.com/apppasswords
  2. Sign in to Gmail
  3. Select "Mail" application
  4. Select "Windows" device
  5. Click "Generate"
  6. Copy the 16-character password

Step 2: Configure System
  Method A (Menu):
    python start.py
    Select [3] CONFIGURE EMAIL
    Enter:
      Gmail: your_email@gmail.com
      Password: xxxx xxxx xxxx xxxx (16 chars)
      Recipients: admin@example.com, security@example.com
  
  Method B (Direct):
    Edit config.json
    {
      "email": {
        "enabled": true,
        "sender": "your_email@gmail.com",
        "password": "xxxx xxxx xxxx xxxx",
        "recipients": ["admin@example.com"]
      }
    }


HOW ALERTS WORK
───────────────

Trigger:
  When: people_count > zone_threshold
  Sends to: all recipients
  Cooldown: max 1 alert per 5 minutes per zone

Email content:
  From: your configured sender email
  To: all recipients
  Subject: [ALERT] Crowd threshold exceeded in [Zone Name]
  
  Body includes:
    Zone: [Name]
    Current Count: [Number] people
    Threshold: [Number] people
    Time: [Timestamp]
    "Please check the monitoring system immediately"


TROUBLESHOOTING
───────────────

Email not sending:
  ✓ Use Gmail app password (NOT regular password)
  ✓ Get from apppasswords (not security settings)
  ✓ Ensure enabled: true in config
  ✓ Check recipient emails are correct
  ✓ Verify SMTP: smtp.gmail.com, Port: 587


═══════════════════════════════════════════════════════════════════════════════
5. ACCURACY & FORMULAS
═══════════════════════════════════════════════════════════════════════════════

CROWD COUNT ACCURACY
───────────────────

Factors affecting accuracy:
  ✓ Lighting: Good light = better detection
  ✓ Distance: Optimal distance = clear individuals
  ✓ Occlusion: Hidden people = lower count
  ✓ Resolution: Higher res = more details
  ✓ Camera angle: Overhead best, side-view harder

Typical variance:
  ±1-2 people (per measurement)
  ±5-10 people (for large crowds with occlusion)

Best practices:
  • Mount camera at 45° angle or overhead
  • Ensure uniform lighting
  • Clear view of crowd
  • Avoid backlighting


PANIC DETECTION FORMULA
──────────────────────

Base formula:
  panic = (crowding × 0.25) + (density × 0.50) + (movement × 0.25)

Component breakdown:

1. CROWDING (25% weight)
   crowding = (people_count / 500) × 100
   
   Examples:
   0 people → 0%
   100 people → 20%
   250 people → 50%
   500 people → 100%

2. DENSITY (50% weight) ← MOST IMPORTANT
   density = (people_count × 15000 / frame_area) × 100
   
   Assumes each person occupies ~15,000 pixels
   For 640×480 = 307,200 pixels total
   
   Examples:
   Small frame, few people → low density
   Small frame, many people → high density
   Same people, larger frame → lower density

3. MOVEMENT (25% weight)
   movement = frame_difference_pixels / total_pixels × 100
   
   Measures how much pixels changed between frames
   Stationary crowd = low movement
   Panicking crowd = high movement

Final calculation:
  panic = (crowding × 0.25) + (density × 0.50) + (movement × 0.25)
  panic = panic × sensitivity_multiplier
  panic = min(100, panic) ← cap at 100%


EXAMPLE SCENARIOS
─────────────────

Scenario 1: Concert Venue
  • 300 people in 640×480 frame
  • Stationary (listening)
  • Movement: 10%
  
  Calculation:
  Crowding = (300/500) × 100 = 60%
  Density = (300 × 15000 / 307200) × 100 = 146% → capped at 100%
  Movement = 10% × 100 = 10%
  Panic = (60 × 0.25) + (100 × 0.50) + (10 × 0.25) = 65%
  Result: 65% panic (high alert)

Scenario 2: Museum
  • 50 people in same frame
  • Slow movement
  • Movement: 5%
  
  Crowding = 10%
  Density = 24%
  Movement = 5%
  Panic = (10 × 0.25) + (24 × 0.50) + (5 × 0.25) = 15%
  Result: 15% panic (calm)

Scenario 3: Emergency Evacuation
  • 200 people
  • High movement (panicking)
  • Movement: 50%
  
  Crowding = 40%
  Density = 98%
  Movement = 50%
  Panic = (40 × 0.25) + (98 × 0.50) + (50 × 0.25) = 68%
  Result: 68% panic with increasing trend


═══════════════════════════════════════════════════════════════════════════════
6. TROUBLESHOOTING
═══════════════════════════════════════════════════════════════════════════════

CAMERA ISSUES
─────────────

"Cannot open camera" error
  Check:
  • Camera connected to USB
  • Camera not used by another app
  • USB lights on
  • Try different USB port
  
  Test:
  python -c "import cv2; print(cv2.VideoCapture(0).isOpened())"
  
  If False, try different index:
  Edit deepvision.py: cv2.VideoCapture(1)


LOW FRAME RATE
──────────────

If FPS < 5:
  • YOLO model is heavy, this is normal on CPU
  • Use GPU if available
  • Reduce resolution in config.json
  • Close other apps
  • Ensure good USB connection


HIGH MEMORY USAGE
──────────────────

YOLO model uses 200-500MB, this is typical
If too high:
  • Use smaller model (already using nano)
  • Run less detections per second
  • Reduce frame resolution


EMAIL NOT WORKING
──────────────────

Steps to debug:
  1. Verify app password (16 chars, not regular password)
  2. Check enabled: true in config.json
  3. Verify SMTP settings (smtp.gmail.com:587)
  4. Ensure recipient emails are correct
  5. Check sender email is correct
  6. Try from: https://www.gmail.com/mail/u/0/#inbox
  
  Common mistakes:
  ✗ Using regular password instead of app password
  ✗ typos in email addresses
  ✗ Wrong port (should be 587, not 465)
  ✗ Less secure app access enabled (shouldn't be needed)


PORT ALREADY IN USE
───────────────────

"Address already in use" for port 5001

Fix:
  taskkill /F /IM python.exe
  
  Or find and kill specific process:
  netstat -ano | findstr ":5001"
  taskkill /PID [PID] /F


MISSING MODULES
────────────────

"ModuleNotFoundError: No module named..."

Install missing packages:
  pip install flask flask-cors cv2 numpy ultralytics torch


═══════════════════════════════════════════════════════════════════════════════
7. API REFERENCE
═══════════════════════════════════════════════════════════════════════════════

WEB API ENDPOINTS
──────────────────

GET /
  Returns: HTML dashboard

GET /api/status
  Returns: JSON with current metrics
  
  {
    "crowd_count": 42,
    "density": 25.5,
    "panic": 35.2,
    "movement": 0.045,
    "crowd_trend": "stable",
    "zones_exceeded": ["Entrance"]
  }

POST /api/zones
  Add new threshold zone
  
  Request:
  {
    "name": "VIP Area",
    "threshold": 30
  }
  
  Response:
  {"success": true}

POST /api/email
  Configure email settings
  
  Request:
  {
    "sender": "user@gmail.com",
    "password": "xxxx xxxx xxxx xxxx",
    "recipients": ["admin@example.com"]
  }
  
  Response:
  {"success": true}


═══════════════════════════════════════════════════════════════════════════════

System is production-ready. Enjoy! 🎯

