
    // Constants & States
    const STATE = {
        WAITING_FOR_STRAIGHT: 'WAITING_FOR_STRAIGHT',
        WAITING_FOR_LEFT: 'WAITING_FOR_LEFT',
        WAITING_FOR_RETURN: 'WAITING_FOR_RETURN',
        CAPTURED: 'CAPTURED'
    };

    let activeState = STATE.WAITING_FOR_STRAIGHT;
    let verifyStream = null;
    let verificationCaptured = false;
    let verificationBase64 = null;
    let verificationDescriptor = null;
    let isScanning = false;
    let captureTimer = null;
    faceModelsLoaded = false;
    let faceMeshInstance = null;
    let isProcessingFrame = false;
    
    // Safety thresholds for MediaPipe
    const STRAIGHT_MIN = 0.75;
    const STRAIGHT_MAX = 1.35;
    const TURN_THRESHOLD_LEFT = 1.6;

    // Toast utility
    function showToast(msg) {
        const toast = document.getElementById('toast-verify-box');
        document.getElementById('toast-verify-text').innerText = msg;
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3500);
    }

    // Switch verification step slides
    function switchStep(stepId) {
        document.querySelectorAll('.verify-step').forEach(step => {
            step.classList.remove('active');
        });
        document.getElementById(stepId).classList.add('active');
        
        const mainWrap = document.getElementById('verify-main-container');
        if (stepId === 'step-camera') {
            mainWrap.style.padding = '0';
            mainWrap.style.background = '#000';
        } else {
            mainWrap.style.padding = 'env(safe-area-inset-top, 24px) 16px env(safe-area-inset-bottom, 24px)';
            mainWrap.style.background = 'var(--verify-bg)';
        }
    }

    async function loadFaceModelsOnce() {
        if (faceModelsLoaded) return true;
        if (typeof faceapi === 'undefined') {
            showToast("face-api library is not loaded. Check internet connection.");
            return false;
        }

        const CDN_URL = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model/';
        const LOCAL_URL = '/static/models/'; 

        try {
            console.log("Loading AI verification models from CDN...");
            await Promise.all([
                faceapi.nets.tinyFaceDetector.loadFromUri(CDN_URL),
                faceapi.nets.faceLandmark68Net.loadFromUri(CDN_URL),
                faceapi.nets.faceRecognitionNet.loadFromUri(CDN_URL),
                faceapi.nets.ageGenderNet.loadFromUri(CDN_URL)
            ]);
            faceModelsLoaded = true;
            return true;
        } catch (err) {
            console.warn("CDN failed. Falling back to local static directory...");
            try {
                await Promise.all([
                    faceapi.nets.tinyFaceDetector.loadFromUri(LOCAL_URL),
                    faceapi.nets.faceLandmark68Net.loadFromUri(LOCAL_URL),
                    faceapi.nets.faceRecognitionNet.loadFromUri(LOCAL_URL),
                    faceapi.nets.ageGenderNet.loadFromUri(LOCAL_URL)
                ]);
                faceModelsLoaded = true;
                return true;
            } catch(e) {
                console.error("AI Models failed to load completely:", e);
                return false;
            }
        }
    }

    function stopCameraAndExit() {
        stopCamera();
        switchStep('step-intro');
    }

    function stopCamera() {
        isScanning = false;
        if (verifyStream) {
            verifyStream.getTracks().forEach(track => track.stop());
            verifyStream = null;
        }
        const video = document.getElementById('verify-video');
        if (video) {
            video.srcObject = null;
        }
        if (faceMeshInstance) {
            faceMeshInstance.close();
            faceMeshInstance = null;
        }
    }

    // OPEN CAMERA FLOW (Using MediaPipe for Live Tracking)
    async function openCameraScreen() {
        switchStep('step-camera');
        
        const video = document.getElementById('verify-video');
        const promptMsg = document.getElementById('verify-prompt-msg');
        const ring = document.getElementById('verify-scanning-ring');

        ring.className = 'scanning-ring';
        promptMsg.innerHTML = '<i class="fas fa-camera" style="color: #6366f1;"></i> Opening camera feed...';
        promptMsg.style.color = '#fff';

        // Reset tracking states
        verificationCaptured = false;
        verificationBase64 = null;
        activeState = STATE.WAITING_FOR_STRAIGHT;
        isScanning = true;
        if (captureTimer) { clearTimeout(captureTimer); captureTimer = null; }

        try {
            verifyStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }
            });
            
            video.muted = true;
            video.playsInline = true;
            video.srcObject = verifyStream;
            try { await video.play(); } catch(e) {}

            await new Promise((resolve) => {
                if (video.readyState >= 2) { resolve(); return; }
                video.addEventListener('canplay', resolve, { once: true });
            });

            promptMsg.innerHTML = '<i class="fas fa-spinner fa-spin" style="color: #818cf8;"></i> Initializing fast tracker...';

            // Initialize MediaPipe FaceMesh
            faceMeshInstance = new FaceMesh({locateFile: (file) => {
                return `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`;
            }});
            faceMeshInstance.setOptions({
                maxNumFaces: 1,
                refineLandmarks: false,
                minDetectionConfidence: 0.5,
                minTrackingConfidence: 0.5
            });
            faceMeshInstance.onResults((results) => {
                isProcessingFrame = false;
                processMediaPipeResults(results, promptMsg, ring);
            });

            // Await initialization by sending a dummy frame
            try { await faceMeshInstance.send({image: video}); } catch(e) {}

            // Start highly-optimized animation loop
            promptMsg.innerHTML = 'Look straight at camera';
            ring.className = 'scanning-ring scanning';
            requestAnimationFrame(() => mediaPipeLoop(video));

        } catch (err) {
            console.error("Camera startup failed:", err);
            showToast("Failed to access front camera. Please allow permissions.");
            stopCamera();
            switchStep('step-intro');
        }
    }

    async function mediaPipeLoop(video) {
        if (!isScanning || verificationCaptured || activeState === STATE.CAPTURED) return;

        if (video.readyState >= 2 && faceMeshInstance && !isProcessingFrame) {
            isProcessingFrame = true;
            try {
                await faceMeshInstance.send({image: video});
            } catch (err) {
                isProcessingFrame = false;
            }
        }
        
        if (isScanning && !verificationCaptured) {
            requestAnimationFrame(() => mediaPipeLoop(video));
        }
    }

    // STATE MACHINE LIVENESS SCAN
    function processMediaPipeResults(results, promptEl, ringEl) {
        if (!isScanning || verificationCaptured || activeState === STATE.CAPTURED) return;

        if (!results.multiFaceLandmarks || results.multiFaceLandmarks.length === 0) {
            promptEl.innerHTML = 'Face not detected. Position your face in frame.';
            promptEl.style.color = '#ef4444';
            ringEl.className = 'scanning-ring scanning';
            activeState = STATE.WAITING_FOR_STRAIGHT;
            if (captureTimer) { clearTimeout(captureTimer); captureTimer = null; }
            return;
        }

        const landmarks = results.multiFaceLandmarks[0];
        
        // MediaPipe indices: 1 = Nose tip, 234 = Left cheek edge, 454 = Right cheek edge
        const nose = landmarks[1];
        const leftCheek = landmarks[234];
        const rightCheek = landmarks[454];

        // Ensure landmarks exist
        if (nose && leftCheek && rightCheek) {
            const distLeft = nose.x - leftCheek.x;
            const distRight = rightCheek.x - nose.x;
            const ratio = distLeft / (distRight || 0.0001);

            const isStraight = ratio > STRAIGHT_MIN && ratio < STRAIGHT_MAX;
            const isTurnedLeft = ratio > TURN_THRESHOLD_LEFT;

            // FLOW LOGIC
            if (activeState === STATE.WAITING_FOR_STRAIGHT) {
                promptEl.innerHTML = 'Look straight';
                promptEl.style.color = '#fff';
                ringEl.className = 'scanning-ring scanning';

                if (isStraight) {
                    activeState = STATE.WAITING_FOR_LEFT;
                }
            } 
            else if (activeState === STATE.WAITING_FOR_LEFT) {
                promptEl.innerHTML = 'Turn your head slightly to the left';
                promptEl.style.color = '#3b82f6';
                ringEl.className = 'scanning-ring turned';

                if (isTurnedLeft) {
                    activeState = STATE.WAITING_FOR_RETURN;
                }
            } 
            else if (activeState === STATE.WAITING_FOR_RETURN) {
                promptEl.innerHTML = 'Look back at camera';
                promptEl.style.color = '#10b981';
                ringEl.className = 'scanning-ring success';

                if (isStraight) {
                    if (!captureTimer) {
                        captureTimer = setTimeout(() => {
                            if (!verificationCaptured && isScanning) {
                                verificationCaptured = true;
                                activeState = STATE.CAPTURED;
                                promptEl.innerHTML = 'Capturing...';
                                triggerSelfieCapture();
                            }
                        }, 500); // 0.5s stability hold to capture
                    }
                } else {
                    if (captureTimer) { clearTimeout(captureTimer); captureTimer = null; }
                }
            }
        }
    }

    // SELFIE CAPTURE & face-api.js Background Analysis
    async function triggerSelfieCapture() {
        const video = document.getElementById('verify-video');
        const canvas = document.getElementById('verify-canvas');
        
        // 1. INSTANT CAPTURE
        const targetWidth = 400;
        const targetHeight = video.videoWidth > 0 ? Math.floor(video.videoHeight * (targetWidth / video.videoWidth)) : 400;
        canvas.width = targetWidth;
        canvas.height = targetHeight;
        canvas.getContext('2d').drawImage(video, 0, 0, targetWidth, targetHeight);
        verificationBase64 = canvas.toDataURL('image/jpeg', 0.85);

        // 2. STOP CAMERA IMMEDIATELY
        stopCamera();

        // 3. SHOW VERIFY LOADING VIEW
        switchStep('step-loading');
        
        try {
            // Load face-api.js models ONLY AFTER the camera is closed
            document.getElementById('loading-subtext').innerText = "Loading Secure AI processing...";
            const modelsLoaded = await loadFaceModelsOnce();
            if (!modelsLoaded) {
                return handleLivenessFailure("Rejected: Could not initialize AI backend.");
            }
            document.getElementById('loading-subtext').innerText = "Analyzing photo securely...";

            const img = new Image();
            img.src = verificationBase64;
            await new Promise((res, rej) => { img.onload = res; img.onerror = rej; });

            // Blur check
            const blurResult = checkBlurriness(canvas); 
            if (blurResult.isBlurry) {
                return handleLivenessFailure("Rejected: Image is too blurry. Please scan under clear lighting.");
            }

            // 4. HEAVY DETECTIONS AFTER CAPTURE
            const allDetections = await faceapi
                .detectAllFaces(img, new faceapi.TinyFaceDetectorOptions({ inputSize: 320 }))
                .withFaceLandmarks()
                .withAgeAndGender()
                .withFaceDescriptors();

            if (allDetections.length === 0) {
                return handleLivenessFailure("Rejected: No clear face detected in your capture.");
            }
            if (allDetections.length > 1) {
                return handleLivenessFailure("Rejected: Multiple faces detected. Please verify alone.");
            }

            const faceMatch = allDetections[0];
            
            // Check confidence and position
            if (faceMatch.detection.score < 0.55) {
                return handleLivenessFailure("Rejected: Face confidence is too low. Ensure proper lighting.");
            }
            
            const box = faceMatch.detection.box;
            if (box.x < 0 || box.y < 0 || box.x + box.width > img.width || box.y + box.height > img.height) {
                return handleLivenessFailure("Rejected: Face is too far outside the frame.");
            }
            
            // Gender Check
            const userGender = "{{ profile.gender|default:''|escapejs }}";
            if (userGender && userGender.toLowerCase() !== 'other' && faceMatch.gender && faceMatch.genderProbability > 0.6) {
                if (faceMatch.gender.toLowerCase() !== userGender.toLowerCase()) {
                    return handleLivenessFailure("Rejected: Gender detection mismatch. Photo does not match profile gender.");
                }
            }

            // Store Descriptor & Base64
            verificationDescriptor = faceMatch.descriptor;
            document.getElementById('verification-image-data').value = verificationBase64;

            // 5. Cloud Upload Backgrounding
            const uploadRes = await fetch('/api/upload/base64/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': '{{ csrf_token }}' },
                body: JSON.stringify({ image: verificationBase64, path: 'verification' })
            });
            const uploadData = await uploadRes.json();
            
            if (uploadData.success) {
                document.getElementById('verification-image-url').value = uploadData.url;
                document.getElementById('verification-status-input').value = 'verified';
                
                // Show gorgeous success
                switchStep('step-success');
            } else {
                return handleLivenessFailure("Rejected: Image secure transit failed (" + uploadData.message + ")");
            }

        } catch (e) {
            console.error("Biometric extraction error:", e);
            handleLivenessFailure("Rejected: Biometric extraction error. Please try again.");
        }
    }

    function checkBlurriness(canvas) {
        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;
        if (width === 0 || height === 0) return { isBlurry: false, variance: 100 };
        
        const imageData = ctx.getImageData(0, 0, width, height);
        const data = imageData.data;
        
        const grayscale = new Uint8Array(width * height);
        for (let i = 0; i < data.length; i += 4) {
            grayscale[i / 4] = data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114;
        }
        
        let mean = 0;
        const laplacian = new Int16Array(width * height);
        for (let y = 1; y < height - 1; y++) {
            for (let x = 1; x < width - 1; x++) {
                const idx = y * width + x;
                const val = grayscale[idx - width] * -1 +
                            grayscale[idx - 1] * -1 +
                            grayscale[idx] * 4 +
                            grayscale[idx + 1] * -1 +
                            grayscale[idx + width] * -1;
                laplacian[idx] = val;
                mean += val;
            }
        }
        mean /= (width * height);
        
        let variance = 0;
        for (let i = 0; i < laplacian.length; i++) {
            variance += Math.pow(laplacian[i] - mean, 2);
        }
        variance /= (width * height);
        
        console.log("Blur variance:", variance);
        // Realistic threshold for mobile cameras
        return { isBlurry: variance < 30, variance };
    }

    function handleLivenessFailure(msg) {
        stopCamera();
        document.getElementById('verification-status-input').value = 'rejected';
        document.getElementById('error-explain').innerText = msg;
        switchStep('step-error');
    }

    function goToPfpStep() {
        switchStep('step-pfp');
    }

    // PFP HANDLING & LOCAL COMPARISON
    let pfpBase64 = null;
    
    function compressImage(file, quality = 0.7, maxWidth = 800) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.src = URL.createObjectURL(file);
            img.onload = () => {
                const canvas = document.createElement('canvas');
                let width = img.width;
                let height = img.height;
                if (width > maxWidth) {
                    height = Math.round((height * maxWidth) / width);
                    width = maxWidth;
                }
                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);
                canvas.toBlob((blob) => {
                    if(!blob) return reject(new Error("Canvas compression failed"));
                    resolve(new File([blob], file.name, { type: 'image/jpeg', lastModified: Date.now() }));
                }, 'image/jpeg', quality);
            };
            img.onerror = reject;
        });
    }

    async function handlePfpSelect(input) {
        if (input.files && input.files[0]) {
            const uploadPlaceholder = document.getElementById('pfp-upload-placeholder');
            const preview = document.getElementById('pfp-avatar');
            const submitBtn = document.getElementById('submit-btn');

            submitBtn.disabled = true;
            submitBtn.style.opacity = '0.6';
            submitBtn.style.cursor = 'not-allowed';
            submitBtn.style.boxShadow = 'none';
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';

            try {
                const compressedFile = await compressImage(input.files[0], 0.75, 800);
                
                const reader = new FileReader();
                reader.onload = async function(e) {
                    pfpBase64 = e.target.result;
                    preview.src = pfpBase64;
                    preview.style.display = 'block';
                    uploadPlaceholder.style.display = 'none';

                    const tempImg = new Image();
                    tempImg.src = pfpBase64;
                    tempImg.onload = async () => {
                        const verifiedOk = await compareProfilePicture(tempImg);
                        if (verifiedOk) {
                            submitBtn.disabled = false;
                            submitBtn.style.opacity = '1';
                            submitBtn.style.cursor = 'pointer';
                            submitBtn.style.boxShadow = '0 8px 24px rgba(99,102,241,0.3)';
                            submitBtn.innerHTML = 'Complete Setup <i class="fas fa-check-circle" style="margin-left: 6px;"></i>';
                        } else {
                            submitBtn.innerHTML = 'Complete Setup';
                            preview.src = '';
                            preview.style.display = 'none';
                            uploadPlaceholder.style.display = 'block';
                            input.value = '';
                        }
                    };
                };
                reader.readAsDataURL(compressedFile);

            } catch (err) {
                console.error(err);
                showToast("Failed to process your profile photo.");
                submitBtn.innerHTML = 'Complete Setup';
            }
        }
    }

    async function compareProfilePicture(pfpImgElement) {
        if (!verificationDescriptor) {
            showToast("Biometric reference not found. Redo verification.");
            return false;
        }

        try {
            const pfpDetection = await faceapi
                .detectSingleFace(pfpImgElement, new faceapi.TinyFaceDetectorOptions({ inputSize: 320 }))
                .withFaceLandmarks()
                .withFaceDescriptor();

            if (!pfpDetection) {
                showToast("Rejected: No clear face detected in your uploaded profile picture.");
                return false;
            }

            // Compare distances
            const distance = faceapi.euclideanDistance(verificationDescriptor, pfpDetection.descriptor);
            const isMatch = distance < 0.6; 

            if (isMatch) {
                const uploadRes = await fetch('/api/upload/base64/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': '{{ csrf_token }}' },
                    body: JSON.stringify({ image: pfpBase64, path: 'profile_pics' })
                });
                const uploadData = await uploadRes.json();
                
                if (uploadData.success) {
                    document.getElementById('profile-pic-url-input').value = uploadData.url;
                    return true;
                } else {
                    showToast("Failed to secure PFP transit: " + uploadData.message);
                    return false;
                }
            } else {
                showToast("Identity mismatch: Profile photo does not match verified selfie. Please upload a different photo.");
                return false;
            }
        } catch (err) {
            console.error("Comparison error:", err);
            showToast("Comparison error. Please try another image.");
            return false;
        }
    }

    // Submit complete form
    document.getElementById('verifyForm').addEventListener('submit', function() {
        const btn = document.getElementById('submit-btn');
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Securing profile...';
    });

