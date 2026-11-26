// Frame Gamepad, TV mode: Steam Frame controllers for TV interfaces (youtube.com/tv and the like).
//
// A TV interface is made for a remote control: it listens for arrow keys, OK and Back, and moves its own selection.
// So instead of acting on the page like frame-gamepad.js does, this turns the controller (read through the Gamepad
// API, see frame-gamepad.js for why) into those key presses. Repeat timings as in FrameTube
// (github.com/coah80/frametube, MIT), which does the same for YouTube in its own browser. Local only: no network.
(() => {
  'use strict';
  if (window !== window.top || window.__frameGamepadTv) return;
  window.__frameGamepadTv = true;

  // Standard gamepad mapping (https://w3c.github.io/gamepad/#remapping) -> [key, keyCode]
  const KEYS = {
    12: ['ArrowUp', 38], 13: ['ArrowDown', 40], 14: ['ArrowLeft', 37], 15: ['ArrowRight', 39],
    0: ['Enter', 13],                 // A: OK
    1: ['Escape', 27],                // B: back
    2: ['MediaPlayPause', 179],       // X
    4: ['MediaRewind', 227],          // LB
    5: ['MediaFastForward', 228],     // RB
  };
  const STICK = { up: 12, down: 13, left: 14, right: 15 };   // either stick, strongly tilted, acts as the D-pad
  const REPEATS = new Set([12, 13, 14, 15, 4, 5]);
  const REPEAT_DELAY = 400, REPEAT_RATE = 110, TILT = 0.6;   // ms, ms, stick deflection

  const held = new Map();   // button index -> time of the next repeat
  const log = (...a) => console.info('[frame-gamepad-tv]', location.host, ...a);

  function send(button) {
    const [key, keyCode] = KEYS[button];
    const target = document.activeElement || document.body;
    for (const type of ['keydown', 'keyup']) {
      target.dispatchEvent(new KeyboardEvent(type, { key, code: key, keyCode, which: keyCode, bubbles: true, cancelable: true }));
    }
  }

  let announced = false;
  function poll(now) {
    const pad = [...navigator.getGamepads()].find(p => p && p.connected);
    if (pad) {
      if (!announced) { announced = true; log('controller ready:', pad.id); }
      const down = new Set();
      pad.buttons.forEach((b, i) => { if (b.pressed && KEYS[i]) down.add(i); });
      for (const [x, y] of [[pad.axes[0], pad.axes[1]], [pad.axes[2], pad.axes[3]]]) {
        if (Math.abs(x || 0) > TILT || Math.abs(y || 0) > TILT) {
          down.add(Math.abs(x) > Math.abs(y) ? (x > 0 ? STICK.right : STICK.left) : (y > 0 ? STICK.down : STICK.up));
        }
      }
      for (const b of down) {
        if (!held.has(b)) { send(b); held.set(b, now + REPEAT_DELAY); }
        else if (REPEATS.has(b) && now >= held.get(b)) { send(b); held.set(b, now + REPEAT_RATE); }
      }
      for (const b of [...held.keys()]) if (!down.has(b)) held.delete(b);
    }
    requestAnimationFrame(poll);
  }
  requestAnimationFrame(poll);
})();
