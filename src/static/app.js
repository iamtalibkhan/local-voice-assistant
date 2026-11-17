// Local Voice Assistant - Frontend Client
document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const chatMessages = document.getElementById("chat-messages");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const micBtn = document.getElementById("mic-btn");
  const statusText = document.getElementById("status-text");
  const recordingTimer = document.getElementById("recording-timer");
  const stopVoiceBtn = document.getElementById("stop-voice-btn");
  const handsfreeBtn = document.getElementById("handsfree-btn");
  const visualizerCanvas = document.getElementById("visualizer");
  const systemStatus = document.getElementById("system-status");
  const settingsPanel = document.getElementById("settings-panel");
  const toggleSettingsBtn = document.getElementById("toggle-settings-btn");
  const closeSettingsBtn = document.getElementById("close-settings-btn");
  const resetSessionBtn = document.getElementById("reset-session-btn");
  const toggleSidebarBtn = document.getElementById("toggle-sidebar-btn");
  const sessionsSidebar = document.getElementById("sessions-sidebar");
  const newChatBtn = document.getElementById("new-chat-btn");
  const pinnedSectionLabel = document.getElementById("pinned-section-label");
  const pinnedSessionsList = document.getElementById("pinned-sessions-list");
  const recentSectionLabel = document.getElementById("recent-section-label");
  const recentSessionsList = document.getElementById("recent-sessions-list");
  const voiceSelect = document.getElementById("voice-select");
  const speedRange = document.getElementById("speed-range");
  const speedDisplay = document.getElementById("speed-display");
  const autoplayCheckbox = document.getElementById("autoplay-audio");
  
  // VAD & Sensitivity Elements
  const silenceRange = document.getElementById("silence-range");
  const silenceDisplay = document.getElementById("silence-display");
  const sensitivityRange = document.getElementById("sensitivity-range");
  const sensitivityDisplay = document.getElementById("sensitivity-display");

  // TTS Playground Elements
  const ttsConfigInput = document.getElementById("tts-test-input");
  const ttsSynthesizeBtn = document.getElementById("tts-synthesize-btn");
  const ttsPlaygroundPlayer = document.getElementById("tts-playground-player");
  const playgroundAudio = document.getElementById("playground-audio");

  // Health Stats Elements
  const statApi = document.getElementById("stat-api");
  const statWhisper = document.getElementById("stat-whisper");
  const statKokoro = document.getElementById("stat-kokoro");

  // Canvas visualizer setup
  const canvasCtx = visualizerCanvas.getContext("2d");
  let audioContext = null;
  let analyser = null;
  let microphoneStream = null;
  let animationId = null;

  // MediaRecorder & Audio capture state
  let mediaRecorder = null;
  let audioChunks = [];
  let isRecording = false;
  let timerInterval = null;
  let recordSeconds = 0;

  // Audio playback cache & state
  let currentAudio = null;
  let activePlayButton = null;
  let isAssistantSpeaking = false;
  let isProcessing = false;
  let isDetailedPending = false;

  // Hands-free & VAD state
  let isHandsFreeActive = false;
  let silenceDuration = 1.5; // seconds
  let silenceTimer = null;

  // Session Memory & Multi-Chat state
  let sessionsData = [];

  function getActiveSessionId() {
    let sid = sessionStorage.getItem("assistant_session_id") || localStorage.getItem("last_active_session_id");
    if (!sid) {
      sid = "sess_" + Math.random().toString(36).substring(2, 10) + "_" + Date.now();
      sessionStorage.setItem("assistant_session_id", sid);
      localStorage.setItem("last_active_session_id", sid);
    }
    return sid;
  }
  let currentSessionId = getActiveSessionId();
  console.log("[Local Assistant] Active Session ID:", currentSessionId);

  async function loadSessionsList() {
    try {
      const res = await fetch("/session");
      if (!res.ok) throw new Error("Failed to load sessions");
      sessionsData = await res.json();
      renderSessionsList();
    } catch (err) {
      console.warn("Could not load sessions list:", err);
      if (recentSessionsList) {
        recentSessionsList.innerHTML = `<div class="sessions-empty">Could not load chats</div>`;
      }
    }
  }

  function renderSessionsList() {
    if (!pinnedSessionsList || !recentSessionsList) return;
    pinnedSessionsList.innerHTML = "";
    recentSessionsList.innerHTML = "";

    const pinned = sessionsData.filter(s => s.is_pinned);
    const recent = sessionsData.filter(s => !s.is_pinned);

    if (pinned.length > 0) {
      pinnedSectionLabel.style.display = "block";
      pinned.forEach(session => {
        pinnedSessionsList.appendChild(createSessionItemElem(session));
      });
    } else {
      pinnedSectionLabel.style.display = "none";
    }

    if (recent.length > 0) {
      recentSectionLabel.style.display = "block";
      recent.forEach(session => {
        recentSessionsList.appendChild(createSessionItemElem(session));
      });
    } else {
      recentSectionLabel.style.display = pinned.length > 0 ? "block" : "none";
      if (pinned.length === 0) {
        recentSessionsList.innerHTML = `<div class="sessions-empty">No conversation history yet</div>`;
      }
    }
  }

  function createSessionItemElem(session) {
    const item = document.createElement("div");
    item.className = "session-item" + (session.id === currentSessionId ? " active" : "");
    item.dataset.id = session.id;

    const contentDiv = document.createElement("div");
    contentDiv.className = "session-item-content";

    const iconSpan = document.createElement("span");
    iconSpan.className = "session-icon";
    iconSpan.textContent = session.is_pinned ? "📌" : "💬";

    const titleSpan = document.createElement("span");
    titleSpan.className = "session-title";
    titleSpan.textContent = session.title || "Conversation";
    titleSpan.title = session.title || "Conversation";

    contentDiv.appendChild(iconSpan);
    contentDiv.appendChild(titleSpan);

    const actionsDiv = document.createElement("div");
    actionsDiv.className = "session-item-actions";

    // Pin / Unpin button
    const pinBtn = document.createElement("button");
    pinBtn.className = "session-action-btn pin-btn" + (session.is_pinned ? " pinned" : "");
    pinBtn.title = session.is_pinned ? "Unpin conversation" : "Pin conversation to top";
    pinBtn.innerHTML = session.is_pinned ? "📌" : "📍";
    pinBtn.onclick = async (e) => {
      e.stopPropagation();
      await togglePinSession(session.id);
    };

    // Rename button
    const editBtn = document.createElement("button");
    editBtn.className = "session-action-btn edit-btn";
    editBtn.title = "Rename conversation";
    editBtn.innerHTML = "✏️";
    editBtn.onclick = async (e) => {
      e.stopPropagation();
      await renameSessionPrompt(session.id, session.title);
    };

    // Delete button
    const delBtn = document.createElement("button");
    delBtn.className = "session-action-btn delete-btn";
    delBtn.title = "Delete conversation";
    delBtn.innerHTML = "🗑️";
    delBtn.onclick = async (e) => {
      e.stopPropagation();
      await deleteSessionPrompt(session.id, session.title);
    };

    actionsDiv.appendChild(pinBtn);
    actionsDiv.appendChild(editBtn);
    actionsDiv.appendChild(delBtn);

    item.appendChild(contentDiv);
    item.appendChild(actionsDiv);

    item.onclick = async () => {
      if (session.id !== currentSessionId) {
        await switchSession(session.id);
      }
    };

    return item;
  }

  async function switchSession(sessionId) {
    if (isProcessing) return;
    try {
      statusText.textContent = "Loading conversation...";
      const res = await fetch(`/session/${encodeURIComponent(sessionId)}`);
      if (!res.ok) throw new Error("Failed to load conversation details");

      const data = await res.json();
      currentSessionId = data.session_id;
      sessionStorage.setItem("assistant_session_id", currentSessionId);
      localStorage.setItem("last_active_session_id", currentSessionId);

      // Restore voice/speed preferences if chat had them
      if (data.voice && voiceSelect) voiceSelect.value = data.voice;
      if (data.speed && speedRange) {
        speedRange.value = data.speed;
        if (speedDisplay) speedDisplay.textContent = `${parseFloat(data.speed).toFixed(1)}x`;
      }

      // Render conversation messages
      chatMessages.innerHTML = "";
      if (data.messages && data.messages.length > 0) {
        data.messages.forEach(msg => {
          appendMessage(msg.role, msg.content, null, msg.role === "assistant");
        });
      } else {
        renderWelcomeCard();
      }

      // Update sidebar active highlights
      document.querySelectorAll(".session-item").forEach(el => {
        el.classList.toggle("active", el.dataset.id === currentSessionId);
      });

      statusText.textContent = `Active: ${data.title}`;
      setTimeout(() => {
        if (statusText.textContent.startsWith("Active:")) {
          statusText.textContent = isHandsFreeActive ? "Auto-listening... (Speak anytime)" : "Ready";
        }
      }, 2000);
    } catch (err) {
      console.error("Error switching session:", err);
      statusText.textContent = "Error: " + err.message;
    }
  }

  function startNewChat() {
    if (isProcessing) return;
    currentSessionId = "sess_" + Math.random().toString(36).substring(2, 10) + "_" + Date.now();
    sessionStorage.setItem("assistant_session_id", currentSessionId);
    localStorage.setItem("last_active_session_id", currentSessionId);

    chatMessages.innerHTML = "";
    renderWelcomeCard();

    document.querySelectorAll(".session-item").forEach(el => {
      el.classList.remove("active");
    });

    statusText.textContent = "New conversation ready";
    chatInput.focus();
    setTimeout(() => {
      if (statusText.textContent === "New conversation ready") {
        statusText.textContent = isHandsFreeActive ? "Auto-listening... (Speak anytime)" : "Ready";
      }
    }, 2000);
  }

  function renderWelcomeCard() {
    chatMessages.innerHTML = `
      <div class="message assistant-message welcome-card">
        <div class="message-header">
          <span class="sender-name">Assistant</span>
          <span class="badge">Local Assistant</span>
        </div>
        <div class="message-content">
          <p>Hello! I am your <strong>Local Voice Assistant</strong>. You can speak to me by pressing the microphone button below or enable <strong>Auto-Listen</strong> for hands-free conversation with automatic pause detection.</p>
          <p class="hint">Everything runs locally: Speech recognition via Whisper, reasoning via Ollama, and speech synthesis via Kokoro TTS.</p>
        </div>
      </div>
    `;
  }

  async function togglePinSession(sessionId) {
    try {
      const res = await fetch(`/session/${encodeURIComponent(sessionId)}/pin`, { method: "POST" });
      if (!res.ok) throw new Error("Failed to pin session");
      await loadSessionsList();
    } catch (err) {
      console.warn("Could not toggle pin:", err);
    }
  }

  async function renameSessionPrompt(sessionId, currentTitle) {
    const newTitle = prompt("Enter a new title for this conversation:", currentTitle || "");
    if (!newTitle || !newTitle.trim()) return;

    try {
      const res = await fetch(`/session/${encodeURIComponent(sessionId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newTitle.trim() }),
      });
      if (!res.ok) throw new Error("Failed to rename session");
      await loadSessionsList();
    } catch (err) {
      alert("Could not rename session: " + err.message);
    }
  }

  async function deleteSessionPrompt(sessionId, title) {
    const confirmed = confirm(`Are you sure you want to delete "${title || 'this conversation'}"? This cannot be undone.`);
    if (!confirmed) return;

    try {
      const res = await fetch(`/session/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to delete session");

      if (sessionId === currentSessionId) {
        startNewChat();
      }
      await loadSessionsList();
    } catch (err) {
      alert("Could not delete session: " + err.message);
    }
  }

  const sensitivityThresholds = {
    1: 15.0, // Low sensitivity (requires louder voice)
    2: 9.0,
    3: 4.5,  // Medium (standard default)
    4: 2.2,
    5: 1.2   // Very high sensitivity (sensitive mic)
  };
  const sensitivityLabels = {
    1: "Low",
    2: "Medium-Low",
    3: "Medium",
    4: "High",
    5: "Very High"
  };
  let currentSpeechThreshold = sensitivityThresholds[3];
  let currentSilenceThreshold = currentSpeechThreshold * 0.55;

  // Initialize
  initSystem();
  setupEventListeners();

  async function initSystem() {
    drawIdleVisualizer();
    await checkHealth();
    await loadVoices();
    await loadSessionsList();

    const savedId = localStorage.getItem("last_active_session_id") || sessionStorage.getItem("assistant_session_id");
    if (savedId && sessionsData.some(s => s.id === savedId)) {
      await switchSession(savedId);
    } else if (sessionsData.length > 0) {
      await switchSession(sessionsData[0].id);
    }
  }

  function setupEventListeners() {
    // Chat form submit (Text mode)
    chatForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const text = chatInput.value.trim();
      if (!text) return;
      chatInput.value = "";
      await handleTextMessage(text);
    });

    // Manual Mic Click
    micBtn.addEventListener("click", () => {
      if (isHandsFreeActive) {
        disableHandsFree();
      } else {
        if (isRecording) {
          stopManualRecording();
        } else {
          startManualRecording();
        }
      }
    });

    // Hands-Free Toggle Button
    handsfreeBtn.addEventListener("click", () => {
      if (isHandsFreeActive) {
        disableHandsFree();
      } else {
        enableHandsFree();
      }
    });

    // Stop speaking button
    stopVoiceBtn.addEventListener("click", () => {
      stopAudio();
    });

    // Speed slider
    speedRange.addEventListener("input", (e) => {
      speedDisplay.textContent = `${parseFloat(e.target.value).toFixed(1)}x`;
    });

    // Silence duration slider
    silenceRange.addEventListener("input", (e) => {
      silenceDuration = parseFloat(e.target.value);
      silenceDisplay.textContent = `${silenceDuration.toFixed(1)}s`;
    });

    // Sensitivity slider
    sensitivityRange.addEventListener("input", (e) => {
      const level = parseInt(e.target.value, 10);
      currentSpeechThreshold = sensitivityThresholds[level] || 4.5;
      currentSilenceThreshold = currentSpeechThreshold * 0.55;
      sensitivityDisplay.textContent = sensitivityLabels[level] || "Medium";
    });

    // Settings drawer toggle
    toggleSettingsBtn.addEventListener("click", () => {
      settingsPanel.classList.toggle("closed");
    });

    closeSettingsBtn.addEventListener("click", () => {
      settingsPanel.classList.add("closed");
    });

    // Sidebar toggle button
    if (toggleSidebarBtn && sessionsSidebar) {
      const isSidebarClosed = localStorage.getItem("sidebar_closed") === "true";
      if (isSidebarClosed) {
        sessionsSidebar.classList.add("closed");
      }

      toggleSidebarBtn.addEventListener("click", () => {
        sessionsSidebar.classList.toggle("closed");
        localStorage.setItem("sidebar_closed", sessionsSidebar.classList.contains("closed"));
      });
    }

    // New Chat button
    if (newChatBtn) {
      newChatBtn.addEventListener("click", () => {
        startNewChat();
      });
    }

    // Keyboard shortcut Ctrl+B / Cmd+B for sidebar toggle
    document.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        if (sessionsSidebar) {
          sessionsSidebar.classList.toggle("closed");
          localStorage.setItem("sidebar_closed", sessionsSidebar.classList.contains("closed"));
        }
      }
    });

    // Reset session memory
    if (resetSessionBtn) {
      resetSessionBtn.addEventListener("click", async () => {
        if (isProcessing) return;
        const confirmed = confirm("Are you sure you want to clear messages in this active conversation?");
        if (!confirmed) return;

        const activeSid = getActiveSessionId();
        try {
          await fetch("/session/reset", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: activeSid }),
          });
        } catch (err) {
          console.warn("Could not reach session reset endpoint:", err);
        }

        chatMessages.innerHTML = "";
        renderWelcomeCard();
        await loadSessionsList();

        statusText.textContent = "Conversation messages cleared.";
        setTimeout(() => {
          if (statusText.textContent.startsWith("Conversation messages")) {
            statusText.textContent = isHandsFreeActive ? "Auto-listening... (Speak anytime)" : "Ready";
          }
        }, 2500);
      });
    }

    // TTS Playground synthesize
    ttsSynthesizeBtn.addEventListener("click", async () => {
      const text = ttsConfigInput.value.trim();
      if (!text) return;

      const voice = voiceSelect.value;
      const speed = parseFloat(speedRange.value);

      ttsSynthesizeBtn.disabled = true;
      ttsSynthesizeBtn.textContent = "Synthesizing...";

      try {
        const response = await fetch("/tts/synthesize-json", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, voice, speed })
        });

        if (!response.ok) {
          throw new Error(`TTS failed: ${response.statusText}`);
        }

        const data = await response.json();
        playgroundAudio.src = `data:audio/wav;base64,${data.audio_base64}`;
        ttsPlaygroundPlayer.style.display = "block";
        playgroundAudio.play();
      } catch (err) {
        alert("TTS Synthesis error: " + err.message);
      } finally {
        ttsSynthesizeBtn.disabled = false;
        ttsSynthesizeBtn.innerHTML = `
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
            <path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
            <path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path>
          </svg> Synthesize Speech`;
      }
    });

    // Keyboard shortcuts
    window.addEventListener("keydown", (e) => {
      if (e.code === "Space" && e.target === document.body && !isRecording && !isHandsFreeActive) {
        e.preventDefault();
        startManualRecording();
      } else if (e.code === "Escape") {
        if (currentAudio && !currentAudio.paused) {
          stopAudio();
        } else {
          settingsPanel.classList.add("closed");
        }
      }
    });

    window.addEventListener("keyup", (e) => {
      if (e.code === "Space" && e.target === document.body && isRecording && !isHandsFreeActive) {
        e.preventDefault();
        stopManualRecording();
      }
    });
  }

  // --- HEALTH & STATUS ---
  async function checkHealth() {
    try {
      const res = await fetch("/health");
      if (res.ok) {
        systemStatus.classList.add("online");
        systemStatus.querySelector(".status-label").textContent = "Online";
        statApi.textContent = "Healthy";
        statApi.className = "stat-status online";
        statWhisper.textContent = "Loaded";
        statWhisper.className = "stat-status online";
      } else {
        throw new Error("Health check non-200");
      }
    } catch {
      systemStatus.classList.remove("online");
      systemStatus.classList.add("offline");
      systemStatus.querySelector(".status-label").textContent = "Offline";
      statApi.textContent = "Unavailable";
      statApi.className = "stat-status offline";
    }
  }

  // --- KOKORO VOICES ---
  async function loadVoices() {
    try {
      const res = await fetch("/tts/voices");
      if (!res.ok) throw new Error("Could not fetch voices");
      const data = await res.json();

      voiceSelect.innerHTML = "";
      data.voices.forEach((v) => {
        const opt = document.createElement("option");
        opt.value = v;
        opt.textContent = v === data.default_voice ? `${v} ★ (Default)` : v;
        if (v === data.default_voice) opt.selected = true;
        voiceSelect.appendChild(opt);
      });

      statKokoro.textContent = `${data.total} Voices Ready`;
      statKokoro.className = "stat-status online";
    } catch (err) {
      console.warn("Could not load voices", err);
      statKokoro.textContent = "Offline";
      statKokoro.className = "stat-status offline";
    }
  }

  // --- AUDIO STREAM & MICROPHONE SETUP ---
  async function ensureMicrophone() {
    const isStreamActive =
      microphoneStream &&
      microphoneStream.active &&
      microphoneStream.getAudioTracks().some((t) => t.readyState === "live");

    if (!isStreamActive) {
      if (microphoneStream) {
        try {
          microphoneStream.getTracks().forEach((t) => t.stop());
        } catch (_) {}
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: false,
          autoGainControl: true,
        },
      });
      microphoneStream = stream;

      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!audioContext) {
        audioContext = new AudioCtx();
      }
      const source = audioContext.createMediaStreamSource(stream);
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.3;
      source.connect(analyser);
    }

    if (audioContext && audioContext.state === "suspended") {
      await audioContext.resume();
    }

    return microphoneStream;
  }

  function getAudioVolume() {
    if (!analyser) return 0;
    const dataArray = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(dataArray);

    let sumSquares = 0;
    for (let i = 0; i < dataArray.length; i++) {
      const normalized = (dataArray[i] - 128) / 128; // -1.0 to 1.0
      sumSquares += normalized * normalized;
    }
    const rms = Math.sqrt(sumSquares / dataArray.length);
    return rms * 100; // Scaled 0 to 100
  }

  // --- HANDS-FREE AUTO-LISTEN MODE (VAD + PAUSE DETECTION) ---

  async function enableHandsFree() {
    try {
      await ensureMicrophone();
      isHandsFreeActive = true;
      handsfreeBtn.classList.add("active");
      handsfreeBtn.querySelector(".handsfree-label").textContent = "Auto-Listen: On";
      statusText.textContent = "Auto-listening... (Speak anytime)";
      micBtn.classList.add("recording");

      startVADMonitoring();
    } catch (err) {
      console.error("Microphone access error for hands-free:", err);
      alert("Microphone permission required for Auto-Listen mode.");
    }
  }

  function disableHandsFree() {
    isHandsFreeActive = false;
    handsfreeBtn.classList.remove("active");
    handsfreeBtn.querySelector(".handsfree-label").textContent = "Auto-Listen: Off";
    micBtn.classList.remove("recording");

    if (silenceTimer) {
      clearTimeout(silenceTimer);
      silenceTimer = null;
    }

    if (isRecording) {
      if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
      }
      isRecording = false;
    }

    stopTimer();
    statusText.textContent = "Ready";
    drawIdleVisualizer();
  }

  function startVADMonitoring() {
    if (animationId) cancelAnimationFrame(animationId);

    function vadLoop() {
      if (!isHandsFreeActive) return;

      animationId = requestAnimationFrame(vadLoop);

      // If the assistant is speaking or audio is processing, pause VAD to prevent feedback
      if (isAssistantSpeaking || isProcessing) {
        drawIdleVisualizer();
        return;
      }

      const volume = getAudioVolume();
      drawVADVisualizer(volume);

      if (!isRecording) {
        // Not recording yet: check if speech has started
        if (volume > currentSpeechThreshold) {
          startSpeechUtterance();
        }
      } else {
        // Currently recording an utterance:
        if (volume > currentSilenceThreshold) {
          // Voice detected: cancel any pending silence countdown
          if (silenceTimer) {
            clearTimeout(silenceTimer);
            silenceTimer = null;
            statusText.textContent = "Listening... (Speaking)";
          }
        } else {
          // Audio volume dropped below silence threshold: start silence timer
          if (!silenceTimer) {
            statusText.textContent = `Pause detected... (${silenceDuration}s)`;
            silenceTimer = setTimeout(() => {
              silenceTimer = null;
              finishSpeechUtterance();
            }, silenceDuration * 1000);
          }
        }
      }
    }

    vadLoop();
  }

  function startSpeechUtterance() {
    if (isRecording || isProcessing || isAssistantSpeaking) return;

    audioChunks = [];
    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "audio/webm";

    try {
      mediaRecorder = new MediaRecorder(microphoneStream, { mimeType });
    } catch (e) {
      console.error("Failed to create MediaRecorder:", e);
      return;
    }

    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };

    mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(audioChunks, { type: mimeType });
      if (audioChunks.length > 0 && audioBlob.size > 200) {
        await processVoiceInput(audioBlob);
      } else {
        isProcessing = false;
        if (isHandsFreeActive) statusText.textContent = "Auto-listening... (Speak anytime)";
      }
    };

    mediaRecorder.start(100);
    isRecording = true;
    startTimer();
    statusText.textContent = "Listening... (Speaking)";
  }

  function finishSpeechUtterance() {
    if (!isRecording) return;
    isRecording = false;
    isProcessing = true; // Lock immediately to prevent re-triggering while finalizing
    stopTimer();
    statusText.textContent = "Transcribing speech...";

    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      try {
        mediaRecorder.requestData();
      } catch (_) {}
      mediaRecorder.stop();
    }
  }

  // --- MANUAL PUSH-TO-TALK MODE ---

  async function startManualRecording() {
    stopAudio();

    try {
      await ensureMicrophone();

      audioChunks = [];
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";

      mediaRecorder = new MediaRecorder(microphoneStream, { mimeType });

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: mimeType });
        if (audioChunks.length > 0 && audioBlob.size > 200) {
          await processVoiceInput(audioBlob);
        } else {
          isProcessing = false;
          statusText.textContent = "Ready";
        }
      };

      mediaRecorder.start(100);
      isRecording = true;

      micBtn.classList.add("recording");
      statusText.textContent = "Listening...";
      startTimer();
      drawActiveVisualizer();
    } catch (err) {
      console.error("Microphone access error:", err);
      alert("Microphone access denied or unavailable. Please grant permissions.");
    }
  }

  function stopManualRecording() {
    if (!isRecording) return;
    isRecording = false;
    isProcessing = true;

    micBtn.classList.remove("recording");
    statusText.textContent = "Transcribing speech...";
    stopTimer();

    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      try {
        mediaRecorder.requestData();
      } catch (_) {}
      mediaRecorder.stop();
    }

    if (animationId) cancelAnimationFrame(animationId);
    drawIdleVisualizer();
  }

  // --- TWO-STEP DIALOG FLOW: TRANSCRIPT FIRST -> THINKING CARD -> DUAL RESPONSE ---

  async function processVoiceInput(audioBlob) {
    isProcessing = true;
    statusText.textContent = "Transcribing speech with Whisper...";

    try {
      // Step 1: Transcribe audio with Whisper
      const transcribeRes = await fetch("/transcribe", {
        method: "POST",
        headers: { "Content-Type": audioBlob.type || "audio/webm" },
        body: audioBlob,
      });

      if (!transcribeRes.ok) {
        throw new Error(`Transcription failed: ${transcribeRes.statusText}`);
      }

      const transcribeData = await transcribeRes.json();
      const userText = (transcribeData.text || "").trim();

      if (!userText) {
        statusText.textContent = isHandsFreeActive ? "Auto-listening... (No speech detected)" : "Ready";
        isProcessing = false;
        return;
      }

      // Step 2: IMMEDIATELY render the user's message dialog box
      appendMessage("user", userText);

      // Step 3: Show thinking card underneath
      statusText.textContent = "Thinking...";
      const thinkingElem = appendThinkingIndicator();

      // Step 4: Call voice LLM + Kokoro TTS (/respond-text) FIRST to engage user immediately
      const activeSid = getActiveSessionId();
      const selectedVoice = voiceSelect.value || "af_heart";
      const selectedSpeed = parseFloat(speedRange.value) || 1.0;

      console.log("[Local Assistant] Fast voice first → /respond-text | session_id:", activeSid);

      // /respond-text: voice LLM (concise, TTS audio) — does NOT write to session (chat API owns that)
      const respondRes = await fetch("/respond-text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: userText,
          voice: selectedVoice,
          speed: selectedSpeed,
          session_id: activeSid,
          save_to_session: false,
        }),
      });

      if (!respondRes.ok) {
        const e = await respondRes.json().catch(() => ({}));
        throw new Error(e.detail || `Voice response error: ${respondRes.status}`);
      }

      const voiceData = await respondRes.json();

      // Step 5: Immediately remove thinking indicator and render the spoken text + audio controls
      removeThinkingIndicator(thinkingElem);
      const streamElements = appendDualStreamMessage(voiceData.response, voiceData.audio_base64);

      // Step 6: Start voice playback right away to engage the user without waiting for /chat
      if (voiceData.audio_base64 && autoplayCheckbox.checked) {
        playAudioFromBase64(voiceData.audio_base64, streamElements.playBtn);
      } else if (!voiceData.audio_base64) {
        statusText.textContent = "Generating detailed response...";
      }

      // Step 7: Concurrently fetch the full detailed markdown response from /chat
      // and append it directly underneath on a new line once completed
      fetchDetailedChatResponse(userText, activeSid, streamElements);
    } catch (err) {
      console.error("Voice pipeline error:", err);
      const activeThinking = document.getElementById("active-thinking-indicator");
      if (activeThinking) removeThinkingIndicator(activeThinking);

      statusText.textContent = "Error: " + err.message;
      appendMessage("assistant", `⚠️ An error occurred: ${err.message}`);
      isProcessing = false;
      isDetailedPending = false;
    }
  }

  async function handleTextMessage(prompt) {
    // 1. Immediately show user's message
    appendMessage("user", prompt);

    // 2. Show assistant thinking card underneath
    statusText.textContent = "Thinking with Ollama...";
    const thinkingElem = appendThinkingIndicator();

    try {
      const activeSid = getActiveSessionId();
      console.log("[Local Assistant] Sending /chat with session_id:", activeSid);
      const response = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, session_id: activeSid })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server error: ${response.status}`);
      }

      const data = await response.json();
      removeThinkingIndicator(thinkingElem);
      appendMessage("assistant", data.response, null, true);
      loadSessionsList().catch(() => {});
      statusText.textContent = "Ready";
    } catch (err) {
      console.error("Chat error:", err);
      removeThinkingIndicator(thinkingElem);
      statusText.textContent = "Error: " + err.message;
      appendMessage("assistant", `⚠️ An error occurred: ${err.message}`);
    }
  }

  // --- TIMER HELPERS ---
  function startTimer() {
    recordingTimer.classList.add("active");
    recordSeconds = 0;
    updateTimerDisplay();
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = setInterval(() => {
      recordSeconds++;
      updateTimerDisplay();
    }, 1000);
  }

  function stopTimer() {
    recordingTimer.classList.remove("active");
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }

  function updateTimerDisplay() {
    const mins = String(Math.floor(recordSeconds / 60)).padStart(2, "0");
    const secs = String(recordSeconds % 60).padStart(2, "0");
    recordingTimer.textContent = `${mins}:${secs}`;
  }

  // --- VISUALIZER DRAWING ---

  function drawIdleVisualizer() {
    const width = visualizerCanvas.width;
    const height = visualizerCanvas.height;
    canvasCtx.clearRect(0, 0, width, height);

    canvasCtx.lineWidth = 2;
    canvasCtx.strokeStyle = isHandsFreeActive ? "rgba(16, 185, 129, 0.4)" : "rgba(99, 102, 241, 0.3)";
    canvasCtx.beginPath();
    canvasCtx.moveTo(0, height / 2);
    canvasCtx.lineTo(width, height / 2);
    canvasCtx.stroke();
  }

  function drawVADVisualizer(currentVol) {
    const width = visualizerCanvas.width;
    const height = visualizerCanvas.height;
    canvasCtx.clearRect(0, 0, width, height);

    if (!analyser) return;

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    analyser.getByteFrequencyData(dataArray);

    const barWidth = (width / bufferLength) * 2;
    let x = 0;

    for (let i = 0; i < bufferLength; i++) {
      const barHeight = (dataArray[i] / 255) * height * 0.9;

      const gradient = canvasCtx.createLinearGradient(0, height, 0, 0);
      if (isRecording) {
        gradient.addColorStop(0, "#10b981");
        gradient.addColorStop(1, "#f59e0b");
      } else {
        gradient.addColorStop(0, "#6366f1");
        gradient.addColorStop(1, "#10b981");
      }

      canvasCtx.fillStyle = gradient;
      canvasCtx.fillRect(x, height - barHeight, barWidth - 1, barHeight);
      x += barWidth;
    }
  }

  function drawActiveVisualizer() {
    if (!isRecording || !analyser) return;

    animationId = requestAnimationFrame(drawActiveVisualizer);

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    analyser.getByteFrequencyData(dataArray);

    const width = visualizerCanvas.width;
    const height = visualizerCanvas.height;

    canvasCtx.clearRect(0, 0, width, height);

    const barWidth = (width / bufferLength) * 2;
    let x = 0;

    for (let i = 0; i < bufferLength; i++) {
      const barHeight = (dataArray[i] / 255) * height * 0.9;

      const gradient = canvasCtx.createLinearGradient(0, height, 0, 0);
      gradient.addColorStop(0, "#6366f1");
      gradient.addColorStop(1, "#ef4444");

      canvasCtx.fillStyle = gradient;
      canvasCtx.fillRect(x, height - barHeight, barWidth - 1, barHeight);
      x += barWidth;
    }
  }

  // --- AUDIO PLAYBACK & STOP CONTROLS ---

  function stopAudio() {
    if (currentAudio) {
      currentAudio.pause();
      currentAudio.currentTime = 0;
      currentAudio = null;
    }
    if (activePlayButton) {
      resetButtonToPlay(activePlayButton);
      activePlayButton = null;
    }
    stopVoiceBtn.style.display = "none";
    isAssistantSpeaking = false;

    if (!isDetailedPending) {
      isProcessing = false;
      if (isHandsFreeActive) {
        statusText.textContent = "Auto-listening... (Speak anytime)";
      } else {
        statusText.textContent = "Ready";
      }
    } else {
      statusText.textContent = "Generating detailed response...";
    }
  }

  function resetButtonToPlay(btn) {
    btn.classList.remove("playing");
    btn.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polygon points="5 3 19 12 5 21 5 3"></polygon>
      </svg> Play Voice
    `;
  }

  function setButtonToStop(btn) {
    btn.classList.add("playing");
    btn.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
        <rect x="4" y="4" width="16" height="16" rx="2"></rect>
      </svg> Stop Voice
    `;
  }

  function playAudioFromBase64(b64Data, buttonElement = null) {
    // If clicking the button that is already playing, stop it!
    if (buttonElement && buttonElement === activePlayButton && currentAudio && !currentAudio.paused) {
      stopAudio();
      return;
    }

    stopAudio();

    const audio = new Audio(`data:audio/wav;base64,${b64Data}`);
    currentAudio = audio;
    isAssistantSpeaking = true;

    stopVoiceBtn.style.display = "inline-flex";
    statusText.textContent = "Speaking...";

    if (buttonElement) {
      activePlayButton = buttonElement;
      setButtonToStop(buttonElement);
    }

    audio.onended = () => {
      stopAudio();
    };

    audio.onpause = () => {
      if (currentAudio === audio) {
        stopAudio();
      }
    };

    audio.play().catch((err) => {
      console.warn("Audio autoplay blocked by browser policy:", err);
      stopAudio();
    });
  }

  // --- UI RENDER MESSAGES & THINKING INDICATOR ---

  function appendThinkingIndicator() {
    const thinkDiv = document.createElement("div");
    thinkDiv.className = "message assistant-message thinking-message";
    thinkDiv.id = "active-thinking-indicator";
    thinkDiv.innerHTML = `
      <div class="message-header">
        <span class="sender-name">Assistant</span>
        <span class="badge">Thinking</span>
      </div>
      <div class="message-content">
        <div class="thinking-dots">
          <span></span><span></span><span></span>
        </div>
      </div>
    `;
    chatMessages.appendChild(thinkDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return thinkDiv;
  }

  function removeThinkingIndicator(elem) {
    if (elem && elem.parentNode) {
      elem.parentNode.removeChild(elem);
    }
  }

  function renderMarkdown(rawText) {
    if (typeof marked !== "undefined" && marked.parse) {
      try {
        return marked.parse(rawText, {
          breaks: true,
          gfm: true
        });
      } catch (err) {
        console.warn("Markdown parsing failed, falling back to escaped text:", err);
      }
    }
    return `<p>${escapeHtml(rawText)}</p>`;
  }

  function appendMessage(sender, text, audioBase64 = null, showSpeakButton = false) {
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${sender}-message`;

    const header = document.createElement("div");
    header.className = "message-header";

    const nameSpan = document.createElement("span");
    nameSpan.className = "sender-name";
    nameSpan.textContent = sender === "user" ? "You" : "Assistant";
    header.appendChild(nameSpan);

    if (sender === "assistant") {
      const badge = document.createElement("span");
      badge.className = "badge";
      badge.textContent = "Local Assistant";
      header.appendChild(badge);
    }

    msgDiv.appendChild(header);

    const contentDiv = document.createElement("div");
    contentDiv.className = "message-content markdown-body";
    contentDiv.innerHTML = sender === "assistant" ? renderMarkdown(text) : `<p>${escapeHtml(text)}</p>`;

    // Open any links in a new tab safely
    contentDiv.querySelectorAll("a").forEach(a => {
      a.setAttribute("target", "_blank");
      a.setAttribute("rel", "noopener noreferrer");
    });

    // Add copy button to code blocks
    contentDiv.querySelectorAll("pre").forEach(pre => {
      const copyBtn = document.createElement("button");
      copyBtn.className = "copy-code-btn";
      copyBtn.textContent = "Copy";
      copyBtn.type = "button";
      copyBtn.title = "Copy code to clipboard";
      copyBtn.onclick = async () => {
        const code = pre.querySelector("code")?.innerText || pre.innerText;
        try {
          await navigator.clipboard.writeText(code);
          copyBtn.textContent = "Copied!";
          setTimeout(() => { copyBtn.textContent = "Copy"; }, 2000);
        } catch (e) {
          console.warn("Clipboard copy failed:", e);
        }
      };
      pre.appendChild(copyBtn);
    });

    msgDiv.appendChild(contentDiv);

    // Audio controls for assistant message
    if (sender === "assistant") {
      const audioControls = document.createElement("div");
      audioControls.className = "message-audio-controls";

      if (audioBase64) {
        const playBtn = document.createElement("button");
        playBtn.className = "play-audio-btn";
        playBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="5 3 19 12 5 21 5 3"></polygon>
          </svg> Play Voice
        `;
        playBtn.onclick = () => playAudioFromBase64(audioBase64, playBtn);
        audioControls.appendChild(playBtn);
      } else if (showSpeakButton) {
        const speakBtn = document.createElement("button");
        speakBtn.className = "play-audio-btn";
        speakBtn.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
            <path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
            <path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path>
          </svg> Speak Response
        `;
        speakBtn.onclick = async () => {
          if (speakBtn === activePlayButton && currentAudio && !currentAudio.paused) {
            stopAudio();
            return;
          }

          speakBtn.disabled = true;
          speakBtn.textContent = "Synthesizing...";
          try {
            const voice = voiceSelect.value || "af_heart";
            const speed = parseFloat(speedRange.value) || 1.0;
            const res = await fetch("/tts/synthesize-json", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ text, voice, speed })
            });
            const ttsData = await res.json();
            playAudioFromBase64(ttsData.audio_base64, speakBtn);
          } catch (err) {
            alert("TTS error: " + err.message);
            resetButtonToPlay(speakBtn);
          } finally {
            speakBtn.disabled = false;
          }
        };
        audioControls.appendChild(speakBtn);
      }

      if (audioControls.children.length > 0) {
        msgDiv.appendChild(audioControls);
      }
    }

    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  function appendDualStreamMessage(voiceText, audioBase64 = null) {
    const msgDiv = document.createElement("div");
    msgDiv.className = "message assistant-message";

    const header = document.createElement("div");
    header.className = "message-header";

    const nameSpan = document.createElement("span");
    nameSpan.className = "sender-name";
    nameSpan.textContent = "Assistant";
    header.appendChild(nameSpan);

    const badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = "Local Assistant";
    header.appendChild(badge);

    msgDiv.appendChild(header);

    const contentDiv = document.createElement("div");
    contentDiv.className = "message-content";

    // 1. Spoken concise response block
    const voiceBlock = document.createElement("div");
    voiceBlock.className = "voice-response-block";
    voiceBlock.innerHTML = `<p>${escapeHtml(voiceText)}</p>`;
    contentDiv.appendChild(voiceBlock);

    // 2. Parallel loading status indicator for detailed chat response
    const detailStatus = document.createElement("div");
    detailStatus.className = "detailed-response-status";
    detailStatus.innerHTML = `
      <div class="thinking-dots">
        <span></span><span></span><span></span>
      </div>
      <span>Generating detailed response...</span>
    `;
    contentDiv.appendChild(detailStatus);

    // 3. Placeholder block for detailed markdown notes (appended on new line)
    const detailBlock = document.createElement("div");
    detailBlock.className = "detailed-response-block markdown-body";
    detailBlock.style.display = "none";
    contentDiv.appendChild(detailBlock);

    msgDiv.appendChild(contentDiv);

    // 4. Audio controls
    let playBtn = null;
    if (audioBase64) {
      const audioControls = document.createElement("div");
      audioControls.className = "message-audio-controls";

      playBtn = document.createElement("button");
      playBtn.className = "play-audio-btn";
      playBtn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="5 3 19 12 5 21 5 3"></polygon>
        </svg> Play Voice
      `;
      playBtn.onclick = () => playAudioFromBase64(audioBase64, playBtn);
      audioControls.appendChild(playBtn);
      msgDiv.appendChild(audioControls);
    }

    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return { msgDiv, contentDiv, detailStatus, detailBlock, playBtn };
  }

  async function fetchDetailedChatResponse(promptText, sessionId, streamElements) {
    const { detailStatus, detailBlock } = streamElements;
    isDetailedPending = true;

    try {
      console.log("[Local Assistant] Fetching detailed response from /chat | session_id:", sessionId);
      const chatRes = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: promptText,
          session_id: sessionId,
        }),
      });

      if (!chatRes.ok) {
        const e = await chatRes.json().catch(() => ({}));
        throw new Error(e.detail || `Chat response error: ${chatRes.status}`);
      }

      const chatData = await chatRes.json();

      // Remove loading status indicator
      if (detailStatus && detailStatus.parentNode) {
        detailStatus.parentNode.removeChild(detailStatus);
      }

      // Render markdown response into detailBlock on a new line
      detailBlock.innerHTML = `
        <hr class="detailed-response-divider" />
        ${renderMarkdown(chatData.response)}
      `;
      detailBlock.style.display = "block";

      // Configure external links
      detailBlock.querySelectorAll("a").forEach((a) => {
        a.setAttribute("target", "_blank");
        a.setAttribute("rel", "noopener noreferrer");
      });

      // Configure copy buttons on code blocks
      detailBlock.querySelectorAll("pre").forEach((pre) => {
        const copyBtn = document.createElement("button");
        copyBtn.className = "copy-code-btn";
        copyBtn.textContent = "Copy";
        copyBtn.type = "button";
        copyBtn.title = "Copy code to clipboard";
        copyBtn.onclick = async () => {
          const code = pre.querySelector("code")?.innerText || pre.innerText;
          try {
            await navigator.clipboard.writeText(code);
            copyBtn.textContent = "Copied!";
            setTimeout(() => { copyBtn.textContent = "Copy"; }, 2000);
          } catch (e) {
            console.warn("Clipboard copy failed:", e);
          }
        };
        pre.appendChild(copyBtn);
      });

      chatMessages.scrollTop = chatMessages.scrollHeight;
      loadSessionsList().catch(() => {});
    } catch (err) {
      console.error("Detailed chat fetch error:", err);
      if (detailStatus) {
        detailStatus.innerHTML = `<span style="color: #f87171;">⚠️ Could not generate detailed notes (${escapeHtml(err.message)})</span>`;
      }
    } finally {
      isDetailedPending = false;
      if (!isAssistantSpeaking) {
        isProcessing = false;
        if (isHandsFreeActive) {
          statusText.textContent = "Auto-listening... (Speak anytime)";
        } else {
          statusText.textContent = "Ready";
        }
      }
    }
  }

  function escapeHtml(string) {
    const div = document.createElement("div");
    div.innerText = string;
    return div.innerHTML;
  }
});
