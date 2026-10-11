from livereload import Server

# cd "/storage/emulated/0/Programs/HTML Projects/new-our-chat/our-chat/Our-Chat/frontend/sign-up-test"

server = Server()

server.watch(
    "*.html",
    delay=0.5
)

server.watch(
    "*.css",
    delay=0.5
)

server.watch(
    "*.js",
    delay=0.5
)

server.serve(
    root=".",
    host="0.0.0.0",
    port=8080,
    debug=True
)
