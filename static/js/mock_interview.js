// AI avatar and expressions
const avatar = document.getElementById("ai-avatar");
const aiAudio = document.getElementById("ai-audio");
const aiText = document.getElementById("ai-text");
const startInterviewBtn = document.getElementById("start-interview-btn");
const repeatQuestionBtn = document.getElementById("repeat-question-btn");

// Interview setup inputs
const roleInput = document.getElementById("mock-role-input");
const companyInput = document.getElementById("mock-company-input");

// Candidate side
const userVideo = document.getElementById("user-video");
const userPlaceholder = document.getElementById("user-placeholder");
const cameraStatusDot = document.getElementById("camera-status-dot");

// Recording controls
const startRecordBtn = document.getElementById("start-record-btn");
const stopRecordBtn = document.getElementById("stop-record-btn");
const recordingDot = document.getElementById("recording-dot");
const recordingText = document.getElementById("recording-text");
const answerLogBody = document.getElementById("answer-log-body");

// Text answer controls
const textAnswerControls = document.getElementById("text-answer-controls");
const voiceAnswerControls = document.getElementById("voice-answer-controls");
const textAnswerInput = document.getElementById("text-answer-input");
const submitTextAnswerBtn = document.getElementById("submit-text-answer-btn");
const textAnswerStatus = document.getElementById("text-answer-status");

// Mode toggle
const answerModeButtons = document.querySelectorAll(".answer-mode-btn");

let answerMode = "voice"; // "voice" or "text"

// Expression sources from data attributes on the <img>
const expressions = {
  neutral: avatar.dataset.neutralSrc,
  blink: avatar.dataset.blinkSrc,
  mouthClosed: avatar.dataset.mouthClosedSrc,
  mouthHalf: avatar.dataset.mouthHalfSrc,
  mouthOpen: avatar.dataset.mouthOpenSrc,
  listen: avatar.dataset.listenSrc,
  think: avatar.dataset.thinkSrc
};

// State flags
let mouthTimer = null;
let mouthIndex = 0;
let isTalking = false;

let blinkTimeout = null;
let isBlinking = false;

let baseExpression = "neutral"; // "neutral" | "listen" | "think"

let mediaRecorder = null;
let recordedChunks = [];
let isRecording = false;

// Mock interview state
const TOTAL_QUESTIONS = 10;
let mockInterviewActive = false;
let lastSpokenText = "";
let lastQuestionText = "";

// Mouth cycle frames
const mouthCycle = ["mouthClosed", "mouthHalf", "mouthOpen", "mouthHalf"];

// ---------------------------
// Expression helpers
// ---------------------------

function showExpression(key) {
  const src = expressions[key];
  if (src) {
    avatar.src = src;
  }
}

// Set the base expression
function setBaseExpression(mode) {
  baseExpression = mode;
  if (!isTalking && !isBlinking) {
    if (mode === "listen") {
      showExpression("listen");
    } else if (mode === "think") {
      showExpression("think");
    } else {
      showExpression("neutral");
    }
  }
}

// ---------------------------
// Mouth animation
// ---------------------------

function startMouthAnimation() {
  if (mouthTimer) return;
  isTalking = true;
  mouthIndex = 0;

  mouthTimer = setInterval(() => {
    const frameKey = mouthCycle[mouthIndex];
    showExpression(frameKey);
    mouthIndex = (mouthIndex + 1) % mouthCycle.length;
  }, 120);
}

function stopMouthAnimation() {
  if (!mouthTimer) return;
  clearInterval(mouthTimer);
  mouthTimer = null;
  isTalking = false;

  if (!isBlinking) {
    setBaseExpression(baseExpression);
  }
}

// Bind to audio events
aiAudio.addEventListener("play", () => {
  setBaseExpression("neutral");
  startMouthAnimation();
});
aiAudio.addEventListener("ended", stopMouthAnimation);
aiAudio.addEventListener("pause", stopMouthAnimation);

// ---------------------------
// Blinking
// ---------------------------

function scheduleBlink() {
  const delay = 2500 + Math.random() * 4000;
  blinkTimeout = setTimeout(doBlink, delay);
}

function doBlink() {
  if (isTalking) {
    scheduleBlink();
    return;
  }

  isBlinking = true;
  showExpression("blink");

  setTimeout(() => {
    isBlinking = false;
    setBaseExpression(baseExpression);
    scheduleBlink();
  }, 140);
}

scheduleBlink();

// ---------------------------
// Camera handling
// ---------------------------

async function initCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: true,
      audio: false
    });

    userVideo.srcObject = stream;
    userVideo.style.display = "block";
    userPlaceholder.style.display = "none";
    cameraStatusDot.classList.add("status-online");
  } catch (err) {
    console.warn("Camera access denied or not available", err);
    userVideo.style.display = "none";
    userPlaceholder.style.display = "flex";
    cameraStatusDot.classList.remove("status-online");
  }
}

