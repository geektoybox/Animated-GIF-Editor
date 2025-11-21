Geek's Animated GIF Editor
================================
I realized I didn't have a simple utility to combine images into an animated GIF without using some random ad-filled, malware infested website and I didn't want to invite more of the same from the App Store so I decided to vibe code this instead. What was meant to simply combine images turned into a bit of an editor that even lets me add/remove or export frames from other animated GIF files. I hope somebody else finds this useful.

This app collects no data and is meant to work on macOS, Windows and Linux.

Requirements
------------

- Python 3.9+
- PyQt6
- Pillow (PIL)

Install dependencies:

    pip install PyQt6 Pillow

Run the app from the folder containing AGIFEdit:

    python -m AGIFEdit.main 
