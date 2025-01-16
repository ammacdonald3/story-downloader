from flask import Blueprint, request, render_template, send_from_directory, jsonify
from .utils import download_story, create_epub_file
import os

# Blueprint for modular routing
main = Blueprint('main', __name__)

@main.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form.get("url")
        output_directory = "app/epub_files"
        os.makedirs(output_directory, exist_ok=True)

        try:
            # Download the story and generate the EPUB
            story_content, story_title, story_author, story_category, story_tags = download_story(url)
            if not story_content:
                return jsonify({
                    "success": False,
                    "error": f"Failed to download the story from the given URL: {url}"
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
            return jsonify({
                "success": False,
                "error": str(e)
            })

    return render_template("index.html")

@main.route("/download/<filename>")
def download_file(filename):
    return send_from_directory("app/epub_files", filename, as_attachment=True)