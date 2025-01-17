from flask import Blueprint, request, render_template, send_from_directory, jsonify
from .utils import download_story, create_epub_file, log_error
import os
from datetime import datetime
import traceback

# Blueprint for modular routing
main = Blueprint('main', __name__)

@main.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form.get("url")
        output_directory = "app/data/epubs"
        os.makedirs(output_directory, exist_ok=True)

        # Log the URL with timestamp
        log_directory = "app/data/logs"
        os.makedirs(log_directory, exist_ok=True)
        log_file = os.path.join(log_directory, "url_log.txt")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a") as f:
            f.write(f"{timestamp} - {url}\n")

        try:
            # Download the story and generate the EPUB
            story_content, story_title, story_author, story_category, story_tags = download_story(url)
            if not story_content:
                error_msg = f"Failed to download the story from the given URL: {url}"
                log_error(error_msg, url)
                return jsonify({
                    "success": False,
                    "error": error_msg
                })

            epub_file_name = create_epub_file(
                story_title, 
                story_author, 
                story_content, 
                output_directory,
                story_category=story_category,
                story_tags=story_tags
            )
            return jsonify({
                "success": True,
                "filename": epub_file_name,
                "category": story_category,
                "tags": story_tags
            })
        except Exception as e:
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            log_error(error_msg, url)
            return jsonify({
                "success": False,
                "error": str(e)
            })

    return render_template("index.html")

@main.route("/download/<filename>")
def download_file(filename):
    return send_from_directory("app/data/epubs", filename, as_attachment=True)