from flask import Flask, request, Response, render_template_string, abort
import threading
import time
import os
import requests
import json

app = Flask(__name__)

# Your ESP32 Firebase URL (replace with your actual Firebase URL)
FIREBASE_URL = "https://smarthome-78a97-default-rtdb.asia-southeast1.firebasedatabase.app/"

UPLOAD_TOKEN = os.getenv("UPLOAD_TOKEN", "changeme")  # ESP → /upload
FLAG_TOKEN   = os.getenv("FLAG_TOKEN",   "changeme")  # dashboard & ESP → /flag /request

latest_lock  = threading.Lock()
latest_jpeg  = b""
need_frame   = False
current_bus  = "Bus1"  # Default selected bus

# Bus control data
bus_states = {
    "Bus1": {"cam": 0},
    "Bus2": {"cam": 0},
    "Bus3": {"cam": 0},
    "Bus4": {"cam": 0},
    "Bus5": {"cam": 0}
}

# Firebase helper functions
def write_to_firebase(path, data):
    """Write data to Firebase Realtime Database"""
    try:
        url = f"{FIREBASE_URL.rstrip('/')}/{path}.json"
        response = requests.put(url, json=data)
        print(f"🔥 Firebase PUT {path} = {data} → Status: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Firebase write error: {e}")
        return False

def read_from_firebase(path):
    """Read data from Firebase Realtime Database"""
    try:
        url = f"{FIREBASE_URL.rstrip('/')}/{path}.json"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"❌ Firebase read error: {e}")
        return None

