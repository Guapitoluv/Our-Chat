from livereload import Server

server = Server()

server.watch(
    "frontend/**/*.html",
    delay=0.5
)

server.watch(
    "frontend/**/*.css",
    delay=0.5
)

server.watch(
    "frontend/**/*.js",
    delay=0.5
)

server.serve(
    root="frontend",
    host="0.0.0.0",
    port=8080,
    debug=True
)
