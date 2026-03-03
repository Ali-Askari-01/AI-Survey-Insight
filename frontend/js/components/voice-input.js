/**
 * Voice Input Component — AssemblyAI-powered voice interview
 * Feature 2: Multi-Channel Collection (Voice channel)
 * Uses MediaRecorder to capture audio → uploads to backend → AssemblyAI transcribes
 * Browser SpeechRecognition provides optional live preview while recording.
 */
const VoiceInput = {
    session: null,
    mediaRecorder: null,
    audioChunks: [],
    recognition: null,
    isRecording: false,
    liveTranscript: '',
    finalTranscript: '',
    responses: [],
    surveyId: null,
    mediaStream: null,

    async init() {
        await this.loadActiveSurvey();
        this.render();
        this.bindEvents();
    },

    async loadActiveSurvey() {
        try {
            const surveys = await API.surveys.list();
            if (surveys && surveys.length > 0) {
                this.surveyId = surveys[0].id;
            } else {
                this.surveyId = 1;
            }
        } catch (e) {
            this.surveyId = 1;
        }
    },

    render() {
        const page = document.getElementById('page-voice');
        if (!page) return;
        page.innerHTML = `
            <div class="voice-input-container">
                <div class="voice-header">
                    <h2><i class="fas fa-microphone"></i> Voice Interview</h2>
                    <p class="text-muted">Speak your responses naturally — our AI will transcribe and analyze them using AssemblyAI.</p>
                </div>

                <div class="voice-status" id="voice-status">
                    <div class="voice-status-icon"><i class="fas fa-microphone-slash"></i></div>
                    <div class="voice-status-text">Click the button below to start</div>
                </div>

                <div class="voice-visualizer" id="voice-visualizer" hidden>
                    <div class="waveform">
                        ${Array(20).fill(0).map(() => '<div class="waveform-bar"></div>').join('')}
                    </div>
                </div>

                <div class="voice-question-display" id="voice-question" hidden>
                    <div class="ai-avatar"><i class="fas fa-robot"></i></div>
                    <div class="voice-question-text" id="voice-question-text"></div>
                </div>

                <div class="voice-transcript" id="voice-transcript" hidden>
                    <label class="text-muted"><i class="fas fa-closed-captioning"></i> Live Preview:</label>
                    <div id="transcript-text" class="transcript-text"></div>
                </div>

                <div class="voice-transcript" id="voice-final-transcript" hidden>
                    <label class="text-muted"><i class="fas fa-check-circle" style="color:var(--success)"></i> AssemblyAI Transcript:</label>
                    <div id="final-transcript-text" class="transcript-text" style="font-weight:500"></div>
                    <div id="transcript-meta" class="text-muted mt-1" style="font-size:0.8rem"></div>
                </div>

                <div class="voice-controls">
                    <button class="btn btn-primary btn-lg voice-record-btn" id="voice-record-btn">
                        <i class="fas fa-microphone"></i>
                        <span id="voice-btn-label">Start Recording</span>
                    </button>
                    <button class="btn btn-secondary" id="voice-submit-btn" hidden>
                        <i class="fas fa-paper-plane"></i> Submit Response
                    </button>
                    <button class="btn btn-ghost" id="voice-skip-btn" hidden>
                        Skip <i class="fas fa-forward"></i>
                    </button>
                </div>

                <div class="voice-history mt-3" id="voice-history" hidden>
                    <h3>Responses</h3>
                    <div id="voice-history-list"></div>
                </div>
            </div>
        `;
    },

    bindEvents() {
        document.getElementById('voice-record-btn')?.addEventListener('click', () => this.toggleRecording());
        document.getElementById('voice-submit-btn')?.addEventListener('click', () => this.submitResponse());
        document.getElementById('voice-skip-btn')?.addEventListener('click', () => this.skipQuestion());
    },

    async toggleRecording() {
        if (this.isRecording) {
            this.stopRecording();
        } else {
            await this.startRecording();
        }
    },

    async startRecording() {
        // Create session if needed
        if (!this.session) {
            try {
                this.session = await API.interviews.createSession({
                    survey_id: this.surveyId,
                    channel: 'voice',
                    respondent_id: 'voice_user_' + Helpers.uid()
                });
            } catch (e) {
                Helpers.toast('Error', 'Failed to start voice session', 'danger');
                return;
            }
        }

        // Request microphone access
        try {
            this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch (e) {
            Helpers.toast('Permission Denied', 'Please allow microphone access to record.', 'danger');
            return;
        }

        // Set up MediaRecorder for actual audio capture
        this.audioChunks = [];
        this.mediaRecorder = new MediaRecorder(this.mediaStream, { mimeType: this.getSupportedMime() });

        this.mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) this.audioChunks.push(e.data);
        };

        this.mediaRecorder.onstop = () => {
            // Audio is ready for upload — handled in stopRecording
        };

        this.mediaRecorder.start(250); // collect in 250ms chunks

        // Optional: start browser SpeechRecognition for live preview
        this.startLivePreview();

        this.isRecording = true;
        this.liveTranscript = '';
        this.finalTranscript = '';
        this.updateRecordingUI(true);
        this.showNextQuestion();
    },

    getSupportedMime() {
        const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
        for (const t of types) {
            if (MediaRecorder.isTypeSupported(t)) return t;
        }
        return 'audio/webm';
    },

    startLivePreview() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) return; // Skip live preview if not supported

        this.recognition = new SpeechRecognition();
        this.recognition.continuous = true;
        this.recognition.interimResults = true;
        this.recognition.lang = 'en-US';
        this.liveTranscript = '';

        this.recognition.onresult = (event) => {
            let interim = '';
            let final = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                if (event.results[i].isFinal) {
                    final += event.results[i][0].transcript;
                } else {
                    interim += event.results[i][0].transcript;
                }
            }
            if (final) this.liveTranscript += final + ' ';

            const el = document.getElementById('transcript-text');
            if (el) el.textContent = this.liveTranscript + (interim || '');
            document.getElementById('voice-transcript').hidden = false;
        };

        this.recognition.onerror = () => { /* live preview is optional */ };
        this.recognition.onend = () => {
            if (this.isRecording) {
                try { this.recognition.start(); } catch (e) { /* ok */ }
            }
        };

        try { this.recognition.start(); } catch (e) { /* ok */ }
    },

    async stopRecording() {
        this.isRecording = false;

        // Stop live preview
        if (this.recognition) {
            try { this.recognition.stop(); } catch (e) {}
        }

        // Stop MediaRecorder
        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
            this.mediaRecorder.stop();
        }

        // Stop microphone stream
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(t => t.stop());
        }

        this.updateRecordingUI(false);

        // Wait a beat for final data chunk
        await new Promise(r => setTimeout(r, 300));

        if (this.audioChunks.length === 0) {
            Helpers.toast('Info', 'No audio captured. Try again.', 'warning');
            return;
        }

        // Upload to AssemblyAI via backend
        const audioBlob = new Blob(this.audioChunks, { type: this.getSupportedMime() });
        const ext = this.getSupportedMime().includes('webm') ? '.webm' : '.ogg';

        Helpers.toast('Processing', 'Uploading audio to AssemblyAI for transcription...', 'info', 5000);

        try {
            const result = await API.interviews.transcribe(audioBlob, `recording${ext}`);

            this.finalTranscript = result.text || '';

            // Show final transcript
            document.getElementById('voice-transcript').hidden = true; // hide live
            const finalEl = document.getElementById('voice-final-transcript');
            const finalText = document.getElementById('final-transcript-text');
            const metaEl = document.getElementById('transcript-meta');

            if (finalEl && finalText) {
                finalEl.hidden = false;
                finalText.textContent = this.finalTranscript || '(No speech detected)';
            }
            if (metaEl) {
                const conf = result.confidence ? `${(result.confidence * 100).toFixed(1)}%` : '—';
                const dur = result.duration_ms ? `${(result.duration_ms / 1000).toFixed(1)}s` : '—';
                const lang = result.language || 'en';
                metaEl.textContent = `Confidence: ${conf}  |  Duration: ${dur}  |  Language: ${lang}`;
            }

            if (this.finalTranscript) {
                document.getElementById('voice-submit-btn').hidden = false;
                document.getElementById('voice-skip-btn').hidden = false;
                Helpers.toast('Success', 'Transcription complete!', 'success');
            } else {
                Helpers.toast('Warning', 'No speech detected. Try recording again.', 'warning');
            }

        } catch (e) {
            console.error('Transcription failed:', e);
            // Fallback to live preview text if available
            if (this.liveTranscript.trim()) {
                this.finalTranscript = this.liveTranscript.trim();
                document.getElementById('voice-submit-btn').hidden = false;
                document.getElementById('voice-skip-btn').hidden = false;
                Helpers.toast('Warning', 'AssemblyAI unavailable — using browser transcript.', 'warning');
            } else {
                Helpers.toast('Error', 'Transcription failed. Please try again.', 'danger');
            }
        }
    },

    updateRecordingUI(recording) {
        const btn = document.getElementById('voice-record-btn');
        const label = document.getElementById('voice-btn-label');
        const viz = document.getElementById('voice-visualizer');
        const status = document.getElementById('voice-status');

        if (recording) {
            btn?.classList.add('recording');
            if (label) label.textContent = 'Stop Recording';
            if (viz) viz.hidden = false;
            if (status) {
                status.innerHTML = `
                    <div class="voice-status-icon recording"><i class="fas fa-circle" style="color:var(--danger);animation:pulse 1s infinite"></i></div>
                    <div class="voice-status-text">Listening... (recording audio for AssemblyAI)</div>
                `;
            }
            this.animateWaveform(true);
        } else {
            btn?.classList.remove('recording');
            if (label) label.textContent = 'Start Recording';
            if (viz) viz.hidden = true;
            if (status) {
                status.innerHTML = `
                    <div class="voice-status-icon"><i class="fas fa-microphone-slash"></i></div>
                    <div class="voice-status-text">Recording stopped</div>
                `;
            }
            this.animateWaveform(false);
        }
    },

    waveformInterval: null,
    animateWaveform(active) {
        const bars = document.querySelectorAll('.waveform-bar');
        if (active) {
            this.waveformInterval = setInterval(() => {
                bars.forEach(bar => {
                    bar.style.height = (10 + Math.random() * 40) + 'px';
                });
            }, 100);
        } else {
            clearInterval(this.waveformInterval);
            bars.forEach(bar => bar.style.height = '10px');
        }
    },

    showNextQuestion() {
        const questionEl = document.getElementById('voice-question');
        const textEl = document.getElementById('voice-question-text');
        if (!questionEl || !textEl) return;

        const questions = [
            "How would you describe your overall experience with our product?",
            "What features do you find most useful?",
            "What improvements would you suggest?",
            "How does our product compare to alternatives you've tried?",
            "Would you recommend our product to others? Why or why not?"
        ];

        const idx = this.responses.length;
        if (idx >= questions.length) {
            this.showCompletion();
            return;
        }

        questionEl.hidden = false;
        textEl.textContent = questions[idx];

        // Speak the question (TTS)
        if ('speechSynthesis' in window) {
            const utterance = new SpeechSynthesisUtterance(questions[idx]);
            utterance.rate = 0.9;
            utterance.pitch = 1;
            window.speechSynthesis.speak(utterance);
        }
    },

    async submitResponse() {
        if (!this.finalTranscript.trim()) return;

        const response = {
            text: this.finalTranscript.trim(),
            timestamp: new Date().toISOString()
        };
        this.responses.push(response);

        // Submit to API
        if (this.session) {
            try {
                await API.interviews.respond({
                    session_id: this.session.session_id,
                    question_id: this.responses.length,
                    response_text: response.text,
                    response_type: 'voice'
                });
            } catch (e) { console.error('Failed to submit voice response:', e); }
        }

        // Update history
        this.updateHistory();

        // Reset for next question
        this.finalTranscript = '';
        this.liveTranscript = '';
        this.audioChunks = [];
        document.getElementById('transcript-text').textContent = '';
        document.getElementById('voice-transcript').hidden = true;
        document.getElementById('voice-final-transcript').hidden = true;
        document.getElementById('voice-submit-btn').hidden = true;
        document.getElementById('voice-skip-btn').hidden = true;

        Helpers.toast('Submitted', 'Response recorded!', 'success');
        this.showNextQuestion();
    },

    skipQuestion() {
        this.responses.push({ text: '[Skipped]', timestamp: new Date().toISOString() });
        this.finalTranscript = '';
        this.liveTranscript = '';
        this.audioChunks = [];
        document.getElementById('transcript-text').textContent = '';
        document.getElementById('voice-transcript').hidden = true;
        document.getElementById('voice-final-transcript').hidden = true;
        document.getElementById('voice-submit-btn').hidden = true;
        document.getElementById('voice-skip-btn').hidden = true;
        this.updateHistory();
        this.showNextQuestion();
    },

    updateHistory() {
        const container = document.getElementById('voice-history');
        const list = document.getElementById('voice-history-list');
        if (!container || !list) return;
        container.hidden = false;

        list.innerHTML = this.responses.map((r, i) => `
            <div class="voice-response-item">
                <div class="voice-response-num">Q${i + 1}</div>
                <div class="voice-response-text">${Helpers.escapeHtml(r.text)}</div>
            </div>
        `).join('');
    },

    showCompletion() {
        if (this.isRecording) this.stopRecording();

        const page = document.getElementById('page-voice');
        if (!page) return;

        page.innerHTML = `
            <div class="voice-input-container" style="text-align:center; padding: var(--space-6)">
                <div style="font-size:4rem; color: var(--success)"><i class="fas fa-check-circle"></i></div>
                <h2 class="mt-2">Voice Interview Complete!</h2>
                <p class="text-muted mt-1">Thank you for sharing your feedback through voice. All ${this.responses.length} responses have been recorded and transcribed by AssemblyAI.</p>
                <button class="btn btn-primary mt-3" onclick="VoiceInput.restart()">
                    <i class="fas fa-redo"></i> Start New Interview
                </button>
            </div>
        `;
    },

    restart() {
        this.session = null;
        this.responses = [];
        this.finalTranscript = '';
        this.liveTranscript = '';
        this.audioChunks = [];
        this.isRecording = false;
        this.init();
    },

    destroy() {
        if (this.isRecording) this.stopRecording();
        if (this.waveformInterval) clearInterval(this.waveformInterval);
        if (this.mediaStream) this.mediaStream.getTracks().forEach(t => t.stop());
        if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    }
};