# ───────── Enhanced HTML dashboard ─────────
HTML = """
<!doctype html>
<html>
<head>
    <meta charset='utf-8'>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BUBT VTS Camera Control</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1000px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
            background: linear-gradient(45deg, #fff, #f0f0f0);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .firebase-status {
            margin-top: 15px;
            padding: 12px;
            background: rgba(52, 152, 219, 0.2);
            border-radius: 8px;
            font-size: 0.9em;
            border-left: 4px solid #3498db;
        }
        
        .controls {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 20px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }
        
        .update-btn {
            padding: 12px 30px;
            font-size: 1.1em;
            font-weight: 600;
            border: none;
            border-radius: 12px;
            background: linear-gradient(45deg, #ff6b6b, #ee5a24);
            color: white;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(238, 90, 36, 0.4);
        }
        
        .update-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 6px 25px rgba(238, 90, 36, 0.6);
        }
        
        .update-btn:active {
            transform: translateY(-1px);
        }
        
        .bus-status {
            margin-bottom: 30px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
        }
        
        .bus-card {
            background: rgba(255, 255, 255, 0.1);
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            transition: all 0.3s ease;
            border: 2px solid transparent;
            cursor: pointer;
            position: relative;
            overflow: hidden;
        }
        
        .bus-card:hover {
            background: rgba(255, 255, 255, 0.2);
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
        }
        
        .bus-card.active {
            background: rgba(46, 204, 113, 0.3);
            border-color: rgba(46, 204, 113, 0.8);
            transform: scale(1.05);
            box-shadow: 0 8px 30px rgba(46, 204, 113, 0.4);
        }
        
        .bus-card.active:hover {
            transform: scale(1.05) translateY(-3px);
        }
        
        .bus-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(270deg, transparent, rgba(255, 255, 255, 0.6), transparent);
            transform: translateX(-100%);
            transition: transform 0.6s ease;
        }
        
        .bus-card:hover::before {
            transform: translateX(100%);
        }
        
        .bus-card h3 {
            margin-bottom: 10px;
            font-size: 1.3em;
            font-weight: 700;
        }
        
        .bus-card .status {
            font-size: 1em;
            font-weight: 600;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        
        .status-icon {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
        }
        
        .status-active {
            background: #2ecc71;
            box-shadow: 0 0 10px rgba(46, 204, 113, 0.8);
            animation: pulse-green 2s infinite;
        }
        
        .status-inactive {
            background: #e74c3c;
        }
        
        @keyframes pulse-green {
            0% { box-shadow: 0 0 10px rgba(46, 204, 113, 0.8); }
            50% { box-shadow: 0 0 20px rgba(46, 204, 113, 1); }
            100% { box-shadow: 0 0 10px rgba(46, 204, 113, 0.8); }
        }
        
        .camera-container {
            text-align: center;
            position: relative;
            margin-top: 20px;
        }
        
        .camera-frame {
            display: inline-block;
            padding: 10px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            transition: all 0.3s ease;
            width: 100%;
            max-width: 600px;
            height: 400px;
            overflow: hidden;
        }
        
        .camera-frame:hover {
            transform: scale(1.02);
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
        }
        
        #camera-img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: 10px;
            transform: rotate(270deg);
            transition: all 0.3s ease;
            background: #2c3e50;
        }
        
        .no-image {
            width: 100%;
            height: 100%;
            background: linear-gradient(45deg, #34495e, #2c3e50);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            font-size: 1.2em;
            color: #bdc3c7;
        }
        
        .no-image-icon {
            font-size: 3em;
            margin-bottom: 10px;
            opacity: 0.5;
        }
        
        .status-indicator {
            position: absolute;
            top: 20px;
            right: 20px;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: 600;
            animation: pulse 2s infinite;
        }
        
        .status-live {
            background: rgba(46, 204, 113, 0.9);
        }
        
        .status-offline {
            background: rgba(231, 76, 60, 0.9);
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }
        
        .loading {
            display: none;
            text-align: center;
            margin-top: 20px;
        }
        
        .spinner {
            border: 3px solid rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            border-top: 3px solid #fff;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .debug-info {
            margin-top: 20px;
            padding: 15px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 10px;
            font-family: monospace;
            font-size: 0.8em;
            text-align: left;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 20px;
            }
            
            .header h1 {
                font-size: 2em;
            }
            
            .controls {
                flex-direction: column;
                gap: 15px;
            }
            
            .camera-frame {
                height: 300px;
            }
            
            .bus-status {
                grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
                gap: 10px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚌 BUBT VTS Camera Control</h1>
            <div class="firebase-status">
                🔥 Connected to Firebase: smarthome-78a97-default-rtdb.asia-southeast1.firebasedatabase.app
            </div>
        </div>
        
        <div class="bus-status" id="busStatus">
            <!-- Bus status cards will be populated by JavaScript -->
        </div>
        
        <div class="controls">
            <button class="update-btn" onclick="requestFrame()">
                📸 Force Update
            </button>
        </div>
        
        <div class="camera-container">
            <div class="status-indicator status-offline" id="statusIndicator">🔴 OFFLINE</div>
            <div class="camera-frame" id="cameraFrame">
                <div class="no-image" id="noImagePlaceholder">
                    <div class="no-image-icon">📷</div>
                    <div>No Camera Feed</div>
                    <div style="font-size: 0.8em; margin-top: 5px; opacity: 0.7;">Click on a bus to activate camera</div>
                </div>
                <img id="camera-img" src="" alt="Camera Feed" style="display: none;" onerror="handleImageError()">
            </div>
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p>Updating camera feed...</p>
            </div>
        </div>
        
        <div class="debug-info" id="debugInfo">
            <strong>Debug Info:</strong><br>
            Last Update: <span id="lastUpdate">Never</span><br>
            Camera Status: <span id="cameraStatus">No Camera Selected</span><br>
            Firebase Status: <span id="firebaseStatus">Unknown</span><br>
            Current Bus: <span id="currentBusDebug">None</span>
        </div>
    </div>

    <script>
        let currentBus = null;
        let lastImageUpdate = 0;
        let imageUpdateInterval;
        let hasActiveCamera = false;
        
        function selectBus(busName) {
            if (busName === currentBus) return; // Already selected
            
            // Immediately clear the old image when switching cameras
            const img = document.getElementById('camera-img');
            const placeholder = document.getElementById('noImagePlaceholder');
            img.style.display = 'none';
            img.src = '';
            placeholder.style.display = 'flex';
            
            // Update status immediately
            const statusIndicator = document.getElementById('statusIndicator');
            statusIndicator.textContent = '🟡 SWITCHING';
            statusIndicator.className = 'status-indicator status-offline';
            
            currentBus = busName;
            document.getElementById('currentBusDebug').textContent = currentBus;
            
            // Show loading
            document.getElementById('loading').style.display = 'block';
            
            // Send bus selection to server (which will write to Firebase)
            fetch(`/select_bus?token={{flag}}&bus=${busName}`, {
                method: 'POST'
            })
            .then(response => response.text())
            .then(data => {
                console.log('✅ Firebase Update:', data);
                updateBusStatus();
                hasActiveCamera = true;
                
                // Show success notification
                showNotification(`${busName} camera activated!`, 'success');
                document.getElementById('firebaseStatus').textContent = 'Connected';
                document.getElementById('cameraStatus').textContent = `${busName} - Waiting for Feed`;
                
                // Update status to waiting
                statusIndicator.textContent = '🟡 WAITING';
                statusIndicator.className = 'status-indicator status-offline';
            })
            .catch(error => {
                console.error('❌ Error selecting bus:', error);
                showNotification('Failed to update Firebase!', 'error');
                document.getElementById('firebaseStatus').textContent = 'Error';
            })
            .finally(() => {
                document.getElementById('loading').style.display = 'none';
            });
        }
        
        function deactivateAllCameras() {
            currentBus = null;
            hasActiveCamera = false;
            
            // Clear the image and show placeholder
            const img = document.getElementById('camera-img');
            const placeholder = document.getElementById('noImagePlaceholder');
            img.style.display = 'none';
            img.src = '';
            placeholder.style.display = 'flex';
            
            // Update status
            const statusIndicator = document.getElementById('statusIndicator');
            statusIndicator.textContent = '🔴 OFFLINE';
            statusIndicator.className = 'status-indicator status-offline';
            document.getElementById('cameraStatus').textContent = 'No Camera Selected';
            document.getElementById('currentBusDebug').textContent = 'None';
            
            // Send deactivation to server
            fetch(`/deactivate_all?token={{flag}}`, {
                method: 'POST'
            })
            .then(() => {
                updateBusStatus();
                showNotification('All cameras deactivated', 'success');
            })
            .catch(error => {
                console.error('❌ Error deactivating cameras:', error);
            });
        }
        
        function requestFrame() {
            if (!hasActiveCamera) {
                showNotification('Please select a bus first!', 'error');
                return;
            }
            
            document.getElementById('loading').style.display = 'block';
            
            fetch(`/request?token={{flag}}`)
            .then(() => {
                setTimeout(() => {
                    document.getElementById('loading').style.display = 'none';
                }, 1000);
            })
            .catch(error => {
                console.error('Error requesting frame:', error);
                document.getElementById('loading').style.display = 'none';
            });
        }
        
        function updateBusStatus() {
            fetch(`/bus_status?token={{flag}}`)
            .then(response => response.json())
            .then(data => {
                const statusContainer = document.getElementById('busStatus');
                statusContainer.innerHTML = '';
                
                let anyActive = false;
                Object.keys(data).forEach(bus => {
                    const isActive = data[bus].cam === 1;
                    if (isActive) anyActive = true;
                    
                    const card = document.createElement('div');
                    card.className = `bus-card ${isActive ? 'active' : ''}`;
                    card.onclick = () => isActive ? deactivateAllCameras() : selectBus(bus);
                    card.innerHTML = `
                        <h3>${bus}</h3>
                        <div class="status">
                            <span class="status-icon ${isActive ? 'status-active' : 'status-inactive'}"></span>
                            ${isActive ? 'LIVE' : 'Click to Activate'}
                        </div>
                    `;
                    statusContainer.appendChild(card);
                });
                
                // Update global state
                hasActiveCamera = anyActive;
                if (!anyActive && currentBus) {
                    // All cameras deactivated, clear display
                    const img = document.getElementById('camera-img');
                    const placeholder = document.getElementById('noImagePlaceholder');
                    img.style.display = 'none';
                    img.src = '';
                    placeholder.style.display = 'flex';
                    currentBus = null;
                }
            })
            .catch(error => {
                console.error('Error fetching bus status:', error);
                document.getElementById('firebaseStatus').textContent = 'Error';
            });
        }
        
        function updateCameraImage() {
            if (!hasActiveCamera) return;
            
            const img = document.getElementById('camera-img');
            const placeholder = document.getElementById('noImagePlaceholder');
            const statusIndicator = document.getElementById('statusIndicator');
            const timestamp = Date.now();
            
            // Create a temporary image to test if new frame is available
            const testImg = new Image();
            testImg.onload = function() {
                // Image loaded successfully
                img.src = `/latest?${timestamp}`;
                img.style.display = 'block';
                placeholder.style.display = 'none';
                lastImageUpdate = timestamp;
                document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
                document.getElementById('cameraStatus').textContent = `${currentBus} - Live`;
                statusIndicator.textContent = '🟢 LIVE';
                statusIndicator.className = 'status-indicator status-live';
            };
            testImg.onerror = function() {
                // No image available but camera is active
                if (hasActiveCamera) {
                    img.style.display = 'none';
                    placeholder.style.display = 'flex';
                    document.getElementById('cameraStatus').textContent = `${currentBus} - Waiting for Feed`;
                    statusIndicator.textContent = '🟡 WAITING';
                    statusIndicator.className = 'status-indicator status-offline';
                }
            };
            testImg.src = `/latest?${timestamp}`;
        }
        
        function handleImageError() {
            if (hasActiveCamera) {
                const img = document.getElementById('camera-img');
                const placeholder = document.getElementById('noImagePlaceholder');
                const statusIndicator = document.getElementById('statusIndicator');
                
                img.style.display = 'none';
                placeholder.style.display = 'flex';
                statusIndicator.textContent = '🔴 NO SIGNAL';
                statusIndicator.className = 'status-indicator status-offline';
                document.getElementById('cameraStatus').textContent = `${currentBus} - No Signal`;
            }
        }
        
        function showNotification(message, type) {
            const notification = document.createElement('div');
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 15px 20px;
                background: ${type === 'success' ? 'rgba(46, 204, 113, 0.9)' : 'rgba(231, 76, 60, 0.9)'};
                color: white;
                border-radius: 10px;
                font-weight: 600;
                z-index: 1000;
                transform: translateX(300px);
                transition: transform 0.3s ease;
            `;
            notification.textContent = message;
            document.body.appendChild(notification);
            
            setTimeout(() => notification.style.transform = 'translateX(0)', 100);
            setTimeout(() => {
                notification.style.transform = 'translateX(300px)';
                setTimeout(() => document.body.removeChild(notification), 300);
            }, 3000);
        }
        
        // Auto-refresh image every 300ms only if camera is active
        imageUpdateInterval = setInterval(() => {
            if (hasActiveCamera) {
                updateCameraImage();
            }
        }, 300);
        
        // Update bus status every 3 seconds
        setInterval(updateBusStatus, 3000);
        
        // Initialize
        updateBusStatus();
    </script>
</body>
</html>
"""

