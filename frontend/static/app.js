/**
 * Alpine.js State Management and WebSocket Handler
 * Manages real-time updates from the backend workflow
 */

function appState() {
    return {
        // WebSocket connection
        ws: null,
        wsConnected: false,
        
        // Upload state
        uploadedImage: null,
        uploadedFile: null,
        isDragging: false,
        isProcessing: false,
        
        // Messages timeline
        messages: [],
        
        // Sample images
        showSampleModal: false,
        sampleImages: [],
        
        // Agent states with tabs
        agents: {
            vision: {
                status: 'idle', // idle, thinking, success, error
                message: 'Waiting for image...',
                code: null,
                activeTab: 'status',
                thinkingSteps: []
            },
            memory: {
                status: 'idle',
                message: 'Ready to search...',
                part: null,
                supplier: null,
                confidence: null,
                activeTab: 'status',
                thinkingSteps: []
            },
            action: {
                status: 'idle',
                message: 'Awaiting approval...',
                orderId: null,
                activeTab: 'status',
                thinkingSteps: []
            }
        },
        
        // Progress phases
        phases: [
            { label: 'Upload', active: false, completed: false },
            { label: 'Discovery', active: false, completed: false },
            { label: 'Vision', active: false, completed: false },
            { label: 'Memory', active: false, completed: false },
            { label: 'Action', active: false, completed: false }
        ],
        
        progressPercent: 0,
        
        // Initialize on component mount
        async init() {
            this.connectWebSocket();
            
            // Initialize syntax highlighting
            if (typeof hljs !== 'undefined') {
                hljs.configure({ languages: ['python', 'json'] });
            }
            
            // Load sample images
            await this.loadSampleImages();
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
        
        // Select a sample image
        async selectSampleImage(name) {
            try {
                const response = await fetch(`/api/test-image/${name}`);
                if (response.ok) {
                    const blob = await response.blob();
                    this.uploadedFile = new File([blob], name, { type: blob.type });
                    this.uploadedImage = URL.createObjectURL(blob);
                    this.showSampleModal = false;
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
            
            const timestamp = Date.now();
            
            switch(data.type) {
                case 'upload_complete':
                    this.updatePhase(0, true, false);
                    this.addMessage('System', data.message, timestamp);
                    break;
                    
                case 'discovery_start':
                    if (data.agent === 'vision') {
                        this.updatePhase(1, false, true);
                        this.agents.vision.status = 'thinking';
                        this.agents.vision.message = 'Discovering via A2A...';
                    } else if (data.agent === 'supplier') {
                        this.agents.memory.status = 'thinking';
                        this.agents.memory.message = 'Discovering via A2A...';
                    }
                    this.addMessage('Discovery', data.message, timestamp);
                    break;
                    
                case 'discovery_complete':
                    if (data.agent === 'vision') {
                        this.updatePhase(1, true, false);
                    }
                    this.addMessage('Discovery', data.message, timestamp);
                    break;
                    
                case 'vision_start':
                    this.updatePhase(2, false, true);
                    this.agents.vision.status = 'thinking';
                    this.agents.vision.message = 'Analyzing with Gemini 3 Flash...';
                    this.addMessage('Vision Agent', data.message, timestamp, data.details);
                    break;
                    
                case 'vision_complete':
                    this.updatePhase(2, true, false);
                    this.agents.vision.status = 'success';
                    this.agents.vision.message = 'Analysis complete ✓';
                    
                    // Highlight code if present
                    if (data.code_output) {
                        const highlighted = this.highlightCode(data.code_output);
                        this.agents.vision.code = highlighted;
                    }
                    
                    this.addMessage('Vision Agent', data.result, timestamp);
                    break;
                    
                case 'vision_error':
                    this.agents.vision.status = 'error';
                    this.agents.vision.message = 'Error occurred ✗';
                    this.addMessage('Vision Agent', data.message, timestamp);
                    this.isProcessing = false;
                    break;
                    
                case 'memory_start':
                    this.updatePhase(3, false, true);
                    this.agents.memory.status = 'thinking';
                    this.agents.memory.message = 'Querying AlloyDB ScaNN...';
                    this.addMessage('Memory Agent', data.message, timestamp, data.details);
                    break;
                    
                case 'memory_complete':
                    this.updatePhase(3, true, false);
                    this.agents.memory.status = 'success';
                    this.agents.memory.message = 'Match found ✓';
                    this.agents.memory.part = data.part;
                    this.agents.memory.supplier = data.supplier;
                    this.agents.memory.confidence = data.confidence;
                    
                    const matchMsg = `${data.part} from ${data.supplier} (${data.confidence})`;
                    this.addMessage('Memory Agent', matchMsg, timestamp);
                    break;
                    
                case 'memory_error':
                    this.agents.memory.status = 'error';
                    this.agents.memory.message = 'Error occurred ✗';
                    this.addMessage('Memory Agent', data.message, timestamp);
                    this.isProcessing = false;
                    break;
                    
                case 'order_placed':
                    this.updatePhase(4, true, false);
                    this.agents.action.status = 'success';
                    this.agents.action.message = 'Order placed ✓';
                    this.agents.action.orderId = data.order_id;
                    this.addMessage('Action', data.message, timestamp);
                    this.isProcessing = false;
                    break;
                
                case 'thinking_update':
                    // Update agent thinking steps
                    if (this.agents[data.agent]) {
                        this.agents[data.agent].thinkingSteps = data.steps || [];
                    }
                    break;
                    
                case 'pong':
                    // Connection health check response
                    break;
                    
                default:
                    console.log('Unknown message type:', data.type);
            }
            
            // Auto-scroll chat to bottom
            this.$nextTick(() => {
                const container = this.$refs.chatContainer;
                if (container) {
                    container.scrollTop = container.scrollHeight;
                }
            });
        },
        
        // Update phase progress
        updatePhase(index, completed, active) {
            this.phases[index].completed = completed;
            this.phases[index].active = active;
            
            // Calculate progress percentage
            const completedCount = this.phases.filter(p => p.completed).length;
            this.progressPercent = (completedCount / this.phases.length) * 100;
        },
        
        // Add message to timeline
        addMessage(type, message, timestamp, details = null) {
            this.messages.push({
                type,
                message,
                timestamp,
                details
            });
        },
        
        // Syntax highlighting for code
        highlightCode(code) {
            if (typeof hljs !== 'undefined') {
                try {
                    return hljs.highlight(code, { language: 'python' }).value;
                } catch (e) {
                    return code;
                }
            }
            return code;
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
            this.uploadedImage = null;
            this.uploadedFile = null;
            this.isProcessing = false;
            this.messages = [];
            
            // Reset agent states
            this.agents.vision = { 
                status: 'idle', 
                message: 'Waiting for image...', 
                code: null, 
                activeTab: 'status',
                thinkingSteps: []
            };
            this.agents.memory = { 
                status: 'idle', 
                message: 'Ready to search...', 
                part: null, 
                supplier: null, 
                confidence: null,
                activeTab: 'status',
                thinkingSteps: []
            };
            this.agents.action = { 
                status: 'idle', 
                message: 'Awaiting approval...', 
                orderId: null,
                activeTab: 'status',
                thinkingSteps: []
            };
            
            // Reset phases
            this.phases.forEach(phase => {
                phase.active = false;
                phase.completed = false;
            });
            this.progressPercent = 0;
        },
        
        // Start analysis workflow
        async startAnalysis() {
            if (!this.uploadedFile || this.isProcessing) return;
            
            this.isProcessing = true;
            this.messages = [];
            
            // Reset states
            this.agents.vision = { 
                status: 'idle', 
                message: 'Starting...', 
                code: null,
                activeTab: 'status',
                thinkingSteps: []
            };
            this.agents.memory = { 
                status: 'idle', 
                message: 'Waiting...', 
                part: null, 
                supplier: null, 
                confidence: null,
                activeTab: 'status',
                thinkingSteps: []
            };
            this.agents.action = { 
                status: 'idle', 
                message: 'Pending...', 
                orderId: null,
                activeTab: 'status',
                thinkingSteps: []
            };
            
            this.phases.forEach(phase => {
                phase.active = false;
                phase.completed = false;
            });
            this.progressPercent = 0;
            
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
            }
        },
        
        // UI helper methods
        getPhaseClass(phase) {
            if (phase.completed) {
                return 'bg-green-500 text-white';
            } else if (phase.active) {
                return 'bg-blue-500 text-white';
            } else {
                return 'bg-gray-700 text-gray-400';
            }
        },
        
        getAgentCardClass(agentType) {
            const status = this.agents[agentType].status;
            
            if (status === 'thinking') {
                return 'border-blue-500 pulse-border';
            } else if (status === 'success') {
                return 'border-green-500';
            } else if (status === 'error') {
                return 'border-red-500';
            } else {
                return 'border-gray-700';
            }
        },
        
        getMessageIcon(type) {
            const icons = {
                'System': '⚙️',
                'Discovery': '🤝',
                'Vision Agent': '👁️',
                'Memory Agent': '🧠',
                'Action': '✅'
            };
            return icons[type] || '📋';
        },
        
        getMessageIconBg(type) {
            const backgrounds = {
                'System': 'bg-gray-700',
                'Discovery': 'bg-purple-900',
                'Vision Agent': 'bg-blue-900',
                'Memory Agent': 'bg-yellow-900',
                'Action': 'bg-green-900'
            };
            return backgrounds[type] || 'bg-gray-700';
        },
        
        // Get message position for conversational layout
        getMessagePosition(type) {
            const positions = {
                'System': 'center',
                'Discovery': 'center',
                'Vision Agent': 'left',
                'Memory Agent': 'right',
                'Action': 'center'
            };
            return positions[type] || 'center';
        }
    };
}

// Make appState globally available for Alpine.js
window.appState = appState;
