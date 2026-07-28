# Demo GIF shot list

A ~30 second screen recording for the top of the README. It shows the core loop:
ask a grounded question, then a quiz with a wrong answer and re-teach.

## Recording it

- Tool: [ScreenToGif](https://www.screentogif.com/) on Windows (records a region
  and exports a GIF directly). Loom or the Xbox Game Bar also work if you export
  to GIF afterward.
- Record the browser window at a normal size. Move slowly and pause a beat on
  each result so it's readable when looped.
- Save the result as `docs/demo.gif`, then uncomment the image line in the README.
- Keep it under a few MB if you can (ScreenToGif can reduce frames/colors on export).

Tip: run it against the local app (`npm run dev` + backend) for instant answers,
or the live site right after the daily quota resets. On a cold or quota-spent
live backend the answers fall back to canned text, which is fine but less shiny.

## The sequence (aim for ~30s total)

1. (0-3s) Open the app. The sample course ("Intro to ML") is already loaded.
2. (3-6s) Click the chat box, type `What is overfitting?`, and send.
3. (6-12s) Let the answer stream in. Pause so the citation chip
   (`[intro_to_ml.md]`) and the footer (`grounded / model / TTFT`) are visible.
4. (12-16s) In "Get quizzed," type `Gradient Descent` and click Start quiz.
5. (16-20s) Pick a deliberately WRONG option and click Submit answer.
6. (20-26s) Pause on the red feedback: the misconception tag, the
   re-explanation, and the follow-up question.
7. (26-30s) Glance at the Mastery panel showing the attempt recorded, then stop.

That single loop covers upload-less start, grounded cited answer, quiz, wrong
answer, and re-teach, which is exactly what the README GIF is meant to show.
