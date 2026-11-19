#!/usr/bin/env python3
"""Cast Player laptop server.
Usage:  python serve.py [media_folder] [port]
Serves index.html + your videos over Wi-Fi (with Range + CORS) so the TV can pull them."""
import os, sys, re, json, socket, mimetypes, webbrowser, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
MEDIA = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
EXT = {'.mp4', '.m4v', '.mkv', '.webm', '.mov', '.avi', '.mp3', '.m4a', '.aac', '.wav', '.flac', '.ogg'}
mimetypes.add_type('video/x-matroska', '.mkv')

def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1)); return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()

LAN = lan_ip()

def list_media():
    out = []
    for root, _, files in os.walk(MEDIA):
        for f in files:
            if os.path.splitext(f)[1].lower() in EXT:
                rel = os.path.relpath(os.path.join(root, f), MEDIA).replace(os.sep, '/')
                out.append({'name': f, 'rel': rel})
    return sorted(out, key=lambda x: x['rel'].lower())

class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *a): pass

    def cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Range, Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
        self.send_header('Access-Control-Expose-Headers', 'Content-Length, Content-Range, Accept-Ranges')

    def reply(self, code, body=b'', ctype='text/plain; charset=utf-8'):
        self.send_response(code); self.cors()
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if self.command != 'HEAD': self.wfile.write(body)

    def do_OPTIONS(self): self.reply(204)
    def do_HEAD(self): self.do_GET()

    def do_GET(self):
        p = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        if p in ('/', '/index.html'):
            return self.reply(200, open(os.path.join(HERE, 'index.html'), 'rb').read(), 'text/html; charset=utf-8')
        if p == '/__list':
            return self.reply(200, json.dumps({'lan': LAN, 'port': PORT, 'folder': MEDIA, 'files': list_media()}).encode(), 'application/json')
        if p.startswith('/media/'):
            fp = os.path.realpath(os.path.join(MEDIA, p[7:]))
            if not fp.startswith(os.path.realpath(MEDIA) + os.sep) or not os.path.isfile(fp):
                return self.reply(404, b'not found')
            return self.send_file(fp)
        self.reply(404, b'not found')

    def send_file(self, fp):
        size = os.path.getsize(fp)
        ctype = mimetypes.guess_type(fp)[0] or 'application/octet-stream'
        start, end, code = 0, size - 1, 200
        m = re.match(r'bytes=(\d*)-(\d*)', self.headers.get('Range', ''))
        if m:
            a, b = m.groups()
            if a == '' and b: start = max(0, size - int(b))
            else:
                start = int(a or 0)
                if b: end = min(int(b), size - 1)
            if start > end or start >= size:
                self.send_response(416); self.cors()
                self.send_header('Content-Range', f'bytes */{size}'); self.send_header('Content-Length', '0'); self.end_headers(); return
            code = 206
        self.send_response(code); self.cors()
        self.send_header('Content-Type', ctype)
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end - start + 1))
        if code == 206: self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        if self.command == 'HEAD': return
        try:
            with open(fp, 'rb') as f:
                f.seek(start); left = end - start + 1
                while left > 0:
                    chunk = f.read(min(262144, left))
                    if not chunk: break
                    self.wfile.write(chunk); left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

if __name__ == '__main__':
    srv = ThreadingHTTPServer(('0.0.0.0', PORT), H)
    print(f'\n  Cast Player running\n  Videos folder : {MEDIA}\n  Open on laptop: http://localhost:{PORT}\n  (TV pulls from: http://{LAN}:{PORT})\n  Ctrl+C to stop\n')
    try: webbrowser.open(f'http://localhost:{PORT}')
    except Exception: pass
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
