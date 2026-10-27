import React, { useState, useEffect, useRef } from "react";

// URL of the Central Face Recognition / EduTrack Backend (Port 8000)
const API_BASE = "http://localhost:8000";

// ── Word-to-Digit Normalizer Dictionary (Tamil + Tanglish + English) ─────
const NUMBER_WORDS = {
  // English digits & words
  zero: "0", one: "1", two: "2", three: "3", four: "4",
  five: "5", six: "6", seven: "7", eight: "8", nine: "9",
  oh: "0", double: "double", triple: "triple",

  // Tamil Unicode Script
  பூஜ்ஜியம்: "0", ஜீரோ: "0", சுழியம்: "0",
  ஒன்று: "1", ஒன்னு: "1", ஒரு: "1",
  இரண்டு: "2", ரெண்டு: "2", ரண்டு: "2",
  மூன்று: "3", மூணு: "3",
  நான்கு: "4", நாலு: "4",
  ஐந்து: "5", அஞ்சு: "5",
  ஆறு: "6",
  ஏழு: "7",
  எட்டு: "8",
  ஒன்பது: "9",
  பத்து: "10",

  // Tanglish (Tamil words in English letters / Transliteration)
  poojiyam: "0", poojyam: "0", pujiyam: "0", jeero: "0", jiro: "0", sunna: "0", suzhiyam: "0",
  onnu: "1", onru: "1", ondru: "1", oru: "1", oone: "1",
  rendu: "2", irandu: "2", irandhu: "2", randu: "2", reandu: "2",
  moonu: "3", moondru: "3", moondhu: "3", munu: "3", monu: "3",
  naalu: "4", naangu: "4", nalu: "4", nangu: "4", nal: "4",
  anju: "5", ainthu: "5", aindhu: "5", anchu: "5", anji: "5",
  aaru: "6", aru: "6", aara: "6",
  ezhu: "7", yezhu: "7", elu: "7", yelu: "7", yealu: "7", yelhu: "7", ezh: "7",
  ettu: "8", yeatu: "8", yettu: "8", etu: "8", eattu: "8",
  onbadhu: "9", onbathu: "9", ombodhu: "9", ombothu: "9", onpathu: "9", onbadu: "9",
  pathu: "10", padhu: "10",
};

// ── Synthesized Audio Tone Generator (Web Audio API) ────────────────────
const playChime = (type = "success") => {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();

    if (type === "success") {
      // 2-tone bright positive chime (523Hz C5 -> 659Hz E5)
      const osc1 = ctx.createOscillator();
      const gain1 = ctx.createGain();
      osc1.type = "sine";
      osc1.frequency.setValueAtTime(523.25, ctx.currentTime);
      osc1.frequency.exponentialRampToValueAtTime(659.25, ctx.currentTime + 0.15);
      gain1.gain.setValueAtTime(0.18, ctx.currentTime);
      gain1.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
      osc1.connect(gain1);
      gain1.connect(ctx.destination);
      osc1.start();
      osc1.stop(ctx.currentTime + 0.35);
    } else if (type === "ping") {
      // High quick activation ping
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      gain.gain.setValueAtTime(0.15, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.2);
    } else if (type === "warning") {
      // Low dual warning buzzer
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(320, ctx.currentTime);
      osc.frequency.linearRampToValueAtTime(220, ctx.currentTime + 0.25);
      gain.gain.setValueAtTime(0.15, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.25);
    }
  } catch (e) {
    console.debug("Audio chime skipped:", e);
  }
};