if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
  initCamera();
} else {
  userVideo.style.display = "none";
  userPlaceholder.style.display = "flex";
}

// ---------------------------
// Mode toggle logic
// ---------------------------

answerModeButtons.forEach(btn => {
  btn.addEventListener("click", () => {
    const mode = btn.dataset.mode;
    if (!mode || mode === answerMode) return;

    answerMode = mode;

    answerModeButtons.forEach(b => {
      b.classList.toggle(
        "answer-mode-btn-active",
        b.dataset.mode === answerMode
      );
    });

    if (answerMode === "voice") {
      voiceAnswerControls.classList.remove("hidden");
      textAnswerControls.classList.add("hidden");
      recordingText.innerText = "Not recording";
    } else {
      voiceAnswerControls.classList.add("hidden");
      textAnswerControls.classList.remove("hidden");
      textAnswerStatus.innerText = "Ready for your typed answer";
    }
  });
});

// ---------------------------
// TTS helper
// ---------------------------

async function speakText(textToSpeak) {
  setBaseExpression("think");

  try {
    const response = await fetch("/api/tts_question", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ text: textToSpeak })
    });

    if (!response.ok) {
      console.error("TTS error", await response.text());
      setBaseExpression("neutral");
      return;
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);

    aiAudio.src = url;
    setBaseExpression("neutral");
    aiAudio.play();
  } catch (err) {
    console.error("TTS request failed", err);
    setBaseExpression("neutral");
  }
}

async function playIntroAndQuestion(intro, question) {
  const introText = intro ? intro.trim() : "";
  const questionText = question || "";
  const combined = introText ? introText + " " + questionText : questionText;

  lastSpokenText = combined;
  lastQuestionText = questionText;
  aiText.innerText = questionText || "The interviewer has a question for you.";

  await speakText(combined);
}

// ---------------------------
// Mock interview flow
// ---------------------------

startInterviewBtn.addEventListener("click", async () => {
  if (mockInterviewActive) return;

  const role = roleInput ? roleInput.value.trim() : "";
  const company = companyInput ? companyInput.value.trim() : "";

  startInterviewBtn.disabled = true;
  repeatQuestionBtn.disabled = true;
  mockInterviewActive = true;

  // Reset log UI state
  answerLogBody.innerHTML =
    "As you answer, your transcript and feedback for each question will appear here in real time.";
  delete answerLogBody.dataset.hasAnswers;

  try {
    const resp = await fetch("/api/mock_interview_start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_title: role, company: company })
    });

    if (!resp.ok) {
      console.error("Error starting mock interview", await resp.text());
      aiText.innerText = "Could not start mock interview. Please try again.";
      mockInterviewActive = false;
      startInterviewBtn.disabled = false;
      return;
    }

    const data = await resp.json();
    const intro = data.intro || "";
    const question = data.question || "Can you tell me about yourself?";

    await playIntroAndQuestion(intro, question);

    repeatQuestionBtn.disabled = false;
  } catch (err) {
    console.error("Error calling /api/mock_interview_start", err);
    aiText.innerText = "Could not start mock interview. Please try again.";
    mockInterviewActive = false;
    startInterviewBtn.disabled = false;
  }
});

repeatQuestionBtn.addEventListener("click", async () => {
  if (!lastSpokenText) return;
  await speakText(lastSpokenText);
});

// Fetch next question after each answer
async function fetchNextMockQuestion() {
  try {
    const resp = await fetch("/api/mock_interview_next_question", {
      method: "POST"
    });

    if (!resp.ok) {
      console.error("Error fetching next mock question:", await resp.text());
      return;
    }

    const data = await resp.json();

    if (data.done) {
      aiText.innerText =
        data.message ||
        "This concludes your mock interview. Great job. You can start another session any time.";
      mockInterviewActive = false;
      startInterviewBtn.disabled = false;
      repeatQuestionBtn.disabled = true;
      lastSpokenText = "";
      lastQuestionText = "";
      return;
    }

    const intro = data.intro || "";
    const question = data.question || "";

    await playIntroAndQuestion(intro, question);
  } catch (err) {
    console.error("Error getting next mock question:", err);
  }
}

// ---------------------------
// Helper to append answer block
// ---------------------------

function appendAnswerBlock(questionText, transcript, evalResult) {
  const feedbackText =
    (evalResult && (evalResult.feedback_text || evalResult.feedback)) || "";

  const block = document.createElement("div");
  block.style.marginBottom = "0.75rem";

  const safeQuestion = questionText || "(question not available)";

  block.innerHTML =
    "<strong>Question:</strong><br>" +
    safeQuestion.replace(/\n/g, "<br>") +
    "<br><br><strong>Your answer:</strong><br>" +
    transcript.replace(/\n/g, "<br>") +
    (feedbackText
      ? "<br><br><strong>Feedback:</strong><br>" +
        feedbackText.replace(/\n/g, "<br>")
      : "");

  if (!answerLogBody.dataset.hasAnswers) {
    answerLogBody.innerHTML = "";
    answerLogBody.dataset.hasAnswers = "1";
  }

  answerLogBody.appendChild(block);
  answerLogBody.scrollTop = answerLogBody.scrollHeight;
}

