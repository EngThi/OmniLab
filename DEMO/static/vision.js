// static/vision.js
console.log("Carregando módulo Vision (Frontend)...");

function vLog(msg, level = "INFO") {
    if (typeof window.remoteLog === "function") window.remoteLog(`VISION: ${msg}`, level);
}

let handLandmarker;
let runningMode = "VIDEO";
let webcamRunning = false;
let visionWs;
let videoElement;
let lastVideoTime = -1;
let prevLandmarks = null;
let lastGestureTime = 0;
let pinchStartTime = null;

const PINCH_THRESHOLD_MS = 1500;
const SWIPE_THRESHOLD = 0.15;
const GESTURE_COOLDOWN = 800; // ms

async function initVisionFrontend() {
    vLog("STARTING_INITIALIZATION");
    console.log("Inicializando MediaPipe Vision JS...");
    
    // Cria elemento de vídeo escondido
    videoElement = document.createElement("video");
    videoElement.style.display = "none";
    videoElement.autoplay = true;
    document.body.appendChild(videoElement);

    // Carrega script principal usando CDN
    const script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision/vision_bundle.js";
    script.crossOrigin = "anonymous";
    script.onload = async () => {
        vLog("MEDIAPIPE_JS_LOADED");
        try {
            const { HandLandmarker, FilesetResolver } = window;
            const vision_wasm = await FilesetResolver.forVisionTasks(
                "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm"
            );

            handLandmarker = await HandLandmarker.createFromOptions(vision_wasm, {
                baseOptions: {
                    modelAssetPath: "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
                    delegate: "GPU"
                },
                runningMode: runningMode,
                numHands: 1,
                minHandDetectionConfidence: 0.5,
                minHandPresenceConfidence: 0.5,
                minTrackingConfidence: 0.5
            });

            vLog("MEDIAPIPE_READY");
            startWebcam();
        } catch (e) {
            vLog(`MEDIAPIPE_INIT_ERROR: ${e.message}`, "CRITICAL");
        }
    };
    script.onerror = () => vLog("MEDIAPIPE_JS_DOWNLOAD_FAILED", "CRITICAL");
    document.head.appendChild(script);
}

function startWebcam() {
    vLog("REQUESTING_WEBCAM");
    navigator.mediaDevices.getUserMedia({ video: true }).then((stream) => {
        vLog("WEBCAM_GRANTED");
        videoElement.srcObject = stream;
        videoElement.addEventListener("loadeddata", () => {
            webcamRunning = true;
            vLog("WEBCAM_RUNNING");
            connectVisionWS();
            requestAnimationFrame(predictWebcam);
        });
    }).catch(err => {
        vLog(`WEBCAM_ERROR: ${err.message}`, "ERROR");
    });
}

function connectVisionWS() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    let host = isLocal ? 'localhost:8000' : window.location.host;
    
    if (!isLocal && typeof BACKEND_URL !== 'undefined' && BACKEND_URL) {
        host = BACKEND_URL;
    }
    
    vLog(`CONNECTING_WS: ${protocol}//${host}/ws/vision`);
    
    visionWs = new WebSocket(`${protocol}//${host}/ws/vision`);
    visionWs.onopen = () => vLog("WS_CONNECTED", "INFO");
    visionWs.onclose = () => {
        vLog("WS_DISCONNECTED", "WARN");
        setTimeout(connectVisionWS, 2000);
    };
}

function detectGestureType(landmarks) {
    if (!landmarks || landmarks.length === 0) return { gesture: "none", pinch_progress: 0.0, x: 0.5, y: 0.5 };
    
    const wrist = landmarks[0];
    const thumb_tip = landmarks[4];
    const index_tip = landmarks[8];
    const middle_tip = landmarks[12];
    const ring_tip = landmarks[16];
    const pinky_tip = landmarks[20];

    const dist_pinch = Math.hypot(thumb_tip.x - index_tip.x, thumb_tip.y - index_tip.y);
    const is_pinching = dist_pinch < 0.05; // Coordenadas em JS são normalizadas (0 a 1)
    const is_thumbs_up = (thumb_tip.y < index_tip.y - 0.1 && thumb_tip.y < middle_tip.y - 0.1 && index_tip.x > middle_tip.x);
    
    const dists = [index_tip, middle_tip, ring_tip, pinky_tip].map(f => Math.hypot(f.x - wrist.x, f.y - wrist.y));
    const is_fist = dists.every(d => d < 0.25);

    let gesture = "none";
    if (prevLandmarks) {
        const dx = index_tip.x - prevLandmarks[8].x;
        if (Math.abs(dx) > SWIPE_THRESHOLD) {
            gesture = dx > 0 ? "swipe_right" : "swipe_left";
        }
    }

    if (is_fist) gesture = "fist";
    else if (is_thumbs_up) gesture = "thumbs_up";
    else if (is_pinching) gesture = "pinch";
    else if (!is_fist && !is_pinching && !is_thumbs_up) gesture = "open";

    prevLandmarks = landmarks;
    return { gesture, dist_pinch, x: index_tip.x, y: index_tip.y };
}

let framesProcessed = 0;
let lastFpsTime = Date.now();
let currentFps = 0;

function predictWebcam() {
    let nowInMs = Date.now();
    let gestureData = {
        type: "gesture", gesture: "none", x: 0.5, y: 0.5, pinch_progress: 0.0, fps: currentFps, timestamp: nowInMs
    };

    if (videoElement.currentTime !== lastVideoTime) {
        lastVideoTime = videoElement.currentTime;
        const results = handLandmarker.detectForVideo(videoElement, nowInMs);
        
        framesProcessed++;
        if (nowInMs - lastFpsTime > 1000) {
            currentFps = framesProcessed;
            framesProcessed = 0;
            lastFpsTime = nowInMs;
        }

        if (results.landmarks && results.landmarks.length > 0) {
            const { gesture, dist_pinch, x, y } = detectGestureType(results.landmarks[0]);
            let final_gesture = gesture;
            let pinch_progress = 0.0;
            
            if (gesture === "pinch") {
                if (!pinchStartTime) pinchStartTime = nowInMs;
                else pinch_progress = Math.min((nowInMs - pinchStartTime) / PINCH_THRESHOLD_MS, 1.0);
            } else {
                pinchStartTime = null;
                if (["swipe_left", "swipe_right", "thumbs_up", "fist"].includes(gesture) && (nowInMs - lastGestureTime < GESTURE_COOLDOWN)) {
                    final_gesture = "none";
                } else if (gesture !== "none") {
                    lastGestureTime = nowInMs;
                }
            }
            gestureData = { 
                type: "gesture", 
                gesture: final_gesture, 
                landmarks: results.landmarks[0],
                confidence: 0.9,
                x, y, 
                pinch_progress, 
                fps: currentFps, 
                timestamp: nowInMs 
            };
        } else {
            prevLandmarks = null;
        }
    }

    if (visionWs && visionWs.readyState === WebSocket.OPEN) {
        // Envia direto quando tem gesto diferente de "none" ou com frequência menor para atualizar posição 'x' e 'y' do mouse
        visionWs.send(JSON.stringify(gestureData));
    }

    if (webcamRunning) {
        requestAnimationFrame(predictWebcam);
    }
}

// Inicialização automática desativada (HUD chama agora)
// if (typeof USE_FRONTEND_VISION !== 'undefined' && USE_FRONTEND_VISION) {
//    initVisionFrontend();
// }
