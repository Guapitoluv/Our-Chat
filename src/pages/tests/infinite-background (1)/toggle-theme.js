const audioContext = new AudioContext();

function beep(
  frequency = 440,
  duration = 0.1
) {
  const oscillator =
    audioContext.createOscillator();

  const gain =
    audioContext.createGain();

  oscillator.frequency.value =
    frequency;

  oscillator.type = "square";

  gain.gain.setValueAtTime(
    0.1,
    audioContext.currentTime
  );

  gain.gain.exponentialRampToValueAtTime(
    0.001,
    audioContext.currentTime + duration
  );

  oscillator.connect(gain);
  gain.connect(audioContext.destination);

  oscillator.start();
  oscillator.stop(
    audioContext.currentTime + duration
  );
}

const b = document.getElementById("toggle-theme");

function randomEven(min, max) {
    const minEven = Math.ceil(min / 2);
    const maxEven = Math.floor(max / 2);
    
    return Math.floor(
        Math.random()
        * (maxEven - minEven + 1)
        + minEven
    ) * 2;
}

b.addEventListener(
    "click",
    () => {
        const i = randomEven(0, 10);
        console.log("beep");
        beep(600+(i*100), 0.5);
        beep(400+(i*100), 0.5);
        beep(200+(i*100), 0.5);
  }
);