export default function StudentGatePassVerify() {
  const [activeTab, setActiveTab] = useState("verify"); // 'verify' | 'incidents' | 'history'
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [recentExits, setRecentExits] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [exitLoading, setExitLoading] = useState(false);

  // ── Voice Recognition Engine States ───────────────────────────────────
  const [speechLang, setSpeechLang] = useState("en-IN"); // 'en-IN' (Tanglish + English) | 'ta-IN' (Pure Tamil)
  const [isListening, setIsListening] = useState(false);
  const [continuousMode, setContinuousMode] = useState(true);
  const [transcript, setTranscript] = useState("");
  const [voiceStatus, setVoiceStatus] = useState("Standby. Click 'Start Voice Guard' to begin.");
  const [lastIntent, setLastIntent] = useState(null);
  const recognitionRef = useRef(null);

  // On Mount: Load data, init voice engine, bind spacebar shortcut
  useEffect(() => {
    fetchRecentExits();
    fetchIncidents();
    initSpeechEngine(speechLang);

    const handleKeyDown = (e) => {
      // Press Spacebar (when not typing in an input) to toggle voice
      if (e.code === "Space" && e.target.tagName !== "INPUT" && e.target.tagName !== "TEXTAREA") {
        e.preventDefault();
        toggleVoiceGuard();
      }
    };
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      if (recognitionRef.current) {
        try { recognitionRef.current.abort(); } catch (_) {}
      }
    };
  }, []);

  // ── Text-To-Speech Feedback (System Speaks Back to Watchman) ───────────
  const speakFeedback = (text) => {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.05;
      utterance.pitch = 1.0;
      utterance.lang = speechLang;
      window.speechSynthesis.speak(utterance);
    }
  };

  // ── Initialize Speech Recognition Engine ──────────────────────────────
  const initSpeechEngine = (langToUse = speechLang) => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setVoiceStatus("Voice input is not supported in this browser. Please use Chrome or Edge.");
      return;
    }

    if (recognitionRef.current) {
      try { recognitionRef.current.abort(); } catch (_) {}
    }

    const reco = new SpeechRecognition();
    reco.continuous = false; // We manage continuous restart manually for better accuracy
    reco.interimResults = true;
    reco.lang = langToUse; // Prioritize Indian English + Tanglish or Tamil Script

    reco.onstart = () => {
      setIsListening(true);
      setVoiceStatus(`🎙️ Listening (${langToUse === "en-IN" ? "Tanglish / English" : "Tamil"})... Speak OTP or Situation`);
      playChime("ping");
    };

    reco.onresult = (event) => {
      let liveText = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        liveText += event.results[i][0].transcript;
      }
      setTranscript(liveText);

      if (event.results[0].isFinal) {
        processSpokenUtterance(liveText);
      }
    };

    reco.onerror = (event) => {
      console.warn("Speech error:", event.error);
      setIsListening(false);
      setVoiceStatus(`Voice note: ${event.error === "no-speech" ? "No speech detected" : event.error}`);
    };

    reco.onend = () => {
      setIsListening(false);
      // Auto-restart if continuous mode is enabled
      if (continuousMode) {
        setTimeout(() => {
          try {
            if (recognitionRef.current && continuousMode) {
              recognitionRef.current.start();
            }
          } catch (_) {}
        }, 600);
      } else {
        setVoiceStatus("Mic Standby. Click 'Start Voice Guard' to speak.");
      }
    };

    recognitionRef.current = reco;
  };

  // ── Voice Start Procedure ─────────────────────────────────────────────
  const toggleVoiceGuard = () => {
    if (!recognitionRef.current) {
      alert("Speech recognition not supported in this browser. Use Google Chrome or Microsoft Edge.");
      return;
    }

    if (isListening) {
      setContinuousMode(false);
      try { recognitionRef.current.stop(); } catch (_) {}
      setIsListening(false);
      setVoiceStatus("Voice Guard stopped. Click Start to reactivate.");
    } else {
      setContinuousMode(true);
      setTranscript("");
      setErrorMsg("");
      setVoiceStatus("Starting Voice Guard...");
      speakFeedback("Voice Guard active. Speak OTP or gate situation.");
      try {
        recognitionRef.current.start();
      } catch (err) {
        console.warn("Speech start issue:", err);
      }
    }
  };

  // ── Voice Command & Natural Language Processor ────────────────────────
  const processSpokenUtterance = async (rawText) => {
    const lower = rawText.toLowerCase().trim();
    if (!lower) return;

    setVoiceStatus(`Processing speech: "${rawText}"...`);

    // Step 1: Check for Exit / Confirm Voice Command (if student pass is already on screen)
    if (result && result.valid) {
      const confirmKeywords = [
        // English
        "confirm", "allow", "exit", "left", "passed", "yes", "okay", "ok",
        // Tamil Unicode
        "வெளிய", "போகலாம்", "அனுப்பு", "விடு", "சரி", "திற",
        // Tanglish
        "veliya", "velila", "veliye", "pogalam", "pogattum", "poraaru", "poran", "poranga",
        "anuppu", "anupu", "anupunga", "anuppunga", "vidu", "vidunga",
        "allow pannu", "exit pannu", "confirm pannu", "panni vidu",
        "gate open", "gate thora", "gate theranthudu", "gate thorandhu",
        "sari", "seri", "kelambattum", "kelambalam"
      ];
      if (confirmKeywords.some((w) => lower.includes(w))) {
        setLastIntent({ name: "CONFIRM_EXIT", confidence: 0.98, raw: rawText });
        playChime("success");
        speakFeedback(`Exit confirmed for ${result.student_name}.`);
        handleConfirmExit();
        return;
      }
    }

    // Step 2: Extract & Normalize Spoken Numbers (Tamil + English + Tanglish)
    const words = lower.split(/\s+/);
    let normalized = [];
    let i = 0;
    while (i < words.length) {
      let w = words[i];
      // Handle 'double X', 'irattai X', 'triple X'
      if ((w === "double" || w === "irattai") && i + 1 < words.length && NUMBER_WORDS[words[i + 1]]) {
        let digit = NUMBER_WORDS[words[i + 1]];
        normalized.push(digit, digit);
        i += 2;
        continue;
      }
      if ((w === "triple" || w === "mummurai") && i + 1 < words.length && NUMBER_WORDS[words[i + 1]]) {
        let digit = NUMBER_WORDS[words[i + 1]];
        normalized.push(digit, digit, digit);
        i += 2;
        continue;
      }
      if (NUMBER_WORDS[w]) {
        normalized.push(NUMBER_WORDS[w]);
      } else if (/^\d+$/.test(w)) {
        normalized.push(w);
      } else {
        let clean = w.replace(/[^a-z0-9]/gi, "");
        if (clean) {
          if (NUMBER_WORDS[clean]) normalized.push(NUMBER_WORDS[clean]);
          else normalized.push(clean);
        }
      }
      i++;
    }

    const combined = normalized.join(" ");

    // Check for 6-digit OTP
    let directMatch = combined.match(/\b\d{6}\b/);
    let extractedOtp = null;
    if (directMatch) {
      extractedOtp = directMatch[0];
    } else {
      let digitsOnly = combined.replace(/\D/g, "");
      if (digitsOnly.length >= 6) {
        extractedOtp = digitsOnly.substring(0, 6);
      }
    }

    // Step 3: If OTP Found -> Verify
    if (extractedOtp) {
      setLastIntent({ name: "VERIFY_OTP", confidence: 0.96, otp: extractedOtp });
      setOtp(extractedOtp);
      setVoiceStatus(`Extracted OTP: ${extractedOtp} · Verifying with server...`);
      verifyOtpCode(extractedOtp);
      return;
    }

    // Step 4: Check if Watchman Spoke a Gate Situation / Incident (Tamil + English + Tanglish)
    const incidentKeywords = [
      // English
      "incident", "problem", "emergency", "medical", "hospital", "ambulance",
      "unauthorized", "accident", "damage", "complaint", "stopped", "fight", "theft",
      // Tamil Unicode
      "பிரச்சனை", "மருத்துவமனை", "ஆம்புலன்ஸ்", "சண்டை", "விபத்து",
      // Tanglish
      "udambu sariyilla", "udambu mudiyala", "faint", "mayakkam", "mayangi", "vizhunthutan", "adi patturuku",
      "sanda", "sandai", "thagaraaru", "thagararu", "vambu", "argue", "vaakuvaadham",
      "illama", "no id", "id card", "id illa", "card illa", "permission illama",
      "gate jump", "wall yeri", "kudhichu", "thappikka", "cross panna", "cross",
      "thaduthu", "thaduthom", "hold pannirukom", "pudichom",
      "parent kooda", "parent vandhurukaanga", "family vandhurukaanga"
    ];

    if (incidentKeywords.some((w) => lower.includes(w))) {
      setLastIntent({ name: "LOG_INCIDENT", confidence: 0.92, raw: rawText });
      await logSpokenIncidentToBackend(rawText);
      return;
    }

    // Fallback: Send to Backend Voice Gateway for Deep NLU Resolution
    try {
      const res = await fetch(`${API_BASE}/api/v1/gatepass/voice-command`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transcript: rawText,
          guard_id: "Main Gate Security",
          active_pass_id: result && result.valid ? result.pass_id : null,
        }),
      });
      const data = await res.json();

      if (data && data.spoken_feedback) {
        setVoiceStatus(`AI: ${data.spoken_feedback}`);
        speakFeedback(data.spoken_feedback);
        if (data.intent === "VERIFY_OTP" && data.data) {
          setResult(data.data);
          if (data.data.valid) playChime("success");
          else playChime("warning");
        } else if (data.intent === "LOG_INCIDENT") {
          fetchIncidents();
        }
      }
    } catch (err) {
      setVoiceStatus(`Could not resolve command: "${rawText}". Say OTP or incident.`);
    }
  };

  // ── Log Spoken Incident to Backend ────────────────────────────────────
  const logSpokenIncidentToBackend = async (rawText) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/gatepass/voice-command`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transcript: rawText,
          guard_id: "Main Gate Security",
        }),
      });
      const data = await res.json();
      if (res.ok && data.success) {
        playChime("success");
        setVoiceStatus(`🚨 Incident Logged: ${data.spoken_feedback}`);
        speakFeedback(data.spoken_feedback);
        fetchIncidents();
      } else {
        setVoiceStatus("Could not log incident on server.");
      }
    } catch (e) {
      console.warn("Incident log failed:", e);
    }
  };

  // ── Fetch Recent Exits & Incidents ────────────────────────────────────
  const fetchRecentExits = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/gatepass/recent-exits`);
      const data = await res.json();
      if (data && data.exits) setRecentExits(data.exits);
    } catch (err) {
      console.warn("Could not load recent exits:", err);
    }
  };

  const fetchIncidents = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/gatepass/incidents`);
      const data = await res.json();
      if (data && data.incidents) setIncidents(data.incidents);
    } catch (err) {
      console.warn("Could not load incidents:", err);
    }
  };

  // ── Verify OTP Code ───────────────────────────────────────────────────
  const verifyOtpCode = async (codeToVerify) => {
    const cleanOtp = String(codeToVerify || otp).trim();
    if (!cleanOtp) {
      setErrorMsg("Please enter or speak the 6-digit OTP.");
      return;
    }

    setLoading(true);
    setErrorMsg("");
    setResult(null);

    try {
      const res = await fetch(`${API_BASE}/api/v1/gatepass/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ otp: cleanOtp }),
      });
      const data = await res.json();

      if (!res.ok) {
        playChime("warning");
        setErrorMsg(data.detail || "Verification failed on server.");
        speakFeedback("Verification failed on server.");
      } else {
        setResult(data);
        if (data.valid) {
          playChime("success");
          speakFeedback(`Gate pass approved for ${data.student_name}. Say 'Confirm' or click allow.`);
        } else {
          playChime("warning");
          setErrorMsg(data.message || "Invalid or Unapproved Gate Pass.");
          speakFeedback(`Gate pass denied: ${data.message || "Not approved"}`);
        }
      }
    } catch (err) {
      playChime("warning");
      setErrorMsg("Could not connect to EduTrack Central API (http://localhost:8000).");
      speakFeedback("Connection to server failed.");
    } finally {
      setLoading(false);
    }
  };

  // ── Confirm Student Exit ──────────────────────────────────────────────
  const handleConfirmExit = async () => {
    if (!result || !result.pass_id) return;
    setExitLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/v1/gatepass/mark-exit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          pass_id: result.pass_id,
          guard_id: "Main Gate Guard",
          remarks: "Verified via Voice Guard Assistant",
        }),
      });
      const data = await res.json();

      if (res.ok && data.success) {
        playChime("success");
        setResult((prev) => ({
          ...prev,
          is_used: 1,
          exited_at: data.record ? data.record.exited_at : new Date().toISOString(),
        }));
        speakFeedback(`Exit confirmed. Have a safe journey.`);
        fetchRecentExits();
      } else {
        alert(data.message || "Could not mark exit on server.");
      }
    } catch (err) {
      alert("Network error: Could not confirm exit.");
    } finally {
      setExitLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      {/* ── Top Header ─────────────────────────────────────────────── */}
      <div style={styles.header}>
        <div>
          <div style={styles.badgeRow}>
            <span style={styles.kioskBadge}>MAIN SECURITY GATE</span>
            <span style={styles.onlineBadge}>● SYSTEM ONLINE</span>
          </div>
          <h1 style={styles.title}>Voice-Assisted Student Gate Pass Control</h1>
          <p style={styles.subtitle}>
            Hands-Free Verification · Tamil & Tanglish AI Normalizer · Instant Incident Auto-Logging
          </p>
        </div>

        {/* Tab Switcher */}
        <div style={styles.tabBar}>
          <button
            onClick={() => setActiveTab("verify")}
            style={activeTab === "verify" ? styles.tabBtnActive : styles.tabBtn}
          >
            🚪 Gate Pass Verify
          </button>
          <button
            onClick={() => setActiveTab("incidents")}
            style={activeTab === "incidents" ? styles.tabBtnActive : styles.tabBtn}
          >
            🚨 Voice Incidents ({incidents.length})
          </button>
          <button
            onClick={() => setActiveTab("history")}
            style={activeTab === "history" ? styles.tabBtnActive : styles.tabBtn}
          >
            📋 Exit History ({recentExits.length})
          </button>
        </div>
      </div>

      {/* ── Voice Assistant Hero Bar (Voice Start Procedure) ─────────── */}
      <div style={isListening ? styles.voiceHeroActive : styles.voiceHero}>
        <div style={styles.voiceHeroLeft}>
          <button
            onClick={toggleVoiceGuard}
            style={isListening ? styles.voiceStartBtnActive : styles.voiceStartBtn}
            title="Click or press Spacebar to toggle"
          >
            <span style={styles.micIcon}>{isListening ? "🔴" : "🎙️"}</span>
            <span style={styles.voiceBtnText}>
              {isListening ? "STOP VOICE GUARD" : "START VOICE GUARD"}
            </span>
            <span style={styles.voiceSubLang}>
              {isListening ? "Listening / கேட்கிறது..." : "பேசி இயக்கவும் (Spacebar)"}
            </span>
          </button>

          {/* Sound Wave Equalizer (Animated when listening) */}
          {isListening && (
            <div style={styles.equalizerContainer}>
              <div style={{ ...styles.eqBar, animationDelay: "0.0s" }} />
              <div style={{ ...styles.eqBar, animationDelay: "0.2s" }} />
              <div style={{ ...styles.eqBar, animationDelay: "0.4s" }} />
              <div style={{ ...styles.eqBar, animationDelay: "0.1s" }} />
              <div style={{ ...styles.eqBar, animationDelay: "0.3s" }} />
            </div>
          )}
        </div>

        <div style={styles.voiceHeroRight}>
          <div style={styles.voiceStatusLine}>
            <span style={styles.statusDot(isListening)} />
            <span style={styles.voiceStatusText}>{voiceStatus}</span>
          </div>
          {transcript && (
            <div style={styles.liveTranscriptBox}>
              <span style={styles.transcriptLabel}>Spoken Audio:</span> "{transcript}"
            </div>
          )}
          {lastIntent && (
            <div style={styles.intentBadge}>
              Detected Intent: <strong>{lastIntent.name}</strong>{" "}
              {lastIntent.otp && <span>(OTP: {lastIntent.otp})</span>}
            </div>
          )}

          {/* Language Mode Toggle (Tanglish / Indian English vs Pure Tamil) */}
          <div style={styles.langSelectorRow}>
            <span style={{ fontSize: "11px", color: "#94a3b8", fontWeight: "600" }}>Spoken Language:</span>
            <button
              type="button"
              onClick={() => {
                setSpeechLang("en-IN");
                initSpeechEngine("en-IN");
                speakFeedback("Tanglish and English mode active.");
              }}
              style={speechLang === "en-IN" ? styles.langBtnActive : styles.langBtn}
            >
              🌐 Tanglish & English
            </button>
            <button
              type="button"
              onClick={() => {
                setSpeechLang("ta-IN");
                initSpeechEngine("ta-IN");
                speakFeedback("தமிழ் பயன்முறை இயக்கப்பட்டது.");
              }}
              style={speechLang === "ta-IN" ? styles.langBtnActive : styles.langBtn}
            >
              🇮🇳 தமிழ் (Tamil)
            </button>
          </div>
        </div>
      </div>

      {/* ── TAB 1: Gate Pass Verification ──────────────────────────── */}
      {activeTab === "verify" && (
        <div style={styles.mainGrid}>
          {/* Left Column: Quick OTP Form & Direct Input */}
          <div style={styles.card}>
            <h2 style={styles.cardHeading}>Keypad or Spoken OTP</h2>
            <p style={styles.cardSub}>
              Ask student for the 6-digit OTP received after HOD approval. Watchman can speak in <strong>Tamil, English, or Tanglish</strong>.
            </p>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                verifyOtpCode(otp);
              }}
              style={styles.form}
            >
              <div style={styles.inputGroup}>
                <input
                  type="text"
                  maxLength={6}
                  placeholder="e.g. 745743"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                  style={styles.otpInput}
                />
                <button
                  type="submit"
                  disabled={loading || otp.length < 6}
                  style={
                    loading || otp.length < 6
                      ? styles.verifyBtnDisabled
                      : styles.verifyBtn
                  }
                >
                  {loading ? "Checking..." : "Verify OTP"}
                </button>
              </div>
            </form>

            {errorMsg && (
              <div style={styles.errorAlert}>
                <span style={styles.alertIcon}>⚠️</span>
                <span>{errorMsg}</span>
              </div>
            )}

            {/* Quick Voice Prompt Cheat Sheet for Watchman */}
            <div style={styles.voiceCheatsheet}>
              <div style={styles.cheatTitle}>🗣️ Tamil, English & Tanglish Spoken Voice Examples:</div>
              <ul style={styles.cheatList}>
                <li><strong>Tanglish OTP:</strong> "student OTP ezhu naalu anju ezhu naalu moonu" or "OTP onnu rendu moonu naalu anju aaru"</li>
                <li><strong>Tamil Script OTP:</strong> "OTP ஏழு நாலு ஐந்து ஏழு நான்கு மூன்று"</li>
                <li><strong>English OTP:</strong> "seven four five seven four three" or "double seven four five..."</li>
                <li><strong>Tanglish Exit Confirm:</strong> "exit confirm pannu", "student veliya pogalam", "allow pannu", "gate thora"</li>
                <li><strong>Tanglish Incident:</strong> "id card illama gate jump panna try pannitan", "medical emergency ambulance call pannom"</li>
                <li><strong>Tanglish Visitor:</strong> "parent kooda student poran permission ketanga"</li>
              </ul>
            </div>
          </div>

          {/* Right Column: Live Student Pass Result Card */}
          <div style={styles.card}>
            <h2 style={styles.cardHeading}>Verification Result</h2>

            {!result && !loading && (
              <div style={styles.emptyState}>
                <div style={styles.emptyIcon}>🛡️</div>
                <div style={styles.emptyTitle}>Awaiting Gate Pass Verification</div>
                <p style={styles.emptyDesc}>
                  Say student OTP into mic or type OTP in the keypad to pull live photo, approvals, and departure permission.
                </p>
              </div>
            )}

            {loading && (
              <div style={styles.emptyState}>
                <div style={styles.spinner} />
                <div style={styles.emptyTitle}>Connecting to EduTrack Database...</div>
              </div>
            )}

            {result && (
              <div style={styles.resultContainer}>
                {/* Status Banner */}
                <div
                  style={
                    result.valid && result.is_used === 0
                      ? styles.statusBannerApproved
                      : styles.statusBannerDenied
                  }
                >
                  <span style={styles.bannerIcon}>
                    {result.valid && result.is_used === 0 ? "✅" : "⛔"}
                  </span>
                  <div>
                    <div style={styles.bannerTitle}>
                      {result.valid && result.is_used === 0
                        ? "PERMISSION GRANTED · ALLOW TO EXIT"
                        : result.is_used === 1
                        ? "GATE PASS ALREADY USED"
                        : "GATE PASS NOT VALID"}
                    </div>
                    <div style={styles.bannerSub}>{result.message}</div>
                  </div>
                </div>

                {/* Student Profile Overview */}
                <div style={styles.studentCard}>
                  <div style={styles.avatarWrapper}>
                    <img
                      src={`${API_BASE}${result.avatar_url}`}
                      alt={result.student_name}
                      style={styles.avatarImg}
                      onError={(e) => {
                        e.target.onerror = null;
                        e.target.src = "https://via.placeholder.com/150/1e293b/38bdf8?text=Student";
                      }}
                    />
                    <div style={styles.avatarBadge}>Verified</div>
                  </div>

                  <div style={styles.studentMeta}>
                    <h3 style={styles.studentName}>{result.student_name}</h3>
                    <div style={styles.metaRow}>
                      <span style={styles.metaLabel}>Roll No:</span>
                      <strong style={styles.metaVal}>{result.roll_number || result.student_id}</strong>
                    </div>
                    <div style={styles.metaRow}>
                      <span style={styles.metaLabel}>Register No:</span>
                      <strong style={styles.metaVal}>{result.register_number || "—"}</strong>
                    </div>
                    <div style={styles.metaRow}>
                      <span style={styles.metaLabel}>Department:</span>
                      <strong style={styles.metaVal}>{result.department || "—"}</strong>
                    </div>
                    <div style={styles.metaRow}>
                      <span style={styles.metaLabel}>Reason:</span>
                      <span style={styles.metaVal}>{result.reason}</span>
                    </div>
                    <div style={styles.metaRow}>
                      <span style={styles.metaLabel}>Permitted Out Time:</span>
                      <strong style={{ ...styles.metaVal, color: "#38bdf8" }}>
                        {result.out_time} ({result.event_date})
                      </strong>
                    </div>
                  </div>
                </div>

                {/* 2-Tier Approval Timeline */}
                <div style={styles.timelineBox}>
                  <div style={styles.timelineItem}>
                    <span style={styles.timelineDot}>✓</span>
                    <div>
                      <strong>Class Incharge:</strong> {result.faculty_name || "Faculty Incharge"}
                      <div style={styles.timelineSub}>{result.faculty_time}</div>
                    </div>
                  </div>
                  <div style={styles.timelineItem}>
                    <span style={styles.timelineDot}>✓</span>
                    <div>
                      <strong>HOD Final Approval:</strong> {result.hod_name || "Head of Department"}
                      <div style={styles.timelineSub}>{result.hod_time}</div>
                    </div>
                  </div>
                </div>

                {/* Action Buttons */}
                {result.valid && result.is_used === 0 && (
                  <div style={styles.actionRow}>
                    <button
                      onClick={handleConfirmExit}
                      disabled={exitLoading}
                      style={exitLoading ? styles.confirmBtnDisabled : styles.confirmBtn}
                    >
                      {exitLoading ? "Recording Exit..." : "🚪 Confirm Student Exit (Allow Out)"}
                    </button>
                  </div>
                )}

                {result.is_used === 1 && (
                  <div style={styles.alreadyExitedNotice}>
                    Student exited campus at <strong>{result.exited_at}</strong>. Pass has expired.
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── TAB 2: Spoken Incident Registry ────────────────────────── */}
      {activeTab === "incidents" && (
        <div style={styles.card}>
          <div style={styles.incidentHeader}>
            <div>
              <h2 style={styles.cardHeading}>Gate Situations & Spoken Incident Registry</h2>
              <p style={styles.cardSub}>
                Watchman can describe any incident verbally into the microphone. Situations are automatically categorized and logged in real-time.
              </p>
            </div>
            <button onClick={fetchIncidents} style={styles.refreshBtn}>
              🔄 Refresh
            </button>
          </div>

          {incidents.length === 0 ? (
            <div style={styles.emptyState}>
              <div style={styles.emptyIcon}>🛡️</div>
              <div style={styles.emptyTitle}>No Incidents Reported</div>
              <p style={styles.emptyDesc}>Gate operations are normal. Say "Incident: [Details]" to log a situation.</p>
            </div>
          ) : (
            <div style={styles.incidentGrid}>
              {incidents.map((inc) => (
                <div key={inc.id} style={styles.incidentCard(inc.severity)}>
                  <div style={styles.incidentTop}>
                    <span style={styles.severityBadge(inc.severity)}>
                      {inc.severity.toUpperCase()}
                    </span>
                    <span style={styles.incidentCat}>{inc.category}</span>
                    <span style={styles.incidentTime}>{inc.logged_at}</span>
                  </div>
                  <div style={styles.incidentDesc}>{inc.description}</div>
                  <div style={styles.incidentGuard}>Logged by: {inc.guard_id}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── TAB 3: Exit History ────────────────────────────────────── */}
      {activeTab === "history" && (
        <div style={styles.card}>
          <div style={styles.incidentHeader}>
            <div>
              <h2 style={styles.cardHeading}>Recent Verified Departures</h2>
              <p style={styles.cardSub}>Audit trail of students who cleared gate verification today.</p>
            </div>
            <button onClick={fetchRecentExits} style={styles.refreshBtn}>
              🔄 Refresh
            </button>
          </div>

          <div style={styles.tableWrapper}>
            <table style={styles.table}>
              <thead>
                <tr style={styles.trHead}>
                  <th style={styles.th}>Pass ID</th>
                  <th style={styles.th}>Student Name</th>
                  <th style={styles.th}>Register No</th>
                  <th style={styles.th}>Department</th>
                  <th style={styles.th}>Reason</th>
                  <th style={styles.th}>Exited At</th>
                </tr>
              </thead>
              <tbody>
                {recentExits.map((item) => (
                  <tr key={item.id} style={styles.trBody}>
                    <td style={styles.td}>#{item.id}</td>
                    <td style={{ ...styles.td, fontWeight: "600", color: "#f8fafc" }}>
                      {item.name || item.student_id}
                    </td>
                    <td style={styles.td}>{item.register_number || "—"}</td>
                    <td style={styles.td}>{item.department || "—"}</td>
                    <td style={styles.td}>{item.reason}</td>
                    <td style={{ ...styles.td, color: "#38bdf8" }}>{item.exited_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Global CSS for Animations */}
      <style>{`
        @keyframes pulseBar {
          0% { height: 6px; }
          50% { height: 28px; }
          100% { height: 6px; }
        }
      `}</style>
    </div>
  );
}

// ── Ultra-Modern Security Kiosk Styling ─────────────────────────────────
const styles = {
  container: {
    maxWidth: "1380px",
    margin: "0 auto",
    padding: "24px 20px 48px",
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    color: "#e2e8f0",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-end",
    marginBottom: "20px",
    borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
    paddingBottom: "16px",
    flexWrap: "wrap",
    gap: "16px",
  },
  badgeRow: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    marginBottom: "6px",
  },
  kioskBadge: {
    background: "#0284c7",
    color: "#fff",
    fontSize: "11px",
    fontWeight: "700",
    padding: "3px 10px",
    borderRadius: "12px",
    letterSpacing: "0.5px",
  },
  onlineBadge: {
    color: "#22c55e",
    fontSize: "12px",
    fontWeight: "600",
  },
  title: {
    fontSize: "26px",
    fontWeight: "800",
    color: "#f8fafc",
    margin: "0 0 4px",
    letterSpacing: "-0.5px",
  },
  subtitle: {
    fontSize: "13px",
    color: "#94a3b8",
    margin: 0,
  },
  tabBar: {
    display: "flex",
    gap: "8px",
    background: "#0f172a",
    padding: "4px",
    borderRadius: "10px",
    border: "1px solid #1e293b",
  },
  tabBtn: {
    background: "transparent",
    color: "#94a3b8",
    border: "none",
    padding: "8px 14px",
    borderRadius: "8px",
    cursor: "pointer",
    fontSize: "13px",
    fontWeight: "600",
    transition: "all 0.2s",
  },
  tabBtnActive: {
    background: "#1e293b",
    color: "#38bdf8",
    border: "none",
    padding: "8px 14px",
    borderRadius: "8px",
    cursor: "pointer",
    fontSize: "13px",
    fontWeight: "700",
    boxShadow: "0 2px 4px rgba(0,0,0,0.2)",
  },

  // ── Voice Hero Box ──────────────────────────────────────────────────
  voiceHero: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    background: "linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%)",
    border: "1px solid #334155",
    borderRadius: "16px",
    padding: "16px 20px",
    marginBottom: "24px",
    boxShadow: "0 4px 20px rgba(0, 0, 0, 0.25)",
    flexWrap: "wrap",
    gap: "16px",
  },
  voiceHeroActive: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    background: "linear-gradient(135deg, #1e1b4b 0%, #064e3b 100%)",
    border: "1px solid #10b981",
    borderRadius: "16px",
    padding: "16px 20px",
    marginBottom: "24px",
    boxShadow: "0 0 25px rgba(16, 185, 129, 0.25)",
    flexWrap: "wrap",
    gap: "16px",
  },
  voiceHeroLeft: {
    display: "flex",
    alignItems: "center",
    gap: "16px",
  },
  voiceStartBtn: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    background: "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)",
    color: "#fff",
    border: "none",
    padding: "10px 18px",
    borderRadius: "12px",
    cursor: "pointer",
    boxShadow: "0 4px 14px rgba(37, 99, 235, 0.35)",
    transition: "all 0.2s",
  },
  voiceStartBtnActive: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    background: "linear-gradient(135deg, #ef4444 0%, #dc2626 100%)",
    color: "#fff",
    border: "none",
    padding: "10px 18px",
    borderRadius: "12px",
    cursor: "pointer",
    boxShadow: "0 0 16px rgba(239, 68, 68, 0.5)",
    transition: "all 0.2s",
  },
  micIcon: {
    fontSize: "18px",
    marginBottom: "2px",
  },
  voiceBtnText: {
    fontSize: "14px",
    fontWeight: "800",
    letterSpacing: "0.5px",
  },
  voiceSubLang: {
    fontSize: "11px",
    opacity: 0.85,
  },
  equalizerContainer: {
    display: "flex",
    alignItems: "center",
    gap: "4px",
    height: "36px",
  },
  eqBar: {
    width: "5px",
    background: "#10b981",
    borderRadius: "4px",
    animation: "pulseBar 0.8s infinite ease-in-out",
  },
  voiceHeroRight: {
    flex: 1,
    minWidth: "260px",
  },
  voiceStatusLine: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    marginBottom: "4px",
  },
  statusDot: (active) => ({
    width: "10px",
    height: "10px",
    borderRadius: "50%",
    background: active ? "#10b981" : "#94a3b8",
    boxShadow: active ? "0 0 8px #10b981" : "none",
  }),
  voiceStatusText: {
    fontSize: "14px",
    fontWeight: "600",
    color: "#f1f5f9",
  },
  liveTranscriptBox: {
    fontSize: "13px",
    color: "#cbd5e1",
    background: "rgba(0, 0, 0, 0.25)",
    padding: "6px 10px",
    borderRadius: "8px",
    marginTop: "6px",
    fontFamily: "monospace",
  },
  transcriptLabel: {
    color: "#38bdf8",
    fontWeight: "700",
    marginRight: "6px",
  },
  intentBadge: {
    display: "inline-block",
    fontSize: "11px",
    color: "#22c55e",
    background: "rgba(34, 197, 94, 0.15)",
    padding: "2px 8px",
    borderRadius: "6px",
    marginTop: "6px",
  },
  langSelectorRow: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    marginTop: "8px",
    flexWrap: "wrap",
  },
  langBtn: {
    background: "#1e293b",
    color: "#94a3b8",
    border: "1px solid #334155",
    padding: "4px 10px",
    borderRadius: "6px",
    fontSize: "11px",
    cursor: "pointer",
    fontWeight: "600",
    transition: "all 0.2s",
  },
  langBtnActive: {
    background: "#0284c7",
    color: "#fff",
    border: "1px solid #38bdf8",
    padding: "4px 10px",
    borderRadius: "6px",
    fontSize: "11px",
    cursor: "pointer",
    fontWeight: "700",
    boxShadow: "0 0 10px rgba(2, 132, 199, 0.4)",
  },

  // ── Layout & Cards ──────────────────────────────────────────────────
  mainGrid: {
    display: "grid",
    gridTemplateColumns: "1.1fr 1.5fr",
    gap: "24px",
  },
  card: {
    background: "#0f172a",
    border: "1px solid #1e293b",
    borderRadius: "16px",
    padding: "24px",
    boxShadow: "0 8px 30px rgba(0, 0, 0, 0.3)",
  },
  cardHeading: {
    fontSize: "18px",
    fontWeight: "700",
    color: "#f8fafc",
    margin: "0 0 6px",
  },
  cardSub: {
    fontSize: "13px",
    color: "#94a3b8",
    margin: "0 0 20px",
  },
  form: {
    marginBottom: "20px",
  },
  inputGroup: {
    display: "flex",
    gap: "10px",
  },
  otpInput: {
    flex: 1,
    background: "#1e293b",
    border: "1px solid #334155",
    color: "#f8fafc",
    fontSize: "24px",
    fontWeight: "800",
    letterSpacing: "4px",
    textAlign: "center",
    padding: "12px 16px",
    borderRadius: "12px",
    outline: "none",
  },
  verifyBtn: {
    background: "linear-gradient(135deg, #0284c7 0%, #0369a1 100%)",
    color: "#fff",
    border: "none",
    fontWeight: "700",
    fontSize: "15px",
    padding: "0 22px",
    borderRadius: "12px",
    cursor: "pointer",
  },
  verifyBtnDisabled: {
    background: "#334155",
    color: "#64748b",
    border: "none",
    fontWeight: "700",
    fontSize: "15px",
    padding: "0 22px",
    borderRadius: "12px",
    cursor: "not-allowed",
  },
  errorAlert: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    background: "rgba(239, 68, 68, 0.15)",
    border: "1px solid #ef4444",
    color: "#fca5a5",
    padding: "12px 14px",
    borderRadius: "10px",
    fontSize: "13px",
    marginBottom: "16px",
  },
  alertIcon: {
    fontSize: "16px",
  },
  voiceCheatsheet: {
    background: "rgba(30, 41, 59, 0.6)",
    border: "1px dashed #334155",
    borderRadius: "12px",
    padding: "14px",
  },
  cheatTitle: {
    fontSize: "13px",
    fontWeight: "700",
    color: "#38bdf8",
    marginBottom: "8px",
  },
  cheatList: {
    fontSize: "12px",
    color: "#cbd5e1",
    margin: 0,
    paddingLeft: "18px",
    lineHeight: "1.7",
  },

  // ── Empty States & Spinner ──────────────────────────────────────────
  emptyState: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    padding: "50px 20px",
    textAlign: "center",
  },
  emptyIcon: {
    fontSize: "48px",
    marginBottom: "14px",
    opacity: 0.6,
  },
  emptyTitle: {
    fontSize: "16px",
    fontWeight: "700",
    color: "#f8fafc",
    marginBottom: "6px",
  },
  emptyDesc: {
    fontSize: "13px",
    color: "#64748b",
    maxWidth: "360px",
    margin: 0,
  },
  spinner: {
    width: "36px",
    height: "36px",
    border: "3px solid #334155",
    borderTop: "3px solid #38bdf8",
    borderRadius: "50%",
    animation: "spin 1s linear infinite",
    marginBottom: "16px",
  },

  // ── Result Container ────────────────────────────────────────────────
  resultContainer: {
    display: "flex",
    flexDirection: "column",
    gap: "18px",
  },
  statusBannerApproved: {
    display: "flex",
    alignItems: "center",
    gap: "14px",
    background: "linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(5, 150, 105, 0.2) 100%)",
    border: "1px solid #10b981",
    borderRadius: "12px",
    padding: "14px 18px",
  },
  statusBannerDenied: {
    display: "flex",
    alignItems: "center",
    gap: "14px",
    background: "linear-gradient(135deg, rgba(239, 68, 68, 0.2) 0%, rgba(185, 28, 28, 0.2) 100%)",
    border: "1px solid #ef4444",
    borderRadius: "12px",
    padding: "14px 18px",
  },
  bannerIcon: {
    fontSize: "26px",
  },
  bannerTitle: {
    fontSize: "15px",
    fontWeight: "800",
    color: "#f8fafc",
    letterSpacing: "0.5px",
  },
  bannerSub: {
    fontSize: "12px",
    color: "#cbd5e1",
    marginTop: "2px",
  },
  studentCard: {
    display: "flex",
    gap: "20px",
    background: "#1e293b",
    borderRadius: "14px",
    padding: "18px",
    border: "1px solid rgba(255, 255, 255, 0.05)",
  },
  avatarWrapper: {
    position: "relative",
    width: "110px",
    height: "130px",
    flexShrink: 0,
  },
  avatarImg: {
    width: "100%",
    height: "100%",
    objectFit: "cover",
    borderRadius: "10px",
    border: "2px solid #38bdf8",
  },
  avatarBadge: {
    position: "absolute",
    bottom: "-6px",
    left: "50%",
    transform: "translateX(-50%)",
    background: "#10b981",
    color: "#fff",
    fontSize: "9px",
    fontWeight: "800",
    padding: "2px 8px",
    borderRadius: "8px",
    letterSpacing: "0.5px",
  },
  studentMeta: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  studentName: {
    fontSize: "18px",
    fontWeight: "800",
    color: "#f8fafc",
    margin: "0 0 4px",
  },
  metaRow: {
    display: "flex",
    gap: "8px",
    fontSize: "13px",
  },
  metaLabel: {
    color: "#94a3b8",
    width: "130px",
  },
  metaVal: {
    color: "#e2e8f0",
  },
  timelineBox: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
    background: "rgba(15, 23, 42, 0.6)",
    padding: "14px 18px",
    borderRadius: "12px",
    border: "1px solid #334155",
  },
  timelineItem: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    fontSize: "13px",
    color: "#e2e8f0",
  },
  timelineDot: {
    width: "20px",
    height: "20px",
    borderRadius: "50%",
    background: "#10b981",
    color: "#fff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "11px",
    fontWeight: "bold",
  },
  timelineSub: {
    fontSize: "11px",
    color: "#94a3b8",
  },
  actionRow: {
    marginTop: "8px",
  },
  confirmBtn: {
    width: "100%",
    background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
    color: "#fff",
    border: "none",
    padding: "14px",
    borderRadius: "12px",
    fontSize: "16px",
    fontWeight: "800",
    cursor: "pointer",
    boxShadow: "0 4px 16px rgba(16, 185, 129, 0.35)",
  },
  confirmBtnDisabled: {
    width: "100%",
    background: "#334155",
    color: "#64748b",
    border: "none",
    padding: "14px",
    borderRadius: "12px",
    fontSize: "16px",
    fontWeight: "800",
    cursor: "not-allowed",
  },
  alreadyExitedNotice: {
    background: "rgba(148, 163, 184, 0.1)",
    border: "1px solid #475569",
    color: "#cbd5e1",
    padding: "12px",
    borderRadius: "10px",
    textAlign: "center",
    fontSize: "13px",
  },

  // ── Incidents Tab ───────────────────────────────────────────────────
  incidentHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: "16px",
  },
  refreshBtn: {
    background: "#1e293b",
    color: "#38bdf8",
    border: "1px solid #334155",
    padding: "6px 12px",
    borderRadius: "8px",
    cursor: "pointer",
    fontSize: "12px",
    fontWeight: "600",
  },
  incidentGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
    gap: "14px",
  },
  incidentCard: (sev) => ({
    background: "#1e293b",
    borderLeft: `4px solid ${sev === "High" ? "#ef4444" : sev === "Medium" ? "#f59e0b" : "#3b82f6"}`,
    borderRadius: "10px",
    padding: "14px",
  }),
  incidentTop: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    marginBottom: "8px",
  },
  severityBadge: (sev) => ({
    background: sev === "High" ? "#ef4444" : sev === "Medium" ? "#f59e0b" : "#3b82f6",
    color: "#fff",
    fontSize: "10px",
    fontWeight: "800",
    padding: "2px 6px",
    borderRadius: "4px",
  }),
  incidentCat: {
    fontSize: "12px",
    fontWeight: "700",
    color: "#f8fafc",
  },
  incidentTime: {
    fontSize: "11px",
    color: "#94a3b8",
    marginLeft: "auto",
  },
  incidentDesc: {
    fontSize: "13px",
    color: "#cbd5e1",
    marginBottom: "8px",
    lineHeight: "1.5",
  },
  incidentGuard: {
    fontSize: "11px",
    color: "#64748b",
  },

  // ── Table Styling ───────────────────────────────────────────────────
  tableWrapper: {
    overflowX: "auto",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: "13px",
  },
  trHead: {
    background: "#1e293b",
  },
  th: {
    textAlign: "left",
    padding: "12px 14px",
    color: "#94a3b8",
    fontWeight: "600",
    borderBottom: "1px solid #334155",
  },
  trBody: {
    borderBottom: "1px solid rgba(255, 255, 255, 0.05)",
  },
  td: {
    padding: "12px 14px",
    color: "#cbd5e1",
  },
};
