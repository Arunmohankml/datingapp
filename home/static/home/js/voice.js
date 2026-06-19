let myPeerId = null;
let peer = null;
let myMediaStream = null;
let connectedPeers = [];

let audioContext = null;
let gainNode = null;

let activeCalls = new Map();

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
}

async function getMedia() {
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
                {
                    urls: "turn:global.relay.metered.ca:80",
                    username: "42c77072861dbb07cf20ec03",
                    credential: "CnxHreDWSoBxZUev"
                },
                {
                    urls: "turn:global.relay.metered.ca:80?transport=tcp",
                    username: "42c77072861dbb07cf20ec03",
                    credential: "CnxHreDWSoBxZUev"
                },
                {
                    urls: "turn:global.relay.metered.ca:443",
                    username: "42c77072861dbb07cf20ec03",
                    credential: "CnxHreDWSoBxZUev"
                },
                {
                    urls: "turns:global.relay.metered.ca:443?transport=tcp",
                    username: "42c77072861dbb07cf20ec03",
                    credential: "CnxHreDWSoBxZUev"
                }
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
        await getMedia();
        call.answer(myMediaStream);

        call.on('stream', function (stream) {
            console.log("STREAM ATTACHED from " + pid);
            updList(pid, call, "add");

            if (document.getElementById(pid + "-audio")) {
                console.log("AUDIO ALREADY EXISTS for " + pid);
                return;
            }

            const audioElement = document.createElement('audio');
            audioElement.srcObject = stream;
            audioElement.id = pid + "-audio";
            audioElement.autoplay = true;
            document.body.appendChild(audioElement);
            console.log("AUDIO CREATED for " + pid);

            if (call.peerConnection) {
                call.peerConnection.addEventListener('icecandidate', event => {
                    if (event.candidate) {
                        const cand = event.candidate.candidate;
                        if (cand.includes('typ relay')) {
                            console.log('TURN relay candidate used:', cand);
                        } else if (cand.includes('typ srflx')) {
                            console.log('STUN (reflexive) candidate:', cand);
                        } else if (cand.includes('typ host')) {
                            console.log('Local host candidate:', cand);
                        }
                    }
                });
            }
        });
    });
}

async function callPeer(pid) {
    if (!peer) return console.log("havnt connected to server");

    var key = String(pid);
    if (activeCalls.has(key)) {
        console.log("DUPLICATE CALL BLOCKED to " + key);
        return;
    }

    await getMedia();
    const call = peer.call(pid, myMediaStream);
    activeCalls.set(key, call);
    console.log("CALL CREATED to " + key);

    call.on('stream', function (stream) {
        console.log("STREAM ATTACHED from " + key);
        updList(key, call, "add");

        if (document.getElementById(key + "-audio")) {
            console.log("AUDIO ALREADY EXISTS for " + key);
            return;
        }

        const audioElement = document.createElement('audio');
        audioElement.srcObject = stream;
        audioElement.id = key + "-audio";
        audioElement.autoplay = true;
        document.body.appendChild(audioElement);
        console.log("AUDIO CREATED for " + key);

        if (call.peerConnection) {
            call.peerConnection.addEventListener('icecandidate', event => {
                if (event.candidate) {
                    const cand = event.candidate.candidate;
                    if (cand.includes('typ relay')) {
                        console.log('TURN relay candidate used:', cand);
                    } else if (cand.includes('typ srflx')) {
                        console.log('STUN (reflexive) candidate:', cand);
                    } else if (cand.includes('typ host')) {
                        console.log('Local host candidate:', cand);
                    }
                }
            });
        }
    });

    call.on('iceStateChanged', () => {
        console.log("ICE connection state changed");
    });

    call.on('error', function (err) {
        console.log("Call error: " + err);
    });

    call.on('close', function () {
        activeCalls.delete(key);
        updList(key, call, "remove");
        var el = document.getElementById(key + "-audio");
        if (el) { try { el.pause(); el.srcObject = null; } catch(e) {} el.remove(); }
        console.log("CALL CLOSED with " + key);
    });

    console.log("Calling " + pid + "...");
}

function updList(id, call, type) {
    if (type === "add") {
        connectedPeers.push({ peer_id: id, call: call });
    } else {
        connectedPeers = connectedPeers.filter(i => i.peer_id !== call.peer);
    }
}

function setUserVolume(id, value) {
    const audio = document.getElementById(id + "-audio");
    if (audio) {
        audio.volume = value;
        console.log(id + " volume set to", value);
    }
}

function getAllUsers() {
    return connectedPeers;
}

function setMyVolume(value) {
    if (gainNode) {
        gainNode.gain.value = value;
    }
    if (myMediaStream) {
        myMediaStream.getAudioTracks().forEach(function(t) {
            t.enabled = value > 0;
        });
    }
}

window.PW = {
    connectToVoice: connectToServer,
    callUser: callPeer,
    setUserVolume: setUserVolume,
    getConnectedUsers: getAllUsers,
    setMyVolume: setMyVolume,
    peer: null,
    disconnectAll: cleanSession
};
