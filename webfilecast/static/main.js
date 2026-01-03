window.socket = io.connect();
window.currentVideoUrl = ''; // Global variable to store the video URL
window.movieFiles = []; // Global variable to store the full movie list

function websocketStatus() {
    const statusDot = document.getElementById('ws_status_dot');

    // Initial state
    statusDot.className = 'connecting';
    statusDot.title = 'Connecting...';

    window.socket.on('connect', () => {
        statusDot.className = 'connected';
        statusDot.title = 'Connected';
    });

    window.socket.on('disconnect', () => {
        statusDot.className = 'disconnected';
        statusDot.title = 'Disconnected';
    });
}

function setPlaybackButtonsState(enabled) {
    const chromecastButton = document.getElementById('play_chromecast_button');
    const browserButton = document.getElementById('open_in_browser_button');

    if (enabled) {
        chromecastButton.disabled = false;
        browserButton.disabled = false;
        chromecastButton.title = 'Play on Chromecast';
        browserButton.title = 'Open in Browser';
        browserButton.onclick = function() {
            window.open(window.currentVideoUrl, '_blank');
        };
    } else {
        chromecastButton.disabled = true;
        browserButton.disabled = true;
        chromecastButton.title = 'Start the server first';
        browserButton.title = 'Start the server first';
        browserButton.onclick = null;
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

    // Clear previous options and add to DOM
    langListElem.innerHTML = '';
    langListElem.appendChild(langListSelect);

    // Case 1: No options
    if (options.length === 0) {
        const placeholder = document.createElement("option");
        placeholder.innerHTML = "No audio streams found";
        placeholder.disabled = true;
        langListSelect.appendChild(placeholder);
        return;
    }

    // Case 2: Multiple options, add a placeholder
    if (options.length > 1) {
        const placeholder = document.createElement("option");
        placeholder.innerHTML = "Select Audio Language";
        placeholder.value = "";
        placeholder.disabled = true;
        placeholder.selected = true;
        langListSelect.appendChild(placeholder);
    }

    // Add all real options (for both 1 and >1 cases)
    for (let i = 0; i < options.length; i++) {
        const opt = document.createElement("option");
        opt.value = options[i][0];
        opt.innerHTML = options[i][1];
        langListSelect.appendChild(opt);
    }

    // Case 3: Exactly one option, auto-select it and notify backend
    if (options.length === 1) {
        langListSelect.value = options[0][0];
        window.socket.emit('select_lang', langListSelect.value);
    }
});

window.socket.on('video_link', function (linkUrl) {
    window.currentVideoUrl = linkUrl;
    setPlaybackButtonsState(true);
});

window.socket.on('player_status_update', function (status) {
    const playerStatus = document.getElementById('player_status');
    playerStatus.innerHTML = `<span class="msg-${status.type}">${status.msg}</span>`;

    if (status.ready !== undefined) {
        document.getElementById('start_server_button').disabled = !status.ready;
    }

    if (status.type === 'error' && status.msg === 'Stopped') {
        setPlaybackButtonsState(false);
        window.currentVideoUrl = '';
    }
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
    const playerStatus = document.getElementById('player_status');
    playerStatus.innerHTML = `<span class="msg-success">Scan finished. ${data.count} files found.</span>`;
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
    setPlaybackButtonsState(false); // Initially disable playback buttons

    const searchInput = document.getElementById('file_search_input');
    const dropdown = document.getElementById('file_list_dropdown');

    searchInput.addEventListener('focus', () => {
        renderFileList(window.movieFiles);
        dropdown.style.display = 'block';
    });

    searchInput.addEventListener('input', () => {
        const searchTerm = searchInput.value.toLowerCase();
        const filteredFiles = window.movieFiles.filter(file =>
            file[1].toLowerCase().includes(searchTerm)
        );
        renderFileList(filteredFiles);
    });

    // Hide dropdown if clicked outside
    document.addEventListener('click', (event) => {
        if (!document.getElementById('file_search_container').contains(event.target)) {
            dropdown.style.display = 'none';
        }
    });
});
