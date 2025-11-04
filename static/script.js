// Simple audio recording script for Chrome using MediaRecorder
// It records audio, then sends it as multipart/form-data to /audio

let mediaRecorder = null;
let recordedChunks = [];

async function startRecording() {
    const statusEl = document.getElementById("audio-status");
    statusEl.textContent = "Requesting microphone access...";
    recordedChunks = [];

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);

        mediaRecorder.ondataavailable = function (e) {
            if (e.data.size > 0) {
                recordedChunks.push(e.data);
            }
        };

        mediaRecorder.onstop = function () {
            const blob = new Blob(recordedChunks, { type: "audio/webm" });
            sendAudio(blob);
            stream.getTracks().forEach(track => track.stop());
        };

        mediaRecorder.start();
        statusEl.textContent = "Recording... speak now.";
        document.getElementById("start-recording").disabled = true;
        document.getElementById("stop-recording").disabled = false;
    } catch (err) {
        console.error("Error accessing microphone:", err);
        statusEl.textContent = "Error accessing microphone: " + err.message;
    }
}

function stopRecording() {
    const statusEl = document.getElementById("audio-status");
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
        statusEl.textContent = "Stopping recording and sending audio...";
        document.getElementById("start-recording").disabled = false;
        document.getElementById("stop-recording").disabled = true;
    }
}

function sendAudio(blob) {
    const statusEl = document.getElementById("audio-status");
    const questionId = document.getElementById("question-id").value;

    const formData = new FormData();
    formData.append("audio", blob, "answer.webm");
    formData.append("question_id", questionId);

    fetch("/audio", {
        method: "POST",
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                statusEl.textContent = "Error: " + data.error;
                return;
            }
            statusEl.textContent = "Transcription and evaluation complete.";

            const feedbackDiv = document.getElementById("feedback");
            document.getElementById("transcript").textContent = data.transcript || "";
            document.getElementById("rel-score").textContent = data.relevance_score;
            document.getElementById("conf-score").textContent = data.confidence_score;
            document.getElementById("final-score").textContent = data.final_score;
            document.getElementById("feedback-text").textContent = data.feedback_text;

            feedbackDiv.style.display = "block";
        })
        .catch(err => {
            console.error("Error sending audio:", err);
            statusEl.textContent = "Error sending audio: " + err.message;
        });
}

window.addEventListener("DOMContentLoaded", function () {
    const startBtn = document.getElementById("start-recording");
    const stopBtn = document.getElementById("stop-recording");

    if (startBtn && stopBtn) {
        startBtn.addEventListener("click", startRecording);
        stopBtn.addEventListener("click", stopRecording);
    }
});
