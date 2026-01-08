window.socket = io.connect();
window.movieFiles = []; // Global variable to store the full movie list

function websocketStatus() {
    const statusDot = document.getElementById('ws_status_dot');

    statusDot.className = 'connecting';
    statusDot.title = 'Connecting...';

    window.socket.on('connect', () => {statusDot.className = 'connected'; statusDot.title = 'Connected';});
    window.socket.on('disconnect', () => {statusDot.className = 'disconnected'; statusDot.title = 'Disconnected';});
}

function setPlayButtonsState(enabled) {
    const chromecastButton = document.getElementById('play_chromecast_button');
    const browserButton = document.getElementById('open_in_browser_button');

    chromecastButton.disabled = !enabled;
    browserButton.disabled = !enabled;

    if (enabled) {
        chromecastButton.title = 'Play on Chromecast';
        browserButton.title = 'Open in Browser';
    } else {
        const defaultTitle = 'Select a file and audio track first';
        chromecastButton.title = defaultTitle;
        browserButton.title = defaultTitle;
    }
}

function renderFileList(filteredFiles) {
    const dropdown = document.getElementById('file_list_dropdown');
    dropdown.innerHTML = '';

    if (filteredFiles.length === 0) {
        const noResult = document.createElement('div');
        noResult.textContent = 'No files found';
        noResult.style.pointerEvents = 'none';
        dropdown.appendChild(noResult);
        return;
    }

    filteredFiles.forEach(file => {
        const item = document.createElement('div');
        item.textContent = file[1]; // Display name
        item.dataset.value = file[0]; // Store filepath
        item.addEventListener('click', () => {
            document.getElementById('file_search_input').value = file[1];
            dropdown.style.display = 'none';
            window.socket.emit('select_file', file[0]);
        });
        dropdown.appendChild(item);
    });
}


window.socket.on('connect', function() {
    console.log('Connected to server, getting file list.');
    window.socket.emit('get_files');
});

window.socket.on('movie_files', function (filelist) {
    console.log('Got movie file list');
    window.movieFiles = filelist;
    renderFileList(window.movieFiles); // Initially render the full list
});

window.socket.on('show_file_details', function (file_details) {
    const fileDetails = document.getElementById('file_details');
    fileDetails.innerHTML = file_details;
});

window.socket.on('lang_options', function (options) {
    console.log('Got language options');
    const langListElem = document.getElementById('lang_list');
    const langListSelect = document.createElement('select');

    langListSelect.addEventListener('change', function () {
        if (this.value) {
            window.socket.emit('select_lang', this.value);
        }
    });

    langListElem.innerHTML = '';
    langListElem.appendChild(langListSelect);

    if (options.length === 0) {
        const placeholder = document.createElement("option");
        placeholder.innerHTML = "No audio streams found";
        placeholder.disabled = true;
        langListSelect.appendChild(placeholder);
        return;
    }

    if (options.length > 1) {
        const placeholder = document.createElement("option");
        placeholder.innerHTML = "Select Audio Language";
        placeholder.value = "";
        placeholder.disabled = true;
        placeholder.selected = true;
        langListSelect.appendChild(placeholder);
    }

    for (let i = 0; i < options.length; i++) {
        const opt = document.createElement("option");
        opt.value = options[i][0];
        opt.innerHTML = options[i][1];
        langListSelect.appendChild(opt);
    }

    if (options.length === 1) {
        langListSelect.value = options[0][0];
        window.socket.emit('select_lang', langListSelect.value);
    }
});

window.socket.on('player_status_update', function (status) {
    const statusText = document.getElementById('player_status_text');
    const progressBar = document.getElementById('player_status_progress');

    statusText.className = `msg-${status.type}`;
    statusText.innerHTML = status.msg;
    progressBar.style.width = '0%';

    if (status.ready !== undefined) {
        setPlayButtonsState(status.ready);
    }
});

window.socket.on('playback_started', function () {
    const chromecastButton = document.getElementById('play_chromecast_button');
    chromecastButton.classList.add('streaming');
    chromecastButton.title = 'Stop Playback';
    chromecastButton.onclick = function() {
        window.socket.emit('stop_playback');
    };
});

window.socket.on('playback_stopped', function () {
    const chromecastButton = document.getElementById('play_chromecast_button');
    chromecastButton.classList.remove('streaming');
    chromecastButton.title = 'Play on Chromecast';
    chromecastButton.onclick = function() {
        window.socket.emit('play_on_chromecast');
    };
    setPlayButtonsState(true);
});

window.socket.on('conversion_progress', function (data) {
    const statusText = document.getElementById('player_status_text');
    const progressBar = document.getElementById('player_status_progress');

    statusText.className = 'msg-info';
    statusText.textContent = `Converting: ${data.progress}%`;
    progressBar.style.width = `${data.progress}%`;
});

window.socket.on('scan_started', function () {
    const refreshButton = document.getElementById('refresh_button');
    refreshButton.disabled = true;
    refreshButton.innerText = '0';
    refreshButton.title = 'Scanning...';
});

window.socket.on('scan_progress', function (data) {
    const refreshButton = document.getElementById('refresh_button');
    refreshButton.innerText = data.count;
    refreshButton.title = `${data.count} files scanned`;
});

window.socket.on('scan_finished', function (data) {
    const refreshButton = document.getElementById('refresh_button');
    refreshButton.disabled = false;
    refreshButton.innerText = '🔄';
    refreshButton.title = 'Refresh List';
    const statusText = document.getElementById('player_status_text');
    statusText.className = 'msg-success';
    statusText.textContent = `Scan finished. ${data.count} files found.`;
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
    setPlayButtonsState(false);
    document.getElementById('open_in_browser_button').onclick = function() {
        window.open('/video', '_blank');
    };

    const searchInput = document.getElementById('file_search_input');
    const dropdown = document.getElementById('file_list_dropdown');

    searchInput.addEventListener('focus', () => {
        renderFileList(window.movieFiles);
        dropdown.style.display = 'block';
    });

    searchInput.addEventListener('input', () => {
        const rawSearch = searchInput.value.toLowerCase();

        const searchParts = rawSearch.match(/".*?"|[^"\s]+/g) || [];

        if (searchParts.length === 0) {
            renderFileList(window.movieFiles);
            return;
        }

        const filteredFiles = window.movieFiles.filter(file => {
            const fileName = file[1].toLowerCase();
            return searchParts.every(part => {
                if (part.startsWith('"') && part.endsWith('"')) {
                    return fileName.includes(part.substring(1, part.length - 1));
                } else {
                    return fileName.includes(part);
                }
            });
        });
        renderFileList(filteredFiles);
    });

    document.addEventListener('click', (event) => {
        if (!document.getElementById('file_search_container').contains(event.target)) {
            dropdown.style.display = 'none';
        }
    });
});
