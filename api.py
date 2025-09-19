from flask import Flask, request, jsonify
from detect_video_bars import VideoBarDetector

app = Flask(__name__)

@app.route("/detect", methods=["GET", "POST"])
def detect():
    video_path = request.args.get("video_path")
    if not video_path:
        return jsonify({"error": "video_path is required"}), 400
    
    result = VideoBarDetector.main(video_path)
    print(result)
    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
