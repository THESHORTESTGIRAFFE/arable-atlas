/**
 * Plotty 🌱 AI - Assistant Controller
 * Handles the chat interface, voice synthesis, and multi-language support.
 */

document.addEventListener('DOMContentLoaded', () => {
    const chatBody = document.getElementById('chatBody');
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendChat');
    const langSelect = document.getElementById('languageSelect');
    const voiceBtn = document.getElementById('voiceBtn');
    const cameraBtn = document.getElementById('cameraBtn');
    const cameraUpload = document.getElementById('cameraUpload');

    if (!chatBody || !chatInput || !sendBtn) return;

    /**
     * Appends a message to the chat body with a smooth fade-in effect.
     */
    function appendMessage(text, isUser = false) {
        const bubbleClass = isUser ? 'user-bubble' : 'bot-bubble';
        const messageDiv = document.createElement('div');
        messageDiv.className = `${bubbleClass} mb-4 animate__animated animate__fadeInUp`;

        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        let audioControls = '';
        if (!isUser) {
            audioControls = `
                <button class="btn btn-sm btn-link text-muted p-0 ms-2" title="Read Aloud" onclick="readAloud('${text.replace(/'/g, "\\'")}')">
                    <i class='bx bx-volume-full'></i>
                </button>
            `;
        }

        messageDiv.innerHTML = `
            <div class="bubble-content shadow-sm d-flex align-items-center">
                ${text}
                ${audioControls}
            </div>
            <div class="bubble-time">${time}</div>
        `;

        chatBody.appendChild(messageDiv);
        chatBody.scrollTo({
            top: chatBody.scrollHeight,
            behavior: 'smooth'
        });
    }

    /**
     * Reads text aloud manually when triggered.
     * Selects the best available voice, prioritizing natural-sounding options.
     */
    window.readAloud = (text) => {
        if ('speechSynthesis' in window) {
            speechSynthesis.cancel(); // Stop any ongoing speech
            const utterance = new SpeechSynthesisUtterance(text);
            
            // Get available voices
            const voices = speechSynthesis.getVoices();
            
            // Prioritize higher-quality, natural-sounding voices
            // This prioritizes Google/Chrome voices which are usually high-fidelity
            const targetLang = langSelect.value === 'sn' ? 'sn' : (langSelect.value === 'nd' ? 'nd' : 'en');
            
            const preferredVoice = voices.find(voice => 
                voice.lang.toLowerCase().startsWith(targetLang) && 
                (voice.name.includes('Google') || voice.name.includes('Natural') || voice.name.includes('Enhanced'))
            );

            if (preferredVoice) {
                utterance.voice = preferredVoice;
            } else {
                // Fallback to basic language matching
                utterance.lang = langSelect.value === 'sn' ? 'sn-ZW' : (langSelect.value === 'nd' ? 'nd-ZW' : 'en-US');
            }

            utterance.rate = 1.0;
            speechSynthesis.speak(utterance);
        }
    };

    /**
     * Sends the current user input to the backend.
     */
    async function sendMessage() {
        const query = chatInput.value.trim();
        if (!query) return;

        appendMessage(query, true);
        chatInput.value = '';

        // Add typing indicator
        const typingDiv = document.createElement('div');
        typingDiv.className = 'bot-bubble mb-4 typing-indicator';
        typingDiv.innerHTML = '<div class="bubble-content bg-transparent border-0 text-muted italic">Plotty is thinking...</div>';
        chatBody.appendChild(typingDiv);
        chatBody.scrollTop = chatBody.scrollHeight;

        try {
            const response = await fetch('/ask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: query,
                    language: langSelect.value
                })
            });

            const data = await response.json();
            chatBody.removeChild(typingDiv);

            if (data.response) {
                appendMessage(data.response);
            } else {
                appendMessage("I encountered an issue processing that. Could you try again?");
            }
        } catch (error) {
            if (chatBody.contains(typingDiv)) chatBody.removeChild(typingDiv);
            appendMessage("I'm having trouble connecting to the server. Please check your connection.");
        }
    }

    // Event Listeners
    sendBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });

    // Voice Input Handling
    if (voiceBtn) {
        voiceBtn.addEventListener('click', () => {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) {
                alert("Voice recognition is not supported in your browser.");
                return;
            }

            const recognition = new SpeechRecognition();
            recognition.lang = langSelect.value === 'sn' ? 'sn-ZW' : 'en-US';
            
            recognition.onstart = () => {
                voiceBtn.classList.add('text-danger', 'animate__animated', 'animate__pulse', 'animate__infinite');
            };

            recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                chatInput.value = transcript;
            };

            recognition.onend = () => {
                voiceBtn.classList.remove('text-danger', 'animate__animated', 'animate__pulse', 'animate__infinite');
            };

            recognition.onerror = () => {
                voiceBtn.classList.remove('text-danger');
            };

            recognition.start();
        });
    }

    // Camera/Image Analysis Integration
    if (cameraBtn && cameraUpload) {
        cameraBtn.addEventListener('click', () => cameraUpload.click());
        cameraUpload.addEventListener('change', async (event) => {
            const file = event.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('image', file);

            appendMessage("Analyzing soil image...", true);

            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();

                if (data.error) {
                    appendMessage(`Error analyzing image: ${data.error}`);
                } else {
                    appendMessage(`Analysis complete for location: ${data.location}. Soil type is ${data.soil_type} with a pH of ${data.ph}. Suitable crops: ${data.crops.join(', ')}.`);
                }
            } catch (error) {
                appendMessage("Failed to upload and analyze the image.");
            }
        });
    }
});
