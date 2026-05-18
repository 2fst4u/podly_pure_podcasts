## 2026-05-18 - Added ARIA labels to FeedDetail and Stats modals
**Learning:** Found several icon-only buttons (Close, Feed Options) using SVGs that lacked `aria-label` attributes in `FeedDetail.tsx`, `ProcessingStatsButton.tsx`, and `ReprocessButton.tsx`.
**Action:** Next time inspecting modals and complex components, verify all SVG-only buttons have descriptive `aria-label`s.
