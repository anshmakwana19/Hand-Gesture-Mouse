🖐️ AI Virtual Hand Gesture Controller

Control your computer using just your hands through a webcam.
This project uses Computer Vision, MediaPipe, and Python automation libraries to create a fully functional gesture-based control system.

Features include:

🖱️ Hand-controlled mouse cursor
👆 Pinch to click / double click / drag
🔊 Volume control using hand rotation
💡 Brightness control using finger gestures
📜 Air scrolling using two-finger gesture
⚡ Smooth cursor movement with gesture recognition
🎥 Real-time hand tracking using webcam




🚀 Features

🖱️ Cursor Control
Open hand → Move cursor
Closed fist → Stop cursor
Pinch thumb + index → Single click
Double pinch → Double click
Hold pinch → Drag & drop

📜 Scroll Mode
Extend index + middle finger
Move fingers up/down to scroll

🔊 Volume Control
Left hand gesture:
Close middle + ring fingers
Rotate hand clockwise/counter-clockwise

💡 Brightness Control
Extend only index finger
Move finger vertically to increase/decrease brightness


🛠️ Technologies Used
Python
OpenCV
MediaPipe
PyAutoGUI
Pycaw
NumPy
Screen Brightness Control
Multithreading


📦 Requirements

Install all dependencies:

pip install -r requirements.txt

Or manually:

pip install opencv-python mediapipe pyautogui numpy pycaw screen-brightness-control comtypes

▶️ How to Run

python main.py

Make sure:

Your webcam is connected
Good lighting is available
Python 3.10+ is installed


📷 Gesture Controls

| Gesture                   | Action             |
| ------------------------- | ------------------ |
| Open Hand                 | Move Cursor        |
| Closed Fist               | Stop Cursor        |
| Pinch                     | Click              |
| Double Pinch              | Double Click       |
| Hold Pinch                | Drag               |
| Two Fingers Up            | Scroll Mode        |
| Rotate Left Hand          | Volume Control     |
| Move Index Finger Up/Down | Brightness Control |



📂 Project Structure

├── main.py
├── requirements.txt
├── README.md
└── .gitignore

⚙️ Performance Optimizations

Multithreaded camera processing
Cursor smoothing algorithm
Gesture dead-zones to reduce accidental triggers
FPS calculation for performance monitoring
Hysteresis-based pinch detection


🔮 Future Improvements
Custom gesture mapping
Virtual keyboard
Gaming mode
AI gesture learning
Cross-platform support
GUI settings panel
🤝 Contributing

Pull requests are welcome.
For major changes, please open an issue first to discuss what you'd like to change.

📜 License

This project is licensed under the MIT License.

👨‍💻 Author

Ansh Makwana

GitHub: add-your-github-link-here
LinkedIn: add-your-linkedin-link-here

⭐ If you like this project, give it a star on GitHub.
