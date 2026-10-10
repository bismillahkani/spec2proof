# Demo recording guide

## 90-second narration

**0–15 sec:** “Spec2Proof closes the gap between a business requirement and evidence that a repair actually satisfies it. The demo is a refund policy with two realistic bugs.”

**15–30 sec:** Create criteria and confirm the contract. “We freeze ten acceptance tests before proposing any repair. The assumptions are visible to the product owner.”

**30–45 sec:** Run tests and inspect AC2/AC4. “These are real Python failures: day 30 is accidentally excluded, and used items receive refunds.”

**45–60 sec:** Propose a patch and show the diff. “Two lines fix the two defects. Tests stay unchanged. Nothing is applied before review.”

**60–75 sec:** Tick approval and rerun. “Now all ten checks pass against the reviewed code, with the same test hash.”

**75–90 sec:** Download evidence. “The receipt includes code, tests, failure logs, the approval record, and reproducible results. Our working private ChatGPT plugin puts this workbench beside the conversation. Human approval takes place in the local browser, then ChatGPT can retrieve the updated proof.”

## Current recording

`docs/demo/spec2proof-demo.webm` records the real local workbench workflow, including opening a direct approval URL, restoring the pending patch, explicit review, rerunning frozen tests, exporting evidence, and reloading the verified proof. It has no voiceover and does not record the ChatGPT host or imply that the private plugin is publicly installable.

For an additional plugin clip, open Spec2Proof in ChatGPT, create a proof and run the baseline, propose the patch, select **Open local review**, approve in the local browser, then return to ChatGPT and select **Refresh proof after approval**. Hide account information and never record API keys or tunnel configuration.

## Record manually

Start `python -m spec2proof.server`, open the local page, and use your OS screen recorder or a browser recorder. Show the complete flow above, including the approval checkbox. Keep the cursor still while explaining the diff. Export as MP4/WebM, and attach to the public repository README or submission when publication is authorized. No real business data is needed.

## Generate an automated recording

With the app running, install optional Playwright and its browser as described in the README, then run `node scripts/browser-demo.cjs`. It saves an actual browser recording, screenshots, a sample evidence ZIP, and a QA summary under `docs/demo/`.

The automated recording has no voiceover. It clicks approval as a **test reviewer**; it is a product demonstration, not an approval attributed to the repository owner. If recording infrastructure is unavailable, the narration above and reproducible local workflow are sufficient for a manual recording.
