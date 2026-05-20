## 2026-05-18 - Added ARIA labels to FeedDetail and Stats modals
**Learning:** Found several icon-only buttons (Close, Feed Options) using SVGs that lacked `aria-label` attributes in `FeedDetail.tsx`, `ProcessingStatsButton.tsx`, and `ReprocessButton.tsx`.
**Action:** Next time inspecting modals and complex components, verify all SVG-only buttons have descriptive `aria-label`s.

## 2026-05-18 - Made custom Audio Player sliders keyboard and screen-reader accessible
**Learning:** Custom interactive elements (like `div`s used for progress bars or volume controls) completely lock out keyboard-only and screen reader users unless manually wired up with ARIA `role="slider"`, `tabIndex`, proper `aria-valuenow`/`min`/`max` attributes, and `onKeyDown` handlers for arrow keys. Also added missing focus styles to the play and mute buttons.
**Action:** When building or reviewing any non-native form control (especially custom sliders or drag inputs), ensure it has full keyboard operability and correct ARIA states mirroring native `<input type="range">` behavior.
