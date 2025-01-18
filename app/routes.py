from flask import Blueprint, request, render_template, send_from_directory, jsonify, abort
from .utils import download_story, create_epub_file, log_error, log_action
import os
from datetime import datetime
import traceback
import urllib.parse

# Blueprint for module routing
main = Blueprint('main', __name__)

@main.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        url = request.form.get("url")
        return process_url(url)

    log_action("Serving index page")
    return render_template("index.html")

@main.route("/api/download")
def api_download():
    """API endpoint for iOS shortcuts to trigger downloads."""
    url = request.args.get('url')
    if not url:
        log_error("API request received without URL parameter")
        return jsonify({
            "success": "false",
            "message": "URL parameter is required"
        }), 400

    # URL might be URL-encoded, so decode it
    url = urllib.parse.unquote(url)
    log_action(f"API request received for URL: {url}")
    
    # Log all URLs first, regardless of validity
    log_directory = os.path.join(os.path.dirname(__file__), "data", "logs")
    os.makedirs(log_directory, exist_ok=True)
    url_log = os.path.join(log_directory, "url_log.txt")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(url_log, "a") as f:
        f.write(f"{timestamp} - {url}\n")
    log_action("URL logged to url_log.txt")
    
    # Check if URL is from allowed domain
    if not url.startswith("https://www.literotica.com/"):
        error_msg = f"Invalid URL domain: {url}"
        log_error(error_msg, url)
        return jsonify({
            "success": "false",
            "message": error_msg
        }), 400

    return process_url(url)

def process_url(url):
    """Process the URL and create EPUB file."""
    # Check if URL is from allowed domain
    if not url.startswith("https://www.literotica.com/"):
        error_msg = f"Invalid URL domain: {url}"
        log_error(error_msg, url)
        return jsonify({
            "success": "false",
            "message": "Invalid URL domain"
        }), 400

    output_directory = os.path.join(os.path.dirname(__file__), "data", "epubs")
    os.makedirs(output_directory, exist_ok=True)
    log_action(f"Created/verified output directory: {output_directory}")

    try:
        # Download the story and generate the EPUB
        log_action("Starting story download...")
        story_content, story_title, story_author, story_category, story_tags = download_story(url)
        if not story_content:
            error_msg = f"Failed to download the story from the given URL: {url}"
            log_error(error_msg, url)
            log_action(f"Download failed: {error_msg}")
            return jsonify({
                "success": "false",
                "message": error_msg
            })

        log_action(f"Successfully downloaded story: '{story_title}' by {story_author}")
        log_action("Starting EPUB creation...")

        epub_file_name = create_epub_file(
            story_title, 
            story_author, 
            story_content, 
            output_directory,
            story_category=story_category,
            story_tags=story_tags
        )
        log_action(f"Successfully created EPUB file: {epub_file_name}")

        # Get the base filename without path
        base_filename = os.path.basename(epub_file_name)

        return jsonify({
            "success": "true",
            "message": f"Successfully downloaded '{story_title}' by {story_author}",
            "title": story_title,
            "author": story_author,
            "saved_as": base_filename
        })
    except Exception as e:
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        log_error(error_msg, url)
        log_action(f"Error occurred: {str(e)}")
        return jsonify({
            "success": "false",
            "message": str(e)
        })

@main.route("/download/<filename>")
def download_file(filename):
    """Download a specific EPUB file."""
    # Basic security check: ensure filename doesn't contain path traversal
    if '..' in filename or filename.startswith('/'):
        log_action(f"Attempted path traversal in download: {filename}")
        abort(404)
        
    output_directory = os.path.join(os.path.dirname(__file__), "data", "epubs")
    log_action(f"Download requested for file: {filename}")
    return send_from_directory(output_directory, filename, as_attachment=True)