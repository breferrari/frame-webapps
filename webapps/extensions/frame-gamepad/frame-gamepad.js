// Frame Gamepad: Steam Frame controllers for web apps in Flatpak Chromium.
//
// Why: Steam can't link a Flatpak window to its shortcut, so the keys/wheel of a Steam Input layout never reach the page.
// But with a *gamepad* layout Steam feeds a virtual Xbox pad, which the page can read itself through the Gamepad API.
// Polls navigator.getGamepads() and acts on it. Inspired by FrameTube (github.com/coah80/frametube, MIT), incl. its repeat timings.
// Acts on the DOM and <video> directly (no reliance on trusted key events). Local only: no network.
// Runs in every frame: the top page handles scrolling, focus and navigation; embedded frames only handle a video player they contain.
(() => {
  'use strict';
  if (window.__frameGamepad) return;
  window.__frameGamepad = true;

  const IS_TOP = window === window.top;
  // Standard gamepad mapping (https://w3c.github.io/gamepad/#remapping)
  const BTN = { A: 0, B: 1, X: 2, Y: 3, LB: 4, RB: 5, LT: 6, RT: 7, VIEW: 8, MENU: 9, LS: 10, RS: 11, UP: 12, DOWN: 13, LEFT: 14, RIGHT: 15 };
  const REPEAT_DELAY = 400, REPEAT_RATE = 110;   // ms
  const DEADZONE = 0.2, SCROLL_SPEED = 28;        // px per frame at full deflection
  const NAV_THRESHOLD = 0.6;                      // left stick X as left/right when strongly tilted

  const held = new Map(); // button index -> { since, last }
  // Log lines show up in logs/<App>-chromium.log as CONSOLE lines ("[frame-gamepad] ...").
  // Set DEBUG to true to also log every button press and the first wheel events.
  const DEBUG = false;
  const log = (...a) => console.info('[frame-gamepad]', location.host, IS_TOP ? 'top' : 'frame', ...a);
  const debug = (...a) => { if (DEBUG) log(...a); };

  // ---------- helpers ----------
  const video = () => {
    const v = [...document.querySelectorAll('video')].filter(e => e.readyState > 0 || e.src || e.currentSrc);
    return v.sort((a, b) => b.clientWidth * b.clientHeight - a.clientWidth * a.clientHeight)[0] || null;
  };
  const isTyping = () => {
    const a = document.activeElement;
    return !!a && (a.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName) && !/^(button|checkbox|radio|range|submit)$/i.test(a.type || ''));
  };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) return false;
    const s = getComputedStyle(el);
    return s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0';
  };
  const FOCUSABLE = 'a[href], button:not([disabled]), [role="button"], [role="link"], [role="tab"], [role="menuitem"], input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])';
  const focusables = () => [...document.querySelectorAll(FOCUSABLE)].filter(visible);

  function toast(msg) {
    if (!IS_TOP || !document.body) return;
    let t = document.getElementById('__frame_gamepad_toast');
    if (!t) {
      t = document.createElement('div');
      t.id = '__frame_gamepad_toast';
      t.style.cssText = 'position:fixed;left:50%;bottom:6%;transform:translateX(-50%);z-index:2147483647;padding:10px 18px;border-radius:10px;' +
        'background:rgba(0,0,0,.8);color:#fff;font:600 16px/1.3 system-ui,sans-serif;pointer-events:none;transition:opacity .4s';
      document.body.appendChild(t);
    }
    t.textContent = msg; t.style.opacity = '1';
    clearTimeout(t.__h); t.__h = setTimeout(() => { t.style.opacity = '0'; }, 2500);
  }

  // Focus ring so D-pad navigation is visible.
  const style = document.createElement('style');
  style.textContent = '.__frame_gp_focus{outline:3px solid #4da3ff!important;outline-offset:3px!important;border-radius:4px}';
  (document.head || document.documentElement).appendChild(style);
  let ring = null;
  function setFocus(el) {
    if (!el) return;
    if (ring) ring.classList.remove('__frame_gp_focus');
    ring = el; el.classList.add('__frame_gp_focus');
    el.focus({ preventScroll: true });
    el.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
  }

  // Spatial navigation: nearest focusable in the pressed direction.
  function moveFocus(dir) {
    const all = focusables();
    if (!all.length) return;
    const cur = ring && document.contains(ring) && visible(ring) ? ring : null;
    if (!cur) {   // start with the focusable nearest the screen centre
      const cx = innerWidth / 2, cy = innerHeight / 2;
      return setFocus(all.reduce((best, e) => {
        const r = e.getBoundingClientRect(), d = Math.hypot(r.x + r.width / 2 - cx, r.y + r.height / 2 - cy);
        return !best || d < best.d ? { e, d } : best;
      }, null).e);
    }
    const c = cur.getBoundingClientRect(), cx = c.x + c.width / 2, cy = c.y + c.height / 2;
    let best = null;
    for (const e of all) {
      if (e === cur || e.contains(cur) || cur.contains(e)) continue;
      const r = e.getBoundingClientRect(), x = r.x + r.width / 2, y = r.y + r.height / 2;
      const dx = x - cx, dy = y - cy;
      const along = { up: -dy, down: dy, left: -dx, right: dx }[dir];
      const across = (dir === 'up' || dir === 'down') ? Math.abs(dx) : Math.abs(dy);
      if (along <= 4) continue;
      const score = along + across * 2.5;
      if (!best || score < best.score) best = { e, score };
    }
    if (best) setFocus(best.e);
    else if (dir === 'up' || dir === 'down') scroller().scrollBy({ top: (dir === 'down' ? 1 : -1) * innerHeight * 0.6, behavior: 'smooth' });
  }

  // The element that should scroll: the scrollable ancestor of whatever is at the screen centre, else the page.
  function scroller() {
    let el = document.elementFromPoint(innerWidth / 2, innerHeight / 2);
    while (el && el !== document.body && el !== document.documentElement) {
      const s = getComputedStyle(el);
      if (/(auto|scroll)/.test(s.overflowY) && el.scrollHeight > el.clientHeight + 4) return el;
      el = el.parentElement;
    }
    return document.scrollingElement || document.documentElement;
  }

  function seek(sec) {
    const v = video(); if (!v) return false;
    v.currentTime = Math.max(0, Math.min((v.duration || 1e9) - 0.5, v.currentTime + sec));
    toast(`${sec > 0 ? '+' : ''}${sec}s`);
    return true;
  }
  function clickByLabel(re) {
    const el = [...document.querySelectorAll('button, a, [role="button"]')].find(e => visible(e) &&
      re.test((e.getAttribute('aria-label') || '') + ' ' + (e.getAttribute('data-testid') || '') + ' ' + e.textContent));
    if (el) { el.click(); return true; }
    return false;
  }

  // ---------- actions ----------
  function press(b) {
    debug('press', b, 'focused=' + (document.activeElement && document.activeElement.tagName), 'ring=' + !!ring, 'video=' + !!video());
    const v = video();
    const inPlayer = !!v && v.clientWidth > innerWidth * 0.5;
    if (!IS_TOP) {
      // Embedded frame: only control a video player it contains. Navigation, clicks and Back belong to the top page.
      if (!v || [BTN.A, BTN.B].includes(b)) return;
      if (!inPlayer && [BTN.UP, BTN.DOWN, BTN.LEFT, BTN.RIGHT].includes(b)) return;
    }
    if (isTyping() && b !== BTN.B) return;
    switch (b) {
      case BTN.A: (ring && document.contains(ring) ? ring : document.activeElement)?.click?.(); break;
      case BTN.B:
        if (document.fullscreenElement) document.exitFullscreen();
        else if (isTyping()) document.activeElement.blur();
        else history.back();
        break;
      case BTN.X: if (v) { v.paused ? v.play() : v.pause(); toast(v.paused ? 'Paused' : 'Playing'); } break;
      case BTN.LB: seek(-10); break;
      case BTN.RB: seek(10); break;
      case BTN.LT: if (!clickByLabel(/previous episode|prev/i)) seek(-30); break;
      case BTN.RT: if (!clickByLabel(/next episode|skip intro|skip credits|skip recap/i)) seek(30); break;
      case BTN.Y: if (v) { (v.closest('[class*="player"]') || v).requestFullscreen?.().catch(() => {}); } break;
      case BTN.UP: inPlayer ? volume(+0.1) : moveFocus('up'); break;
      case BTN.DOWN: inPlayer ? volume(-0.1) : moveFocus('down'); break;
      case BTN.LEFT: inPlayer ? seek(-10) : moveFocus('left'); break;
      case BTN.RIGHT: inPlayer ? seek(10) : moveFocus('right'); break;
    }
  }
  function volume(d) {
    const v = video(); if (!v) return;
    v.muted = false; v.volume = Math.max(0, Math.min(1, +(v.volume + d).toFixed(2)));
    toast(`Volume ${Math.round(v.volume * 100)}%`);
  }


  // Laser-pointer scrolling: SteamVR turns the pointing hand's stick into scroll, but for app windows it often arrives as
  // tiny wheel steps (6-26 px vs ~100 px per notch). Boost small, non-ctrl wheel events so laser scrolling feels normal.
  const WHEEL_BOOST = 6, WHEEL_SMALL = 40;
  let wheelLogged = 0;
  window.addEventListener('wheel', (e) => {
    if (wheelLogged < 15) { wheelLogged++; debug('wheel', 'dy=' + e.deltaY.toFixed(1), 'mode=' + e.deltaMode, 'trusted=' + e.isTrusted); }
    if (e.ctrlKey || e.deltaMode !== 0 || Math.abs(e.deltaY) >= WHEEL_SMALL || Math.abs(e.deltaY) < 0.5) return;
    e.preventDefault();
    scroller().scrollBy(0, e.deltaY * WHEEL_BOOST);
  }, { passive: false, capture: true });

  // ---------- poll loop ----------
  let announced = false;
  function announce(pad) {   // once per browser session, not on every page
    announced = true;
    log('pad', `${pad.index}:${pad.id}:mapping=${pad.mapping}:${pad.buttons.length}b/${pad.axes.length}a`);
    try {
      if (sessionStorage.getItem('__frame_gamepad_seen')) return;
      sessionStorage.setItem('__frame_gamepad_seen', '1');
    } catch (e) { /* storage blocked: just show it */ }
    toast('Controller ready');
  }
  function frame(now) {
    const pads = navigator.getGamepads ? [...navigator.getGamepads()].filter(Boolean) : [];
    if (pads.length) {
      if (!announced) announce(pads[0]);
      // merge all pads (the Frame's two hands may arrive as one virtual pad; be tolerant)
      const pressed = new Set();
      let sy = 0, sx = 0;
      for (const p of pads) {
        p.buttons.forEach((btn, i) => { if (btn.pressed || btn.value > 0.6) pressed.add(i); });
        const ly = p.axes[1] || 0, ry = p.axes[3] || 0, lx = p.axes[0] || 0;
        sy += Math.abs(ry) > Math.abs(ly) ? ry : ly;
        sx += lx;
      }
      // left stick strongly sideways = left/right navigation
      if (sx > NAV_THRESHOLD) pressed.add(BTN.RIGHT); else if (sx < -NAV_THRESHOLD) pressed.add(BTN.LEFT);
      for (const i of pressed) {
        const h = held.get(i);
        if (!h) { held.set(i, { since: now, last: now }); press(i); }
        else if ([BTN.UP, BTN.DOWN, BTN.LEFT, BTN.RIGHT, BTN.LB, BTN.RB].includes(i) && now - h.since > REPEAT_DELAY && now - h.last > REPEAT_RATE) {
          h.last = now; press(i);
        }
      }
      for (const i of [...held.keys()]) if (!pressed.has(i)) held.delete(i);
      // smooth scroll with stick Y (only when not watching full-size video)
      const v = video();
      if (IS_TOP && Math.abs(sy) > DEADZONE && !(v && v.clientWidth > innerWidth * 0.5) && !isTyping()) {
        const mag = (Math.abs(sy) - DEADZONE) / (1 - DEADZONE);
        scroller().scrollBy(0, Math.sign(sy) * mag * mag * SCROLL_SPEED);
      }
    }
    requestAnimationFrame(frame);
  }
  window.addEventListener('gamepadconnected', (e) => { if (!announced) announce(e.gamepad); });
  log('loaded', 'getGamepads=' + !!navigator.getGamepads);
  requestAnimationFrame(frame);
})();
