const voiceSelect = document.getElementById("voice-select");
const volumeSlider = document.getElementById("volume-slider");
const volumeValue = document.getElementById("volume-value");
const emotionSelect = document.getElementById("emotion-select");
const insertEmotionBtn = document.getElementById("insert-emotion-btn");
const messageInput = document.getElementById("message-input");
const sayBtn = document.getElementById("say-btn");
const status = document.getElementById("status");

async function loadVoices() {
    try {
        const resp = await fetch("/voices");
        const data = await resp.json();
        voiceSelect.innerHTML = "";
        for (const voiceId of data.voices) {
            const opt = document.createElement("option");
            opt.value = voiceId;
            opt.textContent = voiceId;
            if (voiceId === data.current) opt.selected = true;
            voiceSelect.appendChild(opt);
        }
        status.textContent = data.voices.length
            ? `${data.voices.length} voice(s) available.`
            : "No voices downloaded yet.";
    } catch (e) {
        status.textContent = "Backend error loading voices.";
    }
}

async function loadEmotions() {
    try {
        const resp = await fetch("/emotions");
        const data = await resp.json();
        emotionSelect.innerHTML = "";
        for (const emotion of data.emotions) {
            const opt = document.createElement("option");
            opt.value = emotion;
            opt.textContent = emotion;
            emotionSelect.appendChild(opt);
        }
    } catch (e) {
        console.error("Error loading emotions:", e);
    }
}

async function loadVolume() {
    try {
        const resp = await fetch("/volume");
        const data = await resp.json();
        if (data.error) {
            console.error(data.error);
            return;
        }
        volumeSlider.value = data.volume;
        volumeValue.textContent = data.volume;
    } catch (e) {
        console.error("Error loading volume:", e);
    }
}

async function setVoice(voiceId) {
    try {
        const resp = await fetch("/voice", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ voice_id: voiceId }),
        });
        const data = await resp.json();
        status.textContent = data.error ? data.error : `Voice set to ${data.current}.`;
    } catch (e) {
        status.textContent = "Backend error setting voice.";
    }
}

let volumeDebounceTimer = null;
function setVolume(volume) {
    volumeValue.textContent = volume;
    clearTimeout(volumeDebounceTimer);
    volumeDebounceTimer = setTimeout(async () => {
        try {
            const resp = await fetch("/volume", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ volume: Number(volume) }),
            });
            const data = await resp.json();
            status.textContent = data.error ? data.error : `Volume set to ${data.volume}.`;
        } catch (e) {
            status.textContent = "Backend error setting volume.";
        }
    }, 300);
}

function insertEmotionTag() {
    const tag = `[${emotionSelect.value}] `;
    const start = messageInput.selectionStart ?? messageInput.value.length;
    const end = messageInput.selectionEnd ?? messageInput.value.length;
    messageInput.value = messageInput.value.slice(0, start) + tag + messageInput.value.slice(end);
    const cursor = start + tag.length;
    messageInput.focus();
    messageInput.setSelectionRange(cursor, cursor);
}

async function sayMessage() {
    const text = messageInput.value.trim();
    if (!text) return;
    try {
        const resp = await fetch("/say", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text, voice_id: voiceSelect.value }),
        });
        const data = await resp.json();
        status.textContent = `Queued with voice "${data.voice_id}".`;
    } catch (e) {
        status.textContent = "Backend error sending message.";
    }
}

voiceSelect.addEventListener("change", (e) => setVoice(e.target.value));
volumeSlider.addEventListener("input", (e) => setVolume(e.target.value));
insertEmotionBtn.addEventListener("click", insertEmotionTag);
sayBtn.addEventListener("click", sayMessage);

loadVoices();
loadEmotions();
loadVolume();
