// AI avatar and expressions
const avatar = document.getElementById("ai-avatar");
const aiAudio = document.getElementById("ai-audio");
const aiText = document.getElementById("ai-text");
const startInterviewBtn = document.getElementById("start-interview-btn");
const repeatQuestionBtn = document.getElementById("repeat-question-btn");

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

// Expression sources from data attributes
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

// Set the base expression (used when not talking / not blinking)
function setBaseExpression(mode) {
  baseExpression = mode;
  if (!isTalking && !isBlinking) {
    showExpression(mode === "listen" ? "listen" :
                   mode === "think" ? "think" : "neutral");
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

  // Return to base expression when done talking
  if (!isBlinking) {
    setBaseExpression(baseExpression);
  }
}

// Bind to audio events (when you plug real TTS, this will sync)
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
  const delay = 2500 + Math.random() * 4000; // 2.5–6.5s
  blinkTimeout = setTimeout(doBlink, delay);
}

function doBlink() {
  if (isTalking) {
    // Try again later if currently talking
    scheduleBlink();
    return;
  }

  isBlinking = true;
  showExpression("blink");

  setTimeout(() => {
    isBlinking = false;
    // Restore base expression
    setBaseExpression(baseExpression);
    scheduleBlink();
  }, 140); // blink duration
}

// Start blinking loop
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
// Mock interview flow
// ---------------------------

startInterviewBtn.addEventListener("click", async () => {
  startInterviewBtn.disabled = true;

  const firstQuestion =
    "Welcome to your mock interview. To start, can you tell me about yourself?";

  await playAIQuestion(firstQuestion);
  repeatQuestionBtn.disabled = false;
});

repeatQuestionBtn.addEventListener("click", async () => {
  await playAIQuestion(aiText.innerText);
});

async function playAIQuestion(text) {
  // Show thinking face briefly before speaking
  setBaseExpression("think");
  aiText.innerText = text;

  // When you have real TTS, replace this with:
  // 1. call backend to get audio URL
  // 2. set aiAudio.src = url and aiAudio.play()
  // For now we just simulate talking with mouth animation.
  setTimeout(() => {
    setBaseExpression("neutral");
    startMouthAnimation();
    setTimeout(() => {
      stopMouthAnimation();
    }, 1800);
  }, 400);
}

// ---------------------------
// Audio recording from candidate
// ---------------------------

async function startRecording() {
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

    // UI + avatar state
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
  if (!isRecording || !mediaRecorder) return;

  mediaRecorder.stop();
  isRecording = false;

  startRecordBtn.disabled = false;
  stopRecordBtn.disabled = true;

  recordingDot.classList.remove("is-recording");
  recordingText.innerText = "Processing answer...";
}

function handleRecordedAnswer(blob) {
  // Here you will send 'blob' to your Flask backend and then to Whisper.
  // Example (later):
  // const formData = new FormData();
  // formData.append("audio", blob, "answer.webm");
  // fetch("/api/submit_answer_audio", { method: "POST", body: formData });

  console.log("Recorded answer blob:", blob);

  answerLogBody.innerText =
    "Audio answer recorded (" +
    blob.size +
    " bytes). This is where the transcription and feedback will appear.";

  // Show thinking expression for a moment, then back to neutral
  setBaseExpression("think");
  setTimeout(() => {
    setBaseExpression("neutral");
    recordingText.innerText = "Not recording";
  }, 1200);
}

// Hook up buttons for recording
startRecordBtn.addEventListener("click", () => {
  startRecording();
});

stopRecordBtn.addEventListener("click", () => {
  stopRecording();
});