// ---------------------------
// Audio recording from candidate
// ---------------------------

async function startRecording() {
  if (answerMode !== "voice") return;
  if (isRecording) return;

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recordedChunks = [];
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = event => {
      if (event.data.size > 0) {
        recordedChunks.push(event.data);
      }
    };

    mediaRecorder.onstop = () => {
      const blob = new Blob(recordedChunks, { type: "audio/webm" });
      handleRecordedAnswer(blob);
      stream.getTracks().forEach(track => track.stop());
    };

    mediaRecorder.start();
    isRecording = true;

    startRecordBtn.disabled = true;
    stopRecordBtn.disabled = false;

    recordingDot.classList.add("is-recording");
    recordingText.innerText = "Recording answer...";
    setBaseExpression("listen");
  } catch (err) {
    console.error("Error starting audio recording", err);
    recordingText.innerText = "Could not access microphone";
  }
}

function stopRecording() {
  if (answerMode !== "voice") return;
  if (!isRecording || !mediaRecorder) return;

  mediaRecorder.stop();
  isRecording = false;

  startRecordBtn.disabled = false;
  stopRecordBtn.disabled = true;

  recordingDot.classList.remove("is-recording");
  recordingText.innerText = "Processing answer...";
}

async function handleRecordedAnswer(blob) {
  answerLogBody.innerText = "Transcribing your answer...";
  recordingText.innerText = "Processing answer...";
  setBaseExpression("think");

  try {
    const formData = new FormData();
    formData.append("audio", blob, "answer.webm");
    formData.append("question", lastQuestionText || aiText.innerText || "");

    const response = await fetch("/api/mock_interview_answer", {
      method: "POST",
      body: formData
    });

    const data = await response.json();

    if (!response.ok || data.error) {
      console.error("Mock interview transcription error:", data.error || data);
      answerLogBody.innerText =
        "There was an error transcribing your answer. Please try again.";
      recordingText.innerText = "Not recording";
      setBaseExpression("neutral");
      return;
    }

    const transcript = data.transcript || "(no transcript)";
    const evalResult = data.evaluation || {};
    const qForLog = lastQuestionText || aiText.innerText || "";

    appendAnswerBlock(qForLog, transcript, evalResult);

    recordingText.innerText = "Not recording";
    setBaseExpression("neutral");

    if (mockInterviewActive) {
      await fetchNextMockQuestion();
    }
  } catch (err) {
    console.error("Error sending mock interview audio:", err);
    answerLogBody.innerText =
      "There was an error sending your answer. Please try again.";
    recordingText.innerText = "Not recording";
    setBaseExpression("neutral");
  }
}

// ---------------------------
// Text answer submission
// ---------------------------

async function submitTextAnswer() {
  if (answerMode !== "text") return;

  const text = (textAnswerInput.value || "").trim();
  if (!text) {
    textAnswerStatus.innerText = "Please type your answer before submitting.";
    return;
  }

  textAnswerStatus.innerText = "Processing answer...";
  setBaseExpression("think");

  try {
    const response = await fetch("/api/mock_interview_answer_text", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        answer_text: text,
        question: lastQuestionText || aiText.innerText || ""
      })
    });

    const data = await response.json();

    if (!response.ok || data.error) {
      console.error("Mock interview text error:", data.error || data);
      textAnswerStatus.innerText =
        "There was an error processing your answer. Please try again.";
      setBaseExpression("neutral");
      return;
    }

    const transcript = data.transcript || text;
    const evalResult = data.evaluation || {};
    const qForLog = lastQuestionText || aiText.innerText || "";

    appendAnswerBlock(qForLog, transcript, evalResult);

    textAnswerStatus.innerText = "Answer submitted. Ready for the next one.";
    textAnswerInput.value = "";
    setBaseExpression("neutral");

    if (mockInterviewActive) {
      await fetchNextMockQuestion();
    }
  } catch (err) {
    console.error("Error sending mock interview text answer:", err);
    textAnswerStatus.innerText =
      "There was an error sending your answer. Please try again.";
    setBaseExpression("neutral");
  }
}

// Hook up buttons
startRecordBtn.addEventListener("click", () => {
  startRecording();
});

stopRecordBtn.addEventListener("click", () => {
  stopRecording();
});

submitTextAnswerBtn.addEventListener("click", () => {
  submitTextAnswer();
});
