export class UserProfileFlyout {
    #triggerBtn = null;
    #popover = null;
    #isOpen = false;

    constructor(containerElement) {
        this.container = containerElement;
        this.#triggerBtn =
            this.container.querySelector("#profile-image")
            || this.container.querySelector("#profile-trigger-btn");
        this.#popover = this.container.querySelector("#profile-popover");

        this.#initEvents();
    }

    #initEvents() {
        this.#triggerBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            this.toggle();
        });

        this.#popover.addEventListener("click", (e) => {
            e.stopPropagation();
        });

        document.addEventListener("click", () => {
            if (this.#isOpen) {
                this.close();
            }
        });

        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && this.#isOpen) {
                this.close();
                this.#triggerBtn.focus();
            }
        });
    }

    toggle() {
        this.#isOpen ? this.close() : this.open();
    }

    open() {
        this.#isOpen = true;
        this.#popover.removeAttribute("hidden");
        this.#triggerBtn.setAttribute("aria-expanded", "true");
    }

    close() {
        this.#isOpen = false;
        this.#popover.setAttribute("hidden", "");
        this.#triggerBtn.setAttribute("aria-expanded", "false");
    }

    setUserData(user) {
        if (!user) return;

        const nameEl = this.#popover.querySelector("#popover-user-name");
        const emailEl = this.#popover.querySelector("#popover-user-email");
        const roleEl = this.#popover.querySelector("#popover-user-role");

        if (nameEl) nameEl.textContent = user.name || "Sem Nome";
        if (emailEl) emailEl.textContent = user.email || "";
        if (roleEl) roleEl.textContent = user.role || "Usuário";
    }
}
