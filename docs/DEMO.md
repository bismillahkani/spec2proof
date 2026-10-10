# Demo recording guide

## 90-second narration

**0–15 sec:** “Spec2Proof closes the gap between a business requirement and evidence that a repair actually satisfies it. The demo is a refund policy with two realistic bugs.”

**15–30 sec:** Create criteria and confirm the contract. “We freeze ten acceptance tests before proposing any repair. The assumptions are visible to the product owner.”

**30–45 sec:** Run tests and inspect AC2/AC4. “These are real Python failures: day 30 is accidentally excluded, and used items receive refunds.”

**45–60 sec:** Propose a patch and show the diff. “Two lines fix the two defects. Tests stay unchanged. Nothing is applied before review.”

**60–75 sec:** Tick approval and rerun. “Now all ten checks pass against the reviewed code, with the same test hash.”

**75–90 sec:** Download evidence. “The receipt includes code, tests, failure logs, the approval record, and reproducible results. The DevDay plugin adapter puts this workbench beside ChatGPT; its host installation is a separate account setup step.”

## Record manually

Start `python -m spec2proof.server`, open the local page, and use your OS screen recorder or a browser recorder. Show the complete flow above, including the approval checkbox. Keep the cursor still while explaining the diff. Export as MP4/WebM, and attach to the public repository README or submission when publication is authorized. No real business data is needed.

## Generate an automated recording

With the app running, install optional Playwright and its browser as described in the README, then run `node scripts/browser-demo.cjs`. It saves an actual browser recording, screenshots, a sample evidence ZIP, and a QA summary under `docs/demo/`.

The automated recording has no voiceover. It clicks approval as a **test reviewer**; it is a product demonstration, not an approval attributed to the repository owner. If recording infrastructure is unavailable, the narration above and reproducible local workflow are sufficient for a manual recording.
