export class InfiniteVideoBackground {
    constructor(canvas, videoSrc, options = {}) {
        this.canvas = canvas;

        this.video =
            document.createElement("video");

        this.video.src = videoSrc;
        this.video.muted = true;
        this.video.loop = true;
        this.video.playsInline = true;
        this.video.preload = "auto";

        this.tileWidth =
            options.tileWidth ?? 100;

        this.tileHeight =
            options.tileHeight ?? 100;

        this.speed =
            options.speed ?? 25;

        this.direction =
            options.direction ?? 45;

        this.maxPixelRatio =
            options.maxPixelRatio ?? 2;

        this.startTime = null;
        this.textureNeedsUpdate = false;

        this.gl = canvas.getContext("webgl2", {
            alpha: false,
            antialias: false,
            powerPreference: "high-performance"
        });

        if (!this.gl) {
            throw new Error(
                "WebGL2 não é suportado."
            );
        }

        this.#createProgram();
        this.#createGeometry();
        this.#createTexture();
        this.#getUniforms();

        this.#resize();

        window.addEventListener(
            "resize",
            () => this.#resize()
        );

        this.#setupVideoFrameUpdates();
    }


    #createProgram() {
        const vertexShaderSource = `#version 300 es

            in vec2 position;

            out vec2 uv;

            void main() {

                uv = position * 0.5 + 0.5;

                gl_Position =
                    vec4(position, 0.0, 1.0);
            }
        `;
        
        const fragmentShaderSource = `#version 300 es

            precision mediump float;

            uniform sampler2D videoTexture;

            uniform vec2 resolution;
            uniform vec2 tileSize;
            uniform vec2 offset;

            in vec2 uv;

            out vec4 color;

            void main() {

                vec2 pixel =
                    uv * resolution;

                pixel += offset;

                vec2 tileUV =
                    mod(pixel, tileSize)
                    / tileSize;

                color =
                    texture(
                        videoTexture,
                        tileUV
                    );
            }
        `;
        
