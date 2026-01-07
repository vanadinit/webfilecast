# Webfilecast
A simple, modern web frontend for [Terminalcast](https://github.com/vanadinit/terminalcast) to cast local video files to your Chromecast.

![New Webfilecast UI](webfilecast.png)

## Features
- **Modern, responsive UI:** A clean, dark interface that works on desktop and mobile.
- **Searchable File List:** Instantly find the file you're looking for, even in large collections. The search supports fuzzy matching and exact phrases in quotes (e.g., `SomeSeries "Episode 7"`).
- **Natural Sorting:** Files are sorted logically, so "Episode 2" comes before "Episode 10".
- **Clear Controls:** Icon-based buttons for starting the server, playing on Chromecast, opening in browser, and stopping the server.
- **Dynamic UI:** Buttons are enabled/disabled based on the application state to guide the user.
- **Real-time Feedback:** See the connection status, server status, and file scan progress at a glance.

## Requirements
- Python 3.10+
- Redis Server (running on localhost)

## Installation
You can install Webfilecast directly from PyPI:
```sh
pip install webfilecast
```
For a production deployment, it is recommended to install the deployment dependencies as well:
```sh
pip install "webfilecast[deployment]"
```

## Usage

1.  **Set Environment Variables:**
    The application is configured via environment variables.

    - `MOVIE_DIRECTORY`: (Required) The absolute path to the directory where your video files are stored.
    - `CORS_ORIGINS`: (Required) A semicolon-separated list of allowed origins for the web frontend (e.g., `http://localhost:8000;http://127.0.0.1:8000`).
    - `TERMINALCAST_KNOWN_HOSTS`: (Optional) A comma-separated list of known Chromecast IP addresses to speed up discovery.

2.  **Run the application:**

    **For Development:**
    A simple development server can be started using the `flask` command. To enable automatic reloading on code changes, use the `--debug` flag.
    ```sh
    # Example
    export MOVIE_DIRECTORY="/path/to/your/videos"
    export CORS_ORIGINS="http://127.0.0.1:5000"
    
    flask --app webfilecast --debug run
    ```
    
    **For Production (Recommended):**
    For the best performance and to ensure all real-time features work correctly, it is highly recommended to use a production-ready WSGI server like `gunicorn` with `eventlet`.
    ```sh
    # Example
    export MOVIE_DIRECTORY="/path/to/your/videos"
    export CORS_ORIGINS="http://your-domain.com"
    
    gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:8000 "webfilecast:app"
    ```
    Then open your browser and navigate to the specified host and port.

## Advanced Configuration (Reverse Proxy)
If you are running Webfilecast behind a reverse proxy (like Nginx) and want to serve the video files through the same domain/port (to avoid mixed content issues or firewall restrictions), you can configure `terminalcast` to use a fixed port and a specific public URL.

1.  **Set additional Environment Variables:**
    - `TERMINALCAST_PORT`: The fixed port where the internal video server should listen (e.g., `8081`).
    - `TERMINALCAST_VIDEO_URL`: The public URL that the Chromecast and browser should use to access the video (e.g., `https://your-domain.com/video`).

2.  **Configure Nginx:**
    Add a location block to your Nginx configuration to proxy the video traffic to the internal `TERMINALCAST_PORT`.

    ```nginx
    server {
        listen 443 ssl;
        server_name your-domain.com;
        
        # ... ssl config ...

        # Main Webfilecast App
        location / {
            proxy_pass http://127.0.0.1:8000; # Gunicorn port
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # WebSocket support
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }

        # Video Streaming
        location /video {
            proxy_pass http://127.0.0.1:8081/video; # TERMINALCAST_PORT
            proxy_set_header Host $host;
            proxy_buffering off; # Important for streaming
        }
    }
    ```

## How it works
The application scans the `MOVIE_DIRECTORY` for video files and caches their metadata in Redis. The web frontend communicates with the Python backend via Socket.IO to select a file, choose an audio stream, and control the casting process. When a video is to be played, a temporary web server is started via `terminalcast` to stream the file to the Chromecast.
