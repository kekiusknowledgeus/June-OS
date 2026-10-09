# Vision

`screen.capture` uses MSS to capture a selected monitor (1-based; 0 means the virtual desktop) or the foreground window. Windows observation supplies title, PID, bounds and observation time. PNGs stay under `data/captures`. Capture is off by default and blocked during privacy mode.

`vision.analyze` only accepts bounded PNGs from June's capture directory. Sending an image to hosted intelligence requires an explicit action preview/approval. June never continuously uploads screenshots. LocalJuneBrain can analyze images if the separately configured local model supports them.

`camera.capture` opens a configured camera index for one frame using OpenCV/DirectShow, saves it locally and releases the device. Camera input is separately disabled by default. No camera hardware capability is fabricated.

For computer interaction, June requires a capture ID no older than two minutes. After approval it checks the target title, window handle, bounds and image hash before acting. A changed target is refused. Active-window capture also checks that the window remained the same while grabbing pixels. After an action, further GUI actions are blocked until its after-image is analyzed. A matching screenshot cannot prove the chosen coordinate is semantically correct; prefer structured file/process/browser tools.

Gemini successfully read a synthetic compiler error image. The live desktop fixture reached vision analysis in an earlier attempt, but the full capture → click → re-analysis test has not completed: foreground focus moved to another application, and the guard prevented clicking. Later attempts stopped before upload when the intended fixture was not foreground. Run `scripts/smoke_screen_loop.py` with the synthetic fixture kept foreground to finish that acceptance test. This is recorded as incomplete, not passed.
