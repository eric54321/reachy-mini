const connectionSelect = document.getElementById("connection-select");
const voiceSelect = document.getElementById("voice-select");
const volumeSlider = document.getElementById("volume-slider");
const volumeValue = document.getElementById("volume-value");
const idlePanel = document.getElementById("idle-panel");
const gamePanel = document.getElementById("game-panel");
const timerInput = document.getElementById("timer-input");
const roundsInput = document.getElementById("rounds-input");
const startBtn = document.getElementById("start-btn");
const confirmBtn = document.getElementById("confirm-btn");
const resetBtn = document.getElementById("reset-btn");
const roundNumberEl = document.getElementById("round-number");
const maxRoundsEl = document.getElementById("max-rounds");
const scoreEl = document.getElementById("score");
const countdownEl = document.getElementById("countdown");
const resultBanner = document.getElementById("result-banner");
const status = document.getElementById("status");

const RESULT_MESSAGES = {
    success: "Nice one! ✅",
    survived_trick: "Whew, good catch! 😌",
    gotcha: "Gotcha! 🎉",
};

async function postJSON(path, body) {
    const resp = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    return resp.json();
}

async function loadConnection() {
    try {
        const resp = await fetch("/connection");
        if (!resp.ok) {
            // Only fired once at page load, unlike the /state poll loop —
            // if this lands during the startup/reconnect window (before
            // routes are registered), it must retry itself, or the
            // dropdown is stuck showing the wrong mode forever.
            setTimeout(loadConnection, 500);
            return;
        }
        const data = await resp.json();
        connectionSelect.value = data.mode;
    } catch (e) {
        setTimeout(loadConnection, 500);
    }
}

async function setConnection(mode) {
    try {
        const data = await postJSON("/connection", { mode });
        if (data.error) {
            status.textContent = data.error;
        } else if (data.restarting) {
            // The app is reconnecting to the other target under the hood
            // (see main.py's /connection route) — polling below recovers
            // on its own once the new instance is back up on this port.
            const label = mode === "sim" ? "simulator" : "physical robot";
            status.textContent = `Switching to ${label}... reconnecting.`;
        }
    } catch (e) {
        status.textContent = "Backend error switching connection.";
    }
}

async function loadVoices() {
    try {
        const resp = await fetch("/voices");
        if (!resp.ok) {
            setTimeout(loadVoices, 500); // see loadConnection() for why this retries
            return;
        }
        const data = await resp.json();
        voiceSelect.innerHTML = "";
        for (const voiceId of data.voices) {
            const opt = document.createElement("option");
            opt.value = voiceId;
            opt.textContent = voiceId;
            if (voiceId === data.current) opt.selected = true;
            voiceSelect.appendChild(opt);
        }
    } catch (e) {
        setTimeout(loadVoices, 500);
    }
}

async function setVoice(voiceId) {
    try {
        const data = await postJSON("/voice", { voice_id: voiceId });
        status.textContent = data.error ? data.error : `Voice set to ${data.current}.`;
    } catch (e) {
        status.textContent = "Backend error setting voice.";
    }
}

async function loadVolume() {
    try {
        const resp = await fetch("/volume");
        if (!resp.ok) {
            setTimeout(loadVolume, 500); // see loadConnection() for why this retries
            return;
        }
        const data = await resp.json();
        if (data.error) return; // e.g. no daemon volume API reachable — leave the slider as-is
        volumeSlider.value = data.volume;
        volumeValue.textContent = data.volume;
    } catch (e) {
        setTimeout(loadVolume, 500);
    }
}

let volumeDebounceTimer = null;
function setVolume(volume) {
    volumeValue.textContent = volume;
    clearTimeout(volumeDebounceTimer);
    volumeDebounceTimer = setTimeout(async () => {
        try {
            const data = await postJSON("/volume", { volume: Number(volume) });
            status.textContent = data.error ? data.error : `Volume set to ${data.volume}.`;
        } catch (e) {
            status.textContent = "Backend error setting volume.";
        }
    }, 300);
}

async function startGame() {
    const timerSeconds = Number(timerInput.value);
    const maxRounds = Number(roundsInput.value);
    const configResp = await postJSON("/config", { timer_seconds: timerSeconds, max_rounds: maxRounds });
    if (configResp.error) {
        status.textContent = configResp.error;
        return;
    }
    const startResp = await postJSON("/start");
    status.textContent = startResp.error || "Game started!";
}

async function confirmAction() {
    confirmBtn.disabled = true; // avoid double-submits while the request is in flight
    await postJSON("/confirm");
}

async function resetGame() {
    await postJSON("/reset");
    resultBanner.hidden = true;
    status.textContent = "Reset.";
}

function renderIdle() {
    idlePanel.hidden = false;
    gamePanel.hidden = true;
}

function renderGame(state) {
    idlePanel.hidden = true;
    gamePanel.hidden = false;
    roundNumberEl.textContent = state.round_number;
    maxRoundsEl.textContent = state.max_rounds;
    scoreEl.textContent = state.score;
    countdownEl.textContent = state.status === "waiting" ? Math.ceil(state.time_remaining) : "–";
    confirmBtn.disabled = state.status !== "waiting";
}

function renderResultBanner(state) {
    if (state.status === "result") {
        resultBanner.hidden = false;
        resultBanner.textContent = RESULT_MESSAGES[state.last_result] || "";
    } else if (state.status === "game_over") {
        resultBanner.hidden = false;
        resultBanner.textContent = state.won
            ? `You won! Survived all ${state.max_rounds} rounds. 🏆`
            : `Game over — caught after ${state.score} round(s).`;
    } else {
        resultBanner.hidden = true;
    }
}

async function pollState() {
    try {
        const resp = await fetch("/state");
        if (!resp.ok) {
            // Briefly 404s right after startup/reconnect, before run() has
            // registered routes — a real response, just not game state yet
            // (its JSON body has no `status` field, so rendering it as one
            // would show "undefined" everywhere). Treat it as "still
            // connecting" and let the next poll retry.
            status.textContent = "Connecting...";
            return;
        }
        const state = await resp.json();

        if (state.status === "idle" || state.status === "game_over") {
            renderIdle();
        } else {
            renderGame(state);
        }
        renderResultBanner(state);

        if (state.status === "game_over") {
            startBtn.textContent = "Play Again";
        }
        status.textContent = "";
    } catch (e) {
        status.textContent = "Backend error loading game state.";
    }
}

connectionSelect.addEventListener("change", (e) => setConnection(e.target.value));
voiceSelect.addEventListener("change", (e) => setVoice(e.target.value));
volumeSlider.addEventListener("input", (e) => setVolume(e.target.value));
startBtn.addEventListener("click", startGame);
confirmBtn.addEventListener("click", confirmAction);
resetBtn.addEventListener("click", resetGame);

loadConnection();
loadVoices();
loadVolume();
pollState();
setInterval(pollState, 300);
