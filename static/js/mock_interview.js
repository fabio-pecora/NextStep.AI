const avatar = document.getElementById("ai-avatar");
const aiAudio = document.getElementById("ai-audio");
const aiText = document.getElementById("ai-text");
const startInterviewBtn = document.getElementById("start-interview-btn");
const repeatQuestionBtn = document.getElementById("repeat-question-btn");

const userVideo = document.getElementById("user-video");
const userPlaceholder = document.getElementById("user-placeholder");
const cameraStatusDot = document.getElementById("camera-status-dot");

const startRecordBtn = document.getElementById("start-record-btn");
const stopRecordBtn = document.getElementById("stop-record-btn");
const recordingDot = document.getElementById("recording-dot");
const recordingText = document.getElementById("recording-text");
const answerLogBody = document.getElementById("answer-log-body");

let mouthTimer = null;
let mouthOpen = false;

let mediaRecorder = null;
let recordedChunks = [];
let isRecording = false;

// ---------------------------
// AI mouth animation
// ---------------------------

function startMouthAnimation() {
  if (mouthTimer) return;
  mouthTimer = setInterval(() => {
    mouthOpen = !mouthOpen;
    avatar.src = mouthOpen
      ? avatar.dataset.openSrc || avatar.src.replace("avatar_closed", "avatar_open")
      : avatar.dataset.closedSrc || avatar.src.replace("avatar_open", "avatar_closed");
  }, 130);
}

function stopMouthAnimation() {
  clearInterval(mouthTimer);
  mouthTimer = null;
  mouthOpen = false;
  if (avatar.dataset.closedSrc) {
    avatar.src = avatar.dataset.closedSrc;
  } else {
    avatar.src = avatar.src.replace("avatar_open", "avatar_closed");
  }
}

// You can explicitly set these if you want
avatar.dataset.closedSrc = avatar.getAttribute("src");
avatar.dataset.openSrc = avatar.dataset.closedSrc.replace("avatar_closed", "avatar_open");

aiAudio.addEventListener("play", startMouthAnimation);
aiAudio.addEventListener("ended", stopMouthAnimation);
aiAudio.addEventListener("pause", stopMouthAnimation);

// ---------------------------
// Camera handling
// ---------------------------

async function initCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
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

// Initialize camera when page loads
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

  // In the future this will call your backend
  const firstQuestion = "Welcome to your mock interview. To start, can you tell me about yourself?";
  await playAIQuestion(firstQuestion);

  repeatQuestionBtn.disabled = false;
});

repeatQuestionBtn.addEventListener("click", async () => {
  await playAIQuestion(aiText.innerText);
});

async function playAIQuestion(text) {
  aiText.innerText = text;

  // Later: POST to /api/generate_tts and set aiAudio.src to the returned URL
  // For now we just play a test sound if you have one, otherwise this will do nothing.
  // Example:
  // aiAudio.src = "/static/audio/example_beep.mp3";
  // aiAudio.play();

  // If you have no audio yet, at least simulate speaking
  startMouthAnimation();
  setTimeout(() => {
    stopMouthAnimation();
  }, 1800);
}

// ---------------------------
// Audio recording of candidate
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

      // stop all tracks from the stream
      stream.getTracks().forEach(track => track.stop());
    };

    mediaRecorder.start();

    isRecording = true;
    startRecordBtn.disabled = true;
    stopRecordBtn.disabled = false;

    recordingDot.classList.add("is-recording");
    recordingText.innerText = "Recording answer...";
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
  // Here you will send the audio blob to your Flask backend
  // For example:
  // const formData = new FormData();
  // formData.append("audio", blob, "answer.webm");
  // fetch("/api/submit_answer_audio", { method: "POST", body: formData });

  console.log("Recorded answer blob:", blob);

  const seconds = (blob.size / 16000).toFixed(1); // rough fake estimate
  answerLogBody.innerText =
    "Audio answer recorded and ready to send to the backend. Size: " +
    blob.size +
    " bytes. This is where the transcription and feedback will appear.";
  recordingText.innerText = "Not recording";
}

// Hook up buttons

startRecordBtn.addEventListener("click", () => {
  startRecording();
});

stopRecordBtn.addEventListener("click", () => {
  stopRecording();
});
