// Shared Motion (motion/react) presets — per frontend-motion skill.
// Keep every spring config here; never hand-roll one inline in a component.

// Default for entrances, layout animations, most UI motion.
const standard = { type: "spring", stiffness: 260, damping: 30, mass: 1 };

// Buttons, icon-buttons, tab switches — snappier, no overshoot.
const press = { type: "spring", stiffness: 400, damping: 35, mass: 0.8 };

// Cards entering/leaving (report/chat message content, session list items).
const card = { type: "spring", stiffness: 220, damping: 26, mass: 1 };

export const springs = { standard, press, card };

// ease-out, for opacity/color-only tweens -- never spring color or box-shadow.
export const easeStandard = [0.22, 1, 0.36, 1];

// Timing scale (seconds, for use with `duration`).
export const duration = {
  instant: 0.1, // color/background changes on press
  fast: 0.18, // hover, badge appearance, focus ring
  standard: 0.26, // most micro-interactions
  entrance: 0.32, // section/card entering, modal/sheet open
};

// Delay between siblings in a staggered list.
export const staggerStep = 0.06;