# ESP → POST /upload  (JPEG)
@app.route("/upload", methods=["POST"])
def upload():
    if request.args.get("token") != UPLOAD_TOKEN:
        abort(401, "bad token")
    data = request.get_data()
    if data[:2] != b'\xff\xd8':
        abort(400, "no jpeg")
    global latest_jpeg, need_frame
    with latest_lock:
        latest_jpeg = data
        need_frame  = False          # clear flag
    print(f"✅ Received JPEG: {len(data)} bytes")
    return "OK", 200

# ESP → GET /flag  (returns "1" or "0")
@app.route("/flag")
def flag():
    if request.args.get("token") != FLAG_TOKEN:
        abort(401)
    return ("1" if need_frame else "0"), 200

# Dashboard → /request  (sets flag)
@app.route("/request")
def request_frame():
    if request.args.get("token") != FLAG_TOKEN:
        abort(401)
    global need_frame
    need_frame = True
    print("🔄 Frame requested via /request endpoint")
    return "OK", 200

# New route for bus selection - writes to Firebase
@app.route("/select_bus", methods=["POST"])
def select_bus():
    if request.args.get("token") != FLAG_TOKEN:
        abort(401)
    
    selected_bus = request.args.get("bus")
    if selected_bus not in bus_states:
        abort(400, "Invalid bus")
    
    global current_bus
    current_bus = selected_bus
    
    # Set all buses to 0, then set selected bus to 1
    for bus in bus_states:
        bus_states[bus]["cam"] = 0
    bus_states[selected_bus]["cam"] = 1
    
    # Write to Firebase - Set all buses to 0 first, then selected bus to 1
    firebase_success = True
    for bus in bus_states:
        cam_value = "1" if bus == selected_bus else "0"  # Firebase expects strings
        path = f"{bus}/cam"
        success = write_to_firebase(path, cam_value)
        if not success:
            firebase_success = False
            print(f"❌ Failed to write to Firebase path: {path}")
        else:
            print(f"✅ Firebase: {path} = {cam_value}")
    
    print(f"🚌 Bus {selected_bus} camera activated, others deactivated")
    print("📊 Current bus states:", bus_states)
    
    if firebase_success:
        return f"Bus {selected_bus} selected and written to Firebase", 200
    else:
        return f"Bus {selected_bus} selected but Firebase write failed", 500

