## 2026-05-18 - Deleting boilerplate vite and react assets

**Learning:** Ensure that deleted assets like `vite.svg` and `react.svg` are also completely removed from `index.html` and component imports.
**Action:** Next time I will make sure not just to delete the files, but correctly grep the codebase and double-check HTML and App.tsx imports for these default Vite+React references before confirming deletion.

## 2026-05-18 - Removing unused exports

**Learning:** When fixing unused or duplicate exports flagged by tools like Knip, do not simply remove the `export` keyword. If a function is actively used, this breaks imports and causes a compilation error. If it is genuinely unused, it leaves behind an unexported local variable, triggering linter failures.
**Action:** Next time, if a function is genuinely unused, I will remove the entire dead code block, not just the `export` keyword. If it's a duplicate export, I will ensure the active export is maintained correctly and the unused one is cleanly removed.

## 2026-05-18 - Checking barrel files (`index.ts`) for usage

**Learning:** Barrel files (`index.ts`) are almost always imported via their parent directory path (e.g., `import { Foo } from './components'`). When checking if a barrel file is unused, you must grep for the directory name being imported, not just the string `index.ts`.
**Action:** Next time, before deleting an `index.ts` file, I will search for imports referencing its parent directory to verify it is genuinely unused.
