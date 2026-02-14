/**
 * Cinematic Demo App State Management
 * Alpine.js state machine for the 4-act autonomous supply chain demo
 */

function appState() {
    return {
        // WebSocket connection
        ws: null,
        wsConnected: false,
        
        // Step wizard (0=Upload, 1=Vision, 2=Memory, 3=Order)
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
                // Create oscillators for layered hum
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
                // Two-tone ascending chime (C5 then E5)
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
        
        // Fake thoughts engine
        startFakeThoughts(type) {
            const thoughts = type === 'vision' ? this.visionThoughts : this.memoryThoughts;
            this.thoughtIndex = 0;
            this.currentThought = thoughts[0];
            
            this.thoughtInterval = setInterval(() => {
                this.thoughtIndex = (this.thoughtIndex + 1) % thoughts.length;
                this.currentThought = thoughts[this.thoughtIndex];
            }, 800);
        },
        
        stopFakeThoughts() {
            if (this.thoughtInterval) {
                clearInterval(this.thoughtInterval);
                this.thoughtInterval = null;
            }
            this.currentThought = '';
        },
        
        // Progress simulation for 90s experience
        simulateProgress() {
            // Phase 1: Thinking (0-30%) - 27s
            this.progressPercent = 0;
            this.currentSubstep = 'Initializing Gemini 3 Flash...';
            
            const thinkingInterval = setInterval(() => {
                if (this.progressPercent < 30) {
                    this.progressPercent += 1;
                    if (this.progressPercent === 10) this.currentSubstep = 'Analyzing image composition...';
                    if (this.progressPercent === 20) this.currentSubstep = 'Identifying object patterns...';
                }
            }, 900); // 27s total for 0→30%
            
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
                }, 900); // 18s for 30→50%
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
                }, 900); // 36s for 50→90%
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
                    
                    // Auto-start the analysis after a brief delay
                    this.$nextTick(() => {
                        setTimeout(() => this.startAnalysis(), 300);
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
                
                // Attempt to reconnect after 3 seconds
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
            
            // Send periodic ping to keep connection alive
            setInterval(() => {
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send('ping');
                }
            }, 30000);
        },
        
        // Handle incoming WebSocket messages
        handleWebSocketMessage(data) {
            console.log('Received:', data);
            
            // Add to raw logs for the drawer
            this.rawLogs.push({...data, timestamp: new Date().toISOString()});
            
            // Limit logs to 100 entries
            if (this.rawLogs.length > 100) {
                this.rawLogs.shift();
            }
            
            switch(data.type) {
                case 'upload_complete':
                    this.step = 1;
                    this.startFakeThoughts('vision');
                    this.simulateProgress();  // Start progress tracking
                    this.playHum();
                    this.orchestratorText = "Control Tower → Vision Agent (A2A Discovery)";
                    break;
                    
                case 'discovery_start':
                    if (data.agent === 'vision') {
                        this.orchestratorText = "Discovering Vision Agent via A2A...";
                    } else if (data.agent === 'supplier') {
                        this.orchestratorText = "Discovering Supplier Agent via A2A...";
                        // Show A2A discovery modal
                        this.showAgentDiscovery = true;
                        this.discoveredAgent = null;
                        // Simulate 3s discovery process
                        setTimeout(() => {
                            this.discoveredAgent = {
                                name: 'supplier',
                                displayName: 'Supplier Agent',
                                description: 'Matches inventory needs with supplier database using AlloyDB vector search and semantic similarity',
                                endpoint: 'supplier-agent.local:8001',
                                capabilities: 'Vector search, Supplier matching, Pricing lookup'
                            };
                            this.playPing(); // Sound effect
                        }, 3000);
                    }
                    break;
                    
                case 'discovery_complete':
                    if (data.agent === 'vision') {
                        this.orchestratorText = "Vision Agent → Gemini 3 Flash (Analyzing)";
                    }
                    // Auto-close A2A modal after showing connected state
                    if (this.showAgentDiscovery) {
                        setTimeout(() => {
                            this.showAgentDiscovery = false;
                        }, 2000);
                    }
                    break;
                    
                case 'vision_start':
                    this.orchestratorText = "Vision Agent → Gemini 3 Flash (Analyzing)";
                    break;
                    
                case 'vision_progress':
                    // Live updates from backend during processing
                    this.liveLogStream.push({
                        time: new Date().toLocaleTimeString(),
                        message: data.message,
                        type: data.substep  // 'thinking', 'code', 'execution'
                    });
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
                    
                    // Store structured vision result with code execution detection
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
                    
                    this.orchestratorText = "Vision Complete ✓";
                    
                    // Auto-advance to memory stage after 2.5s
                    setTimeout(() => {
                        this.step = 2;
                        this.startFakeThoughts('memory');
                        this.orchestratorText = "Vision Agent → Supplier Agent (A2A Discovery)";
                    }, 2500);
                    break;
                    
                case 'vision_error':
                    this.stopFakeThoughts();
                    this.stopHum();
                    this.orchestratorText = "Vision Agent Error ✗";
                    this.isProcessing = false;
                    alert(`Vision Agent Error: ${data.message}`);
                    break;
                    
                case 'memory_start':
                    this.orchestratorText = "Supplier Agent → AlloyDB ScaNN (Searching)";
                    break;
                    
                case 'memory_complete':
                    this.stopFakeThoughts();
                    this.playPing();
                    
                    // Store supplier result
                    this.supplierResult = {
                        part: data.part,
                        supplier: data.supplier,
                        confidence: data.confidence
                    };
                    
                    this.orchestratorText = "Supplier Match Found ✓";
                    
                    // Auto-advance to order stage after 2.5s
                    setTimeout(() => {
                        this.step = 3;
                        this.orchestratorText = "Supplier Agent → Order System (Placing Order)";
                    }, 2500);
                    break;
                    
                case 'memory_error':
                    this.stopFakeThoughts();
                    this.orchestratorText = "Supplier Agent Error ✗";
                    this.isProcessing = false;
                    alert(`Supplier Agent Error: ${data.message}`);
                    break;
                    
                case 'order_placed':
                    this.playSuccess();
                    
                    // Store order result
                    this.orderResult = {
                        orderId: data.order_id
                    };
                    
                    this.orchestratorText = "Order Placed Successfully ✓";
                    this.isProcessing = false;
                    break;
                    
                case 'pong':
                    // Connection health check response
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
            // Stop any ongoing processes
            this.stopFakeThoughts();
            this.stopHum();
            
            // Reset all state
            this.uploadedImage = null;
            this.uploadedFile = null;
            this.isProcessing = false;
            this.step = 0;
            this.visionResult = null;
            this.supplierResult = null;
            this.orderResult = null;
            this.orchestratorText = "System Ready";
            this.rawLogs = [];
            
            // Reset progress tracking
            this.progressPercent = 0;
            this.currentSubstep = '';
            this.codeGenerating = false;
            this.codeExecuting = false;
            this.generatedCode = '';
            this.executionOutput = '';
            this.liveLogStream = [];
            this.showAgentDiscovery = false;
            this.discoveredAgent = null;
        },
        
        // Start analysis workflow
        async startAnalysis() {
            if (!this.uploadedFile || this.isProcessing) return;
            
            this.isProcessing = true;
            
            // Reset results
            this.visionResult = null;
            this.supplierResult = null;
            this.orderResult = null;
            this.rawLogs = [];
            
            // Upload file to backend
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
                
                // Backend will send updates via WebSocket
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