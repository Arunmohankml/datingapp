var myPeerId = null;
var peer = null;
var myMediaStream = null;
var connectedPeers = [];
var audioContext = null;
var gainNode = null;
var activeCalls = new Map();
var mediaReady = false;

function enableMedia() {
    if (mediaReady && myMediaStream) return Promise.resolve();
    return navigator.mediaDevices.getUserMedia({ audio: true }).then(function(stream) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        var source = audioContext.createMediaStreamSource(stream);
        gainNode = audioContext.createGain();
        gainNode.gain.value = 1.0;
        source.connect(gainNode);
        var dest = audioContext.createMediaStreamDestination();
        gainNode.connect(dest);
        myMediaStream = dest.stream;
        mediaReady = true;
    }).catch(function(err) {
        console.log("PW mic error:", err);
        mediaReady = false;
    });
}

function cleanSession() {
    activeCalls.forEach(function(c) { try { c.close(); } catch(e) {} });
    activeCalls.clear();
    connectedPeers.forEach(function(u) { try { u.call.close(); } catch(e) {} });
    connectedPeers = [];
    if (peer) { try { peer.destroy(); } catch(e) {} peer = null; }
    if (audioContext) { try { audioContext.close(); } catch(e) {} audioContext = null; }
    if (myMediaStream) {
        try { myMediaStream.getTracks().forEach(function(t){t.stop()}); } catch(e) {}
        myMediaStream = null;
    }
    document.querySelectorAll('audio').forEach(function(el) {
        if (el.srcObject) { try { el.srcObject.getTracks().forEach(function(t){t.stop()}); } catch(e) {} }
        el.remove();
    });
    myPeerId = null;
    gainNode = null;
    mediaReady = false;
}

function connectToServer(mid) {
    cleanSession();
    if (!mid) { console.log("PW: empty id"); return; }
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
    peer.on('open', function(id) { myPeerId = id; console.log("PW peer open:", id); });
    peer.on('call', function(call) {
        var pid = call.peer;
        if (activeCalls.has(pid)) { console.log("PW reject dup inbound", pid); call.close(); return; }
        activeCalls.set(pid, call);
        enableMedia().then(function() {
            call.answer(myMediaStream);
            call.on('stream', function(stream) {
                connectPeer(pid, call, stream);
            });
        });
        call.on('close', function() {
            activeCalls.delete(pid);
            disconnectPeer(pid);
        });
        call.on('error', function(err) {
            console.log("PW inbound err", pid, err);
            activeCalls.delete(pid);
            disconnectPeer(pid);
        });
    });
}

function callPeer(pid) {
    if (!peer) return console.log("PW: no peer");
    var key = String(pid);
    if (activeCalls.has(key)) { console.log("PW block dup call", key); return; }
    enableMedia().then(function() {
        var call = peer.call(pid, myMediaStream);
        if (!call) return;
        activeCalls.set(key, call);
        call.on('stream', function(stream) {
            connectPeer(key, call, stream);
        });
        call.on('close', function() {
            activeCalls.delete(key);
            disconnectPeer(key);
        });
        call.on('error', function(err) {
            console.log("PW outbound err", key, err);
            activeCalls.delete(key);
            disconnectPeer(key);
        });
    });
}

function connectPeer(id, call, stream) {
    if (document.getElementById(id + "-audio")) return;
    var el = document.createElement('audio');
    el.srcObject = stream;
    el.id = id + "-audio";
    el.autoplay = true;
    document.body.appendChild(el);
    connectedPeers.push({ peer_id: id, call: call });
}

function disconnectPeer(id) {
    connectedPeers = connectedPeers.filter(function(p) { return p.peer_id !== id; });
    var el = document.getElementById(id + "-audio");
    if (el) { try { el.pause(); el.srcObject = null; } catch(e) {} el.remove(); }
}

function setUserVolume(id, value) {
    var el = document.getElementById(id + "-audio");
    if (el) el.volume = value;
}

function setMyVolume(value) {
    if (gainNode) gainNode.gain.value = value;
}

function getAllUsers() {
    return connectedPeers;
}

window.PW = {
    connectToVoice: connectToServer,
    callUser: callPeer,
    setUserVolume: setUserVolume,
    setMyVolume: setMyVolume,
    getConnectedUsers: getAllUsers,
    getMediaStream: function() { return myMediaStream; },
    peer: null,
    disconnectAll: cleanSession
};
