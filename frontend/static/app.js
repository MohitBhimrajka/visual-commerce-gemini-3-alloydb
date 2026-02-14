/**
 * Cinematic Demo App State Management
 * Alpine.js state machine for the 4-act autonomous supply chain demo
 */

function appState() {
    return {
        // WebSocket connection
        ws: null,
        wsConnected: false,

        // Step wizard (0=Upload, 1=Vision, 2=Memory, 3=Order, 4=Complete)
        step: 0,
        isProcessing: false,

        // Upload state
        uploadedImage: null,
        uploadedFile: null,
        isDragging: false,

        // Sample images
        sampleImages: [],

        // Vision result (structured from backend)
        visionResult: null,

        // Supplier result
        supplierResult: null,

        // Order result
        orderResult: null,

        // Fake thoughts engine
        currentThought: '',
        thoughtInterval: null,

        // Progress tracking for 90s experience
        progressPercent: 0,
        progressMessage: '',
        currentSubstep: '',
        substeps: [],
        codeGenerating: false,
        codeExecuting: false,
        generatedCode: '',
        executionOutput: '',
        liveLogStream: [],

        // A2A Agent Discovery
        showAgentDiscovery: false,
        discoveredAgent: null,
        discoveryAgentType: null,  // 'vision' or 'supplier'
        showCode: false,
        showOutput: false,

        visionThoughts: [
            "Initializing Gemini 3 Flash vision pipeline...",
            "Loading OpenCV contour detection kernels...",
            "Analyzing pixel density across shelf regions...",
            "Detecting object boundaries with edge detection...",
            "Classifying detected contours as inventory items...",
            "Cross-referencing item dimensions with known SKUs...",
            "Running statistical validation on count estimates...",
            "Finalizing inventory count with confidence scoring..."
        ],
        memoryThoughts: [
            "Generating embedding vector from visual analysis...",
            "Connecting to AlloyDB via private service connect...",
            "Executing ScaNN approximate nearest neighbor search...",
            "Scanning 1M+ inventory vectors in <50ms...",
            "Ranking supplier matches by cosine similarity...",
            "Retrieving top supplier metadata and pricing..."
        ],
        thoughtIndex: 0,

        // Audio
        audioEnabled: true,
        audioCtx: null,
        humOscillator: null,
        humGain: null,

        // Orchestrator bar text
        orchestratorText: "System Ready",

        // Logs drawer
        showLogs: false,
        rawLogs: [],

        // Initialize on component mount
        async init() {
            this.connectWebSocket();
            await this.loadSampleImages();
            this.initAudio();
        },

        // Web Audio API initialization
        initAudio() {
            try {
                this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            } catch (e) {
                console.warn('Web Audio API not supported:', e);
                this.audioEnabled = false;
            }
        },

        // Toggle audio
        toggleAudio() {
            this.audioEnabled = !this.audioEnabled;
            if (!this.audioEnabled && this.humOscillator) {
                this.stopHum();
            }
        },

        // Play scanning hum (looping)
        playHum() {
            if (!this.audioEnabled || !this.audioCtx) return;

            try {
                this.humOscillator = this.audioCtx.createOscillator();
                this.humGain = this.audioCtx.createGain();

                this.humOscillator.type = 'sine';
                this.humOscillator.frequency.setValueAtTime(100, this.audioCtx.currentTime);

                this.humGain.gain.setValueAtTime(0, this.audioCtx.currentTime);
                this.humGain.gain.linearRampToValueAtTime(0.1, this.audioCtx.currentTime + 0.5);

                this.humOscillator.connect(this.humGain);
                this.humGain.connect(this.audioCtx.destination);

                this.humOscillator.start();
            } catch (e) {
                console.warn('Failed to play hum:', e);
            }
        },

        // Stop scanning hum
        stopHum() {
            if (this.humOscillator && this.humGain) {
                try {
                    this.humGain.gain.linearRampToValueAtTime(0, this.audioCtx.currentTime + 0.3);
                    setTimeout(() => {
                        if (this.humOscillator) {
                            this.humOscillator.stop();
                            this.humOscillator = null;
                            this.humGain = null;
                        }
                    }, 350);
                } catch (e) {
                    console.warn('Failed to stop hum:', e);
                }
            }
        },

        // Play sonar ping
        playPing() {
            if (!this.audioEnabled || !this.audioCtx) return;

            try {
                const oscillator = this.audioCtx.createOscillator();
                const gainNode = this.audioCtx.createGain();

                oscillator.type = 'sine';
                oscillator.frequency.setValueAtTime(880, this.audioCtx.currentTime);

                gainNode.gain.setValueAtTime(0.3, this.audioCtx.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, this.audioCtx.currentTime + 0.3);

                oscillator.connect(gainNode);
                gainNode.connect(this.audioCtx.destination);

                oscillator.start();
                oscillator.stop(this.audioCtx.currentTime + 0.3);
            } catch (e) {
                console.warn('Failed to play ping:', e);
            }
        },

        // Play success chime
        playSuccess() {
            if (!this.audioEnabled || !this.audioCtx) return;

            try {
                const playTone = (freq, delay) => {
                    const oscillator = this.audioCtx.createOscillator();
                    const gainNode = this.audioCtx.createGain();

                    oscillator.type = 'sine';
                    oscillator.frequency.setValueAtTime(freq, this.audioCtx.currentTime + delay);

                    gainNode.gain.setValueAtTime(0.2, this.audioCtx.currentTime + delay);
                    gainNode.gain.exponentialRampToValueAtTime(0.01, this.audioCtx.currentTime + delay + 0.15);

                    oscillator.connect(gainNode);
                    gainNode.connect(this.audioCtx.destination);

                    oscillator.start(this.audioCtx.currentTime + delay);
                    oscillator.stop(this.audioCtx.currentTime + delay + 0.15);
                };

                playTone(523.25, 0);      // C5
                playTone(659.25, 0.15);   // E5
            } catch (e) {
                console.warn('Failed to play success:', e);
            }
        },

        // Fake thoughts engine — varied timing to feel like actual thinking
        startFakeThoughts(type) {
            const thoughts = type === 'vision' ? this.visionThoughts : this.memoryThoughts;
            this.thoughtIndex = 0;
            this.currentThought = thoughts[0];

            const scheduleNext = () => {
                // Vary timing between 1.5s and 3.5s to feel more natural
                const delay = 1500 + Math.random() * 2000;
                this.thoughtInterval = setTimeout(() => {
                    this.thoughtIndex = (this.thoughtIndex + 1) % thoughts.length;
                    this.currentThought = thoughts[this.thoughtIndex];
                    scheduleNext();
                }, delay);
            };
            scheduleNext();
        },

        stopFakeThoughts() {
            if (this.thoughtInterval) {
                clearTimeout(this.thoughtInterval);
                this.thoughtInterval = null;
            }
            this.currentThought = '';
        },

        // Progress simulation for 90s experience
        simulateProgress() {
            this.progressPercent = 0;
            this.currentSubstep = 'Initializing Gemini 3 Flash...';

            const thinkingInterval = setInterval(() => {
                if (this.progressPercent < 30) {
                    this.progressPercent += 1;
                    if (this.progressPercent === 10) this.currentSubstep = 'Analyzing image composition...';
                    if (this.progressPercent === 20) this.currentSubstep = 'Identifying object patterns...';
                }
            }, 900);

            // Phase 2: Code Generation (30-50%) - 18s
            setTimeout(() => {
                this.codeGenerating = true;
                this.currentSubstep = 'Generating Python counting code...';
                const codeInterval = setInterval(() => {
                    if (this.progressPercent < 50) {
                        this.progressPercent += 1;
                    } else {
                        clearInterval(codeInterval);
                    }
                }, 900);
            }, 27000);

            // Phase 3: Code Execution (50-90%) - 36s
            setTimeout(() => {
                this.codeGenerating = false;
                this.codeExecuting = true;
                this.currentSubstep = 'Executing detection algorithm...';
                const execInterval = setInterval(() => {
                    if (this.progressPercent < 90) {
                        this.progressPercent += 1;
                        if (this.progressPercent === 60) this.currentSubstep = 'Processing edge detection...';
                        if (this.progressPercent === 75) this.currentSubstep = 'Counting detected objects...';
                    } else {
                        clearInterval(execInterval);
                        clearInterval(thinkingInterval);
                    }
                }, 900);
            }, 45000);
        },

        // Connect to discovered agent
        connectToAgent() {
            this.showAgentDiscovery = false;
        },

        // Load sample images from backend
        async loadSampleImages() {
            try {
                const response = await fetch('/api/test-images');
                if (response.ok) {
                    const data = await response.json();
                    this.sampleImages = data.images || [];
                }
            } catch (error) {
                console.error('Failed to load sample images:', error);
            }
        },

        // Select a sample image and auto-start
        async selectSampleImage(name) {
            try {
                const response = await fetch(`/api/test-image/${name}`);
                if (response.ok) {
                    const blob = await response.blob();
                    this.uploadedFile = new File([blob], name, { type: blob.type });
                    this.uploadedImage = URL.createObjectURL(blob);

                    // Auto-start the analysis — 500ms gives user time to register the image
                    this.$nextTick(() => {
                        setTimeout(() => this.startAnalysis(), 500);
                    });
                }
            } catch (error) {
                console.error('Failed to load sample image:', error);
                alert('Failed to load sample image. Please try again.');
            }
        },

        // WebSocket connection
        connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;

            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.wsConnected = true;
            };

            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.wsConnected = false;

                setTimeout(() => {
                    if (!this.wsConnected) {
                        this.connectWebSocket();
                    }
                }, 3000);
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };

            setInterval(() => {
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send('ping');
                }
            }, 30000);
        },

        // Handle incoming WebSocket messages
        handleWebSocketMessage(data) {
            console.log('Received:', data);

            // Add to raw logs
            this.rawLogs.push({...data, timestamp: new Date().toISOString()});
            if (this.rawLogs.length > 100) {
                this.rawLogs.shift();
            }

            switch(data.type) {
                case 'upload_complete':
                    this.step = 1;
                    this.startFakeThoughts('vision');
                    this.simulateProgress();
                    // Don't start hum yet — wait until vision_start (after discovery modal)
                    this.orchestratorText = "Control Tower → Vision Agent (A2A Discovery)";
                    break;

                case 'discovery_start':
                    if (data.agent === 'vision') {
                        this.orchestratorText = "Discovering Vision Agent via A2A...";
                        // Show A2A discovery modal for vision agent too
                        this.showAgentDiscovery = true;
                        this.discoveredAgent = null;
                        this.discoveryAgentType = 'vision';
                    } else if (data.agent === 'supplier') {
                        this.orchestratorText = "Discovering Supplier Agent via A2A...";
                        this.showAgentDiscovery = true;
                        this.discoveredAgent = null;
                        this.discoveryAgentType = 'supplier';
                    }
                    break;

                case 'discovery_complete':
                    if (data.agent === 'vision') {
                        this.orchestratorText = "Vision Agent → Gemini 3 Flash (Analyzing)";
                    }

                    // Populate modal with REAL agent card data from backend
                    this.discoveredAgent = {
                        name: data.agent,
                        displayName: data.agent_name || (data.agent === 'vision' ? 'Vision Agent' : 'Supplier Agent'),
                        description: data.agent_description || '',
                        endpoint: data.agent_url || '',
                        version: data.agent_version || '1.0.0',
                        skills: data.agent_skills || [],
                        inputModes: data.agent_input_modes || [],
                        outputModes: data.agent_output_modes || [],
                        protocolVersion: data.agent_protocol_version || '',
                        transport: data.agent_transport || '',
                        streaming: data.agent_streaming ?? false,
                    };

                    // Only play ping for supplier discovery (vision has the hum coming)
                    if (data.agent === 'supplier') {
                        this.playPing();
                    }

                    // Modal stays open until user clicks "Continue"
                    break;

                case 'vision_start':
                    this.orchestratorText = "Vision Agent → Gemini 3 Flash (Analyzing)";
                    this.playHum(); // Start scanning hum when actual analysis begins
                    break;

                case 'vision_progress':
                    // Live updates from backend during processing
                    this.liveLogStream.push({
                        time: new Date().toLocaleTimeString(),
                        message: data.message,
                        type: data.substep
                    });

                    // Update progress phase based on substep from backend
                    if (data.substep === 'code_generating' || data.substep === 'code') {
                        this.codeGenerating = true;
                        this.codeExecuting = false;
                        if (this.progressPercent < 30) this.progressPercent = 30;
                        this.currentSubstep = data.message;
                    } else if (data.substep === 'code_executing' || data.substep === 'execution') {
                        this.codeGenerating = false;
                        this.codeExecuting = true;
                        if (this.progressPercent < 50) this.progressPercent = 50;
                        this.currentSubstep = data.message;
                    } else if (data.substep === 'thinking') {
                        this.currentSubstep = data.message;
                    }

                    if (data.code) {
                        this.generatedCode = data.code;
                    }
                    if (data.output) {
                        this.executionOutput += data.output + '\n';
                    }
                    break;

                case 'vision_complete':
                    this.stopFakeThoughts();
                    this.stopHum();

                    // Jump progress to 100%
                    this.progressPercent = 100;
                    this.codeGenerating = false;
                    this.codeExecuting = false;
                    this.currentSubstep = 'Analysis complete';

                    // Store structured vision result
                    this.visionResult = {
                        item_count: data.item_count,
                        item_type: data.item_type,
                        summary: data.summary,
                        confidence: data.confidence,
                        search_query: data.search_query,
                        hasCodeExecution: (data.result && (
                            data.result.includes("Code output:") ||
                            data.result.includes("Total boxes detected:") ||
                            data.result.includes("code_execution_result")
                        ))
                    };

                    this.orchestratorText = "Vision Complete";

                    // Add has-results class to body for sticky header spacing
                    document.body.classList.add('has-results');

                    // Auto-advance to memory stage
                    setTimeout(() => {
                        this.step = 2;
                        this.startFakeThoughts('memory');
                        this.orchestratorText = "Vision Agent → Supplier Agent (A2A Discovery)";
                    }, 2500);
                    break;

                case 'vision_error':
                    this.stopFakeThoughts();
                    this.stopHum();
                    this.orchestratorText = "Vision Agent Error";
                    this.isProcessing = false;
                    alert(`Vision Agent Error: ${data.message}`);
                    break;

                case 'memory_start':
                    this.orchestratorText = "Supplier Agent → AlloyDB ScaNN (Searching)";
                    break;

                case 'memory_complete':
                    this.stopFakeThoughts();
                    this.playPing();

                    this.supplierResult = {
                        part: data.part,
                        supplier: data.supplier,
                        confidence: data.confidence
                    };

                    this.orchestratorText = "Supplier Match Found";

                    // Auto-advance to order stage
                    setTimeout(() => {
                        this.step = 3;
                        this.orchestratorText = "Supplier Agent → Order System (Placing Order)";
                    }, 2500);
                    break;

                case 'memory_error':
                    this.stopFakeThoughts();
                    this.orchestratorText = "Supplier Agent Error";
                    this.isProcessing = false;
                    alert(`Supplier Agent Error: ${data.message}`);
                    break;

                case 'order_placed':
                    this.playSuccess();

                    this.orderResult = {
                        orderId: data.order_id
                    };

                    this.orchestratorText = "Order Placed Successfully";
                    this.isProcessing = false;
                    // Set step to 4 so step 3 ("Place Order") shows as completed
                    this.step = 4;
                    break;

                case 'pong':
                    break;

                default:
                    console.log('Unknown message type:', data.type);
            }
        },

        // File upload handlers
        handleFileSelect(event) {
            const file = event.target.files[0];
            if (file && file.type.startsWith('image/')) {
                this.processFile(file);
            }
        },

        handleDrop(event) {
            this.isDragging = false;
            const file = event.dataTransfer.files[0];
            if (file && file.type.startsWith('image/')) {
                this.processFile(file);
            }
        },

        processFile(file) {
            this.uploadedFile = file;
            const reader = new FileReader();
            reader.onload = (e) => {
                this.uploadedImage = e.target.result;
            };
            reader.readAsDataURL(file);
        },

        resetUpload() {
            this.stopFakeThoughts();
            this.stopHum();

            this.uploadedImage = null;
            this.uploadedFile = null;
            this.isProcessing = false;
            this.step = 0;
            this.visionResult = null;
            this.supplierResult = null;
            this.orderResult = null;
            this.orchestratorText = "System Ready";
            this.rawLogs = [];

            this.progressPercent = 0;
            this.currentSubstep = '';
            this.codeGenerating = false;
            this.codeExecuting = false;
            this.generatedCode = '';
            this.executionOutput = '';
            this.liveLogStream = [];
            this.showAgentDiscovery = false;
            this.discoveredAgent = null;
            this.discoveryAgentType = null;

            document.body.classList.remove('has-results');
        },

        // Start analysis workflow
        async startAnalysis() {
            if (!this.uploadedFile || this.isProcessing) return;

            this.isProcessing = true;

            this.visionResult = null;
            this.supplierResult = null;
            this.orderResult = null;
            this.rawLogs = [];

            const formData = new FormData();
            formData.append('file', this.uploadedFile);

            try {
                const response = await fetch('/api/analyze', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    throw new Error('Upload failed');
                }

                console.log('Analysis started, listening for WebSocket events...');

            } catch (error) {
                console.error('Upload error:', error);
                alert('Failed to upload image. Please try again.');
                this.isProcessing = false;
                this.step = 0;
            }
        }
    };
}

// Make appState globally available for Alpine.js
window.appState = appState;
