import os
import requests
import time
from bs4 import BeautifulSoup
from ebooklib import epub
from PIL import Image, ImageDraw, ImageFont

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
    session = get_session()
    story_content = ""
    current_page = 1
    story_title = "Unknown Title"
    story_author = "Unknown Author"
    story_category = None
    story_tags = []

    while url:
        print(f"Scraping page: {url}")

        try:
            response = session.get(url, timeout=10)  # Perform the HTTP request
            response.raise_for_status()  # Raise an error for invalid responses

            # Parse the page with BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract title and author for the first page
            if current_page == 1:
                title_tag = soup.find("h1", class_="headline")
                author_tag = soup.find("a", class_="y_eU")
                story_title = title_tag.text.strip() if title_tag else story_title
                story_author = author_tag.text.strip() if author_tag else story_author
                
                # Extract category and tags on first page
                breadcrumb = soup.find("div", id="BreadCrumbComponent")
                if breadcrumb:
                    category_links = breadcrumb.find_all("a", class_="h_aZ")
                    if len(category_links) >= 2:
                        story_category = category_links[1].text.strip()
                
                tag_elements = soup.find_all("a", class_="av_as av_r")
                story_tags = [tag.text.strip() for tag in tag_elements]
                # Add category as the first tag if it exists
                if story_category:
                    story_tags = [story_category] + story_tags
                print(f"Found category: {story_category}")
                print(f"Found tags: {story_tags}")

            # Extract story text (main content resides in `div.aa_ht`)
            content_div = soup.find("div", class_="aa_ht")
            if content_div:
                for paragraph in content_div.find_all("p"):
                    story_content += paragraph.get_text(strip=True) + "\n\n"  # Add paragraphs with spacing

            # Find the next page link
            next_page_link = soup.find("a", class_="l_bJ", title="Next Page")
            if next_page_link:
                url = "https://www.literotica.com" + next_page_link["href"]
                current_page += 1
            else:
                url = None  # Stop looping if there is no next page

            # Delay between requests to mimic human browsing
            time.sleep(3)

        except requests.exceptions.RequestException as e:
            print(f"Error fetching page {current_page}: {e}")
            return None, None, None, None, None

    return story_content, story_title, story_author, story_category, story_tags

def create_epub_file(story_title, story_author, story_content, output_directory, cover_image_path=None, story_category=None, story_tags=None):
    """
    Generate and save an EPUB file with a cover, valid metadata, formatted XHTML content, and navigation.

    Args:
        story_title (str): The title of the story.
        story_author (str): The author of the story.
        story_content (str): The plain text content of the story.
        output_directory (str): Directory to save the resulting EPUB.
        cover_image_path (str, optional): Path to the cover image. If None, a cover is generated.
        story_category (str, optional): The category of the story.
        story_tags (list, optional): The tags of the story.
    """
    # Ensure the output directory exists
    os.makedirs(output_directory, exist_ok=True)

    # Check if a cover image is provided; if not, generate one
    if cover_image_path is None:
        cover_image_path = os.path.join(output_directory, "cover.jpg")
        generate_cover_image(story_title, story_author, cover_image_path)

    # Step 1: Create EPUB book
    book = epub.EpubBook()

    # Step 2: Add metadata
    book.set_title(story_title)
    book.add_author(story_author)
    book.set_language("en")  # Mandatory field
    
    # Add category and tags if available
    if story_category:
        book.add_metadata('DC', 'subject', story_category)
    
    if story_tags:
        for tag in story_tags:
            book.add_metadata('DC', 'subject', tag)

    # Step 3: Add the cover image
    with open(cover_image_path, "rb") as cover_image_file:
        book.set_cover("cover.jpg", cover_image_file.read())

    # Step 4: Add content as a chapter
    chapter = epub.EpubHtml(
        title="Chapter 1",
        file_name="chapter1.xhtml",
        lang="en"
    )
    formatted_content = format_story_content(story_content)  # Format the content into XHTML
    chapter.content = f"<h1>{story_title}</h1><h3>By {story_author}</h3>{formatted_content}"  # Add header and content
    
    # Add category and tags to the content if available
    if story_category or story_tags:
        chapter.content += '<div style="margin: 1em 0; font-style: italic;">'
        if story_category:
            chapter.content += f'Category: {story_category}<br>'
        if story_tags:
            chapter.content += f'Tags: {", ".join(story_tags)}'
        chapter.content += '</div>'
    
    book.add_item(chapter)

    # Step 5: Add navigation (TOC and nav.xhtml)
    book.toc = [epub.Link('chapter1.xhtml', 'Chapter 1', 'chapter1')]
    book.add_item(epub.EpubNav())

    # Step 6: Define spine (reading order)
    book.spine = ['nav', chapter]

    # Step 7: Output EPUB to file
    epub_file_name = f"{story_title.replace(' ', '_')}.epub"
    epub_file_path = os.path.join(output_directory, epub_file_name)
    epub.write_epub(epub_file_path, book, {})

    print(f"EPUB successfully generated at: {epub_file_path}")
    return epub_file_path

def format_story_content(raw_content):
    """
    Convert raw story content (plain text) into valid XHTML with <p> tags.
    """
    css = """
        <style>
            p {
                margin: 1.5em 0;
                line-height: 1.6;
                font-size: 1.1em;
            }
            body {
                max-width: 45em;
                margin: 0 auto;
                padding: 0 1em;
            }
        </style>
    """
    formatted_content = css

    # Split content into paragraphs based on double line breaks
    paragraphs = raw_content.split("\n\n")  # "\n\n" is usually a paragraph separator

    for paragraph in paragraphs:
        # Trim leading/trailing whitespace and wrap in <p> tags
        paragraph = paragraph.strip()
        if paragraph:
            formatted_content += f"<p>{paragraph}</p>\n"

    return formatted_content



from PIL import Image, ImageDraw, ImageFont
import os

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
    import hashlib
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
            
        print(f"Using bundled font: {font_path}")
        # Use the bundled font with large sizes for better visibility
        title_font = ImageFont.truetype(font_path, 128)  # Large title font
        author_font = ImageFont.truetype(font_path, 72)  # Large author font
        print("Successfully loaded font")
    except Exception as e:
        print(f"Font loading error: {str(e)}")
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
    image.save(cover_path, "JPEG", quality=95, optimize=True)  # Save with high quality
    print(f"Cover image saved to: {cover_path}")


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
        print(f"EPUB file created: {epub_path}")
    else:
        print("Failed to download story.")