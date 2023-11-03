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
    fileListSelect.addEventListener('click', function () {window.socket.emit('select_file', fileListSelect.value);});

    for (i = 0; i < filelist.length; i++) {
      var opt = document.createElement("option");
      opt.id = filelist[i];
      opt.innerHTML = filelist[i];
      fileListSelect.appendChild(opt);
    };

    fileListElem.innerHTML = '';
    fileListElem.appendChild(fileListSelect);
})

window.socket.on('show_file_details', function (file_details) {
    const fileDetails = document.getElementById('file_details');
    fileDetails.innerHTML = file_details;
});

window.socket.on('logmessage', function (msg) {
    const messagesElem = document.getElementById('messages');
    const bottomElem = document.getElementById('bottombox');

    const message = document.createElement('p');
    message.innerHTML = msg
    messagesElem.appendChild(message);
    bottomElem.scrollIntoView();
});

$(document).ready(function () {
    websocketStatus();
});
