#!/usr/bin/env python3
"""
DEEPVISION LAUNCHER - Simple menu interface
"""

import subprocess
import sys
import json
import os

def show_menu():
    print("\n" + "="*70)
    print("🎯 DEEPVISION CROWD DETECTION SYSTEM")
    print("="*70)
    print("\n[1] START SYSTEM (Real-time Detection)")
    print("[2] CONFIGURE THRESHOLDS (Add/Edit zones)")
    print("[3] CONFIGURE EMAIL (Setup alerts)")
    print("[4] CHECK CONFIG (View current settings)")
    print("[5] QUIT")
    print("\n" + "-"*70)
    return input("Select (1-5): ").strip()

def configure_thresholds():
    """Configure crowd thresholds"""
    print("\n⚙️  THRESHOLD CONFIGURATION")
    print("-"*70)
    
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except:
        config = {'zones': []}
    
    print("\nCurrent zones:")
    for i, zone in enumerate(config.get('zones', []), 1):
        print(f"  {i}. {zone['name']}: {zone['threshold']} people")
    
    print("\n[1] Add zone")
    print("[2] Remove zone")
    print("[3] Back to menu")
    choice = input("Select: ").strip()
    
    if choice == '1':
        name = input("Zone name (e.g., Entrance): ").strip()
        threshold = int(input("Crowd threshold (people): ").strip())
        config.setdefault('zones', []).append({'name': name, 'threshold': threshold})
        print(f"✅ Added zone: {name}")
    elif choice == '2':
        idx = int(input("Zone number to remove: ").strip()) - 1
        if 0 <= idx < len(config.get('zones', [])):
            removed = config['zones'].pop(idx)
            print(f"✅ Removed: {removed['name']}")
    
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=2)

def configure_email():
    """Configure email alerts"""
    print("\n📧 EMAIL CONFIGURATION")
    print("-"*70)
    print("Setup email alerts when crowd threshold is exceeded")
    print("\nInstruction: Use Gmail app password (not regular password)")
    print("Get it from: https://myaccount.google.com/apppasswords\n")
    
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except:
        config = {}
    
    enabled = input("Enable email alerts? (y/n): ").lower() == 'y'
    
    if enabled:
        sender = input("Gmail address: ").strip()
        password = input("App password (16 chars): ").strip()
        recipients = input("Recipients (comma-separated): ").strip()
        
        config['email'] = {
            'enabled': True,
            'smtp': 'smtp.gmail.com',
            'port': 587,
            'sender': sender,
            'password': password,
            'recipients': [r.strip() for r in recipients.split(',')]
        }
        print("✅ Email configured")
    else:
        config['email'] = {'enabled': False}
        print("⚠️  Email alerts disabled")
    
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=2)

def view_config():
    """Show current configuration"""
    print("\n📋 CURRENT CONFIGURATION")
    print("-"*70)
    
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except:
        config = {}
    
    print(f"\nZones ({len(config.get('zones', []))} configured):")
    for zone in config.get('zones', []):
        print(f"  • {zone['name']}: {zone['threshold']} people")
    
    email = config.get('email', {})
    if email.get('enabled'):
        print(f"\nEmail Alerts: ENABLED")
        print(f"  • From: {email.get('sender', 'N/A')}")
        print(f"  • Recipients: {len(email.get('recipients', []))} people")
    else:
        print(f"\nEmail Alerts: DISABLED")
    
    print(f"\nDisplay Size: {config.get('display_size', [640, 480])}")
    print(f"Panic Sensitivity: {config.get('panic_sensitivity', 1.0)}")

def start_system():
    """Start the detection system"""
    print("\n" + "="*70)
    print("🚀 STARTING DEEPVISION SYSTEM")
    print("="*70)
    print("\nLoading models (may take 30-60 seconds)...")
    print("📱 Browser will open to: http://localhost:5001\n")
    
    try:
        subprocess.run([sys.executable, 'deepvision.py'])
    except KeyboardInterrupt:
        print("\n\n🛑 System stopped")
    except Exception as e:
        print(f"\n❌ Error: {e}")

def main():
    """Main menu loop"""
    while True:
        choice = show_menu()
        
        if choice == '1':
            start_system()
        elif choice == '2':
            configure_thresholds()
        elif choice == '3':
            configure_email()
        elif choice == '4':
            view_config()
        elif choice == '5':
            print("\n👋 Goodbye!")
            break
        else:
            print("❌ Invalid option")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
