import { Page } from "../../core/page/page.js";

import { InfiniteVideoBackground }
    from "./infinite-video-background.js";

import { router } from "../../../router-instance.js";


export class IndexPage extends Page {
    constructor() {
        super(
            "/src/pages/index/index.html"
        );
        
        this.background = null;
        this.consoleInput = null;
    }


    mount() {
        this.consoleInput =
            document.querySelector(
                "#console-input"
            );
        
        this.consoleInput.addEventListener(
            "keydown",
            (event) => {
                if (event.key === "Enter") {
                    event.preventDefault();
                    
                    if (!this.consoleInput.value) return;
                    
                    if (this.consoleInput.value === "chat") {
                        router.renderRoute("/conversation");
                    } 
                    
                    this.consoleInput.value = "";
                }
            }
        );
        
        this.createBackground();
        
        this.element.dataset.theme =
            "light";
        
        this.background.start();
    }


    createBackground() {
        const canvas =
            this.element.querySelector(
                "#background"
            );


        this.background =
            new InfiniteVideoBackground(
                canvas,

                "/public/videos/video-light.mp4",

                {
                    tileWidth: 80,
                    tileHeight: 80,

                    speed: 25,
                    direction: 45 + 90,

                    maxPixelRatio: 2
                }
            );
    }


    handleThemeToggle = () => {
        const newTheme =
            this.element.dataset.theme === "light"
                ? "dark"
                : "light";


        this.element.dataset.theme =
            newTheme;


        this.background?.setVideo(
            `/public/videos/video-${newTheme}.mp4`
        );
    };


    handleMusic = () => {
        if (!this.music) {
            return;
        }


        this.music.play()
            .then(() => {
                console.log("Tocando");
            })
            .catch(error => {
                console.error(
                    error.name
                );

                console.error(
                    error.message
                );
            });
    };


    unmount() {
        this.background?.destroy?.();
        this.background = null;
    }
}