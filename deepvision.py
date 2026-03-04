#!/usr/bin/env python3
"""
DEEPVISION - CROWD DETECTION SYSTEM
Complete, production-ready crowd counting with accurate panic detection and heatmap
"""

import cv2
import numpy as np
import threading
import time
from datetime import datetime
from collections import deque
import json
import os
from flask import Flask, render_template, render_template_string, jsonify, request
from flask_cors import CORS
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Try to import YOLO
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except:
    YOLO_AVAILABLE = False

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    def __init__(self):
        self.load()
    
    def load(self):
        """Load or create config file"""
        try:
            with open('config.json', 'r') as f:
                cfg = json.load(f)
        except:
            cfg = self.default_config()
            self.save(cfg)
        
        self.display_size = tuple(cfg.get('display_size', [640, 480]))
        self.zones = cfg.get('zones', [{'name': 'Main', 'threshold': 100}])
        self.email = cfg.get('email', {})
        self.panic_sensitivity = cfg.get('panic_sensitivity', 1.0)
        self.density_threshold = cfg.get('density_threshold', 50)
    
    def save(self, cfg=None):
        """Save config to file"""
        if cfg is None:
            cfg = {
                'display_size': list(self.display_size),
                'zones': self.zones,
                'email': self.email,
                'panic_sensitivity': self.panic_sensitivity,
                'density_threshold': self.density_threshold
            }
        with open('config.json', 'w') as f:
            json.dump(cfg, f, indent=2)
    
    @staticmethod
    def default_config():
        return {
            'display_size': [640, 480],
            'zones': [{'name': 'Main', 'threshold': 100}],
            'email': {
                'enabled': False,
                'smtp': 'smtp.gmail.com',
                'port': 587,
                'sender': '',
                'password': '',
                'recipients': []
            },
            'panic_sensitivity': 1.0,
            'density_threshold': 50
        }

config = Config()

# ============================================================================
# CROWD DETECTION ENGINE
# ============================================================================

