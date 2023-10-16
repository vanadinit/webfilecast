window.socket = io.connect();

function websocketStatus() {
    let timeoutCounter = 0;
    const statusIndicator = document.getElementById('ws_status');
    const wsConnectStatus = setInterval(function () {
        if (window.socket.connected) {
            statusIndicator.innerHTML = '<span class="msg-success">Connected</span>';
            timeoutCounter = 0;
        } else {
            statusIndicator.innerHTML = '<span class="msg-error">Disconnected (${timeoutCounter})</span>';
            timeoutCounter++;
        }
        if (timeoutCounter > 60) {
            statusIndicator.innerHTML = '<span class="msg-error">Disconnected (Please reload)</span>';
            clearInterval(wsConnectStatus);
        }
    }, 1000);
}

window.socket.on('movie_files', function (filelist) {
    const fileListElem = document.getElementById('file_list');
    const fileListSelect = document.createElement('select');
    fileListSelect.onclick(window.socket.emit('select_file', fileListSelect.value);

    for (i = 0; i < filelist.length; i++) {
      var opt = document.createElement("option");
      opt.id = i;
      opt.innerHTML = i;
      fileListSelect.appendChild(opt);
    };
})

window.socket.on('logmessage', function (msg) {
    const messagesElem = document.getElementById('messages');
    const bottomElem = document.getElementById('boxbottom');

    const message = document.createElement('p');
    message.innerHTML = msg
    messagesElem.appendChild(message);
    bottomElem[0].scrollIntoView();
});

$(document).ready(function () {
    websocketStatus();
});
