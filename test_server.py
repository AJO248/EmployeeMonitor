from http.server import BaseHTTPRequestHandler, HTTPServer
import sys

class S(BaseHTTPRequestHandler):
    def do_POST(self):
        with open("headers_received.txt", "a") as f:
            f.write("--- HEADERS RECEIVED ---\n")
            f.write(str(self.headers))
            f.write("\n")
        self.send_response(200)
        self.end_headers()
        sys.exit(0)

HTTPServer(('127.0.0.1', 8001), S).serve_forever()
