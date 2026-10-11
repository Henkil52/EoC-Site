(function () {
    "use strict";

    var box = document.getElementById("factionChatMessages");
    if (!box) return;

    var factionId = box.getAttribute("data-faction-id");
    var input = document.getElementById("factionChatInput");
    var sendBtn = document.getElementById("factionChatSend");
    var lastId = 0;


    function emojiTokens(s) {
        return s.replace(/\[emoji:([a-zA-Z0-9_.\-]+\.gif)\]/g, function (m, name) {
            return '<img class="emoji-img" src="/static/emoji/' + name + '" alt="">';
        });
    }

    function esc(s) {
        var d = document.createElement("div");
        d.textContent = (s == null ? "" : String(s));
        return d.innerHTML;
    }

    function avatarHtml(item, size) {
        if (item.avatar) {
            return '<img class="chat-avatar" style="width:' + size + 'px;height:' + size + 'px" src="' + esc(item.avatar) + '" alt="">';
        }
        var letter = esc((item.nickname || "?").charAt(0).toUpperCase());
        return '<div class="chat-avatar chat-avatar-fallback" style="width:' + size + 'px;height:' + size + 'px">' + letter + '</div>';
    }

    function roleClass(m) {
        if (m.role === "admin") return " chat-msg-admin";
        if (m.role === "vip") return " chat-msg-vip";
        return "";
    }

    function msgHtml(m) {
        var href = "/view/" + encodeURIComponent(m.author);
        return '<div class="chat-msg' + (m.own ? " own" : "") + '">' +
            '<a class="chat-profile-link" href="' + href + '">' + avatarHtml(m, 32) + '</a>' +
            '<div class="chat-msg-body' + roleClass(m) + '">' +
            '<div class="chat-msg-head"><a class="chat-nick chat-profile-link" href="' + href + '">' + esc(m.nickname) + '</a>' +
            '<span class="chat-time">' + esc(m.time) + '</span></div>' +
            '<div class="chat-text">' + emojiTokens(esc(m.text)) + '</div>' +
            '</div></div>';
    }

    function clearEmpty() {
        var e = box.querySelector(".chat-empty");
        if (e) e.remove();
    }

    function load() {
        fetch("/groups/api/chat/" + factionId + "?since_id=" + lastId)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data || !data.messages || !data.messages.length) return;
                clearEmpty();
                data.messages.forEach(function (m) {
                    lastId = Math.max(lastId, m.id);
                    box.insertAdjacentHTML("beforeend", msgHtml(m));
                });
                box.scrollTop = box.scrollHeight;
            })
            .catch(function () {});
    }

    function send() {
        var text = input.value.trim();
        if (!text) return;
        input.value = "";
        fetch("/groups/api/chat/" + factionId, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: text })
        }).then(function (r) { return r.json(); }).then(function (data) {
            if (data && data.message) {
                clearEmpty();
                lastId = Math.max(lastId, data.message.id);
                box.insertAdjacentHTML("beforeend", msgHtml(data.message));
                box.scrollTop = box.scrollHeight;
            }
        }).catch(function () {});
    }

    sendBtn.onclick = send;
    input.addEventListener("keydown", function (e) {
        if (e.key === "Enter") send();
    });

    setInterval(load, 3000);
    load();
})();
