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

    for (let i = 0; i < filelist.length; i++) {
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

    for (let i = 0; i < options.length; i++) {
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

window.socket.on('player_status_update', function (status) {
    const playerStatus = document.getElementById('player_status');
    playerStatus.innerHTML = `<span class="msg-${status.type}">${status.msg}</span>`;
});

window.socket.on('logmessage', function (msg) {
    console.log('Got message');
    const messagesElem = document.getElementById('messages');

    const message = document.createElement('div');
    message.innerHTML = msg
    messagesElem.appendChild(message);
    message.scrollIntoView(false);
});

$(document).ready(function () {
    websocketStatus();
});
