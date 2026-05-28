## 2026-05-16 - List Rendering Performance
**Learning:** Adding `loading="lazy"` to `<img>` tags in React list components is a quick, native way to improve performance on initial render and save bandwidth without needing a complex virtualization library.
**Action:** Always check list components rendering images and ensure native lazy loading is utilized.

## 2026-05-18 - Input Debouncing
**Learning:** Implementing debouncing for fast-typing inputs combined with heavy client-side filtering prevents excessive re-rendering and CPU spikes. Memoizing default array fallbacks also avoids downstream re-renders.
**Action:** Add `useMemo` and debounced states to frequently updated search filters, especially when the lists being filtered are large.
## 2026-05-18 - Extracting formatTime in AudioPlayer
**Learning:** Moving pure formatting functions outside of React components avoids re-creating the function reference on every re-render, which is particularly beneficial in frequently rendering components like an AudioPlayer.
**Action:** Always extract pure utility functions (like time formatting) outside of the component body, especially in components that re-render frequently due to time updates.
## 2026-05-28 - Extracting formatTime in ProcessingStatsButton
**Learning:** Extracting pure utility functions (like `formatDuration` and `formatTimestamp`) outside of React components is a simple optimization that prevents unnecessary memory allocation and garbage collection overhead during frequent component re-renders (like when interacting with modals).
**Action:** Always extract pure formatting and utility functions outside the main component body, especially in components that manage local state or render frequently.
