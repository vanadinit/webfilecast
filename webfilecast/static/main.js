window.socket = io.connect();

function websocketStatus() {
    let timeoutCounter = 0;
    const statusIndicator = document.getElementById('ws_status');
    const wsConnectStatus = setInterval(function () {
        if (window.socket.connected) {
            statusIndicator.innerHTML = '<span class="msg-success">Connected</span>';
            timeoutCounter = 0;
        } else {
            statusIndicator.innerHTML = `<span class="msg-error">Disconnected (${timeoutCounter})</span>`;
            timeoutCounter++;
        }
        if (timeoutCounter > 60) {
            statusIndicator.innerHTML = '<span class="msg-error">Disconnected (Please reload)</span>';
            clearInterval(wsConnectStatus);
        }
    }, 1000);
}

window.socket.on('movie_files', function (filelist) {
    console.log('Got movie file list');
    const fileListElem = document.getElementById('file_list');
    const fileListSelect = document.createElement('select');
    fileListSelect.addEventListener('change', function () {window.socket.emit('select_file', fileListSelect.value);});

    for (i = 0; i < filelist.length; i++) {
        var opt = document.createElement("option");
        opt.value = filelist[i][0];
        opt.innerHTML = filelist[i][1];
        fileListSelect.appendChild(opt);
    };

    fileListElem.innerHTML = '';
    fileListElem.appendChild(fileListSelect);
    window.socket.emit('select_file', fileListSelect.value);
})

window.socket.on('show_file_details', function (file_details) {
    const fileDetails = document.getElementById('file_details');
    fileDetails.innerHTML = file_details;
});

window.socket.on('lang_options', function (options) {
    console.log('Got language options');
    const langListElem = document.getElementById('lang_list');
    const langListSelect = document.createElement('select');
    langListSelect.addEventListener('change', function () {window.socket.emit('select_lang', langListSelect.value);});

    for (i = 0; i < options.length; i++) {
        var opt = document.createElement("option");
        opt.value = options[i][0];
        opt.innerHTML = options[i][1];
        langListSelect.appendChild(opt);
    };

    langListElem.innerHTML = '';
    langListElem.appendChild(langListSelect);
    window.socket.emit('select_lang', langListSelect.value);
});

window.socket.on('video_link', function (linkUrl) {
    const fileDetails = document.getElementById('video_link');
    fileDetails.innerHTML = `<a href="${linkUrl}" target="_blank">${linkUrl}</a>`;
});

window.socket.on('starting_server', function () {
    const playerStatus = document.getElementById('player_status');
    playerStatus.innerHTML = '<span class="msg-info">Starting Server ...</span>';
})

window.socket.on('start_playing', function () {
    const playerStatus = document.getElementById('player_status');
    playerStatus.innerHTML = '<span class="msg-success">Start Playing ...</span>';
})

window.socket.on('playing', function () {
    const playerStatus = document.getElementById('player_status');
    playerStatus.innerHTML = '<span class="msg-success">Playing ...</span>';
})

window.socket.on('stopping', function () {
    const playerStatus = document.getElementById('player_status');
    playerStatus.innerHTML = '<span class="msg-info">Stopping ...</span>';
})

window.socket.on('stopped', function () {
    const playerStatus = document.getElementById('player_status');
    playerStatus.innerHTML = '<span class="msg-error">Stopped</span>';
})

window.socket.on('audio_conversion_required', function () {
    const playerStatus = document.getElementById('player_status');
    playerStatus.innerHTML = '<span class="msg-error">Audio conversion required! <button onclick="window.socket.emit(\'convert_for_audio_stream\')">Convert</button></span>';
})

window.socket.on('audio_conversion_started', function () {
    const playerStatus = document.getElementById('player_status');
    playerStatus.innerHTML = '<span class="msg-info">Audio conversion started...</span>';
})

window.socket.on('audio_conversion_finished', function () {
    const playerStatus = document.getElementById('player_status');
    playerStatus.innerHTML = '<span class="msg-success">Audio conversion finished</span>';
})

window.socket.on('ready', function (ready) {
    const playerStatus = document.getElementById('player_status');
    if (ready) {
        playerStatus.innerHTML = '<span class="msg-success">Ready to play</span>';
    } else {
        playerStatus.innerHTML = '<span class="msg-success">Player not ready</span>';
    }
})

window.socket.on('logmessage', function (msg) {
    console.log('Got message');
    const messagesElem = document.getElementById('messages');

    const message = document.createElement('p');
    message.innerHTML = msg
    messagesElem.appendChild(message);
    message.scrollIntoView(false);
});

$(document).ready(function () {
    websocketStatus();
});
