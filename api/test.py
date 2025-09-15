from flask import Flask, Response

app = Flask(__name__)

@app.route("/", methods=["GET"])
def hello():
    return Response("API is working!", mimetype="text/plain")