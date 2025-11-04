// static/script.js

document.addEventListener("DOMContentLoaded", () => {
    // 1) CHANGE QUESTION BUTTON ON INDEX PAGE
    const changeBtn = document.getElementById("change-question-btn");

    if (changeBtn) {
        changeBtn.addEventListener("click", async () => {
            changeBtn.disabled = true;
            const originalText = changeBtn.textContent;
            changeBtn.textContent = "Loading...";

            try {
                const response = await fetch("/next_question", {
                    method: "POST"
                });

                if (!response.ok) {
                    throw new Error("Failed to fetch new question");
                }

                const data = await response.json();
                if (data.error) {
                    throw new Error(data.error);
                }

                // Update question text
                const questionTextEl = document.getElementById("question-text");
                if (questionTextEl) {
                    questionTextEl.textContent = data.question;
                }

                // Update hidden field for text answer
                const textQuestionInput = document.querySelector('input[name="question_id"]');
                if (textQuestionInput) {
                    textQuestionInput.value = data.id;
                }

                // Update hidden field for voice answer (index page)
                const voiceQuestionInput = document.getElementById("question-id");
                if (voiceQuestionInput) {
                    voiceQuestionInput.value = data.id;
                }

                // Clear previous feedback from index page if needed
                const transcriptEl = document.getElementById("transcript");
                const relScoreEl = document.getElementById("rel-score");
                const confScoreEl = document.getElementById("conf-score");
                const finalScoreEl = document.getElementById("final-score");
                const feedbackTextEl = document.getElementById("feedback-text");

                if (transcriptEl) transcriptEl.textContent = "";
                if (relScoreEl) relScoreEl.textContent = "";
                if (confScoreEl) confScoreEl.textContent = "";
                if (finalScoreEl) finalScoreEl.textContent = "";
                if (feedbackTextEl) feedbackTextEl.textContent = "";

            } catch (err) {
                console.error(err);
                alert("Could not load a new question. Please try again.");
            } finally {
                changeBtn.disabled = false;
                changeBtn.textContent = originalText;
            }
        });
    }

    // 2) AUDIO RECORDING COMMON LOGIC
    let mediaRecorder = null;
    let audioChunks = [];
    let currentRecordingContext = null;

    async function startRecording(context) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            currentRecordingContext = context;

            mediaRecorder.addEventListener("dataavailable", event => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            });

            mediaRecorder.addEventListener("stop", () => {
                const blob = new Blob(audioChunks, { type: "audio/webm" });
                sendAudio(blob, currentRecordingContext);
            });

            mediaRecorder.start();

            if (context.statusEl) {
                context.statusEl.textContent = "Recording...";
            }
            if (context.startBtn) {
                context.startBtn.disabled = true;
            }
            if (context.stopBtn) {
                context.stopBtn.disabled = false;
            }

        } catch (err) {
            console.error(err);
            if (context.statusEl) {
                context.statusEl.textContent = "Error accessing microphone.";
            }
        }
    }

    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state !== "inactive") {
            mediaRecorder.stop();
            if (currentRecordingContext && currentRecordingContext.statusEl) {
                currentRecordingContext.statusEl.textContent = "Processing audio...";
            }
            if (currentRecordingContext && currentRecordingContext.startBtn) {
                currentRecordingContext.startBtn.disabled = false;
            }
            if (currentRecordingContext && currentRecordingContext.stopBtn) {
                currentRecordingContext.stopBtn.disabled = true;
            }
        }
    }

    async function sendAudio(blob, context) {
        try {
            const formData = new FormData();
            formData.append("audio", blob, "answer.webm");

            // Extra fields: question_id or job_id + question_index
            if (context.extraFields) {
                Object.entries(context.extraFields).forEach(([key, value]) => {
                    formData.append(key, value);
                });
            }

            const response = await fetch(context.endpoint, {
                method: "POST",
                body: formData
            });

            const data = await response.json();

            if (!response.ok || data.error) {
                throw new Error(data.error || "Unknown error");
            }

            if (context.statusEl) {
                context.statusEl.textContent = "Audio processed.";
            }

            // Update feedback UI in the right place
            if (context.transcriptEl) {
                context.transcriptEl.textContent = data.transcript || "";
            }
            if (context.relScoreEl) {
                context.relScoreEl.textContent = data.relevance_score ?? "";
            }
            if (context.confScoreEl) {
                context.confScoreEl.textContent = data.confidence_score ?? "";
            }
            if (context.finalScoreEl) {
                context.finalScoreEl.textContent = data.final_score ?? "";
            }
            if (context.feedbackTextEl) {
                context.feedbackTextEl.textContent = data.feedback_text || "";
            }

        } catch (err) {
            console.error(err);
            if (context.statusEl) {
                context.statusEl.textContent = "Error processing audio.";
            }
            alert("Error processing audio: " + err.message);
        } finally {
            currentRecordingContext = null;
        }
    }

    // 3) HOOK FOR INDEX PAGE (generic practice)
    const indexStartBtn = document.getElementById("start-recording");
    const indexStopBtn = document.getElementById("stop-recording");
    const indexStatusEl = document.getElementById("audio-status");

    if (indexStartBtn && indexStopBtn) {
        indexStartBtn.addEventListener("click", () => {
            const questionIdInput = document.getElementById("question-id");
            const questionId = questionIdInput ? questionIdInput.value : "";

            const context = {
                endpoint: "/audio",
                extraFields: {
                    question_id: questionId
                },
                startBtn: indexStartBtn,
                stopBtn: indexStopBtn,
                statusEl: indexStatusEl,
                transcriptEl: document.getElementById("transcript"),
                relScoreEl: document.getElementById("rel-score"),
                confScoreEl: document.getElementById("conf-score"),
                finalScoreEl: document.getElementById("final-score"),
                feedbackTextEl: document.getElementById("feedback-text")
            };

            startRecording(context);
        });

        indexStopBtn.addEventListener("click", () => {
            stopRecording();
        });
    }

    // 4) HOOK FOR JOB DETAIL PAGE (per question recording)
    const jobBlocks = document.querySelectorAll(".question-block[data-job-id]");

    jobBlocks.forEach(block => {
        const jobId = block.getAttribute("data-job-id");
        const questionIndex = block.getAttribute("data-question-index");

        const startBtn = block.querySelector(".job-start-recording");
        const stopBtn = block.querySelector(".job-stop-recording");
        const statusEl = block.querySelector(".job-audio-status");

        const transcriptEl = block.querySelector(".job-transcript");
        const relScoreEl = block.querySelector(".job-rel-score");
        const confScoreEl = block.querySelector(".job-conf-score");
        const finalScoreEl = block.querySelector(".job-final-score");
        const feedbackTextEl = block.querySelector(".job-feedback-text");

        if (!startBtn || !stopBtn) {
            return;
        }

        startBtn.addEventListener("click", () => {
            const context = {
                endpoint: "/job_audio",
                extraFields: {
                    job_id: jobId,
                    question_index: questionIndex
                },
                startBtn,
                stopBtn,
                statusEl,
                transcriptEl,
                relScoreEl,
                confScoreEl,
                finalScoreEl,
                feedbackTextEl
            };

            startRecording(context);
        });

        stopBtn.addEventListener("click", () => {
            stopRecording();
        });
    });
});
