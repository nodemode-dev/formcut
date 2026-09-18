import argparse
import json
import socketserver
import sys


def response(line):
    from .automation import rpc
    try:
        return rpc(json.loads(line))
    except (ValueError, UnicodeError):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Invalid JSON"}}


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        while line := self.rfile.readline(2_000_001):
            if len(line) > 2_000_000:
                return
            result = response(line)
            if result is not None:
                self.wfile.write((json.dumps(result) + "\n").encode())
                self.wfile.flush()


def main():
    parser = argparse.ArgumentParser(description="FormCut headless JSON-RPC")
    parser.add_argument("--tcp", type=int)
    parser.add_argument("--unix")
    parser.add_argument("--grpc", type=int)
    args = parser.parse_args()
    if args.grpc:
        import grpc
        from concurrent.futures import ThreadPoolExecutor
        server = grpc.server(ThreadPoolExecutor(max_workers=4))
        method = grpc.unary_unary_rpc_method_handler(lambda value, context: response(value), request_deserializer=lambda value: value.decode(), response_serializer=lambda value: json.dumps(value).encode())
        server.add_generic_rpc_handlers((grpc.method_handlers_generic_handler("formcut.Automation", {"Call": method}),))
        server.add_insecure_port(f"127.0.0.1:{args.grpc}")
        server.start()
        server.wait_for_termination()
    elif args.tcp or args.unix:
        cls = socketserver.ThreadingTCPServer if args.tcp else socketserver.ThreadingUnixStreamServer
        address = ("127.0.0.1", args.tcp) if args.tcp else args.unix
        with cls(address, Handler) as server:
            server.serve_forever()
    else:
        for line in sys.stdin:
            result = response(line)
            if result is not None:
                print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
