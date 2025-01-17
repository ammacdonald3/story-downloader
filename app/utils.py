import os
import requests
from bs4 import BeautifulSoup
import time
import random
from PIL import Image, ImageDraw, ImageFont
import ebooklib.epub as epub
import uuid
from urllib.parse import quote
import re
import hashlib
import traceback
from datetime import datetime

def log_error(error_msg, url=None):
    """Log errors to error_log.txt with timestamp and optional URL."""
    log_directory = "app/data/logs"
    os.makedirs(log_directory, exist_ok=True)
    error_log = os.path.join(log_directory, "error_log.txt")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(error_log, "a") as f:
        if url:
            f.write(f"{timestamp} - URL: {url} - Error: {error_msg}\n")
        else:
            f.write(f"{timestamp} - Error: {error_msg}\n")

# Define User-Agent rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
]

def get_random_user_agent():
    """Return a random User-Agent string."""
    import random
    return random.choice(USER_AGENTS)

def get_session():
    """Create and return a session with default headers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": get_random_user_agent(),
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    })
    return session

def download_story(url):
    """Download and extract the full story content and metadata from the given Literotica URL."""
    try:
        session = get_session()
        story_content = ""
        current_page = 1
        story_title = "Unknown Title"
        story_author = "Unknown Author"
        story_category = None
        story_tags = []
        chapter_urls = [url]
        processed_urls = set()
        series_title = None
        chapter_titles = []
        chapter_contents = []

        while chapter_urls:
            current_url = chapter_urls.pop(0)
            if current_url in processed_urls:
                continue
                
            processed_urls.add(current_url)
            current_chapter = len(chapter_contents) + 1
            current_chapter_content = ""

            while current_url:
                try:
                    response = session.get(current_url, timeout=10)
                    response.raise_for_status()

                    # Parse the page with BeautifulSoup
                    soup = BeautifulSoup(response.text, "html.parser")

                    # Extract title and author for the first page of first chapter
                    if current_page == 1:
                        title_tag = soup.find("h1", class_="headline")
                        author_tag = soup.find("a", class_="y_eU")
                        current_title = title_tag.text.strip() if title_tag else "Unknown Chapter"
                        
                        # Only set these for the first chapter
                        if current_chapter == 1:
                            story_title = current_title
                            story_author = author_tag.text.strip() if author_tag else story_author
                            
                            # Extract category and tags on first page
                            breadcrumb = soup.find("div", id="BreadCrumbComponent")
                            if breadcrumb:
                                category_links = breadcrumb.find_all("a", class_="h_aZ")
                                if len(category_links) >= 2:
                                    story_category = category_links[1].text.strip()
                                    if story_category.lower().startswith("inc"):
                                        story_category = "I/T"
                            
                            tag_elements = soup.find_all("a", class_="av_as av_r")
                            story_tags = [tag.text.strip() for tag in tag_elements 
                                        if not tag.text.strip().lower().startswith("inc")]
                            if story_category and story_category not in story_tags:
                                story_tags = [story_category] + story_tags

                    # Extract story text
                    content_div = soup.find("div", class_="aa_ht")
                    if content_div:
                        if current_page == 1:
                            chapter_titles.append(current_title)
                                
                        for paragraph in content_div.find_all("p"):
                            current_chapter_content += paragraph.get_text(strip=True) + "\n\n"

                    # Find the next page link
                    next_page_link = soup.find("a", class_="l_bJ", title="Next Page")
                    if next_page_link:
                        next_url = next_page_link["href"]
                        if not next_url.startswith("http"):
                            next_url = "https://www.literotica.com" + next_url
                        current_url = next_url
                        current_page += 1
                    else:
                        chapter_contents.append(current_chapter_content)
                        
                        # Check for next chapter link
                        series_panel = soup.find("div", class_="panel z_r z_R")
                        if series_panel:
                            if not series_title:
                                story_links = series_panel.find_all("div", class_="z_S")
                                for story_div in story_links:
                                    series_info_span = story_div.find("span", class_="z_pm", string="Series Info")
                                    if series_info_span:
                                        link = story_div.find("a", class_="z_t")
                                        if link:
                                            series_title = link.get_text().strip()
                                            story_title = series_title
                                            break
                            
                            story_links = series_panel.find_all("div", class_="z_S")
                            for story_div in story_links:
                                link = story_div.find("a", class_="z_t")
                                if not link:
                                    continue
                                    
                                next_part_span = story_div.find("span", class_="z_pm")
                                if next_part_span and next_part_span.get_text().strip() == "Next Part":
                                    next_url = link["href"]
                                    if not next_url.startswith("http"):
                                        next_url = "https://www.literotica.com" + next_url
                                    if next_url not in processed_urls:
                                        chapter_urls.append(next_url)
                                    break
                        
                        current_url = None
                        current_page = 1

                    time.sleep(3)

                except requests.RequestException as e:
                    error_msg = f"Network error while downloading chapter {current_chapter}: {str(e)}"
                    log_error(error_msg, current_url)
                    return None, None, None, None, None
                except Exception as e:
                    error_msg = f"Error processing chapter {current_chapter}: {str(e)}\n{traceback.format_exc()}"
                    log_error(error_msg, current_url)
                    return None, None, None, None, None

        # Combine chapters with proper formatting
        story_content = ""
        for i, (title, content) in enumerate(zip(chapter_titles, chapter_contents), 1):
            story_content += f"\n\nChapter {i}: {title}\n\n{content}"
        
        return story_content, story_title, story_author, story_category, story_tags

    except Exception as e:
        error_msg = f"Unexpected error in download_story: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg, url)
        return None, None, None, None, None

def format_story_content(content):
    """Format story content into properly formatted paragraphs for EPUB."""
    # Add CSS for better formatting
    css = """
        <style>
            body {
                margin: 1em;
                padding: 0 1em;
            }
            p {
                margin: 1.5em 0;
                line-height: 1.7;
                font-size: 1.1em;
            }
            h1 {
                margin: 2em 0 1em 0;
                text-align: center;
            }
        </style>
    """
    
    # Split content into paragraphs and wrap each in <p> tags
    paragraphs = content.split('\n\n')
    formatted_paragraphs = [f'<p>{p.strip()}</p>' for p in paragraphs if p.strip()]
    return css + '\n'.join(formatted_paragraphs)

def format_metadata_content(category=None, tags=None):
    """Format metadata content with proper styling."""
    css = """
        <style>
            body {
                margin: 1em;
                padding: 0 1em;
            }
            h1 {
                margin: 2em 0 1em 0;
                text-align: center;
            }
            .metadata {
                margin: 1.5em 0;
                line-height: 1.7;
                font-size: 1.1em;
            }
            .metadata-item {
                margin: 1em 0;
            }
            .metadata-label {
                font-weight: bold;
                margin-right: 0.5em;
            }
        </style>
    """
    
    content = f"{css}<h1>Story Information</h1><div class='metadata'>"
    if category:
        content += f"<div class='metadata-item'><span class='metadata-label'>Category: </span>{category}</div>"
    if tags:
        content += f"<div class='metadata-item'><span class='metadata-label'>Tags: </span>{', '.join(tags)}</div>"
    content += "</div>"
    return content

def create_epub_file(story_title, story_author, story_content, output_directory, cover_image_path=None, story_category=None, story_tags=None):
    """Create an EPUB file from the story content."""
    try:
        # Create output directory if it doesn't exist
        os.makedirs(output_directory, exist_ok=True)

        # Check if a cover image is provided; if not, generate one
        if cover_image_path is None:
            cover_image_path = os.path.join(output_directory, "cover.jpg")
            generate_cover_image(story_title, story_author, cover_image_path)

        # Create EPUB book
        book = epub.EpubBook()

        # Set metadata
        book.set_identifier(str(uuid.uuid4()))
        book.set_title(story_title)
        book.set_language('en')
        book.add_author(story_author)

        # Add metadata to the EPUB
        if story_category:
            book.add_metadata('DC', 'subject', story_category)
        if story_tags:
            for tag in story_tags:
                book.add_metadata('DC', 'subject', tag)

        # Add the cover image
        try:
            if os.path.exists(cover_image_path):
                with open(cover_image_path, 'rb') as cover_file:
                    book.set_cover("cover.jpg", cover_file.read())
        except Exception as e:
            error_msg = f"Error adding cover image: {str(e)}"
            log_error(error_msg)
            # Continue without cover if there's an error

        # Create chapters list for spine and table of contents
        chapters = []
        toc = []

        # Add metadata chapter first if we have category or tags
        if story_category or story_tags:
            try:
                metadata_content = format_metadata_content(story_category, story_tags)
                metadata_chapter = epub.EpubHtml(title='Story Information',
                                               file_name='metadata.xhtml',
                                               content=metadata_content)
                book.add_item(metadata_chapter)
                chapters.append(metadata_chapter)
                toc.append(metadata_chapter)
            except Exception as e:
                error_msg = f"Error adding metadata chapter: {str(e)}"
                log_error(error_msg)
                # Continue without metadata if there's an error

        # Split content into chapters
        chapter_texts = story_content.split("\n\nChapter ")
        
        # Handle the first chunk (might be empty or have content before first chapter)
        if chapter_texts[0].strip():
            try:
                intro_content = format_story_content(chapter_texts[0])
                intro_chapter = epub.EpubHtml(title='Introduction',
                                            file_name='intro.xhtml',
                                            content=f'<h1>Introduction</h1>{intro_content}')
                book.add_item(intro_chapter)
                chapters.append(intro_chapter)
                toc.append(intro_chapter)
            except Exception as e:
                error_msg = f"Error adding introduction chapter: {str(e)}"
                log_error(error_msg)
                # Continue without intro if there's an error

        # Process each chapter
        for i, chapter_text in enumerate(chapter_texts[1:], 1):
            try:
                title_end = chapter_text.find("\n\n")
                if title_end == -1:
                    chapter_title = f"Chapter {i}"
                    chapter_content = chapter_text
                else:
                    chapter_title = f"Chapter {chapter_text[:title_end]}"
                    chapter_content = chapter_text[title_end:].strip()
                
                formatted_content = format_story_content(chapter_content)
                chapter = epub.EpubHtml(title=chapter_title,
                                      file_name=f'chapter_{i}.xhtml',
                                      content=f'<h1>{chapter_title}</h1>{formatted_content}')
                
                book.add_item(chapter)
                chapters.append(chapter)
                toc.append(chapter)
            except Exception as e:
                error_msg = f"Error processing chapter {i}: {str(e)}"
                log_error(error_msg)
                continue

        if not chapters:
            error_msg = "No valid chapters found to create EPUB"
            log_error(error_msg)
            raise ValueError(error_msg)

        # Add navigation files
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # Define Table of Contents and spine
        book.toc = toc
        book.spine = ['nav'] + chapters

        # Save EPUB file
        def sanitize_filename(filename):
            return re.sub(r'[^a-zA-Z0-9._-]', '', filename)

        epub_path = os.path.join(output_directory, f"{sanitize_filename(story_title)}.epub")
        epub.write_epub(epub_path, book, {})
        
        return epub_path

    except Exception as e:
        error_msg = f"Error creating EPUB file for '{story_title}' by {story_author}: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
        raise

def generate_cover_image(title, author, cover_path):
    """
    Generate a cover image with a gradient background, a simulated spine effect, 
    and styled text that mimics the provided design.
    
    Args:
        title (str): The title of the story.
        author (str): The author's name.
        cover_path (str): The file path to save the generated cover.
    """
    # Step 1: Image dimensions and colors
    width, height = 1200, 1600  # Double the size for higher resolution
    
    # Aesthetically pleasing dark colors suitable for white text
    background_colors = [
        (47, 53, 66),   # Dark slate
        (44, 62, 80),   # Midnight blue
        (52, 73, 94),   # Dark ocean
        (69, 39, 60),   # Deep purple
        (81, 46, 95),   # Royal purple
        (45, 52, 54),   # Dark jungle
        (33, 33, 33),   # Charcoal
        (25, 42, 86),   # Navy blue
        (56, 29, 42),   # Wine red
        (28, 40, 51),   # Dark navy
    ]
    
    # Select a background color based on the title (for consistency)
    color_index = int(hashlib.md5(title.encode()).hexdigest(), 16) % len(background_colors)
    background_color = background_colors[color_index]
    
    text_color = (255, 255, 255)  # White text
    spine_color = tuple(max(0, c - 20) for c in background_color)  # Slightly darker version of background color
    
    # Step 2: Create the blank canvas with anti-aliasing
    image = Image.new("RGB", (width, height), background_color)
    draw = ImageDraw.Draw(image, 'RGBA')  # Use RGBA for better anti-aliasing

    # Step 3: Add the spine effect
    spine_width = 40  # Increased spine width for larger image
    draw.rectangle([(0, 0), (spine_width, height)], fill=spine_color)
    
    # Step 4: Load the bundled font
    try:
        # Use the bundled font from static/fonts
        font_path = os.path.join(os.path.dirname(__file__), "static", "fonts", "Open_Sans", "OpenSans-VariableFont_wdth,wght.ttf")
        if not os.path.exists(font_path):
            raise Exception(f"Bundled font not found at {font_path}")
            
        title_font = ImageFont.truetype(font_path, 128)  # Large title font
        author_font = ImageFont.truetype(font_path, 72)  # Large author font
    except Exception as e:
        # Fallback to larger image with default font if bundled font fails
        width *= 2
        height *= 2
        image = Image.new("RGB", (width, height), background_color)
        title_font = ImageFont.load_default()
        author_font = ImageFont.load_default()

    # Step 5: Render the title text
    # Calculate maximum width for text (leaving margins)
    max_text_width = width - (spine_width + 100)  # Leave 50px margin on each side
    
    # Wrap title text
    words = title.split()
    lines = []
    current_line = []
    
    for word in words:
        # Try adding the next word
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=title_font)
        test_width = bbox[2] - bbox[0]
        
        if test_width <= max_text_width:
            current_line.append(word)
        else:
            if current_line:  # If we have words in the current line
                lines.append(' '.join(current_line))
                current_line = [word]
            else:  # If the single word is too long, force it on its own line
                lines.append(word)
                current_line = []
    
    if current_line:  # Add the last line if there are remaining words
        lines.append(' '.join(current_line))
    
    # Calculate total height of all lines
    line_spacing = 40  # Increased spacing between lines
    total_text_height = sum(draw.textbbox((0, 0), line, font=title_font)[3] - draw.textbbox((0, 0), line, font=title_font)[1] for line in lines)
    total_text_height += line_spacing * (len(lines) - 1)  # Add spacing between lines
    
    # Start position for the first line
    current_y = (height // 3) - (total_text_height // 2)  # Center the text block vertically around the 1/3 point
    
    # Draw each line centered
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        line_width = bbox[2] - bbox[0]
        line_height = bbox[3] - bbox[1]
        x = (width - line_width) // 2
        draw.text((x, current_y), line, fill=text_color, font=title_font)
        current_y += line_height + line_spacing

    # Step 6: Render the author text
    author_bbox = draw.textbbox((0, 0), author, font=author_font)  # Get bounding box of the author text
    author_width = author_bbox[2] - author_bbox[0]
    author_height = author_bbox[3] - author_bbox[1]
    author_position = ((width - author_width) // 2, height - 200)  # Moved up from bottom
    draw.text(author_position, author, fill=text_color, font=author_font)

    # Step 7: Save the cover image with high quality
    image = image.resize((600, 800), Image.Resampling.LANCZOS)  # Resize with high-quality resampling
    image.save(cover_path, "JPEG", quality=95, optimize=True)  

# Example usage:
if __name__ == "__main__":
    TEST_URL = "https://www.literotica.com/s/seven-nights-adippin"  # Replace with your story URL
    OUTPUT_DIR = "epub_files"

    # Create output directory if not exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Download story
    full_content, title, author, category, tags = download_story(TEST_URL)
    if full_content:
        epub_path = create_epub_file(title, author, full_content, OUTPUT_DIR, story_category=category, story_tags=tags)
    else:
        print("Failed to download story.")