# New route to deactivate all cameras
@app.route("/deactivate_all", methods=["POST"])
def deactivate_all():
    if request.args.get("token") != FLAG_TOKEN:
        abort(401)
    
    global current_bus, latest_jpeg
    current_bus = None
    
    # Set all buses to 0
    for bus in bus_states:
        bus_states[bus]["cam"] = 0
    
    # Clear the latest image
    with latest_lock:
        latest_jpeg = b""
    
    # Write to Firebase - Set all buses to 0
    firebase_success = True
    for bus in bus_states:
        path = f"{bus}/cam"
        success = write_to_firebase(path, "0")
        if not success:
            firebase_success = False
            print(f"❌ Failed to write to Firebase path: {path}")
        else:
            print(f"✅ Firebase: {path} = 0")
    
    print("🚌 All cameras deactivated")
    print("📊 Current bus states:", bus_states)
    
    if firebase_success:
        return "All cameras deactivated", 200
    else:
        return "Cameras deactivated but Firebase write failed", 500

# New route to get bus status (also sync with Firebase)
@app.route("/bus_status")
def get_bus_status():
    if request.args.get("token") != FLAG_TOKEN:
        abort(401)
    
    # Optionally sync with Firebase to get real-time status
    try:
        for bus in bus_states:
            firebase_value = read_from_firebase(f"{bus}/cam")
            if firebase_value is not None:
                # Convert Firebase string to integer
                bus_states[bus]["cam"] = 1 if firebase_value == "1" else 0
    except Exception as e:
        print(f"❌ Error syncing with Firebase: {e}")
    
    return bus_states, 200

# Browser fetches latest still
@app.route("/latest")
def latest():
    if not latest_jpeg:
        abort(404, "no image yet")
    return Response(latest_jpeg, mimetype="image/jpeg")

# Viewer page
@app.route("/")
def view():
    return render_template_string(HTML, flag=FLAG_TOKEN)

# Debug route to check Firebase connection
@app.route("/debug")
def debug():
    if request.args.get("token") != FLAG_TOKEN:
        abort(401)
    
    debug_info = {
        "firebase_url": FIREBASE_URL,
        "current_bus": current_bus,
        "bus_states": bus_states,
        "has_image": len(latest_jpeg) > 0,
        "image_size": len(latest_jpeg)
    }
    return debug_info, 200

if __name__ == "__main__":
    # Don't initialize any bus as active on startup - let user choose
    for i in range(1, 6):
        write_to_firebase(f"Bus{i}/cam", "0")
    
    print("🚀 Server starting...")
    print("🔥 Firebase URL:", FIREBASE_URL)
    print("📊 All cameras set to inactive - ready for user selection")
    
    app.run(debug=True, host="0.0.0.0", port=5000)
