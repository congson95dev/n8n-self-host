from flask import Flask, request, jsonify
from detect_video_bars import VideoBarDetector

app = Flask(__name__)

@app.route("/detect", methods=["GET", "POST"])
def detect():
    video_path = request.args.get("video_path")
    if not video_path:
        return jsonify({"error": "video_path is required"}), 400
    
    result = VideoBarDetector.main(video_path, version=1)
    print(result)
    return jsonify(result)

@app.route("/detect-v2", methods=["GET", "POST"])
def detectv2():
    video_path = request.args.get("video_path")
    if not video_path:
        return jsonify({"error": "video_path is required"}), 400
    
    result = VideoBarDetector.main(video_path, version=2)
    print(result)
    return jsonify(result)

@app.route("/detect-v3", methods=["GET", "POST"])
def detectv3():
    video_path = request.args.get("video_path")
    if not video_path:
        return jsonify({"error": "video_path is required"}), 400
    
    result = VideoBarDetector.main(video_path, version=3)
    print(result)
    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
