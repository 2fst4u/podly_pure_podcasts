## 2026-05-16 - List Rendering Performance
**Learning:** Adding `loading="lazy"` to `<img>` tags in React list components is a quick, native way to improve performance on initial render and save bandwidth without needing a complex virtualization library.
**Action:** Always check list components rendering images and ensure native lazy loading is utilized.

## 2026-05-18 - Input Debouncing
**Learning:** Implementing debouncing for fast-typing inputs combined with heavy client-side filtering prevents excessive re-rendering and CPU spikes. Memoizing default array fallbacks also avoids downstream re-renders.
**Action:** Add `useMemo` and debounced states to frequently updated search filters, especially when the lists being filtered are large.
