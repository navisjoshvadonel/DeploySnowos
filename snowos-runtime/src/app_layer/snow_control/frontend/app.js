document.addEventListener("DOMContentLoaded", () => {
    const seenInsights = new Set();

    function appendChatMessage(message, kind = "ai", key = null) {
        if (key && seenInsights.has(key)) {
            return;
        }
        if (key) {
            seenInsights.add(key);
        }

        const chat = document.querySelector(".chat-window");
        const entry = document.createElement("div");
        entry.className = `chat-message ${kind}`;
        entry.textContent = message;
        chat.appendChild(entry);
        chat.scrollTop = chat.scrollHeight;
    }

    async function fetchJson(path) {
        const response = await fetch(path);
        if (!response.ok) {
            throw new Error(`Request failed for ${path}`);
        }
        return response.json();
    }

    function renderSystemState(data) {
        document.getElementById("cpu-val").innerText = data.cpu;
        document.getElementById("ram-val").innerText = data.ram;
        document.getElementById("agents-val").innerText = data.agents_active;
        document.getElementById("profile-val").innerText = data.boot_profile;
        document.getElementById("trust-val").innerText = `${data.trust_score}%`;
    }

    function renderBootStatus(data) {
        document.getElementById("boot-profile").innerText = data.profile;
        document.getElementById("boot-state").innerText = data.status;
        document.getElementById("persona-val").innerText = data.identity?.persona || "--";
        document.getElementById("mood-val").innerText = data.identity?.mood || "--";
        document.getElementById("scene-val").innerText = data.identity?.scene || "--";
        document.getElementById("status-val").innerText = data.status;
        document.getElementById("boot-duration-val").innerText = `${data.boot_duration_ms || 0} ms`;
        document.getElementById("boot-node").innerText = `snowos.boot :: ${data.profile}`;
        document.getElementById("persona-node").innerText = data.identity?.persona || "nyx persona";

        const tagline = data.brand?.platform_tagline || "Central intelligence for the SnowOS boot plane";
        document.getElementById("brand-tagline").innerText = tagline;

        appendChatMessage(
            `Boot profile ${data.profile} came up ${data.status} with persona ${data.identity?.persona || "Guide"}.`,
            "ai",
            `boot-${data.profile}-${data.status}`
        );

        if (Array.isArray(data.warnings)) {
            data.warnings.forEach((warning, index) => {
                appendChatMessage(`Warning: ${warning}`, "warning", `warning-${index}-${warning}`);
            });
        }
    }

    function renderFeatures(data) {
        const container = document.getElementById("feature-flags");
        container.innerHTML = "";
        document.getElementById("feature-count-val").innerText = `${data.enabled_count} active`;

        data.enabled.forEach((feature) => {
            const card = document.createElement("div");
            card.className = "feature-chip";
            card.innerHTML = `
                <span>${feature.category}</span>
                <strong>${feature.name}</strong>
                <p>${feature.summary}</p>
            `;
            container.appendChild(card);
        });

        const highlighted = data.enabled.slice(0, 3).map((feature) => feature.name).join(", ");
        if (highlighted) {
            appendChatMessage(
                `AI feature set active: ${highlighted}.`,
                "ai",
                `features-${data.profile}-${highlighted}`
            );
        }
    }

    function renderEvents(data) {
        const feed = document.getElementById("event-feed");
        feed.innerHTML = "";
        data.forEach((event) => {
            const item = document.createElement("div");
            item.className = `event ${event.status.toLowerCase()}`;
            item.innerHTML = `
                <div class="time">[${event.time}] ${event.type.toUpperCase()}</div>
                <div><strong>${event.source}</strong> :: <em>${event.action}</em> -> <b>${event.status}</b></div>
            `;
            feed.appendChild(item);
        });
    }

    async function refreshDashboard() {
        try {
            const [systemState, bootStatus, featureSet, events] = await Promise.all([
                fetchJson("/api/system_state"),
                fetchJson("/api/boot/status"),
                fetchJson("/api/ai/features"),
                fetchJson("/api/events"),
            ]);
            renderSystemState(systemState);
            renderBootStatus(bootStatus);
            renderFeatures(featureSet);
            renderEvents(events);
        } catch (error) {
            appendChatMessage("SnowControl backend is offline or still booting.", "warning", "backend-offline");
            console.error(error);
        }
    }

    setTimeout(() => {
        document.getElementById("intent-modal").classList.remove("hidden");
    }, 3000);

    document.querySelectorAll(".actions button").forEach((button) => {
        button.addEventListener("click", (event) => {
            document.getElementById("intent-modal").classList.add("hidden");
            appendChatMessage(`Operator selected: ${event.target.innerText}`, "user");
        });
    });

    refreshDashboard();
    setInterval(refreshDashboard, 5000);
});