class CrowdDetector:
    """Accurate crowd detection with YOLO fallback to edge detection"""
    
    def __init__(self):
        self.yolo_model = None
        self.confidence_threshold = 0.5
        self.use_yolo = YOLO_AVAILABLE
        
        if YOLO_AVAILABLE:
            try:
                self.yolo_model = YOLO('yolov8n.pt')
                print("✅ YOLO loaded successfully")
            except Exception as e:
                print(f"⚠️  YOLO loading failed: {e}")
                self.use_yolo = False
    
    def detect_people(self, frame):
        """Detect people in frame, returns count and bounding boxes"""
        if self.yolo_model and self.use_yolo:
            try:
                results = self.yolo_model(frame, verbose=False, conf=self.confidence_threshold)
                detections = results[0]
                
                # Get only person class (class 0)
                people_boxes = []
                if detections.boxes is not None:
                    for box in detections.boxes:
                        cls = int(box.cls)
                        if cls == 0:  # person class
                            conf = float(box.conf)
                            # Get xyxy coordinates
                            xyxy = box.xyxy[0].cpu().numpy()
                            x1, y1, x2, y2 = int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])
                            people_boxes.append((x1, y1, x2, y2, conf))
                
                return len(people_boxes), people_boxes
            except Exception as e:
                print(f"YOLO error: {e}")
                return self.detect_edge(frame)
        else:
            return self.detect_edge(frame)
    
    def detect_edge(self, frame):
        """Edge-based detection fallback"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter contours by size to estimate people
        people_contours = [c for c in contours if 500 < cv2.contourArea(c) < 50000]
        
        # Return estimated count and empty boxes (edge detection doesn't give precise boxes)
        return max(1, len(people_contours) // 3), []

detector = CrowdDetector()

# ============================================================================
# PANIC DETECTION ENGINE
# ============================================================================

class PanicDetector:
    """Detect panic based on crowd behavior metrics"""
    
    def __init__(self):
        self.crowd_history = deque(maxlen=30)
        self.movement_history = deque(maxlen=30)
        self.density_history = deque(maxlen=30)
        self.prev_frame = None
        self.sensitivity = config.panic_sensitivity
    
    def calculate_movement(self, frame):
        """Calculate movement intensity (0-1)"""
        if self.prev_frame is None:
            self.prev_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            return 0.0
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(self.prev_frame, gray)
        movement = np.mean(diff) / 255.0
        self.prev_frame = gray
        return movement
    
    def calculate_density(self, frame, people_count):
        """Calculate crowd density percentage"""
        h, w = frame.shape[:2]
        area = h * w
        # Assume each person occupies ~15000 pixels (rough estimate)
        density = min(100, (people_count * 15000 / area) * 100)
        return density
    
    def calculate_panic(self, people_count, density, movement):
        """
        Calculate panic level based on:
        1. Crowd size (more = more panic potential)
        2. Density (crowded = panic)
        3. Movement (erratic movement = panic)
        """
        panic = 0.0
        
        # Factor 1: Crowd size (25%)
        crowding_panic = min(100, (people_count / 500) * 100) * 0.25
        panic += crowding_panic
        
        # Factor 2: Density (50%)
        density_panic = min(100, density) * 0.50
        panic += density_panic
        
        # Factor 3: Movement intensity (25%)
        movement_panic = min(100, movement * 200) * 0.25
        panic += movement_panic
        
        # Apply sensitivity multiplier
        panic = panic * self.sensitivity
        panic = min(100, panic)
        
        return max(0, panic)
    
    def update(self, people_count, frame):
        """Update panic metrics"""
        movement = self.calculate_movement(frame)
        density = self.calculate_density(frame, people_count)
        panic = self.calculate_panic(people_count, density, movement)
        
        self.crowd_history.append(people_count)
        self.movement_history.append(movement)
        self.density_history.append(density)
        
        return {
            'crowd_count': people_count,
            'density': density,
            'movement': movement,
            'panic': panic,
            'crowd_trend': 'increasing' if len(self.crowd_history) > 5 and np.mean(list(self.crowd_history)[-5:]) > np.mean(list(self.crowd_history)[:5]) else 'stable'
        }

panic_detector = PanicDetector()

# ============================================================================
# HEATMAP GENERATOR
# ============================================================================

class HeatmapGenerator:
    """Generate crowd density heatmap"""
    
    def __init__(self, width=640, height=480):
        self.width = width
        self.height = height
        self.heatmap = np.zeros((height, width), dtype=np.float32)
        self.decay = 0.95  # Heatmap decay rate
    
    def update(self, people_boxes):
        """Update heatmap with detected people"""
        # Decay existing heatmap
        self.heatmap *= self.decay
        
        # Add Gaussian blobs for each person
        for x1, y1, x2, y2, conf in people_boxes:
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            w, h = x2 - x1, y2 - y1
            
            # Create Gaussian blob
            y, x = np.ogrid[-h:h, -w:w]
            gaussian = np.exp(-(x**2 + y**2) / (2 * (w/4)**2))
            
            # Add to heatmap (with clipping)
            y1_clip = max(0, cy - h)
            y2_clip = min(self.height, cy + h)
            x1_clip = max(0, cx - w)
            x2_clip = min(self.width, cx + w)
            
            gy1 = y1_clip - (cy - h)
            gy2 = gy1 + (y2_clip - y1_clip)
            gx1 = x1_clip - (cx - w)
            gx2 = gx1 + (x2_clip - x1_clip)
            
            self.heatmap[y1_clip:y2_clip, x1_clip:x2_clip] += gaussian[gy1:gy2, gx1:gx2] * conf
    
    def render(self, frame):
        """Render heatmap overlay on frame"""
        # Normalize heatmap to 0-255
        heatmap_viz = (self.heatmap / np.max(self.heatmap) * 255) if np.max(self.heatmap) > 0 else np.zeros_like(self.heatmap)
        heatmap_viz = heatmap_viz.astype(np.uint8)
        
        # Apply colormap
        heatmap_color = cv2.applyColorMap(heatmap_viz, cv2.COLORMAP_JET)
        
        # Blend with original frame
        result = cv2.addWeighted(frame, 0.7, heatmap_color, 0.3, 0)
        return result

heatmap = HeatmapGenerator(*config.display_size)

# ============================================================================
# EMAIL ALERT SYSTEM
# ============================================================================

class EmailAlerter:
    """Send email alerts"""
    
    def __init__(self, email_config):
        self.config = email_config
        self.last_alert = {}
        self.cooldown = 300  # 5 minutes
    
    def should_send(self, zone_name):
        """Check if enough time has passed since last alert for this zone"""
        now = time.time()
        last = self.last_alert.get(zone_name, 0)
        return now - last > self.cooldown
    
    def send_alert(self, zone_name, people_count, threshold):
        """Send email alert"""
        if not self.config.get('enabled') or not self.should_send(zone_name):
            return False
        
        try:
            sender = self.config['sender']
            password = self.config['password']
            recipients = self.config['recipients']
            
            if not sender or not password or not recipients:
                return False
            
            msg = MIMEMultipart()
            msg['From'] = sender
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = f"[ALERT] Crowd threshold exceeded in {zone_name}"
            
            body = f"""
CROWD LIMIT EXCEEDED

Zone: {zone_name}
Current Count: {people_count} people
Threshold: {threshold} people
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please check the monitoring system immediately.
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.config['smtp'], self.config['port']) as server:
                server.starttls()
                server.login(sender, password)
                server.send_message(msg)
            
            self.last_alert[zone_name] = time.time()
            print(f"📧 Alert sent for {zone_name}")
            return True
        
        except Exception as e:
            print(f"❌ Email error: {e}")
            return False