        const vertexShader =
            this.#createShader(
                this.gl.VERTEX_SHADER,
                vertexShaderSource
            );
        
        const fragmentShader =
            this.#createShader(
                this.gl.FRAGMENT_SHADER,
                fragmentShaderSource
            );
        
        this.program =
            this.gl.createProgram();
        
        this.gl.attachShader(
            this.program,
            vertexShader
        );

        this.gl.attachShader(
            this.program,
            fragmentShader
        );

        this.gl.linkProgram(
            this.program
        );
        
        if (
            !this.gl.getProgramParameter(
                this.program,
                this.gl.LINK_STATUS
            )
        ) {
            throw new Error(
                this.gl.getProgramInfoLog(
                    this.program
                )
            );
        }
        
        this.gl.useProgram(
            this.program
        );
    }


    #createShader(type, source) {
        const shader =
            this.gl.createShader(type);

        this.gl.shaderSource(
            shader,
            source
        );

        this.gl.compileShader(shader);
        
        if (
            !this.gl.getShaderParameter(
                shader,
                this.gl.COMPILE_STATUS
            )
        ) {
            const error =
                this.gl.getShaderInfoLog(
                    shader
                );

            this.gl.deleteShader(
                shader
            );

            throw new Error(error);
        }
        
        return shader;
    }


    #createGeometry() {
        const vertices =
            new Float32Array([

                -1, -1,
                 1, -1,
                -1,  1,

                -1,  1,
                 1, -1,
                 1,  1
            ]);
        
        const buffer =
            this.gl.createBuffer();
        
        this.gl.bindBuffer(
            this.gl.ARRAY_BUFFER,
            buffer
        );
        
        this.gl.bufferData(
            this.gl.ARRAY_BUFFER,
            vertices,
            this.gl.STATIC_DRAW
        );
        
        const position =
            this.gl.getAttribLocation(
                this.program,
                "position"
            );
        
        this.gl.enableVertexAttribArray(
            position
        );
        
        this.gl.vertexAttribPointer(
            position,
            2,
            this.gl.FLOAT,
            false,
            0,
            0
        );
    }


    #createTexture() {
        this.texture =
            this.gl.createTexture();
        
        this.gl.bindTexture(
            this.gl.TEXTURE_2D,
            this.texture
        );
        
        this.gl.texParameteri(
            this.gl.TEXTURE_2D,
            this.gl.TEXTURE_WRAP_S,
            this.gl.REPEAT
        );

        this.gl.texParameteri(
            this.gl.TEXTURE_2D,
            this.gl.TEXTURE_WRAP_T,
            this.gl.REPEAT
        );
        
        this.gl.texParameteri(
            this.gl.TEXTURE_2D,
            this.gl.TEXTURE_MIN_FILTER,
            this.gl.LINEAR
        );

        this.gl.texParameteri(
            this.gl.TEXTURE_2D,
            this.gl.TEXTURE_MAG_FILTER,
            this.gl.LINEAR
        );
        
        /*
         * Corrige a orientação vertical
         * do vídeo.
         */
        this.gl.pixelStorei(
            this.gl.UNPACK_FLIP_Y_WEBGL,
            true
        );
    }


    #getUniforms() {
        this.resolutionLocation =
            this.gl.getUniformLocation(
                this.program,
                "resolution"
            );
        
        this.tileSizeLocation =
            this.gl.getUniformLocation(
                this.program,
                "tileSize"
            );
        
        this.offsetLocation =
            this.gl.getUniformLocation(
                this.program,
                "offset"
            );
    }


    #resize() {
        const pixelRatio =
            Math.min(
                window.devicePixelRatio,
                this.maxPixelRatio
            );
        
        this.canvas.width =
            window.innerWidth *
            pixelRatio;
        
        this.canvas.height =
            window.innerHeight *
            pixelRatio;
        
        this.gl.viewport(
            0,
            0,
            this.canvas.width,
            this.canvas.height
        );
    }


    #setupVideoFrameUpdates() {
        if (
            "requestVideoFrameCallback"
            in HTMLVideoElement.prototype
        ) {
            const update = () => {
                this.textureNeedsUpdate = true;

                this.video.requestVideoFrameCallback(update);
            };
            
            this.video.requestVideoFrameCallback(update);
            
        } else {
            this.textureNeedsUpdate = true;
        }
    }


    #updateTexture() {
        if (
            !this.textureNeedsUpdate ||
            this.video.readyState <
            HTMLMediaElement.HAVE_CURRENT_DATA
        ) {
            return;
        }
        
        this.gl.bindTexture(
            this.gl.TEXTURE_2D,
            this.texture
        );
        
        this.gl.texImage2D(
            this.gl.TEXTURE_2D,
            0,
            this.gl.RGBA,
            this.gl.RGBA,
            this.gl.UNSIGNED_BYTE,
            this.video
        );
        
        this.textureNeedsUpdate =
            false;
    }


    #render = (time) => {
        if (this.startTime === null) {
            this.startTime = time;
        }
        
        const elapsed =
            (time - this.startTime) / 1000;
        
        const angle =
            this.direction * Math.PI / 180;
        
        const offsetX =
            (
                elapsed *
                this.speed *
                Math.cos(angle)
            ) % this.tileWidth;
        
        const offsetY =
            (
                elapsed *
                this.speed *
                Math.sin(angle)
            ) % this.tileHeight;
        
        this.#updateTexture();
        
        this.gl.useProgram(
            this.program
        );
        
        this.gl.uniform2f(
            this.resolutionLocation,
            this.canvas.width,
            this.canvas.height
        );
        
        this.gl.uniform2f(
            this.tileSizeLocation,
            this.tileWidth,
            this.tileHeight
        );
        
        this.gl.uniform2f(
            this.offsetLocation,
            offsetX,
            offsetY
        );

        this.gl.drawArrays(
            this.gl.TRIANGLES,
            0,
            6
        );
        
        requestAnimationFrame(
            this.#render
        );
    };


    setVideo(videoSrc, options = {}) {
        const reset =
            options.reset ?? false;
        
        this.video.pause();
        
        this.video.src = videoSrc;
        
        this.video.load();
        
        this.textureNeedsUpdate = true;
        
        if (reset) this.startTime = null;

        this.#setupVideoFrameUpdates();
        
        this.video.play().catch(error => {
            console.error(
                "Não foi possível reproduzir o vídeo:",
                error
            );
        });
    }


    async start() {
        await this.video.play();

        requestAnimationFrame(
            this.#render
        );
    }
}