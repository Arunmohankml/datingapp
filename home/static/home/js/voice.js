let myPeerId = null;
let peer = null;
let myMediaStream = null;
let connectedPeers = [];
let audioContext = null;
let gainNode = null;
let activeCalls = new Map();
let mediaReady = false;

function removeAllAudio() {
    document.querySelectorAll('audio').forEach(function(el) {
        if (el.srcObject) {
            try { el.srcObject.getTracks().forEach(function(t){t.stop()}); } catch(e) {}
        }
        el.remove();
    });
}

function cleanSession() {
    activeCalls.forEach(function(call) { try { call.close(); } catch(e) {} });
    activeCalls.clear();
    connectedPeers.forEach(function(u){ try { u.call.close(); } catch(e) {} });
    connectedPeers = [];
    if (peer) { try { peer.destroy(); } catch(e) {} peer = null; }
    if (audioContext) { try { audioContext.close(); } catch(e) {} audioContext = null; }
    if (myMediaStream) {
        try { myMediaStream.getTracks().forEach(function(t){t.stop()}); } catch(e) {}
        myMediaStream = null;
    }
    removeAllAudio();
    myPeerId = null;
    gainNode = null;
    mediaReady = false;
}

async function initMedia() {
    if (mediaReady && myMediaStream) return;
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioContext.createMediaStreamSource(stream);
        gainNode = audioContext.createGain();
        gainNode.gain.value = 1.0;
        source.connect(gainNode);
        const destination = audioContext.createMediaStreamDestination();
        gainNode.connect(destination);
        myMediaStream = destination.stream;
        mediaReady = true;
    } catch (err) {
        console.log("Error accessing microphone:", err);
    }
}

function connectToServer(mid) {
    cleanSession();
    if (mid === "") {
        console.log("Input is empty");
        return;
    }
    peer = new Peer(mid, {
        config: {
            iceServers: [
                { urls: "stun:stun.relay.metered.ca:80" },
                { urls: "turn:global.relay.metered.ca:80", username: "42c77072861dbb07cf20ec03", credential: "CnxHreDWSoBxZUev" },
                { urls: "turn:global.relay.metered.ca:80?transport=tcp", username: "42c77072861dbb07cf20ec03", credential: "CnxHreDWSoBxZUev" },
                { urls: "turn:global.relay.metered.ca:443", username: "42c77072861dbb07cf20ec03", credential: "CnxHreDWSoBxZUev" },
                { urls: "turns:global.relay.metered.ca:443?transport=tcp", username: "42c77072861dbb07cf20ec03", credential: "CnxHreDWSoBxZUev" }
            ]
        },
        debug: 3
    });
    window.PW.peer = peer;

    peer.on('open', function (id) {
        myPeerId = id;
        console.log("Your peer id is " + id);
    });

    peer.on('call', async function (call) {
        var pid = call.peer;
        if (activeCalls.has(pid)) {
            console.log("DUPLICATE INCOMING CALL REJECTED from " + pid);
            call.close();
            return;
        }
        console.log("Got call from " + pid);
        activeCalls.set(pid, call);
        await initMedia();
        call.answer(myMediaStream);

        call.on('stream', function (stream) {
            updList(pid, call, "add");
            if (document.getElementById(pid + "-audio")) return;
            var el = document.createElement('audio');
            el.srcObject = stream;
            el.id = pid + "-audio";
            el.autoplay = true;
            document.body.appendChild(el);
        });

        call.on('close', function () {
            activeCalls.delete(pid);
            updList(pid, call, "remove");
            var el = document.getElementById(pid + "-audio");
            if (el) { try { el.pause(); el.srcObject = null; } catch(e) {} el.remove(); }
            console.log("INCOMING CALL CLOSED with " + pid);
        });

        call.on('error', function (err) {
            console.log("INCOMING CALL ERROR " + pid + ": " + err);
            activeCalls.delete(pid);
        });
    });
}

async function callPeer(pid) {
    if (!peer) return console.log("not connected to server");
    var key = String(pid);
    if (activeCalls.has(key)) {
        console.log("DUPLICATE CALL BLOCKED to " + key);
        return;
    }
    await initMedia();
    var call = peer.call(pid, myMediaStream);
    activeCalls.set(key, call);

    call.on('stream', function (stream) {
        console.log("Connected with " + key);
        updList(key, call, "add");
        if (document.getElementById(key + "-audio")) return;
        var el = document.createElement('audio');
        el.srcObject = stream;
        el.id = key + "-audio";
        el.autoplay = true;
        document.body.appendChild(el);
    });

    call.on('iceStateChanged', function () {});
    call.on('error', function (err) {
        console.log("CALL ERROR " + key + ": " + err);
        activeCalls.delete(key);
    });
    call.on('close', function () {
        activeCalls.delete(key);
        updList(key, call, "remove");
        var el = document.getElementById(key + "-audio");
        if (el) { try { el.pause(); el.srcObject = null; } catch(e) {} el.remove(); }
        console.log("CALL CLOSED " + key);
    });
}

function updList(id, call, type) {
    if (type === "add") {
        connectedPeers.push({ peer_id: id, call: call });
    } else {
        connectedPeers = connectedPeers.filter(function(i) { return i.peer_id !== id; });
    }
}

function setUserVolume(id, value) {
    var el = document.getElementById(id + "-audio");
    if (el) el.volume = value;
}

function getAllUsers() {
    return connectedPeers;
}

function setMyVolume(value) {
    if (gainNode) gainNode.gain.value = value;
}

window.PW = {
    connectToVoice: connectToServer,
    callUser: callPeer,
    setUserVolume: setUserVolume,
    getConnectedUsers: getAllUsers,
    setMyVolume: setMyVolume,
    getMediaStream: function() { return myMediaStream; },
    peer: null,
    disconnectAll: cleanSession
};