alerter = EmailAlerter(config.email)

# ============================================================================
# FLASK APPLICATION
# ============================================================================

app = Flask(__name__)
CORS(app)

class VideoStream:
    """Manage video streaming"""
    
    def __init__(self):
        self.cap = None
        self.running = False
        self.lock = threading.Lock()
        self.current_frame = None  # For web streaming
        self.current_stats = {
            'crowd_count': 0,
            'density': 0,
            'panic': 0,
            'movement': 0,
            'zones_exceeded': []
        }
    
    def start(self):
        """Start camera capture"""
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("❌ Cannot open camera")
            return False
        
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.display_size[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.display_size[1])
        self.cap.set(cv2.CAP_PROP_FPS, 15)
        
        self.running = True
        threading.Thread(target=self.process_frames, daemon=True).start()
        return True
    
    def process_frames(self):
        """Main video processing loop"""
        frame_count = 0
        
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                break
            
            try:
                frame = cv2.resize(frame, config.display_size)
                
                # Detect people
                people_count, people_boxes = detector.detect_people(frame)
                
                # Update panic detector
                panic_stats = panic_detector.update(people_count, frame)
                
                # Update heatmap
                heatmap.update(people_boxes)
                
                # Apply heatmap overlay
                frame_with_heatmap = heatmap.render(frame)
                
                # Draw bounding boxes
                for x1, y1, x2, y2, conf in people_boxes:
                    cv2.rectangle(frame_with_heatmap, (x1, y1), (x2, y2), (0, 255, 0), 2)
                
                # Add info panel (no overlap)
                h, w = frame_with_heatmap.shape[:2]
                
                # Top left panel
                cv2.rectangle(frame_with_heatmap, (0, 0), (300, 120), (0, 0, 0), -1)
                cv2.putText(frame_with_heatmap, f"People: {people_count}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(frame_with_heatmap, f"Density: {panic_stats['density']:.1f}%", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(frame_with_heatmap, f"Movement: {panic_stats['movement']:.2f}", (10, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                
                # Top right panel - Panic meter
                panic_level = panic_stats['panic']
                gauge_color = (0, 165, 255) if panic_level < 50 else (0, 0, 255)
                cv2.rectangle(frame_with_heatmap, (w-250, 0), (w, 120), (0, 0, 0), -1)
                cv2.putText(frame_with_heatmap, f"PANIC: {panic_level:.1f}%", (w-240, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, gauge_color, 2)
                
                # Panic bar
                bar_width = int((panic_level / 100) * 200)
                cv2.rectangle(frame_with_heatmap, (w-240, 50), (w-240+bar_width, 70), gauge_color, -1)
                cv2.rectangle(frame_with_heatmap, (w-240, 50), (w-40, 70), (100, 100, 100), 2)
                
                cv2.putText(frame_with_heatmap, f"Trend: {panic_stats['crowd_trend']}", (w-240, 110),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 255, 0), 1)
                
                # Bottom panel - Zone alerts
                zones_text = "Zones OK" if not panic_stats.get('zones_exceeded') else "ALERT:" + ", ".join(panic_stats['zones_exceeded'])
                cv2.rectangle(frame_with_heatmap, (0, h-40), (w, h), (0, 0, 0), -1)
                color = (0, 0, 255) if panic_stats.get('zones_exceeded') else (0, 255, 0)
                cv2.putText(frame_with_heatmap, zones_text, (10, h-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 1)
                
                # Check zone thresholds
                zones_exceeded = []
                for zone in config.zones:
                    if people_count > zone['threshold']:
                        zones_exceeded.append(zone['name'])
                        alerter.send_alert(zone['name'], people_count, zone['threshold'])
                
                panic_stats['zones_exceeded'] = zones_exceeded
                
                # Update state
                with threading_lock:
                    self.current_stats = panic_stats
                    self.current_frame = frame_with_heatmap
                
                frame_count += 1
                if frame_count % 30 == 0:
                    print(f"Frame {frame_count}: {people_count} people, Panic: {panic_level:.1f}%, Density: {panic_stats['density']:.1f}%")
            
            except Exception as e:
                print(f"Error processing frame: {e}")
                time.sleep(0.1)
    
    def stop(self):
        """Stop video stream"""
        self.running = False
        if self.cap:
            self.cap.release()

video_stream = VideoStream()
threading_lock = threading.Lock()
current_frame = None

@app.route('/')
def index():
    """Complete single-page dashboard with all features"""
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DeepVision - Crowd Detection System</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                color: #fff;
                min-height: 100vh;
                padding: 20px;
            }
            
            .container {
                max-width: 2000px;
                margin: 0 auto;
            }
            
            header {
                text-align: center;
                margin-bottom: 30px;
                padding: 20px;
                background: rgba(255,255,255,0.05);
                border-radius: 15px;
                border: 1px solid rgba(255,255,255,0.1);
            }
            
            h1 {
                font-size: 2.5em;
                color: #00ff88;
                margin-bottom: 10px;
                text-shadow: 0 0 20px rgba(0,255,136,0.5);
            }
            
            .status-bar {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 15px;
                margin-bottom: 20px;
            }
            
            .stat {
                background: rgba(255,255,255,0.08);
                padding: 20px;
                border-radius: 10px;
                border-left: 4px solid #00ff88;
                text-align: center;
            }
            
            .stat-label {
                font-size: 0.9em;
                color: #aaa;
                margin-bottom: 10px;
                text-transform: uppercase;
            }
            
            .stat-value {
                font-size: 2.5em;
                font-weight: bold;
                color: #00ff88;
                font-family: 'Courier New', monospace;
            }
            
            .stat-unit {
                font-size: 0.8em;
                color: #888;
                margin-top: 5px;
            }
            
            .main-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
                margin-bottom: 20px;
            }
            
            .panel {
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 12px;
                padding: 20px;
                backdrop-filter: blur(10px);
            }
            
            .panel-title {
                font-size: 1.3em;
                color: #00ff88;
                margin-bottom: 15px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            
            .icon {
                font-size: 1.5em;
            }
            
            .panic-meter {
                width: 100%;
                height: 30px;
                background: #333;
                border-radius: 15px;
                overflow: hidden;
                margin: 15px 0;
                border: 1px solid #555;
            }
            
            .panic-fill {
                height: 100%;
                background: linear-gradient(90deg, #00ff00, #ffff00, #ff6600, #ff0000);
                width: 0%;
                transition: width 0.3s ease;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #000;
                font-weight: bold;
                font-size: 0.8em;
            }
            
            .heatmap {
                width: 100%;
                height: 250px;
                background: linear-gradient(to bottom, #0000ff, #00ffff, #ffff00, #ff0000);
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 1.1em;
                margin: 15px 0;
            }
            
            .zones-container {
                max-height: 300px;
                overflow-y: auto;
            }
            
            .zone-item {
                background: rgba(0,255,136,0.1);
                padding: 12px;
                margin-bottom: 10px;
                border-radius: 8px;
                border-left: 3px solid #00ff88;
                display: grid;
                grid-template-columns: 1fr 80px 80px;
                gap: 10px;
                align-items: center;
            }
            
            .zone-item.alert {
                background: rgba(255,0,0,0.2);
                border-left-color: #ff0000;
            }
            
            .zone-name {
                font-weight: bold;
            }
            
            .zone-input {
                background: #1a1a1a;
                border: 1px solid #444;
                color: #fff;
                padding: 8px;
                border-radius: 5px;
                width: 100%;
            }
            
            button {
                background: linear-gradient(135deg, #00ff88, #00cc6f);
                color: #000;
                border: none;
                padding: 12px 20px;
                border-radius: 8px;
                cursor: pointer;
                font-weight: bold;
                transition: all 0.3s;
                margin: 5px;
            }
            
            button:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 20px rgba(0,255,136,0.4);
            }
            
            button.danger {
                background: linear-gradient(135deg, #ff6b6b, #ff5252);
                color: white;
            }
            
            input, textarea {
                background: #1a1a1a;
                border: 1px solid #444;
                color: #fff;
                padding: 10px;
                border-radius: 5px;
                width: 100%;
                margin: 5px 0;
                font-family: inherit;
            }
            
            label {
                display: block;
                margin-top: 10px;
                color: #aaa;
                font-size: 0.9em;
            }
            
            .alert-box {
                background: rgba(255,0,0,0.2);
                border: 1px solid #ff6b6b;
                padding: 15px;
                border-radius: 8px;
                margin: 10px 0;
                color: #ff9999;
            }
            
            .success-box {
                background: rgba(0,255,136,0.2);
                border: 1px solid #00ff88;
                padding: 15px;
                border-radius: 8px;
                margin: 10px 0;
                color: #00ff88;
            }
            
            .trend {
                display: inline-block;
                padding: 5px 10px;
                background: rgba(0,255,136,0.2);
                border-radius: 5px;
                font-size: 0.9em;
                margin-top: 10px;
            }
            
            .trend.up {
                color: #ff6b6b;
            }
            
            .trend.stable {
                color: #00ff88;
            }
            
            @media (max-width: 1400px) {
                .main-grid {
                    grid-template-columns: 1fr;
                }
                
                .status-bar {
                    grid-template-columns: repeat(2, 1fr);
                }
            }
            
            .movement-indicator {
                width: 100%;
                height: 20px;
                background: #333;
                border-radius: 10px;
                overflow: hidden;
                margin: 10px 0;
            }
            
            .movement-bar {
                height: 100%;
                background: linear-gradient(90deg, #00ff00, #ffff00, #ff0000);
                width: 0%;
                transition: width 0.3s ease;
            }
            
            .density-level {
                color: #aaa;
                font-size: 0.9em;
                margin-top: 10px;
            }
            
            .config-section {
                margin-top: 20px;
                padding-top: 20px;
                border-top: 1px solid rgba(255,255,255,0.1);
            }
            
            .full-width {
                grid-column: 1 / -1;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>🎯 DeepVision - Real-Time Crowd Detection</h1>
                <p>Smart crowd monitoring with panic detection and alerts</p>
            </header>
            
            <!-- Real-time Metrics -->
            <div class="status-bar">
                <div class="stat">
                    <div class="stat-label">👥 People Count</div>
                    <div class="stat-value" id="crowdCount">0</div>
                    <div class="stat-unit">individuals</div>
                </div>
                
                <div class="stat">
                    <div class="stat-label">📊 Crowd Density</div>
                    <div class="stat-value" id="density">0</div>
                    <div class="stat-unit">percent</div>
                </div>
                
                <div class="stat">
                    <div class="stat-label">⚠️ Panic Level</div>
                    <div class="stat-value" id="panic">0</div>
                    <div class="stat-unit">percent</div>
                </div>
                
                <div class="stat">
                    <div class="stat-label">🎬 Movement</div>
                    <div class="stat-value" id="movement">0</div>
                    <div class="stat-unit">intensity</div>
                </div>
            </div>
            
            <!-- Main Content Grid -->
            <div class="main-grid">
                <!-- Panic Detection Panel -->
                <div class="panel">
                    <div class="panel-title">
                        <span class="icon">⚠️</span> Panic Detection System
                    </div>
                    
                    <div style="margin: 20px 0;">
                        <label style="margin-bottom: 5px;">Panic Level</label>
                        <div class="panic-meter">
                            <div class="panic-fill" id="panicFill" style="width: 0%;">0%</div>
                        </div>
                    </div>
                    
                    <div style="margin: 20px 0;">
                        <label>Movement Intensity</label>
                        <div class="movement-indicator">
                            <div class="movement-bar" id="movementBar" style="width: 0%;"></div>
                        </div>
                        <div style="color: #aaa; font-size: 0.85em; margin-top: 5px;">
                            <span id="movementText">0.000</span> | 
                            <span id="trendIndicator">Stable</span>
                        </div>
                    </div>
                    
                    <div style="margin-top: 20px; padding: 15px; background: rgba(0,255,136,0.1); border-radius: 8px;">
                        <strong>Detection Algorithm:</strong>
                        <ul style="margin-top: 10px; margin-left: 20px; color: #aaa; font-size: 0.9em;">
                            <li>Crowd Size: 25% weight</li>
                            <li>Spatial Density: 50% weight</li>
                            <li>Movement: 25% weight</li>
                        </ul>
                    </div>
                </div>
                
                <!-- Live Webcam Feed -->
                <div class="panel">
                    <div class="panel-title">
                        <span class="icon">📹</span> Live Camera Feed
                    </div>
                    
                    <div style="width: 100%; border-radius: 10px; overflow: hidden; background: #000;">
                        <img id="videoFeed" src="/video_feed" style="width: 100%; height: auto; display: block; border-radius: 10px;" alt="Live feed">
                    </div>
                    
                    <div style="margin-top: 15px; padding: 12px; background: rgba(0,255,136,0.1); border-radius: 8px; font-size: 0.9em; color: #aaa;">
                        <strong>🎬 What you're seeing:</strong>
                        <ul style="margin-top: 8px; margin-left: 20px;">
                            <li>🟩 Green boxes = Detected people</li>
                            <li>🔥 Red overlay = Crowd density heatmap</li>
                            <li>📊 Top-left stats = Live metrics</li>
                            <li>⚠️ Top-right panic meter = Threat level</li>
                            <li>📍 Bottom alerts = Zone threshold status</li>
                        </ul>
                    </div>
                </div>
                
                <!-- Heatmap Panel -->
                <div class="panel">
                    <div class="panel-title">
                        <span class="icon">📍</span> Threshold Zones
                    </div>
                    
                    <div class="zones-container" id="zonesContainer">
                        <!-- Zones will be populated here -->
                    </div>
                    
                    <div class="config-section">
                        <h3 style="color: #00ff88; margin-bottom: 10px;">➕ Add New Zone</h3>
                        <input type="text" id="newZoneName" placeholder="Zone name (e.g., Entrance)" style="margin-bottom: 10px;">
                        <input type="number" id="newZoneThreshold" placeholder="Crowd threshold (people)" style="margin-bottom: 10px;">
                        <button onclick="addZone()" style="width: 100%;">Add Zone</button>
                    </div>
                </div>
                
                <!-- Email Configuration Panel -->
                <div class="panel">
                    <div class="panel-title">
                        <span class="icon">📧</span> Email Alert System
                    </div>
                    
                    <label>Gmail Address:</label>
                    <input type="email" id="emailSender" placeholder="your_email@gmail.com">
                    
                    <label>App Password (16 chars):</label>
                    <input type="password" id="emailPassword" placeholder="xxxx xxxx xxxx xxxx">
                    
                    <label>Recipients (comma-separated):</label>
                    <textarea id="emailRecipients" placeholder="admin@example.com, security@example.com" style="height: 80px;"></textarea>
                    
                    <div style="margin: 15px 0;">
                        <label style="display: flex; align-items: center;">
                            <input type="checkbox" id="emailEnabled" style="width: auto; margin-right: 10px;">
                            Enable email alerts
                        </label>
                    </div>
                    
                    <button onclick="saveEmailConfig()" style="width: 100%;">💾 Save Configuration</button>
                    <button onclick="testEmail()" style="width: 100%; background: linear-gradient(135deg, #6b9bff, #6b7bff);">📤 Send Test Email</button>
                    
                    <div id="emailStatus"></div>
                    
                    <div style="margin-top: 15px; padding: 15px; background: rgba(0,100,200,0.1); border-radius: 8px; border-left: 3px solid #0064ff;">
                        <strong>How to get Gmail app password:</strong>
                        <ol style="margin-top: 10px; margin-left: 20px; color: #aaa; font-size: 0.9em;">
                            <li>Go to myaccount.google.com/apppasswords</li>
                            <li>Select "Mail" app, "Windows" device</li>
                            <li>Click "Generate"</li>
                            <li>Copy the 16-char password</li>
                        </ol>
                    </div>
                </div>
                
                <!-- System Info Panel (Full Width) -->
                <div class="panel full-width">
                    <div class="panel-title">
                        <span class="icon">⚙️</span> System Information & Settings
                    </div>
                    
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">
                        <div>
                            <strong>Panic Sensitivity:</strong>
                            <input type="range" id="panicSensitivity" min="0.5" max="2.0" step="0.1" value="1.0" style="width: 100%; margin: 10px 0;">
                            <div id="sensitivityValue" style="text-align: center; color: #aaa;">1.0x</div>
                        </div>
                        
                        <div>
                            <strong>Detection Status:</strong>
                            <div style="margin-top: 15px; padding: 10px; background: rgba(0,255,136,0.2); border-radius: 5px;">
                                <span id="detectionStatus">🟢 Active</span>
                            </div>
                        </div>
                        
                        <div>
                            <strong>Last Updated:</strong>
                            <div style="margin-top: 15px; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 5px;">
                                <span id="lastUpdate" style="color: #aaa; font-family: monospace;">--:--:--</span>
                            </div>
                        </div>
                    </div>
                    
                    <div style="margin-top: 20px;">
                        <h3 style="color: #00ff88; margin-bottom: 10px;">📹 Load Video File</h3>
                        <input type="file" id="videoFile" accept="video/*" style="margin-bottom: 10px;">
                        <button onclick="uploadVideo()" style="width: 100%; background: linear-gradient(135deg, #6b9bff, #6b7bff);">📤 Load Video</button>
                        <div id="uploadStatus" style="margin-top: 10px;"></div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            // Update metrics every 1 second
            setInterval(updateMetrics, 1000);
            
            // Update panic sensitivity display
            document.getElementById('panicSensitivity').addEventListener('input', (e) => {
                document.getElementById('sensitivityValue').textContent = e.target.value + 'x';
            });
            
            async function updateMetrics() {
                try {
                    const response = await fetch('/api/status');
                    const data = await response.json();
                    
                    // Update stats
                    document.getElementById('crowdCount').textContent = data.crowd_count;
                    document.getElementById('density').textContent = Math.round(data.density);
                    document.getElementById('panic').textContent = Math.round(data.panic);
                    document.getElementById('movement').textContent = data.movement.toFixed(3);
                    
                    // Update panic meter
                    const panicFill = document.getElementById('panicFill');
                    panicFill.style.width = data.panic + '%';
                    panicFill.textContent = Math.round(data.panic) + '%';
                    
                    // Update movement bar
                    const movementBar = document.getElementById('movementBar');
                    movementBar.style.width = Math.min(100, data.movement * 100) + '%';
                    document.getElementById('movementText').textContent = data.movement.toFixed(3);
                    
                    // Update trend
                    const trend = data.crowd_trend === 'increasing' ? '↗️ Increasing' : '→ Stable';
                    const trendClass = data.crowd_trend === 'increasing' ? 'up' : 'stable';
                    document.getElementById('trendIndicator').innerHTML = '<span class="trend ' + trendClass + '">' + trend + '</span>';
                    
                    // Update zones
                    updateZones(data.zones_exceeded);
                    
                    // Update last update time
                    const now = new Date();
                    document.getElementById('lastUpdate').textContent = now.toLocaleTimeString();
                    
                    // Draw heatmap
                    drawHeatmap(data.density, data.crowd_count);
                    
                } catch (error) {
                    console.error('Error fetching metrics:', error);
                }
            }
            
            function updateZones(zonesExceeded) {
                const container = document.getElementById('zonesContainer');
                fetch('/api/zones').then(r => r.json()).then(data => {
                    container.innerHTML = '';
                    data.zones.forEach(zone => {
                        const isAlert = zonesExceeded.includes(zone.name);
                        container.innerHTML += `
                            <div class="zone-item ${isAlert ? 'alert' : ''}">
                                <span class="zone-name">${zone.name}</span>
                                <input type="text" class="zone-input" value="${zone.threshold}" readonly>
                                <button class="danger" onclick="removeZone('${zone.name}')" style="margin: 0; padding: 8px;">🗑️</button>
                            </div>
                        `;
                    });
                });
            }
            
            function drawHeatmap(density, crowdCount) {
                const canvas = document.getElementById('heatmapCanvas');
                const ctx = canvas.getContext('2d');
                
                // Simple gradient heatmap
                const gradient = ctx.createLinearGradient(0, 0, canvas.width, 0);
                gradient.addColorStop(0, '#0000ff');
                gradient.addColorStop(0.33, '#00ff00');
                gradient.addColorStop(0.66, '#ffff00');
                gradient.addColorStop(1, '#ff0000');
                
                ctx.fillStyle = gradient;
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                
                // Add text
                ctx.fillStyle = '#fff';
                ctx.font = 'bold 16px Arial';
                ctx.textAlign = 'center';
                ctx.fillText(`Density: ${Math.round(density)}% | People: ${crowdCount}`, canvas.width/2, canvas.height/2);
            }
            
            async function addZone() {
                const name = document.getElementById('newZoneName').value.trim();
                const threshold = parseInt(document.getElementById('newZoneThreshold').value);
                
                if (!name || !threshold) {
                    alert('Please enter zone name and threshold');
                    return;
                }
                
                try {
                    await fetch('/api/zones', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name, threshold })
                    });
                    
                    document.getElementById('newZoneName').value = '';
                    document.getElementById('newZoneThreshold').value = '';
                    updateZones([]);
                } catch (error) {
                    console.error('Error adding zone:', error);
                }
            }
            
            async function removeZone(name) {
                if (!confirm(`Remove zone "${name}"?`)) return;
                
                try {
                    await fetch('/api/zones/' + name, { method: 'DELETE' });
                    updateZones([]);
                } catch (error) {
                    console.error('Error removing zone:', error);
                }
            }
            
            async function saveEmailConfig() {
                const config = {
                    enabled: document.getElementById('emailEnabled').checked,
                    sender: document.getElementById('emailSender').value,
                    password: document.getElementById('emailPassword').value,
                    recipients: document.getElementById('emailRecipients').value.split(',').map(e => e.trim())
                };
                
                try {
                    const response = await fetch('/api/email', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(config)
                    });
                    
                    const result = await response.json();
                    const statusDiv = document.getElementById('emailStatus');
                    statusDiv.className = 'success-box';
                    statusDiv.textContent = '✅ Email configuration saved!';
                    setTimeout(() => statusDiv.innerHTML = '', 3000);
                } catch (error) {
                    const statusDiv = document.getElementById('emailStatus');
                    statusDiv.className = 'alert-box';
                    statusDiv.textContent = '❌ Error saving configuration';
                }
            }
            
            async function testEmail() {
                try {
                    await fetch('/api/email/test', { method: 'POST' });
                    const statusDiv = document.getElementById('emailStatus');
                    statusDiv.className = 'success-box';
                    statusDiv.textContent = '✅ Test email sent!';
                    setTimeout(() => statusDiv.innerHTML = '', 3000);
                } catch (error) {
                    const statusDiv = document.getElementById('emailStatus');
                    statusDiv.className = 'alert-box';
                    statusDiv.textContent = '❌ Error sending test email';
                }
            }
            
            async function uploadVideo() {
                const fileInput = document.getElementById('videoFile');
                const file = fileInput.files[0];
                
                if (!file) {
                    alert('Please select a video file');
                    return;
                }
                
                const statusDiv = document.getElementById('uploadStatus');
                statusDiv.className = '';
                statusDiv.textContent = '⏳ Uploading...';
                
                const formData = new FormData();
                formData.append('video', file);
                
                try {
                    const response = await fetch('/api/upload_video', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        statusDiv.className = 'success-box';
                        statusDiv.textContent = '✅ Video loaded! Now processing...';
                        fileInput.value = '';
                        setTimeout(() => statusDiv.innerHTML = '', 3000);
                    } else {
                        statusDiv.className = 'alert-box';
                        statusDiv.textContent = '❌ ' + (result.error || 'Error uploading video');
                    }
                } catch (error) {
                    statusDiv.className = 'alert-box';
                    statusDiv.textContent = '❌ Upload failed: ' + error.message;
                }
            }
            
            // Load zones and email config on startup
            window.addEventListener('load', () => {
                updateZones([]);
                fetch('/api/email').then(r => r.json()).then(data => {
                    document.getElementById('emailEnabled').checked = data.enabled;
                    document.getElementById('emailSender').value = data.sender || '';
                    document.getElementById('emailRecipients').value = (data.recipients || []).join(', ');
                });
            });
        </script>
    </body>
    </html>
    ''')

@app.route('/api/status')
def api_status():
    """Return current status"""
    with threading_lock:
        return jsonify({
            'crowd_count': video_stream.current_stats.get('crowd_count', 0),
            'density': video_stream.current_stats.get('density', 0),
            'panic': video_stream.current_stats.get('panic', 0),
            'movement': video_stream.current_stats.get('movement', 0),
            'crowd_trend': video_stream.current_stats.get('crowd_trend', 'stable'),
            'zones_exceeded': video_stream.current_stats.get('zones_exceeded', [])
        })

@app.route('/api/zones', methods=['GET'])
def api_zones_get():
    """Get all zones"""
    return jsonify({'zones': config.zones})

@app.route('/api/zones', methods=['POST'])
def api_zones_post():
    """Add new zone"""
    data = request.json
    config.zones.append({
        'name': data['name'],
        'threshold': data['threshold']
    })
    config.save()
    return jsonify({'success': True})

@app.route('/api/zones/<name>', methods=['DELETE'])
def api_zones_delete(name):
    """Delete a zone"""
    config.zones = [z for z in config.zones if z['name'] != name]
    config.save()
    return jsonify({'success': True})

@app.route('/api/email', methods=['GET'])
def api_email_get():
    """Get email configuration"""
    return jsonify({
        'enabled': config.email.get('enabled', False),
        'sender': config.email.get('sender', ''),
        'recipients': config.email.get('recipients', [])
    })

@app.route('/api/email', methods=['POST'])
def api_email_post():
    """Configure email"""
    data = request.json
    config.email = {
        'enabled': data.get('enabled', True),
        'smtp': 'smtp.gmail.com',
        'port': 587,
        'sender': data['sender'],
        'password': data['password'],
        'recipients': data['recipients']
    }
    config.save()
    return jsonify({'success': True})

@app.route('/api/email/test', methods=['POST'])
def api_email_test():
    """Send test email"""
    if not config.email.get('enabled'):
        return jsonify({'error': 'Email not configured'}), 400
    
    try:
        alerter.send_alert('TEST', 100, 50)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/upload_video', methods=['POST'])
def api_upload_video():
    """Upload and process video file"""
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        # Save uploaded file
        upload_dir = 'uploaded_videos'
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        
        video_path = os.path.join(upload_dir, file.filename)
        file.save(video_path)
        
        # Stop current camera stream
        global video_stream
        video_stream.stop()
        
        # Restart with video file
        video_stream.cap = cv2.VideoCapture(video_path)
        if not video_stream.cap.isOpened():
            return jsonify({'error': 'Cannot open video file'}), 400
        
        video_stream.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.display_size[0])
        video_stream.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.display_size[1])
        video_stream.running = True
        threading.Thread(target=video_stream.process_frames, daemon=True).start()
        
        return jsonify({'success': True, 'message': f'Video {file.filename} loaded'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/video_feed')
def video_feed():
    """Stream video feed as MJPEG"""
    def generate():
        while True:
            with threading_lock:
                frame = video_stream.current_frame
            
            if frame is None:
                continue
            
            # Encode frame to JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
            
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n'
                   b'Content-Length: ' + str(len(frame_bytes)).encode() + b'\r\n\r\n' +
                   frame_bytes + b'\r\n')
            time.sleep(0.033)  # ~30 FPS
    
    return app.response_class(generate(),
                            mimetype='multipart/x-mixed-replace; boundary=frame')

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "="*70)
    print("🎯 DEEPVISION - CROWD DETECTION SYSTEM")
    print("="*70)
    
    if not video_stream.start():
        print("❌ Failed to start video stream")
        return
    
    print("✅ System started")
    print("📱 Open browser: http://localhost:5001")
    
    try:
        app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print("\n🛑 Stopping system...")
        video_stream.stop()

if __name__ == '__main__':
    main()
